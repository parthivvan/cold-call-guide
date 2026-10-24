import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from postgrest.exceptions import APIError
from supabase import Client, create_client

load_dotenv(Path(__file__).resolve().parent / ".env")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("cold_call_guide")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured.")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash").strip()

ALLOWED_OUTCOMES = {
    "agreed_to_receive_report", "next_step_agreed", "interested", "follow_up",
    "call_again", "not_interested", "do_not_call", "wrong_person", "moved_company", "not_logged",
}
OUTCOME_DEFINITIONS = {
    "agreed_to_receive_report": "Agreed to receive information by WhatsApp or email",
    "next_step_agreed": "Agreed to a concrete next step",
    "interested": "Expressed interest without a specific next step",
    "follow_up": "Asked for follow-up or a named callback time",
    "call_again": "Asked the caller to try again later",
    "not_interested": "Clearly not interested",
    "do_not_call": "Asked not to be contacted again",
    "wrong_person": "The person reached is not the right contact",
    "moved_company": "The contact has left the company",
    "not_logged": "Evidence is insufficient to assign another outcome",
}
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
app = FastAPI(title="Cold-Call Guide API", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "apikey"],
)

class CreateCallBody(BaseModel):
    prospect_name: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)

class StageResultBody(BaseModel):
    stage_id: int = Field(gt=0)
    happened_key: Optional[str] = Field(default=None, max_length=100)
    prospect_words: Optional[str] = Field(default=None, max_length=5000)
    next_stage_id: int = Field(gt=0)

class CloseCallBody(BaseModel):
    outcome: str
    summary: Optional[str] = Field(default=None, max_length=2000)

def validate_uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail="Invalid call ID. A UUID is required.")

def execute(query, action: str):
    try:
        return query.execute()
    except APIError as exc:
        logger.warning("Supabase API error during %s (code=%s)", action, getattr(exc, "code", "unknown"))
        raise HTTPException(status_code=503, detail="Database request failed. Check backend logs.")
    except httpx.HTTPError:
        logger.exception("Supabase network error during %s", action)
        raise HTTPException(status_code=503, detail="Could not reach the database. Please retry.")
    except Exception:
        logger.exception("Unexpected database error during %s", action)
        raise HTTPException(status_code=503, detail="Database operation failed. Please retry.")

def fetch_call(call_id: str) -> dict:
    safe_id = validate_uuid(call_id)
    result = execute(supabase.table("calls").select("*").eq("id", safe_id).limit(1), "fetch call")
    if not result.data:
        raise HTTPException(status_code=404, detail="Call not found.")
    return result.data[0]

def fetch_stage(stage_id: int) -> dict:
    result = execute(supabase.table("stages").select("id,position,name").eq("id", stage_id).limit(1), "fetch stage")
    if not result.data:
        raise HTTPException(status_code=404, detail="Stage not found.")
    return result.data[0]

def fallback_outcome(entries: list[dict]) -> str:
    for item in reversed(entries):
        key = (item.get("happened_key") or "").lower()
        if key in {"whatsapp", "email"}:
            return "agreed_to_receive_report"
        if key in {"call_time", "callback_time", "referral"}:
            return "follow_up"
        if key == "wrong_person":
            return "wrong_person"
        if key == "moved_company":
            return "moved_company"
        if key == "not_interested":
            return "not_interested"
    return "not_logged"

def extract_json(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.rstrip().endswith("```"):
        cleaned = cleaned.rstrip()[:-3]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM did not return a JSON object.")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("LLM response must be an object.")
    return value

def call_llm(context: str) -> dict:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured.")
    prompt = (
        "Choose the most appropriate outcome and one factual summary sentence. Return only JSON with keys "
        "suggested_outcome and summary. Do not invent facts. If ambiguous, choose not_logged.\nAllowed outcomes:\n"
        + "\n".join(key + ": " + value for key, value in OUTCOME_DEFINITIONS.items())
        + "\nCall notes:\n" + context
    )
    with httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
        if LLM_PROVIDER == "cerebras":
            response = client.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers={"Authorization": "Bearer " + LLM_API_KEY},
                json={"model": LLM_MODEL, "temperature": 0.1, "messages": [
                    {"role": "system", "content": "Return valid JSON only. Do not invent facts."},
                    {"role": "user", "content": prompt},
                ]},
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
        else:
            response = client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/" + LLM_MODEL + ":generateContent",
                headers={"x-goog-api-key": LLM_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}},
            )
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    parsed = extract_json(text)
    outcome, summary = parsed.get("suggested_outcome"), parsed.get("summary")
    if outcome not in ALLOWED_OUTCOMES or not isinstance(summary, str) or not summary.strip():
        raise ValueError("LLM returned an invalid suggestion.")
    return {"suggested_outcome": outcome, "summary": summary.strip()[:2000], "source": "llm"}

