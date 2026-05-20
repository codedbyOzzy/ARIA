# Architecture v2.0

ARIA is built on a fundamental paradigm shift: **Parallel Cognitive Execution.** 

Traditional AI assistants operate on a sequential event loop. You speak -> it transcribes -> it searches memory -> it queries the model -> it acts. This sequential pipeline guarantees high latency.

ARIA shatters this by dividing cognitive workload across independent engines that start simultaneously.

## 1. The Tri-Core Engine

ARIA runs three primary engines asynchronously.

### 1.1. Input Engine
The moment `Alt+Space` is triggered or a voice command is initiated, the Input Engine begins processing. It classifies the intent of the user locally (within milliseconds). If the query is simple (e.g., "what time is it"), it routes to the Fast Path and bypasses the main model entirely. 

### 1.2. Memory Engine (Parallel Context)
The most critical innovation in ARIA. The moment input starts, the Memory Engine begins semantic vector searches against the user's personal knowledge base. It does not wait for the Input Engine to finish. By the time the primary Agent Core is ready to reason, the user's context (past conversations, preferences, and relevant documents) is already loaded into memory.

### 1.3. Agent Core
The central orchestrator. It receives the parsed intent and the parallel-loaded context. It connects to the configured BYOK (Bring Your Own Key) provider and streams the response back token-by-token. If a physical action is required, it triggers the Action modules seamlessly.

## 2. The Legacy of the 7 Stones

ARIA is the direct evolution of the FRIDAY Synapse architecture, which was composed of 7 independent "Stones". While the Stones are no longer standalone event-bus nodes, their intelligence lives on inside the Tri-Core Engine:

- **THE ARC & ARCHIVE** → Absorbed into the Memory Engine for persistent episodic tracking.
- **ORACLE** → Absorbed into the Input Engine for rapid model routing.
- **SPECTRE & VIGIL** → Absorbed into the Agent Core for state tracking and prediction.
- **VoiceStone & ActionStone** → Bound directly to the Input Engine and Agent Core tool executor.

By removing the network hops between these components, ARIA achieves < 1.2s latency while maintaining the full depth of FRIDAY's original cognition.
