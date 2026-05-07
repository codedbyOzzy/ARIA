# F.R.I.D.A.Y.

> *"Most AI assistants answer your questions. F.R.I.D.A.Y. learns who you are."*

**Female Replacement Intelligent Digital Assistant Youth** — a personal AI system built on Windows, running locally, and growing smarter with every conversation.

Not a chatbot. Not a widget. A system with memory, voice, tools, and four adaptive intelligence layers that make it genuinely yours over time.

**Platform:** Windows 11 · **Status:** Active Development · **License:** Apache 2.0

---

## What it actually does

```
You say:    "launch my usual setup"
            "what was that memory leak we fixed last week?"
            "summarize the news and remind me at 7"
            "open steam and launch the game we were talking about"

F.R.I.D.A.Y. handles it.
```

Not because it was pre-programmed with those phrases.  
Because it built a model of who you are and how you talk.

---

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  app_new.py — PySide6 + QML Iron Man HUD                        │
  └────────────────────────┬────────────────────────────────────────┘
                           │
         ┌─────────────────┼──────────────────────┐
         │                 │                      │
         ▼                 ▼                      ▼
  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐
  │ LiveAudio   │  │ SafeBrain    │  │  LocalVoice        │
  │ (Gemini     │  │ Router       │  │  (offline fallback)│
  │  Live Audio)│  │              │  └────────────────────┘
  └─────────────┘  │  ┌─────────┐│
                   │  │  Brain  ││  GPT-4.1-mini / o4-mini / Gemini
                   │  └─────────┘│
                   │  ┌─────────┐│
                   │  │LocalLLM ││  Ollama (qwen2.5)
                   │  └─────────┘│
                   └──────┬───────┘
                          │
              ┌───────────┴───────────┐
              │      50+ Tools        │
              │  Desktop · System     │
              │  Files · Web · Voice  │
              │  Memory · Steam · ... │
              └───────────────────────┘
```

### The four adaptive intelligence layers

```
  ┌────────────────────────────────────────────────────────┐
  │  Layer 1 — Expression                                   │
  │                                                        │
  │  Mind Stone     learns your communication style        │
  │  Echo Stone     detects whether explanations landed    │
  │                                                        │
  │  Together: delivery that calibrates and validates      │
  │  itself every turn.                                    │
  ├────────────────────────────────────────────────────────┤
  │  Layer 2 — Context                                     │
  │                                                        │
  │  Bond Stone     builds a persistent model of your      │
  │                 world — projects, stack, constraints,  │
  │                 preferences — across every session.    │
  ├────────────────────────────────────────────────────────┤
  │  Layer 3 — Prediction                                  │
  │                                                        │
  │  Intuition Stone  learns where your conversations      │
  │                   go. Prepares answers before          │
  │                   you finish asking.                   │
  └────────────────────────────────────────────────────────┘
```

These four modules are built as standalone open-source tools.  
→ **[Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones)** — the full collection.

---

## Voice

Two voice modes, one interface.

**Gemini Live Audio** (default)
- Native real-time audio — no chunking, no latency pipeline
- Natural interruption (barge-in) support
- Continuous session with full context

**Local Voice Pipeline** (offline fallback)
- STT: faster-whisper (small model, CPU)
- TTS: edge-tts `tr-TR-AhmetNeural` — Neural Turkish voice
- Sentence-level streaming: first sentence speaks before the rest generates
- VAD-based mic detection — no push-to-talk

```
  You speak
      │
      ├── VAD detects voice
      │
      ├── faster-whisper transcribes
      │
      ├── SafeBrainRouter routes
      │         ├── Simple / fast → Ollama (qwen2.5, local)
      │         └── Complex / research → GPT-4.1-mini / Gemini
      │
      └── edge-tts speaks — sentence by sentence
