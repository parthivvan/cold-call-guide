$ErrorActionPreference = "Stop"
$base = if ($env:BASE_URL) { $env:BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:8000" }
function Pass($label) { Write-Host "PASS: $label" -ForegroundColor Green }
$health = Invoke-RestMethod "$base/health"
if ($health.status -ne "ok") { throw "Health check failed" }
Pass "GET /health"
$stages = Invoke-RestMethod "$base/stages"
if (@($stages).Count -ne 8) { throw "Expected 8 stages; got $(@($stages).Count)" }
Pass "GET /stages"
$created = Invoke-RestMethod -Method Post -Uri "$base/calls" -ContentType "application/json" -Body (@{prospect_name="Smoke Test";company="Example Co"} | ConvertTo-Json)
$id = $created.id
if (-not $id) { throw "No call ID returned" }
Pass "POST /calls"
$body = @{stage_id=1;happened_key="right_person";prospect_words="Smoke test";next_stage_id=2} | ConvertTo-Json
$saved = Invoke-RestMethod -Method Post -Uri "$base/calls/$id/stages" -ContentType "application/json" -Body $body
if ($saved.call.current_stage_id -ne 2) { throw "Current stage did not advance" }
Pass "POST /calls/{id}/stages"
$closed = Invoke-RestMethod -Method Post -Uri "$base/calls/$id/close" -ContentType "application/json" -Body (@{outcome="not_logged";summary="Smoke test"} | ConvertTo-Json)
if (-not $closed.ended_at) { throw "Ended timestamp missing" }
Pass "POST /calls/{id}/close"
$history = Invoke-RestMethod "$base/calls"
if (-not ($history | Where-Object { $_.id -eq $id })) { throw "New call missing from history" }
Pass "GET /calls"
Write-Host "All smoke tests passed." -ForegroundColor Green
