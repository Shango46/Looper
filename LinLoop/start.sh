#!/bin/bash
# One-click launcher for Looper. Usage: bash start.sh   (or ./start.sh if it's executable)
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Looper isn't installed yet. Run ./install.sh (or: bash install.sh) first."
    read -r -p "Press Enter to close..." _
    exit 1
fi

echo "Starting Looper..."
nohup ./.venv/bin/python run.py > server.log 2>&1 &
disown
sleep 2

URL="http://127.0.0.1:8731"
if command -v xdg-open &>/dev/null; then
    xdg-open "$URL" >/dev/null 2>&1 &
    disown
else
    echo "Open $URL in your browser."
fi

echo "Looper is running in the background (log: server.log)."
echo "To stop it: pkill -f 'run.py' from this folder, or use the systemd toggle in the app's Settings page."
read -r -p "Press Enter to close this window..." _
