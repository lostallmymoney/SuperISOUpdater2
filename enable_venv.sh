#!/bin/sh
# Enable a Python virtual environment safely

# Exit immediately on error
set -e

# Default venv directory (can be overridden)
VENV_DIR="${1:-.venv}"

# Check if directory exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found at: $VENV_DIR"
    echo "To create one, run: python3 -m venv $VENV_DIR"
    exit 1
fi

# Check if activate script exists
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "❌ No activate script found in $VENV_DIR/bin/"
    exit 1
fi

# Activate the virtual environment
echo "✅ Activating virtual environment: $VENV_DIR"
# Use . so it affects the current shell
. "$VENV_DIR/bin/activate"

# Optional message after activation
echo "🐍 Python venv enabled. Current Python:"