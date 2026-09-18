# 一键启动 server + web(各开一个窗口)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $Root "third_party\index-tts\.venv\Scripts\python.exe"

if (-not (Test-Path (Join-Path $Root "assets\characters"))) {
  & python (Join-Path $Root "scripts\sync_assets.py")
}

Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$Root'; & '$Py' -m uvicorn apps.server.main:app --host 127.0.0.1 --port 9890 --reload --reload-dir apps/server"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$Root\apps\web'; pnpm dev"
Write-Host "server -> http://127.0.0.1:9890/docs   web -> http://localhost:3000"
