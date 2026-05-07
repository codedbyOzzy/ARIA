# 🧠 F.R.I.D.A.Y.

> Personal Desktop AI System — Windows-native, privacy-first

**Status:** Active Development · **Platform:** Windows 11 · **License:** Apache 2.0

---

F.R.I.D.A.Y. (Female Replacement Intelligent Digital Assistant Youth) is a personal AI assistant inspired by JARVIS. It runs entirely on your machine — no cloud dependency, your data stays private.

---

## Features

- **Persistent Memory** — 5-category learning system that evolves with you
- **Desktop Control** — App launch, file ops, screenshots, system stats
- **Voice Interaction** — Local STT/TTS with optional cloud fallback
- **Telegram Remote Access** — Control your PC from anywhere
- **Adaptive Learning** — Four "stone" systems (Mind, Echo, Bond, Intuition)
- **Multi-Model Routing** — GPT-4.1-mini, o4-mini, Gemini, Ollama

---

## Architecture

```
app_new.py (Qt UI)
       │
       ├── SafeBrainRouter
       │       ├── LocalLLM (Ollama)
       │       └── Brain (OpenAI/Gemini)
       │
       └── Voice Backend
               ├── LiveAudio (cloud TTS/STT)
               └── LocalVoice (offline pipeline)

       └── 50+ Tools
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| UI | PySide6 + QML |
| Primary LLM | GPT-4.1-mini / o4-mini |
| Local LLM | Ollama (qwen2.5) |
| Vision | Gemini Vision |
| STT | faster-whisper |
| TTS | edge-tts (Neural) |
| Memory | TF-IDF + embeddings |
| Desktop | pyautogui + Win32 |

---

## Roadmap

| Phase | Status |
|-------|--------|
| Core architecture | ✅ Done |
| Memory system | ✅ Done |
| Voice interaction | ✅ Done |
| Desktop control | ✅ Done |
| Telegram integration | ✅ Done |
| Adaptive learning layers | ✅ Done |
| Skills/plugin system | 🔄 In progress |
| Test suite | 🔄 In progress |
| Public beta | 📋 Planned |

---

## Contact

- [GitHub](https://github.com/codedbyOzzy/ProjectFRIDAY)
- [Showcase](https://showcasefridayv2.netlify.app)

*"I am F.R.I.D.A.Y. How can I assist you today?"*