@app.get("/")
def root() -> dict:
    return {"name": "Cold-Call Guide API", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/stages")
def get_stages() -> list[dict]:
    return execute(supabase.table("stages").select("*").order("position"), "list stages").data or []

@app.post("/calls", status_code=201)
def create_call(body: CreateCallBody) -> dict:
    first = execute(supabase.table("stages").select("id").eq("position", 1).limit(1), "find stage one")
    if not first.data:
        raise HTTPException(status_code=500, detail="Stage 1 is missing. Run db/seed.sql.")
    stage_id = first.data[0]["id"]
    result = execute(supabase.table("calls").insert({
        "prospect_name": body.prospect_name.strip(), "company": body.company.strip(),
        "current_stage_id": stage_id, "furthest_stage_id": stage_id,
    }), "create call")
    if not result.data:
        raise HTTPException(status_code=503, detail="Call could not be saved.")
    return result.data[0]

@app.post("/calls/{call_id}/stages")
def record_stage(call_id: str, body: StageResultBody) -> dict:
    safe_id = validate_uuid(call_id)
    call = fetch_call(safe_id)
    fetch_stage(body.stage_id)
    next_stage = fetch_stage(body.next_stage_id)
    furthest_id = call.get("furthest_stage_id") or call.get("current_stage_id")
    if not furthest_id:
        raise HTTPException(status_code=500, detail="Call has no stage.")
    furthest = fetch_stage(furthest_id)
    new_furthest = body.next_stage_id if next_stage["position"] > furthest["position"] else furthest_id
    result = execute(supabase.table("stage_results").insert({
        "call_id": safe_id, "stage_id": body.stage_id,
        "happened_key": body.happened_key, "prospect_words": body.prospect_words,
    }), "save stage result")
    updated = execute(supabase.table("calls").update({
        "current_stage_id": body.next_stage_id, "furthest_stage_id": new_furthest,
    }).eq("id", safe_id), "update call stage")
    if not result.data or not updated.data:
        raise HTTPException(status_code=503, detail="Stage save was incomplete; check the call record.")
    return {"stage_result": result.data[0], "call": updated.data[0]}

@app.post("/calls/{call_id}/suggest-outcome")
def suggest_outcome(call_id: str) -> dict:
    safe_id = validate_uuid(call_id)
    fetch_call(safe_id)
    response = execute(
        supabase.table("stage_results").select("stage_id,happened_key,prospect_words,created_at")
        .eq("call_id", safe_id).order("created_at"),
        "load stage notes",
    )
    entries = response.data or []
    stage_names, notes = {}, []
    for entry in entries:
        sid = entry["stage_id"]
        if sid not in stage_names:
            stage_response = execute(supabase.table("stages").select("name").eq("id", sid).limit(1), "load stage name")
            stage_names[sid] = stage_response.data[0]["name"] if stage_response.data else "Stage " + str(sid)
        notes.append(stage_names[sid] + " | tap: " + (entry.get("happened_key") or "none") +
                     " | prospect words: " + (entry.get("prospect_words") or "none"))
    try:
        return call_llm("\n".join(notes) or "No notes recorded.")
    except Exception:
        logger.warning("LLM unavailable; using fallback rules.", exc_info=True)
        chosen = fallback_outcome(entries)
        return {"suggested_outcome": chosen,
                "summary": "Based on recorded notes: " + OUTCOME_DEFINITIONS[chosen].lower() + ".",
                "source": "rules"}

@app.post("/calls/{call_id}/close")
def close_call(call_id: str, body: CloseCallBody) -> dict:
    safe_id = validate_uuid(call_id)
    fetch_call(safe_id)
    if body.outcome not in ALLOWED_OUTCOMES:
        raise HTTPException(status_code=422, detail={"message": "Invalid outcome.", "allowed": sorted(ALLOWED_OUTCOMES)})
    result = execute(supabase.table("calls").update({
        "outcome": body.outcome, "summary": (body.summary or "").strip() or None,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", safe_id), "close call")
    if not result.data:
        raise HTTPException(status_code=503, detail="Call could not be closed.")
    return result.data[0]

@app.get("/calls")
def list_calls() -> list[dict]:
    result = execute(
        supabase.table("calls").select("*, furthest_stage:stages!calls_furthest_stage_id_fkey(name,position)")
        .order("started_at", desc=True),
        "list calls",
    )
    return result.data or []
