<div align="center">

<img src="images/core-gold.png" width="180"/>

# FRIDAY Synapse

### The AI layer your desktop deserves.

*Not a chatbot. Not a wrapper. A persistent intelligence that lives on your machine.*

<br/>

![Status](https://img.shields.io/badge/Status-Early%20Access%20Soon-gold?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%2011-0078D4?style=for-the-badge&logo=windows)
![AI](https://img.shields.io/badge/AI-Multi--Model%20Orchestration-8A2BE2?style=for-the-badge)

<br/>

</div>

---

## What is FRIDAY Synapse?

FRIDAY Synapse is a **Windows-native AI desktop system** — not a browser extension, not a SaaS dashboard, not a simple chatbot interface.

It runs on your machine. It controls your desktop. It remembers everything about you. And every session, it knows you a little better.

Built around a **cognitive architecture** called the Intelligence Stone System — seven specialized modules that work in parallel to understand, remember, decide, and act — FRIDAY Synapse is the closest thing to a real Iron Man-style AI assistant that currently exists on a consumer desktop.

<br/>

<div align="center">
<img src="images/core-yellow.png" width="760"/>
</div>

<br/>

---

## Core Pillars

### 🧠 Multi-Model Intelligence Routing

FRIDAY Synapse doesn't use a single AI model — it uses the right one for each task, automatically.

| Request Type | Model Used | Why |
|---|---|---|
| Quick question / action | GPT-4.1-mini | Speed, cost-efficiency |
| Complex reasoning / debugging | o4-mini | Deep thinking, step-by-step logic |
| Offline / privacy mode | Ollama (local) | Zero internet, zero cost |
| Primary API unavailable | Gemini 2.5 Flash | Silent automatic fallback |

No manual switching. No interruptions. You talk — it routes.

---

### 🎙️ Real Voice Interaction

Not simulated. Not push-to-talk. Actual continuous listening with human-like response flow.

- **VAD-based wake detection** — speaks when you speak, stops when you stop
- **Dual STT pipeline** — Groq Whisper (cloud, fast) → faster-whisper (offline fallback)
- **Streaming Neural TTS** — speech starts on the *first sentence*, not after the full response
- **Barge-in support** — interrupt mid-sentence, it adjusts immediately
- **Echo suppression** — doesn't hear its own voice as new input

---

### 💾 Persistent Semantic Memory

Every conversation builds the relationship. FRIDAY Synapse doesn't forget.

- 5-category memory store: `preferences · facts · events · goals · context`
- Semantic retrieval — finds relevant memories even when phrasing differs
- Auto-extraction — learns from conversation without explicit "remember this"
- Cross-session continuity — picks up exactly where you left off
- Importance scoring — prioritizes what matters, quietly fades what doesn't

---

### 🖥️ Deep Desktop Integration

Full OS-level control. Not web scraping, not browser tricks — actual Windows API calls.

```
"Open Spotify"                    →  app launches instantly
"Minimize Chrome"                 →  Win32 SW_MINIMIZE, <1ms
"Set volume to 60%"               →  system audio adjusted
"What's on my screen?"            →  screenshot → Gemini Vision analysis
"Fix the email I just copied"     →  clipboard → LLM → back to clipboard
"Remind me in 30 minutes"         →  fires at exact time, spoken aloud
"Why is this code crashing?"      →  o4-mini reasoning, full context
"Launch CS2"                      →  Steam integration, direct launch
"Search YouTube for lo-fi beats"  →  Playwright browser automation
```

50+ integrated tools. All callable by voice or text.

---

## The Intelligence Stone System

The core of what makes FRIDAY Synapse different.

Most AI assistants are stateless. You explain yourself every session. They answer, you move on. Nothing accumulates.

FRIDAY Synapse runs **seven specialized cognitive modules** in parallel — called Intelligence Stones — each responsible for a specific layer of understanding.

<br/>

<div align="center">
<img src="images/core-orange.png" width="760"/>
</div>

<br/>

```
  EchoStone      Detects comprehension failures and rephrase loops.
                 Recognizes when explanations didn't land — before you repeat yourself.

  VoiceStone     Manages the full audio pipeline — VAD, STT, TTS, barge-in.
                 The ears and voice of the system.

  VisionStone    Screenshot capture, screen analysis, OCR.
                 Sees what you see when you need a second pair of eyes.

  ActionStone    Win32 API, PyAutoGUI, file system, process control.
                 The hands — executes physical commands on your machine.

  WebStone       Web search, full article reading, live data retrieval.
                 Not snippets — actual content from the source.

  LogicStone     The orchestrator. Routes each request to the right model,
                 manages tool calling, parallel execution, and synthesis.

  MindStone      Adaptive style engine. Tracks your communication patterns —
                 tone, depth, pace — and adjusts responses to match you specifically.
```

These aren't features layered on top of a chatbot. They're parallel processes running a cognitive loop — each one informing the others.

---

## Proactive System

FRIDAY Synapse doesn't wait to be asked.

| Trigger | Response |
|---|---|
| App launch | Startup briefing: time, active reminders, system status |
| RAM / CPU spike | Voice alert with context |
| Battery low | Immediate spoken warning |
| Extended silence | Surfaces relevant memory or pending thought |
| Repeated daily routine | Suggests automating it |
| Reminder fires | Voice notification at exact scheduled time |

---

## Interface

Qt 6 / QML native Windows application. Not a browser tab.

- **Animated AI core** — reactive orb that reflects system state (listening / thinking / speaking)
- **Waveform feedback** — visual audio response during voice interaction
- **Live conversation log** — full session history, always visible
- **Status layer** — real-time system awareness (model in use, tool being called, latency)
- **Drag & drop** — drop a file onto the window to analyze it instantly

The goal was an interface that *feels* alive. Not a chat window — a control surface.

---

## Architecture Overview

```
  FRIDAY Synapse
         │
         ├── BrainCore (Event Bus)
         │       ├── EchoStone    ← Memory + behavior analysis
         │       ├── VoiceStone   ← STT / TTS / VAD pipeline
         │       ├── VisionStone  ← Screen capture + Vision API
         │       ├── ActionStone  ← OS control (Win32, PyAutoGUI)
         │       ├── WebStone     ← Search + full web reading
         │       ├── LogicStone   ← LLM routing + tool orchestration
         │       └── MindStone    ← Adaptive communication style
         │
         └── ProactiveEngine     ← Background monitoring + briefings
```

All stones communicate through a **typed event bus** — zero direct coupling. Each stone subscribes only to the events it needs. Adding new capabilities means adding a new stone.

Full architecture details → [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | PySide6 + QML (Qt 6) — native Windows |
| Voice Input | Groq Whisper · faster-whisper (offline fallback) |
| Voice Activity | webrtcvad — frame-level VAD |
| Primary LLM | OpenAI GPT-4.1-mini |
| Reasoning LLM | OpenAI o4-mini |
| Local LLM | Ollama — qwen2.5 family |
| Fallback LLM | Google Gemini 2.5 Flash |
| Vision | Gemini Vision — screenshot analysis |
| Voice Output | edge-tts Neural TTS + pygame streaming |
| Memory | TF-IDF + OpenAI embeddings · JSON store |
| Desktop Control | Win32 API · pyautogui · PowerShell |
| Browser Automation | Playwright |

---

## Language Support

FRIDAY Synapse is currently **Turkish-optimized** — the voice pipeline, persona, and response quality are tuned specifically for Turkish.

**English support is in active development** as part of the commercial release. The model stack (Whisper, GPT-4.1, Gemini) handles English natively — the remaining work is persona localization, TTS voice selection, and UI strings.

Target languages at launch: **Turkish · English**

---

## Status

| Component | State |
|---|---|
| Core architecture (Stone System) | ✅ Complete |
| Intelligence Stone system | ✅ Complete |
| Voice pipeline (TR) | ✅ Complete |
| Memory system | ✅ Complete |
| Desktop tools (50+) | ✅ Complete |
| Proactive engine | ✅ Complete |
| Multi-model routing | ✅ Complete |
| English language support | 🔄 In progress |
| First-run setup wizard | 🔄 In progress |
| Public release packaging | 📋 Planned |

---

## Availability

FRIDAY Synapse is **not publicly released yet.**

An **early access version** is coming. Follow this repository to stay updated.

<div align="center">

**[→ Visit the Showcase](https://showcasefridayv2.netlify.app)**

</div>

---

## Open-Source Layer

The **Intelligence Stone interfaces** — the cognitive architecture that powers this system — are available as a standalone open-source library:

**[→ codedbyOzzy/Intelligence-Stones](https://github.com/codedbyOzzy/Intelligence-Stones)**

Zero dependencies. Drop-in ready. Use them in your own projects.

---

<div align="center">

*Every session, it knows more.*  
*Every command, it responds faster.*  
*Every conversation, it remembers.*

<br/>

**Built by [Ozzy](https://github.com/codedbyOzzy)**

</div>
