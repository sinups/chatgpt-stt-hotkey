<div align="center">

# 🎙️ ChatGPT STT Hotkey

**Push-to-talk speech-to-text for macOS using ChatGPT**

Hold `Fn` → speak → release → paste with `⌘V`

[![macOS](https://img.shields.io/badge/macOS-13%2B-black?logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![ChatGPT](https://img.shields.io/badge/ChatGPT-Plus-74aa9c?logo=openai&logoColor=white)](https://openai.com/chatgpt/mac/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

**No API keys. No tokens. No costs.**
Uses your existing ChatGPT Plus subscription through the desktop app widget.

</div>

## ✨ How it works

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐
│  Hold Fn │ ──▶ │  Widget opens │ ──▶ │  Speak   │ ──▶ │ Release  │
│          │     │  🎙️ Recording │     │  ...     │     │  Fn      │
└──────────┘     └──────────────┘     └──────────┘     └────┬─────┘
                                                            │
                                                            ▼
                                                   ┌──────────────┐
                                                   │ 📋 Clipboard  │
                                                   │    ⌘V paste   │
                                                   └──────────────┘
```

1. **Hold `Fn`** — ChatGPT compact widget opens, recording starts automatically
2. **Speak** — you see the recording indicator in the widget
3. **Release `Fn`** — recording stops, ChatGPT transcribes your speech
4. **`⌘V`** — transcribed text is in your clipboard, paste anywhere

The widget acts as a visual indicator during recording and closes automatically when done.

## 🚀 Installation

One command:

```bash
curl -fsSL https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main/install.sh | bash
```

The installer will:
- ✅ Check for macOS, ChatGPT app, Python, Homebrew
- ✅ Install `cliclick` (for UI automation)
- ✅ Download and set up the scripts
- ✅ Configure a `launchd` service (auto-starts with your Mac)
- ✅ Guide you through Accessibility permissions (one-time setup)
- ✅ Add handy shell aliases

### Requirements

| Requirement | Details |
|:--|:--|
| **macOS** | 13 Ventura or later |
| **ChatGPT** | [Desktop app](https://openai.com/chatgpt/mac/) with Plus subscription |
| **Homebrew** | [brew.sh](https://brew.sh) |
| **Python 3** | With `pyobjc` (`pip3 install pyobjc-framework-Quartz pyobjc-framework-Cocoa`) |

### Accessibility Permission

The installer will prompt you to add `Python.app` to **System Settings → Privacy & Security → Accessibility**. This is required for the script to:
- Listen for the `Fn` key globally
- Send keyboard shortcuts to open/close the ChatGPT widget
- Click UI elements in the widget

## 🛠️ Management

```bash
stt-status    # Service status + recent log
stt-restart   # Restart the service
stt-stop      # Stop the service
stt-log       # View full log
stt-update    # Pull latest version & restart
```

The service checks for updates every 6 hours and shows a macOS notification when a new version is available.

## 🗑️ Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.chatgpt-stt.plist
rm ~/Library/LaunchAgents/com.chatgpt-stt.plist
rm -rf ~/Projects/chatgpt-stt-hotkey
```

Then remove the `# ChatGPT STT` aliases from your `~/.zshrc`.

## 🔧 How it works under the hood

| Component | Purpose |
|:--|:--|
| `CGEventTap` | Captures `Fn` key press/release globally |
| `CGEvent` | Sends `⌥Space` to open widget (bypasses held Fn modifier) |
| `cliclick` | Clicks the microphone and stop buttons by screen coordinates |
| Accessibility API (JXA) | Finds button positions dynamically, reads transcribed text |
| `launchd` | Runs as a background service, auto-restarts, monitors ChatGPT process |

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  chatgpt-stt-service.sh                             │
│  └── Waits for ChatGPT process, launches/restarts   │
│      └── chatgpt_stt.py                             │
│          ├── CGEventTap (listen for Fn)              │
│          ├── CGEvent (send ⌥Space / Esc)             │
│          ├── JXA/osascript (find UI elements)        │
│          └── cliclick (click buttons)                │
└─────────────────────────────────────────────────────┘
```

## 🤔 Why?

ChatGPT Plus includes excellent speech-to-text via the desktop app, but using it requires:
1. Press shortcut to open widget
2. Click the microphone button
3. Speak
4. Click stop
5. Select text
6. Copy
7. Switch back to your app
8. Paste

This tool reduces it to: **hold Fn → speak → release → paste**.

## ⚠️ Limitations

- **macOS only** — uses macOS-specific APIs (CGEvent, Accessibility, launchd)
- **ChatGPT Plus required** — the speech-to-text feature is part of ChatGPT Plus subscription
- **UI automation is fragile** — ChatGPT app updates may change button positions/structure
- **Fn key** — on some Mac keyboards, Fn triggers other system features (Globe key). The script filters out Fn+modifier combinations to avoid conflicts

## 📄 License

MIT — do whatever you want with it.

---

<div align="center">

Made with 🤖 by [sinups](https://github.com/sinups)

</div>
