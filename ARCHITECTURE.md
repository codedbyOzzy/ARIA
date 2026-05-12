# FRIDAY Synapse Architecture v1.0

> *"Intelligence is not a single point. It is the convergence of Soul, Mind, and Body."*

---

## The Awareness Ecosystem Philosophy
FRIDAY Synapse v1.0 moves beyond the "Stone" collection. It is now designed as an **Awareness Ecosystem**. The architecture is structured into four distinct cognitive layers that run in a continuous loop through a unified event bus.

This architecture ensures:
- **Temporal Continuity** — Sessions are no longer isolated; they are arcs.
- **Predictive Intent** — The system understands the next step before it's asked.
- **Emotional Resonance** — Long-term user motivation and triggers are modeled.

---

## The Convergence Loop (Message Journey)
The core of the system is the **BrainCore Event Bus**. Every interaction triggers a 4-layer awareness pipeline.

### Layer 1: Strategic Intelligence (ORACLE)
**Goal:** Optimal model selection and task routing.
- Analyzes query complexity (Trivial → Deep) and urgency.
- Executes weighted oylama (voting) via specialized sub-stones.
- Routes to the most efficient LLM (gpt-4, o4-mini, or local fallback).

### Layer 2: Predictive Synthesizer (SPECTRE)
**Goal:** Proactive intent detection.
- Synthesizes current conversation arcs to predict the next logical user step.
- Prepares tool contexts or information bridges before the user asks for them.
- Reduces cognitive friction by suggesting relevant memories or actions.

### Layer 3: Historical Narrative (THE ARC & ARCHIVE)
**Goal:** Longitudinal awareness and temporal wisdom.
- **THE ARC:** Tracks "Episodes" and "Decisions" across weeks and months. Detects "Ghost Threads" (reappearing narrative loops).
- **ARCHIVE:** Manages the Emotional Signature. Upgrades memories through a hierarchy: Short-Term → Medium-Term → Longitudinal.

### Layer 4: Sensory Action (VIGIL & TOOLS)
**Goal:** Real-time state tracking and physical execution.
- **VIGIL (Tide, Compass, Ember, Mirror):** Monitors if the user is active, tracks multi-turn goals, and detects assistant confidence.
- **ACTION STONES:** Win32 API, PyAutoGUI, and native Windows tool integration.

---

## BrainCore Event Bus
The central nervous system of FRIDAY Synapse remains event-driven but now handles **context-enriched payloads**.

```
USER_SPOKE
    │
    ├── 1. Strategic Routing (ORACLE)
    ├── 2. Intent Prediction (SPECTRE)
    ├── 3. Narrative Retrieval (THE ARC)
    ├── 4. Emotional Context (ARCHIVE)
    ├── 5. Real-Time State (VIGIL)
    │
    └── FINAL CONVERGENCE → Hyper-Contextual System Prompt
```

---

## Memory Hierarchy (v1.0 Upgrade)
Memory is no longer a simple JSON store. It is now a **Temporal Hierarchy**:

1.  **Short-Term (THE ARC):** Active episodes and immediate session context. (0-2 weeks)
2.  **Medium-Term (ARCHIVE):** Summarized project progress and recurring topics. (2-8 weeks)
3.  **Longitudinal (ARCHIVE):** Core user facts, emotional motivators, and project history. (2+ months)
4.  **Emotional Signature:** Persistent tracking of user frustration triggers and engagement styles.

---

## Key Design Decisions in v1.0
- **Zero-Dependency Awareness:** All core awareness modules (Oracle, Spectre, etc.) run using Python standard library for maximum stability.
- **Parallel Context Extraction:** Narrative and state extraction (The Arc absorb / Archive upgrade) runs asynchronously after the response is sent.
- **Adaptive Style Injection:** MindStone constantly tunes the LLM's frequency to the user's observed cognitive pace.
- **Proactive Silence Surface:** The system uses the "Ember" state to surface unresolved thoughts during idle periods.

---

*Last updated: May 12, 2026*