```

---

## Memory

Five-category persistent memory system. Not a chat log — structured knowledge.

| Category | Stored |
|----------|--------|
| `FACT` | Things that are objectively true |
| `PREFERENCE` | How you like things done |
| `CONTEXT` | Your projects, setup, environment |
| `SKILL` | Things F.R.I.D.A.Y. learned it can do for you |
| `RELATIONSHIP` | People and their roles in your world |

Recall is semantic — TF-IDF with embedding-based backfill.  
The most relevant memories surface automatically before each response.

---

## Tools

Organized by what they control.

### Desktop & UI
| Tool | What it does |
|------|-------------|
| `open_application` | Dynamic app discovery via Start Menu + registry |
| `close_application` | Close by process name |
| `look_at_screen` | Screenshot → Gemini Vision → answer |
| `find_and_click` | Screenshot → AI locates element → clicks it |
| `type_text` | Type into active window |
| `press_key` | Keyboard combos (`ctrl+c`, `alt+f4`, etc.) |
| `click_at / right_click_at` | Pixel-level mouse control |
| `scroll` | Scroll up/down/left/right |

### Window Management
| Tool | What it does |
|------|-------------|
| `list_windows` | All open windows with titles |
| `focus_window` | Bring window to front |
| `minimize_window` | Minimize by title (partial match) |
| `maximize_window` | Maximize by title |
| `close_window` | Close by title |
| `set_window_size` | Resize to exact dimensions |

### System Control
| Tool | What it does |
|------|-------------|
| `get_system_stats` | CPU, RAM, disk, GPU usage |
| `list_processes` | Running processes sorted by memory/CPU |
| `kill_process` | End process by name or PID |
| `get_process_info` | Detailed info on a specific process |
| `get_clipboard / set_clipboard` | Read and write clipboard |
| `set_volume / volume_up / volume_down / mute_volume` | Audio control |
| `media_play_pause / media_next / media_prev` | Media keys |
| `lock_screen / sleep_mode` | Power states |
| `shutdown_computer / restart_computer / cancel_shutdown` | Power management |
| `run_powershell` | Execute PowerShell command |

### Files & Filesystem
| Tool | What it does |
|------|-------------|
| `find_file` | Recursive file search |
| `list_folder` | Directory listing with sizes |
| `read_file` | Read text file content |
| `write_text_file` | Create/overwrite file |
| `open_and_write_file` | Write then open in default app |
| `rename_file / move_file / copy_file` | File operations |
| `delete_file_safe` | Safe delete with confirmation |
| `get_file_info` | Size, timestamps, permissions |
| `create_folder` | Create directory |

### Web & Information
| Tool | What it does |
|------|-------------|
| `search_web` | Web search with snippets |
| `get_weather` | Weather for any location |
| `get_turkish_news` | Turkish news headlines via RSS |
| `get_world_news` | International news headlines |
| `open_website` | Open URL in default browser |

### Browser Automation
| Tool | What it does |
|------|-------------|
| `youtube_search` | Search YouTube, open results |
| `youtube_play` | Find and play a video (Playwright) |
| `google_search` | Google search in browser |

### Reminders & Notes
| Tool | What it does |
|------|-------------|
| `set_reminder` | Timed reminder with Windows notification + voice |
| `list_reminders` | All pending reminders |
| `cancel_reminder` | Cancel by ID |
| `take_note` | Timestamped note to desktop file |
| `read_notes` | Read all notes |
| `clear_notes` | Clear note file |

### Memory Tools
| Tool | What it does |
|------|-------------|
| `remember_this` | Store a fact explicitly |
| `recall_memory` | Semantic search over memory |
| `forget_memory` | Remove a specific memory |
| `memory_stats` | Memory store overview |

### Steam
| Tool | What it does |
|------|-------------|
| `steam_open_library` | Open Steam library |
| `steam_list_installed` | List all installed games |
| `steam_launch_game` | Launch by name (`steam://rungameid`) |

---

## Proactive System

F.R.I.D.A.Y. doesn't only respond — it watches.

| Trigger | Action |
|---------|--------|
| RAM usage > threshold | Windows notification + voice alert |
| CPU usage > threshold | Windows notification + voice alert |
| Battery low | Voice warning |
| Morning briefing time | News + weather + agenda summary |
| Reminder fires | Windows notification + voice |
| Detected routine | Suggests automating it |

Routine detection learns from usage patterns: if you do the same sequence 3+ times across 2+ days, F.R.I.D.A.Y. suggests turning it into a remembered command.

---

