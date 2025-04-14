# Ksoloti MCP (Model-Controlled Programming)

## Overview

Ksoloti MCP (Model-Controlled Programming) is a feature that allows you to create Ksoloti patches using natural language descriptions. The system leverages Google's Gemini API to convert your textual descriptions into functional patches.

## Features

- Generate patches using natural language descriptions
- HTTP API for remote integration
- Built-in UI in the Ksoloti patcher
- Support for Google Gemini 2.0 Flash model

## Usage

### Via the UI

1. Open the Ksoloti patcher
2. Go to **Edit > Create Patch with Natural Language**
3. Enter a description of the patch you want to create in the text field
4. Click "Generate Patch"

### API Configuration

1. Click the "Settings" button in the MCP dialog
2. Enter your Gemini API key
   - You can obtain a Gemini API key from [Google AI Studio](https://aistudio.google.com/)
   - Create or log in to your Google account
   - Navigate to API keys and create a new key
   - Copy and paste the key into the settings dialog

### HTTP API

The MCP server runs on port 8080 by default and exposes the following endpoints:

- `POST /api/generate` - Generate a patch from a natural language description
  - Request body: `{"description": "your description here"}`
  - Response: `{"status": "accepted", "message": "Patch generation started. The patch will open when ready."}`

- `GET /api/health` - Check if the MCP server is running
  - Response: `{"status": "up", "version": "1.0.0"}`

## Examples

Here are some examples of descriptions you can use:

- "Create a simple sine wave oscillator with volume control"
- "Make a drum machine with kick and snare"
- "Build a subtractive synth with two oscillators, a filter, and an envelope"
- "Create an ambient pad with reverb and delay"
- "Make a sequencer that controls a bass synth"

## Limitations

When used without a Gemini API key, the system will fall back to a mock implementation with predefined responses for certain keywords like "oscillator", "drum", etc.

## Troubleshooting

- If you encounter errors, check that your API key is correctly entered
- Make sure your computer has internet access to communicate with the Gemini API
- Check the console for any error messages

## Development

The MCP system consists of the following components:

- `MCPServer.java` - HTTP server that listens for requests to generate patches
- `NLPPatchGenerator.java` - Processes natural language into patch specifications
- `LLMService.java` - Interface for language model services
- `LLMServiceGemini.java` - Implementation for Google's Gemini API
- `LLMServiceMock.java` - Mock implementation for testing
- `MCPDialog.java` - UI for entering natural language descriptions
- `MCPSettingsDialog.java` - UI for configuring API keys 