# One-click start: server + web (each in its own window, survives this window / Trae close)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $Root "third_party\index-tts\.venv\Scripts\python.exe"

if (-not (Test-Path (Join-Path $Root "assets\characters"))) {
  & python (Join-Path $Root "scripts\sync_assets.py")
}

Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$Root'; & '$Py' -m uvicorn apps.server.main:app --host 127.0.0.1 --port 9890"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$Root\apps\web'; pnpm dev"

Write-Host ""
Write-Host "=================================================="
Write-Host "  EndfieldVoiceForge started (two windows)"
Write-Host "  Web    -> http://localhost:3000"
Write-Host "  Server -> http://127.0.0.1:9890/docs"
Write-Host "  Stop   -> double-click stop.bat, or close those two windows"
Write-Host "=================================================="

Start-Sleep -Seconds 6
Start-Process "http://localhost:3000"
