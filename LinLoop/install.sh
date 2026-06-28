#!/bin/bash
# One-click installer for Looper on Linux Mint (or any Debian-based distro with python3).
# Usage: bash install.sh   (or ./install.sh if it's executable)
set -e
cd "$(dirname "$0")"

echo "=== Looper installer ==="

if ! command -v python3 &>/dev/null; then
    echo "python3 not found. Install it first:"
    echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "Creating virtual environment (.venv)..."
python3 -m venv .venv

echo "Installing Python dependencies..."
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "Running environment setup (Chrome detection / Playwright)..."
./.venv/bin/python setup/setup_environment.py || true

mkdir -p data company_data

echo
echo "=== Install complete ==="
echo "Run ./start.sh (or: bash start.sh) to launch Looper."
