# Toolkit for Antigravity

Real-time AI quota monitor & cache manager for Google Antigravity IDE — track Gemini, Claude, and GPT usage, visualize consumption trends, and manage conversation cache, all in one sidebar panel.

## Features at a Glance

- 🎯 Quota Monitoring - Real-time status with visual thresholds
- 📊 Usage Analytics - Interactive charts and history tracking
- 🧹 Cache Management - Manage AI conversation history and files
- 🎨 Native Integration - UI components adapted to IDE themes
- 🌍 Localization - Support for 13 languages including runtime notifications
- 🛠️ Diagnostics - Built-in connection check and error reporting
- 🤖 Hands-free Mode - Auto-accept agent commands for heavy workflows
- ✍️ AI Commit - Generate commit messages via Local LLM or Claude
- ⚙️ Quick Config Access - One-click editing for Rules, MCP, and Allowlist
- 🔄 Service Recovery - Restart, Reset, and Reload tools for Antigravity IDE stability

## Key Features

### Smart Quota Monitoring

- Visual quota display grouped by AI model groups (Gemini, Claude, GPT, etc.)
- Status bar shows remaining quota with emoji indicators (🟢🟡🔴) and cache size
- Hover tooltip showing all model quotas and reset times
- Configurable warning (≤30%) and critical (≤10%) thresholds

### Usage Trends & Analytics

- Interactive bar charts showing usage over time (10-120 minutes)
- 24-hour history tracking with persistent storage
- Color-coded visualization by AI model group
- Usage Rate: Real-time consumption speed (%/hour)
- Runway Prediction: Estimated time until quota exhaustion

### Token Credits Tracking

- Prompt Credits: Used for conversation input and result generation (reasoning)
- Flow Credits: Used for search, modification, and command execution (operations)
- User info card visibility can be toggled in settings

### Cache Management

- Brain Tasks: Browse and delete AI conversation caches
- See task size, file count, and creation date
- Preview images, markdown, and code files
- One-click deletion with automatic cleanup
- Code Context: Manage code analysis caches per project
- Smart Cleanup: Automatically closes related editor tabs

### Auto-Accept (Hands-free Mode)

- Automatically accepts Agent-suggested terminal commands and file edits
- Dual strategy: command API (primary) + CDP injection (fallback for sandboxed webviews)
- Toggle on/off via the sidebar "Rocket" switch

CDP Fallback Setup: For the CDP fallback to work, Antigravity must be launched with --remote-debugging-port=9222. This is only needed when the command API is unavailable due to webview sandboxing.

Windows launcher:

```bat
@echo off
taskkill /F /IM Antigravity.exe /T 2>nul
start "" "D:\Develop\Antigravity\Antigravity.exe" --remote-debugging-port=9222
```

macOS/Linux launcher:

```bash
#!/bin/bash
pkill -f "Antigravity"
/Applications/Antigravity.app/Contents/MacOS/Electron --remote-debugging-port=9222 &
```

### Commit Message Generator (Claude)

A workaround for when the built-in "Generate commit message" feature is unavailable.

Setup:
1. Get an API key from Anthropic Console
2. Run Antigravity Toolkit: Set Anthropic API Key
3. Enter your API key (stored securely, never in plaintext)

Usage:
1. Stage your changes with git add
2. Run Antigravity Toolkit: Generate Commit Message (Claude)
3. The commit message auto-populates in the SCM input box

Configuration:
- Model: Choose between Claude Sonnet 4, 3.5 Sonnet, or Opus
- Max Diff Size: Limit characters sent (default: 80,000)
- Format: Conventional commits or simple style

### Service Recovery Tools

- Restart: Reboots the background Language Server if the Agent is unresponsive
- Reset: Clears user status cache to fix stuck quota updates
- Reload: Refreshes the VS Code window to resolve UI glitches

### Quick Configuration Access

- Edit Global Rules
- Configure MCP settings
- Manage Browser Allowlist

## Available Commands

| Command | What it does |
|---------|-------------|
| Open Panel | Open the sidebar panel |
| Refresh Quota | Manually refresh quota data |
| Show Cache Size | Show total cache size notification |
| Clean Cache | Delete all cache data |
| Open Settings | Open extension settings |
| Show Disclaimer | View privacy and safety disclaimer |
| Restart Language Server | Restart Antigravity Agent Service |
| Reset User Status | Reset the status updater |
| Run Diagnostics | Run connectivity diagnostics |
| Reload Window | Refresh the webview to resolve UI glitches |
| Toggle Auto-Accept | Enable/Disable automatic command acceptance |
| Generate Commit Message | Generate commit message using Local LLM or Claude |
| Set Anthropic API Key | Configure Anthropic API Key |

## Configuration

### Quota Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Polling Interval | 90s | How often to refresh quota (min: 60s) |
| Show Quota | ✓ | Display quota in status bar |
| Status Bar Style | percentage | Display mode: percentage, resetTime, used, or remaining |
| Quota Style | semi-arc | Visualization style: semi-arc or classic-donut |
| Visualization Mode | groups | Show dashboard by groups or models |
| UI Scale | 1.0 | Global scale factor for panel elements (0.8 to 2.0) |
| Show GPT Quota | ✗ | Whether to display GPT family models in the panel |
| History Range | 90 min | Time range for usage chart (10-120 minutes) |
| Warning Threshold | 30% | Status bar turns warning color at this level |
| Critical Threshold | 10% | Status bar turns critical color at this level |

### Cache Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Show Cache Size | ✓ | Display cache size in status bar |
| Check Interval | 120s | How often to check cache size (30-600s) |
| Warning Threshold | 500 MB | Status bar color warning when exceeded |
| Hide Empty Folders | ✗ | Hide empty folders in Brain and Code Tracker trees |
| Auto Clean | ✗ | Automatically clean cache when exceeded |
| Auto Clean Keep Count | 5 | Number of newest tasks to keep during auto-clean (1-50) |

### Commit Message Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Endpoint | http://localhost... | API URL (Ollama, Anthropic, OpenAI compatible) |
| Model | llama3.2 | Model name (e.g. llama3.2, claude-3-haiku) |
| Max Diff Size | 80000 | Max characters of diff to send to LLM |
| Format | conventional | Message format (conventional or simple) |

## Privacy & Safety

Toolkit for Antigravity does not collect, transmit, or store any user data. All operations are performed locally on your machine. The extension only communicates with local components — nothing is sent to external servers.

## Platform Support

- Windows, macOS, Linux
- 13 languages: English, 简体中文, 繁體中文, 日本語, Français, Deutsch, Español, Português (Brasil), Italiano, 한국어, Русский, Polski, Türkçe

## Notable Contributors

- @restinnotes - CDP Auto-Accept implementation
- @simbaTmotsi - Local LLM Commit Message Generator
- @AMDphreak - Gemini Flash/Pro grouping, quota reset alignment
- @chonkydonkers - User tier credits display
- @vincenzofabiano92 - Connection stability, Italian localization, test runner

## License

Apache License, Version 2.0

## Links

- GitHub: https://github.com/n2ns/antigravity-panel
