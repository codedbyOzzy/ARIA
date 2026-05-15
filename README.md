<div align="center">

<img src="images/core-gold.png" width="170" alt="FRIDAY Synapse core"/>

# FRIDAY Synapse

### A private Windows-native AI assistant architecture showcase

**Persistent memory. Voice interaction. Desktop control. Multi-model reasoning.**

**English** | [Türkçe](README.tr.md)

<br/>

![Status](https://img.shields.io/badge/Status-Private%20Beta-gold?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?style=for-the-badge&logo=windows)
![Focus](https://img.shields.io/badge/Focus-AI%20Desktop%20OS-8A2BE2?style=for-the-badge)
![Source](https://img.shields.io/badge/Source-Showcase%20Only-222222?style=for-the-badge)

<br/>

*"Not a chatbot tab. Not a prompt wrapper. FRIDAY is designed as a persistent assistant that lives with the operating system."*

</div>

---

## What This Repository Is

**ProjectFridaySynapse** is the public showcase for FRIDAY, a private Windows-native AI desktop assistant built by [Ozzy](https://github.com/codedbyOzzy).

This repository explains the product vision, cognitive architecture, public modules, privacy boundaries, and roadmap behind FRIDAY without exposing private runtime code, credentials, personal memory files, or sensitive automation logic.

The private FRIDAY runtime combines:

- A PySide6/QML desktop interface
- Continuous voice input and neural text-to-speech
- Multi-model reasoning with OpenAI, Gemini, Groq, and local LLM fallback
- Persistent memory, session history, narrative tracking, and user adaptation
- Windows desktop tools for apps, files, clipboard, browser, Steam, Telegram, system stats, and reminders
- A modular event-driven architecture built around FRIDAY "Stones"

<br/>

<div align="center">
<img src="images/synapse-architecture.svg" width="840" alt="FRIDAY Synapse architecture map"/>
</div>

---

## What This Repository Is Not

This is **not** the private FRIDAY source-code repository.

It does not include:

- Private assistant runtime code
- API keys, prompts containing personal data, or user memory files
- Desktop automation internals that could expose unsafe control surfaces
- Personal logs, session history, or local configuration
- Any production secrets or private model-routing policies

FRIDAY is a local-first personal assistant. The public showcase is intentionally separated from the private runtime.

See [PRIVACY.md](PRIVACY.md) and [PUBLIC_MODULES.md](PUBLIC_MODULES.md) for the boundary.

---

## System Overview

FRIDAY is organized as a layered assistant OS rather than a single chat loop.

| Layer | Purpose | Example Modules |
|---|---|---|
| Interface Layer | Desktop UI, setup flow, settings, chat surface | PySide6, QML, Setup Wizard |
| Event Layer | Routes events between system components | BrainCore, StoneEvent |
| Reasoning Layer | Chooses models, streams answers, calls tools | Brain, SafeBrainRouter, ORACLE |
| Memory Layer | Remembers facts, goals, episodes, and decisions | MemoryStore, THE ARC, ARCHIVE |
| Awareness Layer | Predicts next steps and tracks state | SPECTRE, VIGIL |
| Personality Layer | Adapts tone, style, and user-world model | MindStone, EchoStone, BondStone, IntuitionStone |
| Action Layer | Performs real desktop and web tasks | Tools, VoiceStone, ActionStone, WebStone |

---

## The Interaction Loop

<div align="center">
<img src="images/interaction-loop.svg" width="840" alt="FRIDAY interaction loop"/>
</div>

Every user turn moves through a context-rich loop:

| Step | Module | What Happens |
|---|---|---|
| 1. Capture | VoiceStone / UI Bridge | Receives text or speech and emits a user event |
| 2. Context | EchoStone / Memory | Retrieves relevant memories and comprehension signals |
| 3. Route | SafeBrainRouter / ORACLE | Selects local, fast cloud, or deeper reasoning path |
| 4. Predict | SPECTRE / VIGIL | Adds likely next-step and current-state context |
| 5. Reason | Brain | Streams a response and calls tools when needed |
| 6. Act | Tools | Opens apps, reads files, searches web, controls Windows |
| 7. Learn | Memory / Stones | Stores useful facts, style signals, goals, and outcomes |
| 8. Speak | TTS / UI | Displays and speaks the final response |

---

## Capabilities

### Native Desktop Assistance

- Open and close Windows applications
- Manage windows, clipboard, files, folders, and system stats
- Control volume, media playback, reminders, and notes
- Launch browser workflows, YouTube, Steam, and Telegram actions
- Read selected files and summarize relevant content

### Voice-First Interaction

- Local voice loop with speech-to-text
- Neural text-to-speech via Edge voices
- Echo suppression and barge-in safeguards
- Turkish and English support

### Memory and Adaptation

- Persistent user memory across sessions
- Category-based facts, goals, preferences, events, and context
- Episodic narrative tracking through THE ARC
- Longitudinal emotional/profile memory through ARCHIVE
- Communication-style adaptation through MindStone and EchoStone

### Multi-Model Intelligence

- Fast daily reasoning path
- Deep reasoning path for analysis, debugging, and planning
- Local model path for simple safe queries
- Gemini and Groq fallbacks for resilience
- Circuit-breaker style provider handling

---

## Public Ecosystem

Some FRIDAY concepts are public as standalone libraries or architecture references:

- [Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones) - adaptive persona and cognition modules
- [THESingularity](https://github.com/codedbyOzzy/THESingularity) - public awareness-layer work
- [FRIDAY Showcase](https://showcasefridayv2.netlify.app) - visual product showcase

The full Windows assistant runtime remains private.

---

## Repository Guide

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | High-level technical architecture |
| [ROADMAP.md](ROADMAP.md) | Current direction and planned work |
| [SHOWCASE.md](SHOWCASE.md) | Example scenarios and user-facing demos |
| [PUBLIC_MODULES.md](PUBLIC_MODULES.md) | Public vs private module boundary |
| [PRIVACY.md](PRIVACY.md) | Privacy, data, and security posture |
| [CHANGELOG.md](CHANGELOG.md) | Public showcase update history |

---

## Current Status

FRIDAY is currently a **private beta desktop assistant**. The architecture is actively evolving, and this repository is maintained as the public-facing product and architecture showcase.

The goal is simple: make powerful personal AI feel local, persistent, useful, and human enough to belong on the desktop.

<div align="center">

<br/>

**Built by [Ozzy](https://github.com/codedbyOzzy)**

</div>
