# Cold-Call Guide

A focused call companion for recording prospect conversations across eight stages. It uses Supabase, a FastAPI backend, and a React interface for live calls and call history. At call close, a configured LLM can suggest an outcome and summary; deterministic rules are used if the LLM is unavailable.

## Deployment
1. Run `db/schema.sql` then `db/seed.sql` in Supabase SQL Editor if the tables/stages are not already configured.
2. Render backend: root directory `backend`; build `pip install -r requirements.txt`; start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Set Render environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ALLOWED_ORIGINS`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`.
4. Vercel project root: `frontend`. Set `VITE_API_BASE_URL` to the Render API URL.
5. Add the exact Vercel origin to `ALLOWED_ORIGINS` on Render and redeploy the backend.
6. Verify `/health`, `/stages`, a complete call lifecycle, and past calls.

## Local setup (PowerShell)

Backend:
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit backend/.env with private credentials. Never commit it.
uvicorn main:app --reload --port 8000
```

Frontend in a second terminal:
```powershell
cd frontend
npm install
Copy-Item .env.example .env
# Set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## What I learned from 100 calls and decisions made
Fill from your own review:
- [FINDING 1]
- [FINDING 2]
- [FINDING 3]
- [DECISION]

Research notes mention a 93-second median call, permission asked before purpose in 55/100 calls, and roughly 10/13 calls marked not_logged apparently having a real next step. Re-check against source data before quoting publicly.

## Security
Never commit .env files, service keys, LLM keys, or raw transcripts. Keep the Supabase service key on the backend only.
