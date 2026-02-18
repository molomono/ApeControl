#!/bin/bash

# ApeControl Installation Script
# This script symlinks ApeControl into the Klipper extras directory.

KLIPPER_PATH="${HOME}/klipper"
EXTRAS_PATH="${KLIPPER_PATH}/klippy/extras"
REPO_PATH=$(pwd)

echo "Starting ApeControl installation..."

# 1. Check if Klipper directory exists
if [ ! -d "$EXTRAS_PATH" ]; then
    echo "Error: Klipper extras directory not found at $EXTRAS_PATH"
    echo "Please ensure Klipper is installed in your home directory."
    exit 1
fi

# 2. Create symlink for the main entry point
echo "🔗 Linking ape_control.py..."
ln -sf "${REPO_PATH}/ape_control.py" "${EXTRAS_PATH}/ape_control.py"

# 3. Create symlink for the modules directory
echo "🔗 Linking control_modules directory..."
# Note: Linking the folder directly allows Klipper to import from it
ln -sf "${REPO_PATH}/control_modules" "${EXTRAS_PATH}/control_modules"

# 4. Verify the links
if [ -L "${EXTRAS_PATH}/ape_control.py" ] && [ -L "${EXTRAS_PATH}/control_modules" ]; then
    echo "Success: ApeControl is now linked to Klipper extras."
    echo "Restarting Klipper..."
    sudo systemctl restart klipper
    echo "[OK]"
else
    echo "Warning: Symlinks were created but verification failed."
    exit 1
fi