## Model Routing

```
  User input
      │
      ├── Intent parser (qwen2.5:3b — fast, local)
      │         ├── Desktop/system command → direct tool call
      │         ├── Simple question → Ollama (qwen2.5:7b)
      │         └── Complex / research → Brain (cloud)
      │
      └── Brain
                ├── Standard queries → GPT-4.1-mini
                ├── Reasoning tasks  → o4-mini
                └── Vision / live    → Gemini
```

Cloud is used only when it matters. Local handles everything it can.

---

## Quick Start

```bash
git clone https://github.com/codedbyOzzy/ProjectFRIDAY
cd ProjectFRIDAY/Desktop/Vision/JarvisBrain_v2

pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env

python app_new.py
```

**Required:**  
- Python 3.9+  
- Ollama running locally (`ollama pull qwen2.5`)  
- At minimum one API key: OpenAI or Gemini

**Optional:**  
- faster-whisper for offline STT  
- Playwright for browser automation (`playwright install chromium`)

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI | PySide6 + QML |
| Primary LLM | GPT-4.1-mini, o4-mini |
| Reasoning LLM | o4-mini |
| Local LLM | Ollama (qwen2.5:7b / :3b) |
| Vision | Gemini Vision |
| Live Audio | Gemini Live Audio API |
| STT | faster-whisper (small, CPU) |
| TTS | edge-tts — tr-TR-AhmetNeural |
| Memory | TF-IDF + embedding backfill |
| Desktop Control | pyautogui + Win32 API |
| Browser | Playwright (Chromium) |
| Adaptive Intelligence | [Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones) |

---

## Files

```
app_new.py                   Entry point — Qt/QML UI, Gemini Live Audio default
friday/
  brain.py                   Cloud LLM (OpenAI + Gemini) + tool calling
  router.py                  SafeBrainRouter — routing, streaming, stone observation
  local_llm.py               Ollama integration with circuit breaker
  live_audio.py              Gemini Live Audio (real-time native audio)
  local_voice.py             Offline STT + TTS pipeline
  memory.py                  5-category persistent memory with semantic recall
  stt.py                     faster-whisper STT with health probe + fallbacks
  tts_engine.py              edge-tts + pygame playback
  persona.py                 Identity, system prompt factory, stone injection
  mind_stone.py              Communication style learner
  echo_stone.py              Comprehension pattern detector
  bond_stone.py              Persistent user world model
  intuition_stone.py         Conversation arc predictor
  tools/
    actions.py               App launch, web, weather, news, volume, media
    desktop.py               Screenshot, vision click, keyboard, mouse
    system_control.py        Windows, processes, clipboard, power
    filesystem.py            File operations
    browser_automation.py    YouTube, Google (Playwright)
    reminder.py              Timed reminders with notifications
    quick_notes.py           Desktop note file
    memory_tools.py          Memory CRUD tools
    steam_tools.py           Steam game management
    system_alerts.py         Proactive RAM/CPU/battery watcher
qt_ui/
  Main.qml                   Iron Man HUD — reactor animation, voice waveform
```

---

## Roadmap

| Feature | Status |
|---------|--------|
| Core architecture | ✅ Done |
| Persistent memory | ✅ Done |
| Voice interaction | ✅ Done |
| Desktop control | ✅ Done |
| Proactive system | ✅ Done |
| 4-Stone adaptive intelligence | ✅ Done |
| Model routing + circuit breaker | ✅ Done |
| Gemini Live Audio | ✅ Done |
| Skills / plugin system | 🔄 In progress |
| Telegram remote access | 🔄 In progress |
| Test suite | 🔄 In progress |
| Public beta | 📋 Planned |

---

## Related

**[Intelligence Stones](https://github.com/codedbyOzzy/Intelligence-Stones)** — The adaptive intelligence modules (Mind Stone, Echo Stone, Bond Stone, Intuition Stone) as a standalone, zero-dependency open-source library.  
Each stone is a drop-in Python module. No framework required.

---

## Showcase

**[showcasefridayv2.netlify.app](https://showcasefridayv2.netlify.app)**

---

*"I am F.R.I.D.A.Y. How can I assist you today?"*
