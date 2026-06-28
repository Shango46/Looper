@echo off
setlocal
cd /d "%~dp0"

echo Starting Looper server...
start "Looper Server" /min ".venv\Scripts\python.exe" "run.py"

echo Waiting for server to come up...
timeout /t 3 /nobreak >nul

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --new-window "http://127.0.0.1:8731"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --new-window "http://127.0.0.1:8731"
) else (
    start chrome --new-window "http://127.0.0.1:8731"
)

echo.
echo Looper is running in the "Looper Server" window. Close that window to stop it.
