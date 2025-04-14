# Ksoloti

![Ksoloti Core front and back](/doc/ksoloti_core_front_and_back.jpg)

based on Axoloti by Johannes Taelman

johannes.taelman@gmail.com

Fork with a standalone patcher and firmware edits for the Ksoloti Core board by ksoloti.axo@gmail.com


This patcher has legacy support for Axoloti Core boards.


Axoloti is a platform for sketching music-DSP algorithms running on standalone hardware.




Ksoloti Core boards and related kits are available at:


[Thonk (UK)](https://www.thonk.co.uk/brand/ksoloti)


[Alt Circuits (US)](https://altcircuits.com/)


More info:


[Ksoloti resources, schematics, build guides](https://ksoloti.github.io)


[Ksoloti Forum](https://ksoloti.discourse.group)


[Ksoloti Discord Group](https://discord.com/invite/629kNnhj5R)


[Axoloti Community Forum Backup](https://sebiik.github.io/community.axoloti.com.backup/)


[Ksoloti on Instagram](https://instagram.com/ksoloti.axo/)


[Axoloti website](http://www.axoloti.com) (inactive?)


# Ksoloti Gills Integration Tool

A natural language processing tool for adding Gills hardware controls to Ksoloti/Axoloti patches.

## Overview

The Gills Integration Tool allows users to describe controls they want in natural language, and the system automatically adds appropriate Gills objects to their patch. This makes it easier to prototype control interfaces without needing to manually add and configure each control.

## Features

- Add Gills controls (pots, buttons, LEDs) to patches using natural language descriptions
- Intelligent control type detection from common terms 
- Automatic placement and configuration of controls
- Simple standalone test application for demonstration

## Usage

### Using in Your Patch

```java
import axoloti.mcp.GillsIntegrationTool;

// Add controls to your patch
int controlsAdded = GillsIntegrationTool.addGillsControlsFromDescription(
    yourPatchGUI, 
    "I need a knob for volume, a button for trigger, and an LED for status"
);
```

### Examples of Natural Language Descriptions

- "I need a pot for volume and another for frequency"
- "Add a button for trigger and an LED for status"
- "Create a volume knob and a cutoff slider"

### Demo Application

A simple demo application (TestGillsApp) is included to demonstrate the tool's functionality:

1. Run the TestGillsApp class
2. Enter your description in the text field
3. Click "Add Gills Controls"
4. The controls will be added to the patch canvas below

## Testing

Unit tests are provided in the `GillsIntegrationToolTest` class. You can run them using the `GillsIntegrationToolTestRunner`.

## Device Connection for Testing

If you're having trouble maintaining a connection to your device when testing the Gills controls, follow these steps:

### 1. Compile the Firmware

Run the included script to compile the firmware:

```bash
chmod +x compile_firmware.sh
./compile_firmware.sh
```

This script will:
- Enable Expert Mode in your preferences
- Compile the firmware
- Verify the firmware binary exists

### 2. Using the TestGillsApp

The TestGillsApp now includes features to help with device connection:

1. **Connect to Device** - Establishes a connection to your Ksoloti device
2. **Upload to Device** - Uploads the current patch with Gills controls to the device

### 3. Manual Firmware Steps (if needed)

If the script doesn't work, you can manually:

1. Edit the `ksoloti.prefs` file to include:
   ```xml
   <ExpertMode>true</ExpertMode>
   ```

2. Compile the firmware:
   ```bash
   cd firmware
   make clean
   make -j4
   ```

3. Verify the binary was created at `firmware/build/ksoloti.bin`

### 4. Troubleshooting

- **Connection Drops**: Ensure Expert Mode is enabled and firmware is properly compiled
- **Upload Fails**: Make sure you're connected to the device before uploading
- **Missing Controls**: Check for common naming conventions in your descriptions (e.g., "pot for volume")

## Supported Control Types

| Control Type | Keywords                                  | Gills Object Path |
|--------------|-------------------------------------------|------------------|
| Pot          | pot, potentiometer, knob, slider, dial    | gills/in/pot     |
| Button       | button, switch, trigger                   | gills/in/button  |
| LED          | led, light, indicator                     | gills/out/led    |

## Implementation Details

The GillsIntegrationTool works by:

1. Parsing the natural language description to identify control types and purposes
2. Mapping keywords to Gills control types
3. Creating appropriate Gills objects with proper attributes
4. Arranging objects in the patch with appropriate spacing

## Contributing

To extend the GillsIntegrationTool, consider:

1. Adding support for more control types
2. Improving the natural language processing capabilities
3. Adding more complex layout algorithms
4. Enhancing the attribute configuration for different controls


