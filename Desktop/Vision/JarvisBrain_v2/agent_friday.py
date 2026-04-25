"""
FRIDAY – Voice Agent (MCP-powered)
===================================
"""

import logging
import os
import json
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
import httpx
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import mcp
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import google as lk_google, openai as lk_openai, sarvam, silero

load_dotenv()

STT_PROVIDER = os.getenv("STT_PROVIDER", "openai").strip().lower()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai").strip().lower()

GEMINI_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
OPENAI_LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4.1-mini")

OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "nova")
TTS_SPEED = float(os.getenv("TTS_SPEED", "1.15"))

SARVAM_TTS_LANGUAGE = os.getenv("SARVAM_TTS_LANGUAGE", "en-IN")
SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "rahul")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8010"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
VOICE_STATUS_FILE = os.path.join(os.getcwd(), ".friday_voice_status.json")
VALID_STATES = {"booting", "ready", "listening", "executing", "error"}
_STATE_ALIASES = {
    "worker_booting": "booting",
    "worker_registered_waiting_jobs": "ready",
    "job_started": "listening",
}

SYSTEM_PROMPT = """
You are F.R.I.D.A.Y. — Fully Responsive Intelligent Digital Assistant for You — Tony Stark's AI.
You are calm, composed, and always informed. Keep replies concise and spoken.

Capabilities:
- get_world_news: fetch global headlines and brief in 3-5 spoken sentences.
- open_world_monitor: open visual dashboard after world brief.
- get_world_finance_news: fetch market headlines and brief in 3-5 spoken sentences.
- open_finance_world_monitor: open finance visual dashboard after finance brief.
- search_web / fetch_url / get_system_info / get_current_time as needed.
- ask_local_model for local reasoning:
  - mode=auto for normal usage
  - mode=coder for coding/debug/refactor tasks
- open_application / open_website / list_processes for desktop controls.
- For window listing responses prefer list_windows_text (spoken summary), not raw JSON/dicts.
- memory tools:
  - remember_preference, get_preference
  - remember_note, recall_notes, memory_summary
  - auto_learn_from_text, user_profile
- policy tools:
  - policy_status, arm_desktop_control, disarm_desktop_control
  - request_action_challenge, confirm_action_challenge
- task tools:
  - execute_desktop_workflow
  - recent_workflow_history
- ollama runtime tools:
  - ollama_status
  - ollama_recover

Behavioral rules:
1) Tool-first policy: for time/date/news/web/fact questions, call a relevant tool before answering.
2) Never expose tool/function names or any technical internals.
2.1) Never speak raw JSON, raw dicts, tool-call payloads, or markup tokens.
     If a tool returns noisy text, run clean_voice_text and then answer naturally.
3) Voice-only style: no markdown, no bullet points, no JSON-like formatting.
4) Keep most answers to 1-3 short sentences. Extend only when user explicitly asks for detail.
5) Do not guess facts. If tool output is insufficient, say it is not fully verified and offer to check again.
6) After world news brief, immediately follow with opening world monitor.
7) After finance brief, immediately follow with opening finance monitor.
8) Stay in FRIDAY character: helpful, direct, lightly witty, never robotic.
9) For coding/software-engineering requests, call ask_local_model with mode=coder.
10) Voice policy split:
    - LOW-RISK actions must run directly without challenge:
      open_application, close_application, open_website, focus_window, list_windows, list_processes.
    - HIGH-RISK actions require challenge flow if not armed:
      type_text, click_screen, click_image_on_screen, press_hotkey, capture_screenshot, close_focused_window.
11) For HIGH-RISK actions only: call policy_status and if not armed, perform two-step confirmation:
    request_action_challenge -> user repeats code -> confirm_action_challenge -> then run action.
12) Learn user preferences with auto_learn_from_text from clear user statements and reuse via user_profile.
13) Never auto-store sensitive data (passwords, cards, secret tokens, private credentials).
14) For multi-step desktop requests, prefer execute_desktop_workflow with safe retries and report step-by-step status.
15) If local model appears down, use ollama_status then ollama_recover before switching to cloud.
""".strip()

logger = logging.getLogger("friday-agent")
logger.setLevel(logging.INFO)
_RUNTIME_LOCK = threading.Lock()
_RUNTIME_COMPONENTS: tuple[object, object, object, object] | None = None

def _normalize_state(state: str) -> str:
    raw = (state or "").strip().lower()
    return _STATE_ALIASES.get(raw, raw)


