# JarvisBrain_v2 — Friday Integration

This folder now includes the same core structure as `friday-tony-stark-demo`:

- `server.py` → FastMCP SSE server
- `agent_friday.py` → LiveKit voice worker
- `friday/` package → tools, prompts, resources, config

## Run

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Start MCP server:

```powershell
python server.py
```

3. Start voice worker (new terminal):

```powershell
python agent_friday.py dev
```

## Windows "ethanplus-style" mode (no API key)

If you want a flow closer to `ethanplusai/jarvis` but on Windows and without Claude/Fish keys:

```powershell
.\Use-Ethanplus-Mode.ps1
```

This sets a no-key preset in `.env`:
- `STT_PROVIDER=faster_whisper`
- `LLM_PROVIDER=ollama`
- `TTS_PROVIDER=edge`
- `FRIDAY_PROFILE=ethanplus`

Then start normally:

```powershell
.\Run-JarvisBrain_v2.bat
```

## One-command launch (recommended)

```powershell
.\start.ps1
```

If you want stale port/process cleanup before launch:

```powershell
.\start.ps1 -Fresh
```

Desktop app mode (recommended): simply double-click:

```text
Run-JarvisBrain_v2.bat
```

This opens a stylish desktop interface (animated orb) where you can:
- Start/stop FRIDAY stack
- See live status (policy/ollama/profile)
- Open Control Panel or LiveKit from UI buttons
- Use "Start Direct Listen" to run microphone commands directly from the UI (without LiveKit)

Legacy headless mode:

```text
Run-Headless.bat
```

Stop both services:

```powershell
.\stop.ps1
```

Control panel UI:

- [http://127.0.0.1:8030](http://127.0.0.1:8030)

## Notes

- MCP endpoint: `http://127.0.0.1:8010/sse`
- LiveKit credentials are loaded from `.env`
- Provider switches are controlled by:
  - `STT_PROVIDER`
  - `LLM_PROVIDER`
  - `TTS_PROVIDER`
  - `FRIDAY_PROFILE` (`friday` | `ethanplus`)
  - `LLM_PROVIDER=ollama` for local-first mode
  - `OLLAMA_MODEL` and `OLLAMA_BASE_URL` for local model routing
  - `OLLAMA_CODER_MODEL` for coding/debug tasks

## Desktop control capability (current)

Current MCP tools can:
- open websites (`open_website`)
- open common apps (`open_application`)
- close apps (`close_application`)
- list running processes (`list_processes`)
- list/focus desktop windows (`list_windows`, `focus_window`)
- keyboard and mouse control (`type_text`, `press_hotkey`, `click_screen`)
- take screenshots (`capture_screenshot`)
- close focused window (`close_focused_window`)
- UI template automation (`locate_image_on_screen`, `wait_for_image_on_screen`, `click_image_on_screen`)
- safety policy (`policy_status`, `arm_desktop_control`, `disarm_desktop_control`)
- persistent memory (`remember_preference`, `get_preference`, `remember_note`, `recall_notes`)
- multi-step executor (`execute_desktop_workflow`, `recent_workflow_history`)
- Ollama watchdog (`ollama_status`, `ollama_recover`)

This means the agent can perform basic desktop actions now, and we can extend to advanced controls incrementally.

## Safety behavior

High-risk desktop-changing actions are blocked by default.
You need to arm controls first, then pass the returned `confirm_token` to sensitive tools.

Voice-friendly mode:
- Low-risk actions (open/close app, focus/list windows/processes) are allowed directly for smoother voice usage.
- High-risk actions (typing, clicks, hotkeys, screenshots) still require challenge/token.

Direct Listen mode (UI local microphone):
- "Notepad ac", "Notepad kapat"
- "YouTube ac", "Chrome ac"
- "Acik pencereleri listele"
- "Saat kac", "Dunyada ne oluyor"

Blackbox diagnostics:
- Runtime events/errors are written to `.friday_blackbox.jsonl`
- UI includes "Refresh Blackbox" to inspect latest 20 events
