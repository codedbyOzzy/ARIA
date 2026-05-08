# FRIDAY Synapse — System Architecture

A high-level overview of how the system is structured. Implementation details are intentionally omitted.

---

## Philosophy

FRIDAY Synapse is not built as a monolithic app with a chatbot embedded inside it. It's designed as a **cognitive operating layer** — a set of specialized modules running in parallel, each owning a specific domain of intelligence, communicating through a shared event bus.

This architecture makes the system:
- **Composable** — new capabilities are new stones, not patches to existing code
- **Resilient** — one module failing doesn't cascade to others
- **Observable** — every event is typed, named, and traceable

---

## The BrainCore Event Bus

The central nervous system of FRIDAY Synapse.

```
BrainCore
    │
    ├── register_stone(stone)     ← adds a module to the system
    ├── dispatch(event)           ← broadcasts a typed event to all stones
    ├── initialize_all()          ← starts all stones in dependency order
    └── shutdown_all()            ← graceful teardown on app exit
```

Every stone subscribes to the events it cares about. No stone directly calls another. All communication passes through the bus.

Events are typed `StoneEvent` objects with:
- `name` — the event type (e.g. `USER_SPOKE`, `SPEAK_TEXT`, `FILE_DROPPED`)
- `source` — which stone or system originated it
- `payload` — structured data dictionary

---

## Intelligence Stones

### EchoStone
**Domain:** Memory, behavior analysis, conversation continuity

- Loads and manages the persistent memory store on startup
- Intercepts `USER_SPOKE` events to extract and store new memories
- Provides memory context retrieval for LogicStone before each LLM call
- Detects rephrase loops — when the user re-asks the same thing differently

---

### VoiceStone
**Domain:** Audio input/output pipeline

- Manages continuous microphone listening via webrtcvad (VAD)
- STT chain: Groq Whisper (primary) → faster-whisper (offline fallback)
- Dispatches `USER_SPOKE` events when speech is transcribed
- Handles TTS output via edge-tts Neural TTS + pygame streaming
- Implements barge-in: stops current speech if new input detected
- Echo suppression: ignores input while FRIDAY is speaking

```
Microphone → webrtcvad → speech buffer → Groq Whisper → USER_SPOKE event
SPEAK_TEXT event → edge-tts → pygame streaming playback
```

---

### VisionStone
**Domain:** Visual context — screen capture and image analysis

- Screenshot capture on demand
- Screen region selection
- Routes image data to Gemini Vision API for analysis
- Triggered via `LOOK_AT_SCREEN` or `FILE_DROPPED` events

---

### ActionStone
**Domain:** OS-level execution

- Win32 API calls: window minimize/maximize/close/focus
- PyAutoGUI: mouse movement, clicks, keyboard input
- PowerShell execution for system-level operations
- File system: create, read, write, delete, search
- Application launch via Start Menu discovery cache

---

### WebStone
**Domain:** Internet access and live data

Three-tier search system:
1. `search_web` — fast metadata + snippets (~280 chars per result)
2. `read_webpage` — full content extraction from a specific URL
3. `search_and_read` — search + reads the best result in full

Also handles:
- Weather (OpenWeatherMap)
- News (Turkish and world)
- Clipboard read/write

---

### LogicStone
**Domain:** Decision-making, LLM routing, tool orchestration

The orchestrator of FRIDAY Synapse. Every `USER_SPOKE` event flows here.

```
USER_SPOKE
    │
    ├── 1. Request memory context from EchoStone
    ├── 2. Route to appropriate LLM:
    │       ├── GPT-4.1-mini   (standard, tools enabled)
    │       ├── o4-mini        (complex reasoning, no tools)
    │       ├── Ollama local   (offline mode)
    │       └── Gemini 2.5     (fallback)
    ├── 3. Execute tool calls in parallel (ThreadPoolExecutor)
    ├── 4. Synthesize final response
    └── 5. Dispatch SPEAK_TEXT event
```

Tool results are processed in parallel — multi-tool responses have no sequential bottleneck.

---

### MindStone
**Domain:** Adaptive communication style

Observes each interaction and builds a behavioral profile:
- Response length preference (short vs. detailed)
- Tone preference (formal vs. casual)
- Technical depth expectation
- Reaction to humor

Injects a style directive into every LLM prompt, gradually shifting FRIDAY's communication toward the user's observed preferences.

---

## ProactiveEngine

Runs as a background daemon thread. Not part of the event bus — it *emits* events rather than consuming them.

```
On startup (after 6s delay):
  → build_startup_brief() — time + reminders + system status
  → dispatch SPEAK_TEXT

Every 30s:
  → Check idle time
  → If idle > 25 min and no recent warning:
      → Surface best unsurfaced memory/thought, or
      → Dispatch presence notification

Reminder callbacks:
  → Registered at startup
  → Fire SPEAK_TEXT at exact scheduled time
```

---

## Voice Threading Model

```
Main Thread          Audio Thread          Worker Thread
     │                    │                     │
  Qt UI loop          webrtcvad             LLM calls
  Event dispatch      Speech buffer         Tool execution
  QML rendering       STT pipeline          TTS generation
                      Barge-in detection
```

Audio capture and speech processing run on a dedicated daemon thread. LLM inference and tool execution run on a separate worker. The main thread handles only UI rendering and event dispatching.

TTS uses a **producer-consumer pipeline**:
- Producer: sentence splitter streams text chunks as LLM generates
- Consumer: pygame playback begins on first sentence
- Result: first word of speech plays 1-2 seconds after generation begins, not after full response

---

## Memory System

```
MemoryStore
    │
    ├── Categories: PREFERENCE · FACT · EVENT · GOAL · CONTEXT
    ├── Retrieval:  TF-IDF (primary) → OpenAI embeddings (if key available)
    ├── Storage:    JSON file, auto-backup on each write
    ├── Dedup:      cosine similarity threshold (configurable)
    └── Decay:      importance scores decay over time, critical memories persist
```

Memories are extracted automatically during conversation by the EchoStone's LLM-based extraction pipeline. No manual tagging required.

---

## Routing Logic

```
Is it a simple conversational reply?
  └── GPT-4.1-mini (streaming, tools enabled)

Does it require deep reasoning, code analysis, or multi-step planning?
  └── o4-mini (no streaming, thinking mode)

Is offline mode active or API quota exceeded?
  └── Ollama local (qwen2.5:7b or qwen2.5:3b for intent)

Did OpenAI fail 3+ consecutive times?
  └── Gemini 2.5 Flash (automatic, silent)
```

Circuit breaker prevents cascading failures to local model. Failure counters reset on successful calls.

---

## Key Design Decisions

**No direct stone-to-stone calls.** Everything through the event bus. This makes the system debuggable — every interaction is a named, logged event.

**Parallel tool execution.** Multiple tool calls from a single LLM response run concurrently via `ThreadPoolExecutor`. Latency scales with the slowest tool, not the sum.

**Streaming TTS from sentence 1.** The response pipeline splits on sentence boundaries and begins audio playback before the LLM has finished generating. Perceived response time is dramatically lower than the actual generation time.

**Memory is always on.** There's no "remember this" mode. Every conversation is observed by EchoStone. Important information is extracted and stored automatically.

**Proactive by default.** FRIDAY Synapse doesn't wait to be addressed. It monitors, surfaces, and notifies — within boundaries the user can configure.
