#!/bin/bash

# Configuration
SCRIPT="monitor_runner.py"

# Check if playwright is installed (just in case, though we know it is)
if ! python3 -c "import playwright" &> /dev/null; then
    echo "Playwright not found in system python. Trying to install via pip..."
    pip install --break-system-packages playwright
    playwright install chromium
fi

echo "Starting Monitor Script..."
python3 "$SCRIPT" "$@"
