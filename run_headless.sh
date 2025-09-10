#!/bin/bash
# CR-0073: Headless Runner Startup Script for Unix/Linux
# Trade bot headless modda başlatma

echo "========================================"
echo "    Trade Bot Headless Runner"
echo "========================================"

# Check if virtual environment activation script exists
if [ -f "activate_env.sh" ]; then
    echo "Activating Python environment..."
    source activate_env.sh
elif [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: No virtual environment found, using system Python"
fi

# Check Python
if ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python or activate environment."
    exit 1
fi

echo "Python version: $(python --version)"
echo "Starting Trade Bot in headless mode..."
echo "Press Ctrl+C to stop gracefully"

# Run headless trader with arguments passed from command line
python src/headless_runner.py "$@"

echo ""
echo "Headless runner stopped."
