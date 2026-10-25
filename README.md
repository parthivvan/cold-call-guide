# Cold-Call Guide

A focused call companion for recording and reviewing prospect conversations across eight stages. It uses a React frontend, a FastAPI backend, and Supabase for persistent call and stage-result storage.

## Live deployment

- **Vercel app:** https://cold-call-guide-beta.vercel.app/
- **Render API:** https://cold-call-guide-api-yhjy.onrender.com/
- **Render health endpoint:** https://cold-call-guide-api-yhjy.onrender.com/health
- **Interactive API docs:** https://cold-call-guide-api-yhjy.onrender.com/docs
- **Public repository:** https://github.com/parthivvan/cold-call-guide

The health endpoint should return `{"status":"ok"}`. The `/stages` endpoint returns the eight configured stages.

## Technology stack

- **Frontend:** React and Vite
- **Backend:** Python, FastAPI, Uvicorn/Gunicorn
- **Database:** Supabase (PostgreSQL), with schema and seed SQL in `db/`
- **Deployment:** Vercel for the frontend; Render for the backend

## LLM used and what it does

The configured LLM is **Google Gemini 2.0 Flash** (`LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.0-flash`). When a call is closed, the backend can send the recorded stage notes to Gemini to suggest a call outcome and a concise factual summary. The backend validates the suggested outcome against the allowed outcome list. If the LLM is unavailable or returns an invalid response, deterministic rule-based logic supplies a fallback suggestion. The LLM API key is stored only in Render's environment variables, never in the browser.

## Core workflow

1. Start a call by entering the prospect and company.
2. Move through the eight stages and record what happened plus the prospect's words.
3. Save stage results to Supabase as the call progresses.
4. At close, review the suggested outcome and summary, choose the final outcome, and save the call.
5. Review past calls and their recorded outcome and furthest stage.

## Design decisions

- **Eight explicit stages:** give the caller a repeatable flow while still allowing stage navigation in any order.
- **Capture the prospect's words:** keep a place for the prospect's actual phrasing rather than relying only on a general impression.
- **Treat an LLM result as a suggestion:** the caller can review and change the final outcome; rule-based fallback keeps the close flow usable if Gemini is unavailable.

In the video walkthrough, connect these decisions to the actual transcript provided with the task. Do not claim a quantitative finding unless you have checked it against the source transcripts.

## Deployment configuration

### Supabase

The schema is in `db/schema.sql`; initial stage content is in `db/seed.sql`. Run these SQL files in the Supabase SQL Editor only if the tables and stage rows have not already been created. Do not rerun setup SQL against an already configured database without checking its effects first.

### Render backend

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command is configured in `render.yaml`.
- Required environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `ALLOWED_ORIGINS`.
- For LLM suggestions: `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.0-flash`, and `LLM_API_KEY`.

Set `ALLOWED_ORIGINS` to the exact Vercel origin: `https://cold-call-guide-beta.vercel.app`. Keep service and LLM keys private.

### Vercel frontend

- Root directory: `frontend`
- Framework: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://cold-call-guide-api-yhjy.onrender.com`

When changing frontend environment variables, redeploy Vercel so the new value is included in the build.

## Local setup (PowerShell)

Backend, from the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit backend/.env with private credentials. Never commit it.
uvicorn main:app --reload --port 8000
```

Frontend in a second terminal, from the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
# Set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## Security

Never commit `.env` files, Supabase service keys, Gemini API keys, or raw transcripts. The Supabase service key and Gemini API key must remain on the backend only.
