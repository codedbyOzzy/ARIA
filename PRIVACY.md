# Privacy by Design

ARIA is engineered with a strict local-first philosophy. A personal operating system must remain strictly personal. 

## 1. Zero Cloud Telemetry
ARIA does not ping a central server. There is no telemetry, no analytics, no user tracking, and no centralized database. The software lives exclusively on your machine. 

## 2. Local Memory Architecture
When ARIA learns about you—your preferences, your schedule, your past conversations—that data is stored entirely in local SQLite databases and local vector stores on your hard drive. 

No third-party service has access to your long-term memory or episodic narrative. 

## 3. Bring Your Own Key (BYOK)
You are in complete control of the cognitive engine. By utilizing a BYOK model, ARIA acts only as the interface between you and the provider of your choice.

- **Cloud Providers:** If you connect OpenAI, Anthropic, or Gemini, your prompts are sent directly to their APIs. 
- **Absolute Privacy (Local Models):** For users who require absolute air-gapped privacy, ARIA fully supports running local models via Ollama. When running locally, not a single byte of text leaves your machine.

Your API keys are stored locally as environment variables and are never transmitted anywhere except directly to the provider.
