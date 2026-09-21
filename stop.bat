@echo off
echo Stopping EndfieldVoiceForge (server 9890 + web 3000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 9890,3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo Done.
pause
