#!/bin/bash

# Compile Ksoloti Firmware Script
# This script assists in compiling the firmware needed for the Gills Integration Tool

echo "=== Ksoloti Firmware Compilation Tool ==="
echo "This script will help compile the firmware needed for the Gills Integration Tool"

# Find firmware directory
FIRMWARE_DIR="firmware"
PREFS_FILE="ksoloti.prefs"

# Check if firmware directory exists
if [ ! -d "$FIRMWARE_DIR" ]; then
    echo "ERROR: Firmware directory '$FIRMWARE_DIR' not found."
    echo "Please run this script from the Ksoloti project root directory."
    exit 1
fi

# Check and enable expert mode in preferences
if [ -f "$PREFS_FILE" ]; then
    # Check if expert mode is already enabled
    if grep -q "<ExpertMode>true</ExpertMode>" "$PREFS_FILE"; then
        echo "Expert mode is already enabled in $PREFS_FILE"
    else
        # Try to enable expert mode
        if grep -q "<ExpertMode>" "$PREFS_FILE"; then
            # Replace existing ExpertMode tag
            sed -i '' 's/<ExpertMode>.*<\/ExpertMode>/<ExpertMode>true<\/ExpertMode>/g' "$PREFS_FILE"
            echo "Expert mode has been enabled in $PREFS_FILE"
        else
            # Add ExpertMode tag before closing Preferences tag
            sed -i '' 's/<\/Preferences>/<ExpertMode>true<\/ExpertMode>\n<\/Preferences>/g' "$PREFS_FILE"
            echo "Expert mode has been added to $PREFS_FILE"
        fi
    fi
else
    # Create a new preferences file with expert mode enabled
    echo "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" > "$PREFS_FILE"
    echo "<Preferences>" >> "$PREFS_FILE"
    echo "    <ExpertMode>true</ExpertMode>" >> "$PREFS_FILE"
    echo "</Preferences>" >> "$PREFS_FILE"
    echo "Created new $PREFS_FILE with expert mode enabled"
fi

# Change to firmware directory
cd "$FIRMWARE_DIR" || exit 1
echo "Changed to directory: $(pwd)"

# Compile firmware
echo "Compiling firmware... (this may take a few minutes)"
make clean
make -j4

# Check if compilation was successful
if [ -f "build/ksoloti.bin" ]; then
    echo "=== Firmware compilation successful! ==="
    echo "Firmware binary created at: $(pwd)/build/ksoloti.bin"
    echo ""
    echo "You can now run the TestGillsApp and connect to your device."
else
    echo "=== Firmware compilation failed! ==="
    echo "Please check the error messages above."
    exit 1
fi

# Return to original directory
cd ..

echo "Done." 