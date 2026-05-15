# FRIDAY Synapse Architecture

FRIDAY Synapse is the architecture behind a private Windows-native AI desktop assistant. It is built around a modular event-driven system where voice, memory, reasoning, tools, and user adaptation communicate through a shared core.

This document describes the public architecture without exposing private runtime source code or sensitive automation details.

---

## Design Principles

### 1. Local-First Presence

FRIDAY is designed to live on the user's machine, not only inside a browser tab. The assistant can interact with the desktop, remember long-term context, and keep a persistent relationship with the user's workflow.

### 2. Event-Driven Modularity

The runtime is organized around a central event bus. Components emit and consume events such as `USER_SPOKE`, `REQUEST_CONTEXT`, `CONTEXT_PROVIDED`, `SPEAK_TEXT`, and `TURN_COMPLETED`.

This keeps the assistant extensible: voice, memory, reasoning, proactive monitoring, and UI updates can evolve independently.

### 3. Context Before Reasoning

The assistant does not send a raw user message directly to a model. It first builds context from memory, recent sessions, narrative history, user-state signals, and comprehension patterns.

### 4. Safe Multi-Model Routing

Simple safe requests can be handled locally. Tool use, current information, desktop control, and deeper analysis go through the cloud reasoning path with fallbacks.

---

## High-Level Runtime Flow

<div align="center">
<img src="images/synapse-architecture.svg" width="860" alt="FRIDAY Synapse architecture map"/>
</div>

```text
User text or voice
      |
      v
UI Bridge / VoiceStone
      |
      v
BrainCore Event Bus
      |
      +--> EchoStone builds memory and comprehension context
      |
      +--> LogicStone invokes SafeBrainRouter
      |
      +--> Brain selects model, streams response, and calls tools
      |
      +--> Tools interact with Windows, files, web, voice, and apps
      |
      +--> Memory and awareness layers learn from the completed turn
      |
      v
UI response + TTS response
```

---

## Core Layers

### Interface Layer

The desktop UI is built with PySide6 and QML. It provides the main chat surface, first-run setup wizard, settings panel, provider configuration, file drop handling, and status updates.

### Event Layer

`BrainCore` is the central dispatcher. It registers Stone modules, initializes them, and distributes targeted or broadcast events.

Key concepts:

- `StoneEvent`: standard payload for communication
- `BaseStone`: lifecycle contract for modules
- Targeted events for direct module communication
- Broadcast events for multi-module observation

### Reasoning Layer

The reasoning path is split between `SafeBrainRouter` and `Brain`.

`SafeBrainRouter` decides whether a request is eligible for local handling. It avoids local routing for risky, action-heavy, web-current, vision, clipboard, or app-control tasks.

`Brain` handles:

- Streaming model responses
- OpenAI primary path
- Gemini and Groq fallback paths
- Tool schema generation
- Parallel tool execution
- Conversation compression
- Integration with ORACLE, SPECTRE, THE ARC, ARCHIVE, SelfModel, PolicyStore, BeliefStore, and GoalEngine

### Memory Layer

FRIDAY uses multiple memory surfaces:

- Short-term session log
- Persistent category memory
- Episodic narrative memory
- Longitudinal archive memory
- Behavioral and style memory

The base memory store supports facts, preferences, events, goals, and context. Retrieval uses relevance, importance, and recency scoring.

### Awareness Layer

The awareness layer adds proactive and self-reflective signals:

- `ORACLE`: task complexity and model routing
- `SPECTRE`: next-step prediction
- `VIGIL`: real-time user-state and goal tracking
- `THE ARC`: episode and decision continuity
- `ARCHIVE`: long-term emotional and longitudinal memory

### Personality Layer

FRIDAY adapts over time through:

- `MindStone`: communication style and verbosity
- `EchoStone`: comprehension and overload signals
- `BondStone`: user-world model
- `IntuitionStone`: likely conversation direction

These modules help the assistant respond in a way that fits the user instead of using the same generic tone forever.

### Action Layer

The tool system gives FRIDAY controlled access to desktop functions:

- Application launch and closing
- Window management
- Clipboard operations
- File and folder operations
- Web search and page reading
- Weather, news, and system stats
- Steam, Telegram, reminders, notes, diagrams, and code execution

The public showcase does not expose sensitive automation code or personal runtime data.

---

## Model Strategy

The private runtime supports a multi-provider strategy:

| Path | Purpose |
|---|---|
| Local LLM | Short, safe, text-only requests |
| Fast cloud model | Daily reasoning, tool calls, general tasks |
| Deep reasoning model | Analysis, debugging, planning, complex tasks |
| Gemini fallback | Provider resilience |
| Groq fallback | Secondary resilience path |

The exact model choices can evolve with the runtime. The architecture is designed around routing policy rather than a single hard-coded model.

---

## Privacy Boundary

FRIDAY stores personal context locally in runtime files. Those files are intentionally excluded from this showcase.

The public repository describes how the system is structured. It does not publish private memory, session logs, API keys, desktop automation internals, or personal assistant configuration.

See [PRIVACY.md](PRIVACY.md).

---

## Last Updated

May 2026
