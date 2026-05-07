# F.R.I.D.A.Y. — System Architecture

A high-level overview of how the system is structured. Implementation details are intentionally omitted.

---

## Layer Overview

```
┌──────────────────────────────────────────────────────────┐
│                  Desktop UI (Qt 6 / QML)                 │
│   Animated orb · Chat log · Status · Mic controls        │
└───────────────────────────┬──────────────────────────────┘
                            │ user input (voice or text)
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    Voice Pipeline                         │
│                                                          │
│   STT: Google STT (internet) -> faster-whisper (offline) │
│   TTS: edge-tts tr-TR-AhmetNeural + pygame               │
│   Barge-in: RMS monitor during playback                  │
└───────────────────────────┬──────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    SafeBrainRouter                        │
│                                                          │
│   Fast / conversational  ->  GPT-4.1-mini               │
│   Deep reasoning         ->  o4-mini                    │
│   Offline / free         ->  Ollama (qwen2.5)           │
│   Cloud unavailable      ->  Gemini 2.5 Flash           │
└───────────┬───────────────────────────┬──────────────────┘
            │                           │
            ▼                           ▼
┌──────────────────┐         ┌────────────────────────┐
│   50+ Tools      │         │   Memory System        │
│   parallel exec  │         │   5-category store     │
│   per-tool       │         │   semantic retrieval   │
│   timeout guard  │         │   auto-extraction      │
└──────────────────┘         └────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────┐
│              4-Stone Adaptive Intelligence                │
│                                                          │
│  Mind Stone      learns how you communicate              │
│  Echo Stone      detects whether it worked               │
│  Bond Stone      builds a model of your world            │
│  Intuition Stone predicts where the conversation goes    │
└──────────────────────────────────────────────────────────┘
```

---

## Desktop UI

Built with Qt 6 / QML. Runs as a native Windows application — no browser, no web runtime.

The visual centerpiece is a Canvas-rendered animated orb: a living, organic shape that breathes slowly at rest, reacts to incoming audio levels, and pulses with expanding radiate rings when speaking. All animation runs at 60 fps.

Conversation history is displayed in a scrollable log alongside the orb. The UI communicates with the backend entirely through Qt signals — no polling, no shared state. Typed and voice commands share the same processing pipeline.

---

## Voice Layer

**Speech-to-Text:** Microphone input is processed by a voice activity detection loop. When a complete utterance is captured, it is sent for transcription in priority order:

1. **Google STT** (SpeechRecognition, cloud) — fast, accurate for Turkish
2. **faster-whisper** (local, CPU) — offline fallback when internet is unavailable

Hallucination filtering runs on all results.

**Barge-in:** A background thread monitors the microphone during TTS playback. If the RMS exceeds a threshold, playback stops immediately and the new utterance is processed.

**Text-to-Speech:** Responses synthesized with Microsoft edge-tts (`tr-TR-AhmetNeural`, Neural Turkish voice). Playback uses pygame with a producer-consumer architecture: as the LLM streams sentence N, the producer is already synthesizing sentence N+1. First audio typically plays within 1-2 seconds of the model starting to respond.

---

## LLM Router

The router classifies each query before routing:

| Path | Used when | Model |
|------|-----------|-------|
| Local | Short, conversational, offline queries | Ollama qwen2.5 |
| Fast cloud | General queries, tool use, research | GPT-4.1-mini |
| Reasoning | Complex problems, debugging, strategy | o4-mini |
| Fallback | OpenAI unavailable | Gemini 2.5 Flash |

A circuit breaker monitors the local model. If it degrades, the router falls back to cloud automatically and silently.

---

## Memory System

A file-backed persistent store. Every entry has:

- `content` — the fact in plain text
- `category` — one of: `preference`, `fact`, `context`, `skill`, `relationship`
- `importance` — 0-1 score used to prioritize retrieval
- `tags` — optional labels for fast filtering
- `created_at` — timestamp

**Auto-extraction** runs in a background thread after each conversation turn. A lightweight model analyzes the exchange and identifies new personal facts. Results are deduplicated before writing. A backup is created before every save.

**Retrieval** is semantic: TF-IDF with embedding-based backfill. The most relevant memories surface automatically into the model's context window before each response. The model can also trigger explicit `remember`, `recall`, and `forget` calls mid-conversation.

---

## Tool System

Tools are Python functions registered with the LLM. The model decides when to call them.

Execution is parallel: if the model calls multiple tools in one turn, they run concurrently. Each tool has a per-call timeout — a hanging tool does not block the conversation.

| Category | Tools |
|----------|-------|
| Desktop | open/close/minimize/maximize/focus apps and windows |
| Vision | screenshot + Gemini vision analysis, AI-guided click |
| Input | type text, press key combos, mouse click, scroll |
| System | CPU/RAM/disk/battery stats, process management, clipboard |
| Power | volume, media controls, lock, sleep, shutdown |
| Files | read, write, create, rename, move, copy, delete |
| Web | search, read page, Turkish news, world news, weather |
| Browser | YouTube search/play, Google search (Playwright) |
| Memory | remember, recall, forget, memory stats |
| Reminders | set, list, cancel — fires as voice announcement |
| Notes | timestamped desktop note file |
| Steam | open library, list installed games, launch by name |
| Code | run Python code, run Python file |
| Proactive | background RAM/CPU/battery monitor with voice alerts |

---

## 4-Stone Adaptive Intelligence

Four lightweight modules injected into the system prompt, each adding one layer of genuine understanding.

```
Mind Stone      observes every turn -> builds a communication style profile
                -> directive: "Keep it short. Lead with code."

Echo Stone      measures reaction to each response
                -> detects: false confirmation, rephrase, overload, deepening
                -> directive: "This user often confirms without understanding.
                               Check comprehension before moving on."

Bond Stone      extracts who the user is across all sessions
                -> tracks: stack, projects, constraints, preferences
                -> directive: "Stack: Python, CUDA, Ollama.
                               Project: Vision. No cuBLAS installed."

Intuition Stone learns which topics consistently follow which others
                -> predicts follow-up questions before they are asked
                -> directive: "CUDA questions are often followed by memory
                               questions. Consider addressing it proactively."
```

All four stones are zero-dependency Python modules available as open-source:
[Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones)

---

## Proactive Engine

A background engine that runs while the assistant is active:

| Trigger | Action |
|---------|--------|
| Session start | Greeting + current time + system state (direct TTS, no LLM call) |
| RAM/CPU above threshold | Windows notification + voice alert |
| Battery low | Voice warning |
| Reminder fires | Voice announcement at scheduled time |
| Routine detected (3+ days) | Suggests automating the pattern |

---

## What Is Not Described Here

The following are intentionally excluded from this public document:

- System prompt content and persona definition
- Routing thresholds and decision logic
- Memory extraction prompts
- Tool implementation code
- Authentication and API configuration
- Personal user data and memory contents
