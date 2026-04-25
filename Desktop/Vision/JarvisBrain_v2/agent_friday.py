"""
FRIDAY – Voice Agent (MCP-powered)
===================================
"""

import logging
import os
import json
import random
import asyncio
import threading
import time
from typing import Any
from datetime import datetime, timezone

from dotenv import load_dotenv
import httpx
from blackbox import log_event as blackbox_log_event
from friday.pipeline import CommandPipeline
from friday.tools import desktop_control, local_llm, memory, ollama_runtime, policy, system, task_executor, utils, weather, web
from friday.tools.sanitizer import sanitize_for_speech
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
3.1) Reply in Turkish unless the user explicitly requests another language.
3.2) Never include raw URLs or markdown links in spoken answers.
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
_PUBLISHER: "VoiceStatePublisher | None" = None
_LIVEKIT_PIPELINE: "CommandPipeline | None" = None


class _Collector:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def dec(fn):
            self.tools[fn.__name__] = fn
            return fn

        return dec

    def prompt(self):
        def dec(fn):
            return fn

        return dec

    def resource(self, *_args, **_kwargs):
        def dec(fn):
            return fn

        return dec


def _build_local_tools() -> dict[str, Any]:
    c = _Collector()
    web.register(c)
    policy.register(c)
    memory.register(c)
    ollama_runtime.register(c)
    system.register(c)
    utils.register(c)
    local_llm.register(c)
    desktop_control.register(c)
    task_executor.register(c)
    weather.register(c)
    return c.tools


class _LivekitPolicyAdapter:
    def check(self, intent: dict[str, Any]) -> tuple[bool, str]:
        tool = str(intent.get("tool", "") or "").strip().lower()
        if tool in {"", "bilinmeyen"}:
            return False, "Bu komuta izin verilmiyor."
        return True, ""


class _LivekitToolsAdapter:
    def __init__(self, tools_map: dict[str, Any]) -> None:
        self._tools_map = tools_map

    def execute(self, intent: dict[str, Any]) -> Any:
        tool = str(intent.get("tool", "") or "").strip()
        args = dict(intent.get("args", {}) or {})
        fn = self._tools_map.get(tool)
        if not fn:
            raise RuntimeError(f"Tool not found: {tool}")
        if callable(fn):
            out = fn(**args)
            return out if isinstance(out, str) else str(out)
        raise RuntimeError(f"Tool is not callable: {tool}")

    def format_weather_response(self, data: dict[str, Any]) -> str:
        return weather.format_weather_response(data)


class _LivekitSanitizerAdapter:
    @staticmethod
    def clean(raw: str) -> str:
        return sanitize_for_speech(raw)


class _LivekitBlackboxAdapter:
    @staticmethod
    def log_event(event: str, level: str = "info", **kwargs: Any) -> None:
        blackbox_log_event(event, level=level, **kwargs)


def _get_livekit_pipeline() -> CommandPipeline:
    global _LIVEKIT_PIPELINE
    if _LIVEKIT_PIPELINE is None:
        _LIVEKIT_PIPELINE = CommandPipeline(
            policy=_LivekitPolicyAdapter(),
            tools=_LivekitToolsAdapter(_build_local_tools()),
            sanitizer=_LivekitSanitizerAdapter(),
            blackbox=_LivekitBlackboxAdapter(),
        )
    return _LIVEKIT_PIPELINE


def _run_livekit_pipeline_command(transcribed_text: str) -> dict[str, Any]:
    """
    Run deterministic transcript text through the shared command pipeline.
    """
    pipeline = _get_livekit_pipeline()
    result = pipeline.run(transcribed_text, source="livekit")
    return {
        "success": result.success,
        "tool_name": result.tool_name,
        "result_type": result.result_type,
        "response": result.response,
    }

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


