#!/bin/sh
# Create a Python virtual environment in .venv if it does not exist

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
    echo "Virtual environment created."
else
    echo ".venv already exists."
fi

echo "Activating virtual environment and installing requirements..."
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Done. To activate later, run: . .venv/bin/activate"
