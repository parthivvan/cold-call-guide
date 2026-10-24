#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
pass(){ echo "PASS: $1"; }
health=$(curl -fsS "$BASE_URL/health"); echo "$health" | grep -q '"status":"ok'; pass "GET /health"
stages=$(curl -fsS "$BASE_URL/stages"); echo "$stages" | grep -q '"position":8'; pass "GET /stages"
created=$(curl -fsS -X POST "$BASE_URL/calls" -H 'Content-Type: application/json' -d '{"prospect_name":"Smoke Test","company":"Example Co"}')
id=$(python -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$created"); test -n "$id"; pass "POST /calls"
saved=$(curl -fsS -X POST "$BASE_URL/calls/$id/stages" -H 'Content-Type: application/json' -d '{"stage_id":1,"happened_key":"right_person","prospect_words":"Smoke test","next_stage_id":2}')
echo "$saved" | grep -q '"current_stage_id":2'; pass "POST /calls/{id}/stages"
closed=$(curl -fsS -X POST "$BASE_URL/calls/$id/close" -H 'Content-Type: application/json' -d '{"outcome":"not_logged","summary":"Smoke test"}')
echo "$closed" | grep -q '"ended_at":'; pass "POST /calls/{id}/close"
history=$(curl -fsS "$BASE_URL/calls"); echo "$history" | grep -q "$id"; pass "GET /calls"
echo "All smoke tests passed."
