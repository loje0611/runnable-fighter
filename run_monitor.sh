#!/bin/bash

# Configuration
SCRIPT="monitor_runner.py"

# Check if playwright is installed (just in case, though we know it is)
if ! python3 -c "import playwright" &> /dev/null; then
    echo "Playwright not found. Installing..."
    pip install --break-system-packages playwright
    python3 -m playwright install chromium
fi

echo "Starting Monitor Script..."
python3 "$SCRIPT" "$@"
