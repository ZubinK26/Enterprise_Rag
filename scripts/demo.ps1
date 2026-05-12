#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BaseUrl = if ($env:SERVER_URL) { $env:SERVER_URL } else { "http://127.0.0.1:8000" }

for ($i = 0; $i -lt 90; $i++) {
    try {
        Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

try {
    Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
} catch {
    throw "Timed out waiting for health at $BaseUrl"
}

$resultsDir = Join-Path $Root "results"
New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null

Write-Host "--- POST /ingest"
$ingest = Invoke-RestMethod -Method Post -Uri "$BaseUrl/ingest"
$ingestPath = Join-Path $resultsDir "demo_ingest.json"
($ingest | ConvertTo-Json -Depth 8) | Set-Content -Path $ingestPath -Encoding utf8

Write-Host "--- POST /evaluate"
$eval = Invoke-RestMethod -Method Post -Uri "$BaseUrl/evaluate" `
    -ContentType "application/json" `
    -Body '{"case_file":"eval_cases/eval_cases.json"}'
$evalPath = Join-Path $resultsDir "demo_evaluate.json"
($eval | ConvertTo-Json -Depth 12) | Set-Content -Path $evalPath -Encoding utf8

Write-Host "Wrote:"
Write-Host "  $ingestPath"
Write-Host "  $evalPath"
