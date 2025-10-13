#!/bin/sh
# Create and install the current Python project in an isolated pipx environment

# Ensure pipx is installed
if ! command -v pipx >/dev/null 2>&1; then
    echo "pipx not found. Attempting to install pipx using apt..."
    if command -v apt >/dev/null 2>&1; then
        echo "You may be prompted for your password to install pipx via sudo."
        sudo apt update && sudo apt install -y pipx || {
            echo "Failed to install pipx with apt. Trying pip as fallback...";
            python3 -m pip install --user pipx --break-system-packages || { echo "Failed to install pipx."; exit 1; }
        }
        pipx ensurepath
        echo "Please restart your terminal or run: export PATH=\"$HOME/.local/bin:$PATH\""
    else
        echo "apt not found. Trying pip as fallback..."
        python3 -m pip install --user pipx --break-system-packages || { echo "Failed to install pipx."; exit 1; }
        python3 -m pipx ensurepath
        echo "Please restart your terminal or run: export PATH=\"$HOME/.local/bin:$PATH\""
    fi
fi

# Install the current project with pipx

if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    echo "Installing the current project in an isolated pipx environment..."
    pipx install --force . || { echo "pipx install failed."; exit 1; }
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt into the pipx environment..."
        PKG_NAME=$(python3 setup.py --name 2>/dev/null || basename "$PWD")
        pipx inject "$PKG_NAME" -r requirements.txt || { echo "pipx inject failed."; exit 1; }
    fi
    echo "Installation complete. Use the command provided by your package to run it."
    pipx ensurepath
else
    echo "No setup.py or pyproject.toml found. Please run this script from your project root."
    exit 1
fi
