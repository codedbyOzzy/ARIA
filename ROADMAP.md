# FRIDAY Synapse — Roadmap

What's done, what's in progress, and where this is going.

---

## What's Working Now

### Voice
- Continuous microphone listening with webrtcvad (frame-level VAD)
- Dual STT: Groq Whisper (cloud) → faster-whisper (offline fallback)
- Barge-in interruption — speak while FRIDAY is speaking, it stops and listens
- Echo suppression — doesn't pick up its own TTS output as input
- Streaming Neural TTS (edge-tts) — speech starts on sentence 1, not after full response
- Offline TTS fallback (pyttsx3)

### Intelligence & Routing
- Per-query LLM routing: GPT-4.1-mini / o4-mini / Ollama / Gemini 2.5
- Parallel tool execution (ThreadPoolExecutor — multiple tools, one round-trip)
- Intent-based routing — detects reasoning tasks, sends to o4-mini automatically
- Circuit breaker — protects local model from cascading failures
- Streaming LLM responses with real-time TTS handoff

### Memory
- 5-category persistent store: preference, fact, event, goal, context
- Importance scoring + time-decay
- Semantic retrieval: TF-IDF (offline) or OpenAI embeddings (when available)
- Auto-extraction — memories pulled from conversation without explicit commands
- Duplicate detection with configurable similarity threshold
- Automatic JSON backup on every write

### Desktop Tools (50+)
- Application launch (Start Menu discovery + cache)
- Window control: minimize, maximize, close, focus (Win32 API, <1ms)
- Volume, display, system stats
- Screenshot + Gemini Vision analysis
- Clipboard: read, write, process (summarize, translate, fix, explain)
- File system: create, read, write, delete, search content
- Code execution: run Python inline or from file
- Browser automation: Playwright (search, navigate, fill forms)
- Steam integration: game launch, library search
- Web: search, full article read, weather, news (Turkish + world)

### Adaptive Intelligence (MindStone)
- Communication style profiling (length, depth, tone, humor)
- Per-session style directive injection into LLM prompts
- Gradual adaptation — doesn't reset between sessions

### Proactive Engine
- Startup briefing: time + active reminders + system status (RAM, battery)
- Reminder fire notifications (voice + exact scheduling)
- Idle-mode thought surfacing (pending memories and notes)
- RAM/CPU/battery threshold alerts

### UI
- Qt 6 / QML native Windows app
- Animated reactive orb (idle / listening / thinking / speaking states)
- Voice waveform visualization
- Real-time conversation log
- Status overlay (current model, active tool, latency)
- Drag & drop file analysis

### Language Support
- Full English support — persona, TTS voice, STT, system prompts, UI strings
- Full Turkish support — voice pipeline tuned specifically for Turkish
- `FRIDAY_LANGUAGE=en` or `tr` in `.env` — switch at any time

### Setup & Distribution
- `setup.bat` one-click installer — checks Python, installs dependencies, validates API keys
- `.env.example` template with full documentation in English
- First-run setup wizard (SetupWizard.qml) — language, API key entry, voice test
- BYOK model — users bring their own API keys, zero subscription

### Telegram Remote Access
- Full Telegram bot integration — control your PC from anywhere
- Send commands via Telegram message, receive responses and screenshots
- Works on any device with Telegram installed

---

## In Progress

### Release Packaging
- Single-file Windows `.exe` installer (no Python required)
- Auto-update mechanism
- License key activation flow

---

## Planned

### Short-Term (Post-Beta)
- Session conversation export
- Memory review and edit UI
- Voice speed and volume controls
- Per-app window behavior profiles (e.g. always minimize on certain apps)

### Medium-Term
- Scheduled task system (run X every day at Y)
- Plugin / skill system (user-installable capability packs)
- Offline-first mode improvements

### Long-Term
- Multi-language support beyond TR/EN
- Cross-device memory sync
- Custom TTS voice training
- Autonomous multi-step task execution (planner + executor loop)
- Mobile companion app

---

## What This Is Not

FRIDAY Synapse is not a general-purpose cloud AI service. It is not trying to be ChatGPT with a desktop app wrapper.

The goal is a **persistent, private, deeply integrated** AI system that gets better the longer you use it — something that knows your machine, your habits, and your preferences in a way that no stateless chatbot ever can.

The architecture is designed around that goal. The memory system, the adaptive stones, the proactive engine — all of it exists to make the system more *yours* over time.

---

*Last updated: May 9, 2026*
