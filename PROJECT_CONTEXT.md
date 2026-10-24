# Cold-Call Guide

## Goal
A caller keeps the live-call screen beside a phone call. It walks through eight stages, records an outcome and the prospect's own words, saves the call, and lists past calls with the furthest stage reached.

## Stack
- Supabase PostgreSQL (db/schema.sql, db/seed.sql)
- FastAPI/Python backend, deployed to Render
- React + Vite frontend, deployed to Vercel
- Gemini by default or Cerebras, called only by the backend

## Environment
Backend: SUPABASE_URL, SUPABASE_SERVICE_KEY, ALLOWED_ORIGINS, LLM_PROVIDER, LLM_API_KEY, LLM_MODEL.
Frontend: VITE_API_BASE_URL.

## API
GET /health; GET /stages; POST /calls; POST /calls/{id}/stages; POST /calls/{id}/suggest-outcome; POST /calls/{id}/close; GET /calls.

Allowed outcomes: agreed_to_receive_report, next_step_agreed, interested, follow_up, call_again, not_interested, do_not_call, wrong_person, moved_company, not_logged.

Fallback rules: whatsapp/email -> agreed_to_receive_report; call_time/callback_time/referral -> follow_up; wrong_person -> wrong_person; moved_company -> moved_company; not_interested -> not_interested; otherwise -> not_logged.

Never commit secrets or raw transcripts. Validate inputs and verify changes locally.
