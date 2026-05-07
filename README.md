# F.R.I.D.A.Y — Personal Desktop AI System

> Not just an assistant. A system that learns who you are.

Active development — not publicly released yet.

<p align="center">
  <img src="images/core-gold.png" width="800"/>
</p>

---

## Overview

F.R.I.D.A.Y. is a local-first desktop AI system built for Windows — designed to go beyond traditional assistants.

Instead of relying on a single model or API, it uses **multi-model orchestration** combined with **direct OS-level control** and **four adaptive intelligence layers** that learn how you communicate, whether you understood, who you are, and where the conversation is going.

---

## Key Features

- **Real-time voice interaction** — Google STT + faster-whisper offline fallback + Neural TTS
- **Multi-model routing** — GPT-4.1-mini · o4-mini · Gemini 2.5 · Ollama
- **50+ integrated tools** — desktop control, web research, memory, Steam, browser automation, and more
- **Persistent memory** — 5-category semantic memory that evolves with you across sessions
- **Streaming TTS** — speech starts on the first sentence, not after the full response
- **Proactive system** — monitors RAM, CPU, battery; fires morning briefings; suggests automating routines
- **Self-learning** — learns from successful commands, builds routine patterns, adapts over time
- **4-Stone Adaptive Intelligence** — four modules that learn your style, comprehension, world, and intent
- **Local fallback** — Ollama keeps it running offline, for free

---

## How It Works

F.R.I.D.A.Y. dynamically decides how to handle each request before processing begins:

```
Simple command / chat    →  GPT-4.1-mini   (fast, cost-efficient)
Complex reasoning        →  o4-mini        (deep thinking, strategy, debug)
Offline / free queries   →  Ollama local   (zero cost, zero internet)
OpenAI unavailable       →  Gemini 2.5     (silent automatic fallback)
```

No manual switching. No interruptions.

---

## 4-Stone Adaptive Intelligence

The part that makes F.R.I.D.A.Y. different from a wrapper around GPT-4.

```
  Mind Stone     learns how you communicate — style, depth, pace
                 → adjusts tone and format to match you specifically

  Echo Stone     detects whether its explanations actually landed
                 → recognises false confirmations, rephrase loops, overload

  Bond Stone     builds a persistent model of your world across sessions
                 → your projects, stack, constraints — no re-explaining required

  Intuition Stone  learns where conversations go
                   → prepares answers before you finish asking
```

Together, they form a self-correcting communication layer that accumulates understanding with every conversation.

These four modules are open-source, zero-dependency, and available as standalone drop-ins:  
→ **[Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones)**

---

## Interface

<p align="center">
  <img src="images/core-yellow.png" width="800"/>
</p>

Instead of a traditional chat interface, F.R.I.D.A.Y. uses a **reactive system UI** built in Qt 6 / QML:

- A central AI core that visually responds to state changes
- Wave-based feedback for listening, thinking, and speaking
- Real-time conversation history
- Always-on system awareness

The goal is an interface that feels alive, not like a browser tab.

---

## Architecture

<p align="center">
  <img src="images/core-orange.png" width="800"/>
</p>

```
  app_new.py — PySide6 + QML Iron Man HUD
       │
       ├── Voice Pipeline
       │       ├── STT: Google STT → faster-whisper (offline fallback)
       │       └── TTS: edge-tts tr-TR-AhmetNeural + pygame
       │
       └── SafeBrainRouter
               ├── Brain (GPT-4.1-mini / o4-mini / Gemini)
               └── LocalLLM (Ollama — offline)
                      │
                   50+ Tools
```

| Layer | Technology |
|-------|------------|
| UI | PySide6 + QML (Qt 6) |
| Voice Input | Google STT · faster-whisper (offline fallback) |
| Primary LLM | OpenAI GPT-4.1-mini |
| Reasoning LLM | OpenAI o4-mini |
| Local LLM | Ollama (qwen2.5:7b) |
| Fallback LLM | Google Gemini 2.5 Flash |
| Vision | Gemini Vision (screen analysis) |
| Voice Output | edge-tts tr-TR-AhmetNeural + pygame |
| Memory | TF-IDF + semantic embeddings · JSON store |
| Desktop Control | Win32 API · pyautogui |
| Adaptive Intelligence | [Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones) |

---

## Example Commands

```
"Open Spotify"                          → app launches instantly
"Minimize Chrome"                       → Win32 SW_MINIMIZE, <1ms
"Set volume to 60%"                     → system audio adjusted
"What's on my screen?"                  → screenshot → Gemini vision analysis
"Who is Nikola Tesla?"                  → search + full article read
"Fix the email I just copied"           → clipboard → GPT → back to clipboard
"Remind me about the meeting in 30 min" → fires at exact time, spoken aloud
"Why is this code throwing a KeyError?" → o4-mini reasoning mode
"Launch CS2"                            → Steam integration, direct launch
"Search YouTube for lo-fi beats"        → Playwright browser automation
"Note this down"                        → timestamped desktop note file
```

---

## Proactive System

F.R.I.D.A.Y. doesn't only respond — it watches.

| Trigger | Action |
|---------|--------|
| RAM / CPU above threshold | Windows notification + voice alert |
| Battery low | Voice warning |
| Morning time | News + weather + agenda summary |
| Reminder fires | Windows notification + voice |
| Repeated routine (3+ days) | Suggests automating it |

---

## Showcase

**[showcasefridayv2.netlify.app](https://showcasefridayv2.netlify.app)**

---

## Status

Currently in active development.  
Public release, documentation, and setup guide coming when it's ready.

---

## Vision

F.R.I.D.A.Y. is an attempt to build a **persistent AI layer on top of the desktop** —  
a system that evolves with the user instead of acting as a stateless tool.

Every session, it knows more. Every command, it responds faster. Every conversation, it remembers.

---

*"I am F.R.I.D.A.Y. How can I assist you today?"*

**by Ozzy**
