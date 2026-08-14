@echo off
rem Starts the addon and opens the shows editor. Close the server window to stop.
cd /d "%~dp0"

where python >nul 2>&1 || (
  echo Python is required but was not found on PATH.
  pause
  exit /b 1
)

start "Catch-up TV ^& More" python run_server.py
rem the app loads credentials and binds before it can answer
timeout /t 4 /nobreak >nul
start "" http://localhost:7860
