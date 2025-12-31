#!/bin/bash

# Configuration
SCRIPT="monitor_runner.py"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Ensure Playwright browsers are installed
if ! python3 -c "import playwright.sync_api" &> /dev/null; then
     echo "Playwright browsers not found (or module issue). Installing..."
     python3 -m playwright install chromium
else
     # Check if chromium specifically is install? Hard to check easily without running.
     # We can just run install, it returns quickly if already installed.
     echo "Checking Playwright browsers..."
     python3 -m playwright install chromium
fi

echo "Starting Monitor Script in BACKGROUND..."
nohup python3 "$SCRIPT" "$@" > /dev/null 2>&1 &
PID=$!
echo "Monitor started. PID: $PID"
echo "Console output discarded. Logs are in 'availability.log'."
echo "To stop the monitor, run: kill $PID"