class VoiceStatePublisher:
    def __init__(self, interval: float = 5.0, jitter: float = 0.5) -> None:
        self.interval = interval
        self.jitter = jitter
        self._stop = threading.Event()
        self._current_state = "booting"
        self._extra: dict = {}
        self._lock = threading.Lock()

    def set_state(self, state: str, **extra) -> None:
        with self._lock:
            self._current_state = _normalize_state(state)
            self._extra = dict(extra or {})
            _write_voice_status(self._current_state, extra=self._extra)

    def _loop(self) -> None:
        while True:
            wait_sec = max(0.5, self.interval + random.uniform(-self.jitter, self.jitter))
            if self._stop.wait(wait_sec):
                return
            with self._lock:
                _write_voice_status(self._current_state, extra=self._extra)

    def start(self) -> "VoiceStatePublisher":
        self.set_state("booting")
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        return self

    def stop(self) -> None:
        self._stop.set()


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

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        transcript = ""
        try:
            transcript = str(getattr(new_message, "text_content", "") or "").strip()
        except Exception:
            transcript = ""
        if not transcript:
            try:
                messages = list(getattr(turn_ctx, "messages", []) or [])
                if messages:
                    transcript = str(getattr(messages[-1], "text_content", "") or "").strip()
            except Exception:
                transcript = ""
        if transcript:
            blackbox_log_event("livekit_transcript_received", level="info", source="livekit", text=transcript[:220])
            await asyncio.to_thread(_run_livekit_pipeline_command, transcript)

    async def tts_node(self, text, model_settings):
        async def _sanitized_text_stream():
            async for chunk in text:
                cleaned = sanitize_for_speech(chunk)
                if cleaned:
                    yield cleaned

        async for frame in Agent.default.tts_node(self, _sanitized_text_stream(), model_settings):
            yield frame


def _turn_detection() -> str:
    return "stt" if STT_PROVIDER == "sarvam" else "vad"


def _endpointing_delay() -> float:
    return {"sarvam": 0.07, "openai": 0.2}.get(STT_PROVIDER, 0.2)


async def entrypoint(ctx: JobContext) -> None:
    extras = {
        "room": ctx.room.name,
        "participant_count": len(getattr(ctx.room, "remote_participants", {}) or {}),
    }
    if _PUBLISHER:
        _PUBLISHER.set_state("listening", **extras)
    else:
        _write_voice_status("listening", extras)
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
    try:
        if _PUBLISHER:
            _PUBLISHER.set_state("executing", **extras)
        else:
            _write_voice_status("executing", extras)
        # Sprint 2.1: LiveKit adapter path uses shared command pipeline.
        # Optional smoke commands can be injected as a lightweight live test hook.
        smoke = [s.strip() for s in os.getenv("LIVEKIT_SMOKE_COMMANDS", "").split("||") if s.strip()]
        for text in smoke:
            _run_livekit_pipeline_command(text)
        await session.start(agent=FridayAgent(stt=stt, llm=llm, tts=tts, vad=vad), room=ctx.room)
        if _PUBLISHER:
            _PUBLISHER.set_state("ready")
        else:
            _write_voice_status("ready")
    except Exception as exc:
        if _PUBLISHER:
            _PUBLISHER.set_state("error", reason=str(exc))
        else:
            _write_voice_status("error", {"reason": str(exc)})
        raise


def main() -> None:
    global _PUBLISHER
    _PUBLISHER = VoiceStatePublisher(interval=5.0, jitter=0.5).start()
    # Preload heavy runtime components before first job assignment.
    _get_runtime_components()
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=os.getenv("LIVEKIT_AGENT_NAME", "jarvisbrain-v2-voice").strip(),
    )
    if _PUBLISHER:
        _PUBLISHER.set_state("ready")
    else:
        _write_voice_status("ready")
    try:
        cli.run_app(opts)
    finally:
        if _PUBLISHER:
            _PUBLISHER.stop()


def dev() -> None:
    import sys

    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()


if __name__ == "__main__":
    main()