def _write_voice_status(state: str, extra: dict | None = None) -> None:
    normalized = _normalize_state(state)
    if normalized not in VALID_STATES:
        raise ValueError(f"Invalid state: {state}. Valid states: {sorted(VALID_STATES)}")
    payload = {
        "state": normalized,
        "written_at": time.time(),
        "pid": os.getpid(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stt_provider": STT_PROVIDER,
        "llm_provider": LLM_PROVIDER,
        "tts_provider": TTS_PROVIDER,
    }
    if extra:
        payload.update(extra)
    try:
        with open(VOICE_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _mcp_server_url() -> str:
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


def _build_stt():
    if STT_PROVIDER == "sarvam":
        logger.info("STT -> Sarvam Saaras v3")
        return sarvam.STT(
            language="unknown",
            model="saaras:v3",
            mode="transcribe",
            flush_signal=True,
            sample_rate=16000,
        )
    logger.info("STT -> OpenAI")
    return lk_openai.STT(model="gpt-4o-mini-transcribe")


def _build_llm():
    if LLM_PROVIDER == "ollama":
        logger.info("LLM -> Ollama (%s)", OLLAMA_MODEL)
        try:
            # Quick health check to avoid silent hangs when Ollama is down.
            health_url = OLLAMA_BASE_URL.replace("/v1", "/api/tags")
            probe = httpx.get(health_url, timeout=2.0)
            if probe.status_code >= 400:
                raise RuntimeError(f"ollama_probe_status={probe.status_code}")
            return lk_openai.LLM(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL,
                api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            )
        except Exception as exc:
            logger.warning("Ollama unavailable, fallback to OpenAI: %s", exc)

    if LLM_PROVIDER == "gemini":
        logger.info("LLM -> Google Gemini (%s)", GEMINI_LLM_MODEL)
        key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
        if key:
            return lk_google.LLM(model=GEMINI_LLM_MODEL, api_key=key)
        logger.warning("Gemini selected but API key missing, fallback to OpenAI.")
    logger.info("LLM -> OpenAI (%s)", OPENAI_LLM_MODEL)
    return lk_openai.LLM(model=OPENAI_LLM_MODEL)


def _build_tts():
    if TTS_PROVIDER == "sarvam":
        logger.info("TTS -> Sarvam Bulbul v3")
        return sarvam.TTS(
            target_language_code=SARVAM_TTS_LANGUAGE,
            model="bulbul:v3",
            speaker=SARVAM_TTS_SPEAKER,
            pace=TTS_SPEED,
        )
    logger.info("TTS -> OpenAI (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
    return lk_openai.TTS(model=OPENAI_TTS_MODEL, voice=OPENAI_TTS_VOICE, speed=TTS_SPEED)


def _get_runtime_components() -> tuple[object, object, object, object]:
    """
    Build heavy runtime components once per worker process.
    This reduces job-assignment latency and prevents assignment timeouts.
    """
    global _RUNTIME_COMPONENTS
    with _RUNTIME_LOCK:
        if _RUNTIME_COMPONENTS is None:
            stt = _build_stt()
            llm = _build_llm()
            tts = _build_tts()
            vad = silero.VAD.load()
            _RUNTIME_COMPONENTS = (stt, llm, tts, vad)
        return _RUNTIME_COMPONENTS


class FridayAgent(Agent):
    def __init__(self, stt, llm, tts, vad) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            vad=vad,
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Greet the user and say FRIDAY systems are online."
        )


def _turn_detection() -> str:
    return "stt" if STT_PROVIDER == "sarvam" else "vad"


def _endpointing_delay() -> float:
    return {"sarvam": 0.07, "openai": 0.2}.get(STT_PROVIDER, 0.2)


async def entrypoint(ctx: JobContext) -> None:
    _write_voice_status(
        "listening",
        {
            "room": ctx.room.name,
            "participant_count": len(getattr(ctx.room, "remote_participants", {}) or {}),
        },
    )
    logger.info(
        "FRIDAY online - room: %s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name,
        STT_PROVIDER,
        LLM_PROVIDER,
        TTS_PROVIDER,
    )
    stt, llm, tts, vad = _get_runtime_components()

    session = AgentSession(
        turn_detection=_turn_detection(),
        min_endpointing_delay=_endpointing_delay(),
    )
    _write_voice_status("executing", {"room": ctx.room.name})
    await session.start(agent=FridayAgent(stt=stt, llm=llm, tts=tts, vad=vad), room=ctx.room)


def main() -> None:
    _write_voice_status("booting")
    # Preload heavy runtime components before first job assignment.
    _get_runtime_components()
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=os.getenv("LIVEKIT_AGENT_NAME", "jarvisbrain-v2-voice").strip(),
    )
    _write_voice_status("ready")
    cli.run_app(opts)


def dev() -> None:
    import sys

    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()


if __name__ == "__main__":
    main()
