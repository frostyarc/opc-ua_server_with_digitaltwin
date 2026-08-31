@echo off
echo Stopping any existing opcua_server.py / bridge_server / web_app processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'opcua_server\.py|bridge_server:app|web_app:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 2 /nobreak >nul

start "OPCUA Server 4846" /d "%~dp0" cmd /k python opcua_server.py
start "Bridge Server 8765" /d "%~dp0" cmd /k python -m uvicorn bridge_server:app --port 8765
start "Web Order App 8000" /d "%~dp0..\08-27" cmd /k python -m uvicorn web_app:app

echo Started 3 servers in separate windows. Old processes were cleaned up first.
echo Press any key to close this window - leave the other 3 windows open.
pause >nul
