import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()  # reads backend/.env (ignored by git)

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Allowed outcomes – mirrors the CHECK constraint in the DB schema.
ALLOWED_OUTCOMES = {
    "agreed_to_receive_report",
    "next_step_agreed",
    "interested",
    "follow_up",
    "call_again",
    "not_interested",
    "do_not_call",
    "wrong_person",
    "moved_company",
    "not_logged",
}

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Cold-Call Guide API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateCallBody(BaseModel):
    prospect_name: str
    company: str


class StageResultBody(BaseModel):
    stage_id: int
    happened_key: Optional[str] = None
    prospect_words: Optional[str] = None
    next_stage_id: int


class CloseCallBody(BaseModel):
    outcome: str
    summary: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_call(call_id: str) -> dict:
    """Return a call row or raise 404."""
    res = supabase.table("calls").select("*").eq("id", call_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Call {call_id!r} not found.")
    return res.data


def _stage_position(stage_id: int) -> int:
    """Return the position of a stage or raise 404."""
    res = supabase.table("stages").select("position").eq("id", stage_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Stage {stage_id} not found.")
    return res.data["position"]


# ---------------------------------------------------------------------------
# Routes – existing
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Liveness check used by Render and the frontend."""
    return {"status": "ok"}


@app.get("/stages")
def get_stages() -> list[dict]:
    """Return all call stages ordered by their position column."""
    res = (
        supabase.table("stages")
        .select("*")
        .order("position")
        .execute()
    )
    if res.data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch stages from database.")
    return res.data


# ---------------------------------------------------------------------------
# Routes – call management
# ---------------------------------------------------------------------------

@app.post("/calls", status_code=201)
def create_call(body: CreateCallBody) -> dict:
    """
    Create a new call and initialise both current and furthest stage to stage 1
    (the stage with position = 1).
    """
    # Resolve stage 1 by position so we don't hard-code an ID.
    stage_res = (
        supabase.table("stages")
        .select("id")
        .eq("position", 1)
        .single()
        .execute()
    )
    if not stage_res.data:
        raise HTTPException(status_code=500, detail="Stage 1 not found in database.")
    stage_1_id: int = stage_res.data["id"]

    call_res = (
        supabase.table("calls")
        .insert({
            "prospect_name": body.prospect_name,
            "company": body.company,
            "current_stage_id": stage_1_id,
            "furthest_stage_id": stage_1_id,
        })
        .execute()
    )
    if not call_res.data:
        raise HTTPException(status_code=500, detail="Failed to create call.")
    return call_res.data[0]


@app.post("/calls/{call_id}/stages")
def record_stage(call_id: str, body: StageResultBody) -> dict:
    """
    Save a stage_results row for the given call, advance current_stage_id,
    and advance furthest_stage_id only when the new stage is further ahead.
    """
    call = _fetch_call(call_id)

    # Insert the stage result.
    result_res = (
        supabase.table("stage_results")
        .insert({
            "call_id": call_id,
            "stage_id": body.stage_id,
            "happened_key": body.happened_key,
            "prospect_words": body.prospect_words,
        })
        .execute()
    )
    if not result_res.data:
        raise HTTPException(status_code=500, detail="Failed to save stage result.")

    # Decide whether furthest_stage_id should advance.
    next_position = _stage_position(body.next_stage_id)
    current_furthest_id: int = call["furthest_stage_id"]
    furthest_position = _stage_position(current_furthest_id)

    new_furthest_id = (
        body.next_stage_id if next_position > furthest_position else current_furthest_id
    )

    # Update the call.
    update_res = (
        supabase.table("calls")
        .update({
            "current_stage_id": body.next_stage_id,
            "furthest_stage_id": new_furthest_id,
        })
        .eq("id", call_id)
        .execute()
    )
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to update call stage.")

    return {
        "stage_result": result_res.data[0],
        "call": update_res.data[0],
    }


@app.post("/calls/{call_id}/close")
def close_call(call_id: str, body: CloseCallBody) -> dict:
    """
    Set outcome, summary, and ended_at on the call.
    Validates outcome against the allowed set defined in PROJECT_CONTEXT.md.
    """
    _fetch_call(call_id)  # raises 404 if unknown

    if body.outcome not in ALLOWED_OUTCOMES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid outcome {body.outcome!r}. "
                f"Allowed values: {sorted(ALLOWED_OUTCOMES)}"
            ),
        )

    update_res = (
        supabase.table("calls")
        .update({
            "outcome": body.outcome,
            "summary": body.summary,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", call_id)
        .execute()
    )
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to close call.")
    return update_res.data[0]


@app.get("/calls")
def list_calls() -> list[dict]:
    """
    Return all calls newest-first, each with the furthest stage's name and position
    joined from the stages table.
    """
    res = (
        supabase.table("calls")
        .select("*, furthest_stage:stages!calls_furthest_stage_id_fkey(name, position)")
        .order("started_at", desc=True)
        .execute()
    )
    if res.data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch calls.")
    return res.data
