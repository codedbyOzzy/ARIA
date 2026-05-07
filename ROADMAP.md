# F.R.I.D.A.Y. — Roadmap

Development status and direction. This reflects what is actually built.

---

## What Is Working Now

### Voice
- [x] Continuous microphone listening with voice activity detection
- [x] Google STT (SpeechRecognition, cloud) — primary, Turkish optimized
- [x] faster-whisper local STT (offline fallback, CPU)
- [x] Hallucination filtering (foreign characters, Whisper artifacts, repetition)
- [x] Barge-in: interrupt F.R.I.D.A.Y. mid-sentence by speaking
- [x] Echo suppression after TTS playback

### Text-to-Speech
- [x] Microsoft Neural TTS (edge-tts, tr-TR-AhmetNeural)
- [x] Producer-consumer streaming: sentence N+1 generates while sentence N plays
- [x] Barge-in stop signal propagated to playback
- [x] Offline pyttsx3 fallback

### LLM and Routing
- [x] Per-query routing between local and cloud models
- [x] Local path: Ollama qwen2.5, streaming, rolling conversation history
- [x] Cloud path: GPT-4.1-mini with streaming and tool calling
- [x] Reasoning path: o4-mini for complex queries
- [x] Gemini 2.5 Flash fallback when OpenAI is unavailable
- [x] Circuit breaker on local model (auto-fallback on degradation)
- [x] Intent parsing with a fast 3B model before routing

### Memory
- [x] 5-category persistent store: preference, fact, context, skill, relationship
- [x] Importance scoring (0.0-1.0) per entry
- [x] Semantic retrieval with TF-IDF + embedding backfill
- [x] Auto-extraction after each conversation turn (background, LLM-powered)
- [x] Duplicate detection before writing
- [x] Automatic backup before every save

### Tools
- [x] Parallel tool execution with per-tool timeout
- [x] Desktop: open/close/minimize/maximize/focus apps and windows
- [x] Vision: screenshot + Gemini analysis, AI-guided element click
- [x] System: CPU, RAM, disk, battery, process management
- [x] Clipboard: read, write, process contents
- [x] Files: read, write, create, rename, move, copy, delete
- [x] Web: search, read page, Turkish news, world news, weather
- [x] Browser automation: YouTube search/play, Google search (Playwright)
- [x] Memory tools: remember, recall, forget, stats
- [x] Reminders: set, list, cancel with voice announcement on fire
- [x] Quick notes: timestamped desktop note file
- [x] Steam: library, installed games list, launch by name
- [x] Code execution: run Python code and files inline
- [x] Proactive alerts: background RAM/CPU/battery watcher

### Adaptive Intelligence (4-Stone System)
- [x] Mind Stone — communication style learning (verbosity, depth, examples)
- [x] Echo Stone — comprehension pattern detection (false confirmation, overload)
- [x] Bond Stone — persistent user world model (stack, projects, constraints)
- [x] Intuition Stone — conversation arc prediction (follow-up topic modeling)

### UI
- [x] Qt 6 / QML native Windows application
- [x] Canvas-rendered animated orb (60 fps, breathing animation)
- [x] Voice-reactive orb (expands with audio level)
- [x] Speaking state: expanding radiate rings
- [x] Scrollable conversation log
- [x] Text input (typed messages bypass STT)
- [x] Status indicators (listening / thinking / speaking / error)

### Proactive Engine
- [x] Startup briefing: time + system status on every launch (direct TTS, no LLM)
- [x] System alerts: RAM and battery warnings via direct TTS
- [x] Reminder firing: scheduled voice announcements
- [x] Routine detection: learns patterns across sessions

---

## What Is Next

### Short-term
- [ ] Session conversation log (persist full history to disk across restarts)
- [ ] Memory review UI (browse, edit, delete memories from the interface)
- [ ] Voice speed control (real-time adjustment without restart)
- [ ] Plugin/skill system (drop-in tool modules without modifying core)

### Medium-term
- [ ] Telegram remote access (control the desktop from your phone)
- [ ] Offline-first mode (full functionality without internet)
- [ ] Scheduled tasks ("every morning at 8, tell me the weather and news")
- [ ] Conversation summary ("what did we talk about recently?")

### Long-term
- [ ] Multi-language support (while keeping Turkish as primary)
- [ ] Cross-device memory sync (encrypted)
- [ ] Custom TTS voice
- [ ] Autonomous multi-step task execution with confirmation gates

---

## Design Principles

- **Turkish-first** — every layer is optimized for Turkish before other languages
- **Local-capable** — core functionality works without cloud APIs; cloud enhances, not enables
- **Private by default** — personal memory, credentials, and behavioral data never leave the local machine
- **Fast first response** — the user hears F.R.I.D.A.Y. start talking within 1-2 seconds of finishing their sentence
- **Adaptive** — the system learns communication preferences, not just commands
