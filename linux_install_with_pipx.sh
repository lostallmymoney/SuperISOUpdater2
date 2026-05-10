#!/bin/sh
# Create and install the current Python project in an isolated pipx environment
set -eu

cleanup_build_artifacts() {
    rm -rf build dist
    find . -maxdepth 1 -type d -name "*.egg-info" -exec rm -rf {} +
}

# Ensure pipx is installed
if ! command -v pipx >/dev/null 2>&1; then
    echo "pipx not found. Attempting to install pipx using apt..."
    if command -v apt >/dev/null 2>&1; then
        echo "You may be prompted for your password to install pipx via sudo."
        sudo apt update && sudo apt install -y pipx || {
            echo "Failed to install pipx with apt. Trying pip as fallback..."
            python3 -m pip install --user pipx --break-system-packages || {
                echo "Failed to install pipx."
                exit 1
            }
        }
        pipx ensurepath --force
        echo "Please restart your terminal or run: export PATH=\"$HOME/.local/bin:\$PATH\""
    else
        echo "apt not found. Trying pip as fallback..."
        python3 -m pip install --user pipx --break-system-packages || {
            echo "Failed to install pipx."
            exit 1
        }
        python3 -m pipx ensurepath --force
        echo "Please restart your terminal or run: export PATH=\"$HOME/.local/bin:\$PATH\""
    fi
fi

# Install the current project with pipx

if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    PKG_NAME="sisou2"
    APP_NAME="sisou2"

    echo "Removing previous pipx installation for $PKG_NAME..."
    pipx uninstall "$PKG_NAME" >/dev/null 2>&1 || true
    rm -rf "$HOME/.local/pipx/venvs/$PKG_NAME"
    rm -rf "$HOME/.local/share/pipx/venvs/$PKG_NAME"
    rm -f "$HOME/.local/bin/$APP_NAME"

    echo "Removing local build artifacts..."
    cleanup_build_artifacts

    echo "Installing the current project in a clean isolated pipx environment..."
    pipx install --force . || {
        echo "pipx install failed."
        cleanup_build_artifacts
        exit 1
    }
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt into the pipx environment..."
        pipx inject --force "$PKG_NAME" -r requirements.txt || {
            echo "pipx inject failed."
            cleanup_build_artifacts
            exit 1
        }
    fi
    cleanup_build_artifacts
    echo "Installation complete. Run it with: $APP_NAME"
    pipx ensurepath --force
else
    echo "No setup.py or pyproject.toml found. Please run this script from your project root."
    exit 1
fi
