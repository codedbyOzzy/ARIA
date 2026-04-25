from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pyttsx3
import sounddevice as sd
import speech_recognition as sr
from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMessageBox
from friday.pipeline import CommandPipeline
from friday.stt_health import run_health_check
from friday.tools import desktop_control, local_llm, memory, ollama_runtime, policy, system, task_executor, utils, weather, web
from blackbox import BLACKBOX_FILE, last_error, last_success, log_event, tail_events


ROOT = Path(__file__).resolve().parent
MCP_URL = "http://127.0.0.1:8010/sse"
PANEL_URL = "http://127.0.0.1:8030"
STATUS_URL = f"{PANEL_URL}/api/status"


def recovery_action(service_online: bool, pipeline_ready: bool, voice_state: str = "") -> str:
    state = str(voice_state or "").strip().lower()
    if not service_online:
        return "restart"
    if not pipeline_ready:
        return "retry"
    if state == "error":
        return "retry"
    return ""


class UiPolicyAdapter:
    def check(self, intent: dict[str, Any]) -> tuple[bool, str]:
        tool = str(intent.get("tool", "") or "").strip().lower()
        if tool in {"", "bilinmeyen"}:
            return False, "Bu komutu yerel modda anlayamadim."
        return True, ""


class UiToolsAdapter:
    def __init__(self, run_tool):
        self._run_tool = run_tool

    def execute(self, intent: dict[str, Any]) -> Any:
        tool = str(intent.get("tool", "") or "").strip()
        args = dict(intent.get("args", {}) or {})
        return self._run_tool(tool, **args)

    def format_weather_response(self, data: dict[str, Any]) -> str:
        return weather.format_weather_response(data)


class UiSanitizerAdapter:
    def __init__(self, run_tool):
        self._run_tool = run_tool

    def clean(self, raw: str) -> str:
        return self._run_tool("clean_voice_text", text=raw)


class UiBlackboxAdapter:
    @staticmethod
    def log_event(event: str, level: str = "info", **kwargs: Any) -> None:
        log_event(event, level=level, **kwargs)


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


class FridayUiBridge(QObject):
    statusChanged = Signal()
    busyChanged = Signal()
    toastChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        log_event("ui_init")
        self._running = False
        self._service_online = False
        self._pipeline_ready = False
        self._busy = False
        self._policy = "unknown"
        self._ollama = "unknown"
        self._profile = "unknown"
        self._voice = "unknown"
        self._last_error_msg = ""
        self._last_error_ts = 0.0
        self._last_success_msg = ""
        self._recovery_action = ""
        self._direct_listening = False
        self._direct_last_text = ""
        self._toast = "FRIDAY arayuzu hazir."
        self._auto_start_attempted = False
        self._lock = threading.Lock()
        self._listen_stop = threading.Event()
        self._listen_thread: threading.Thread | None = None
        self._tools = _build_local_tools()
        self._pipeline = CommandPipeline(
            policy=UiPolicyAdapter(),
            tools=UiToolsAdapter(self._call_tool_raw),
            sanitizer=UiSanitizerAdapter(self._call_tool_raw),
            blackbox=UiBlackboxAdapter(),
        )
        self._tts = pyttsx3.init()
        self._stt_health: dict[str, Any] | None = None
        self._stt_last_check = 0.0
        self._stt_check_interval = 30.0
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(2500)
        self._poll_timer.timeout.connect(self.refreshStatus)
        self._poll_timer.start()
        self._heartbeat = QTimer()
        self._heartbeat.setInterval(5000)
        self._heartbeat.timeout.connect(self._emit_heartbeat)
        self._heartbeat.start()
        self.refreshStatus()
        QTimer.singleShot(1200, self.ensureStarted)

    @Property(bool, notify=statusChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=statusChanged)
    def policyText(self) -> str:
        return self._policy

    @Property(str, notify=statusChanged)
    def ollamaText(self) -> str:
        return self._ollama

    @Property(str, notify=statusChanged)
    def profileText(self) -> str:
        return self._profile

    @Property(str, notify=statusChanged)
    def voiceText(self) -> str:
        return self._voice

    @Property(bool, notify=statusChanged)
    def serviceOnline(self) -> bool:
        return self._service_online

    @Property(bool, notify=statusChanged)
    def pipelineReady(self) -> bool:
        return self._pipeline_ready

    @Property(str, notify=statusChanged)
    def lastErrorMsg(self) -> str:
        return self._last_error_msg

    @Property(float, notify=statusChanged)
    def lastErrorTs(self) -> float:
        return self._last_error_ts

    @Property(str, notify=statusChanged)
    def lastSuccessMsg(self) -> str:
        return self._last_success_msg

    @Property(str, notify=statusChanged)
    def recoveryAction(self) -> str:
        return self._recovery_action

    @Property(bool, notify=statusChanged)
    def directListening(self) -> bool:
        return self._direct_listening

    @Property(str, notify=statusChanged)
    def directLastText(self) -> str:
        return self._direct_last_text

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=toastChanged)
    def toast(self) -> str:
        return self._toast

    def _set_busy(self, value: bool) -> None:
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit()

    def _set_toast(self, text: str) -> None:
        self._toast = text
        self.toastChanged.emit()
        self.statusChanged.emit()
        log_event("ui_toast", text=text[:200])

    def _emit_heartbeat(self) -> None:
        log_event(
            "ui_heartbeat",
            running=self._running,
            busy=self._busy,
            direct_listening=self._direct_listening,
            voice_state=self._voice,
        )

    def _compute_recovery_action(self) -> str:
        return recovery_action(
            service_online=self._service_online,
            pipeline_ready=self._pipeline_ready,
            voice_state=self._voice,
        )

    def _speak(self, text: str) -> None:
        msg = str(text or "").strip()
        if not msg:
            return
        try:
            self._tts.say(msg)
            self._tts.runAndWait()
            log_event("tts_spoken", text=msg[:220])
        except Exception:
            log_event("tts_error", level="error", trace=traceback.format_exc(limit=5))

    def _call_tool_raw(self, name: str, *args, **kwargs) -> str:
        fn = self._tools.get(name)
        if not fn:
            raise RuntimeError(f"Tool not found: {name}")
        try:
            if asyncio.iscoroutinefunction(fn):
                out = str(asyncio.run(fn(*args, **kwargs)))
            else:
                out = str(fn(*args, **kwargs))
            return out
        except Exception as exc:
            raise RuntimeError(f"{name}_failed: {exc}") from exc

    def _run_tool(self, name: str, *args, **kwargs) -> str:
        try:
            out = self._call_tool_raw(name, *args, **kwargs)
            log_event("tool_ok", tool=name, result=str(out)[:260])
            return str(out)
        except Exception as exc:
            log_event("tool_error", level="error", tool=name, error=str(exc), trace=traceback.format_exc(limit=6))
            return str(exc)

    def _handle_direct_command(self, text: str) -> str:
        log_event("direct_command_received", text=(text or "")[:220])
        return self._process_voice_command(text)

    def _process_voice_command(self, text: str) -> str:
        log_event("heard_text", level="info", text=(text or "")[:220], source="direct")
        result = self._pipeline.run(text, source="direct")
        log_event(
            "tool_result",
            level="info" if result.success else "error",
            tool=result.tool_name,
            result_type=result.result_type,
            success=result.success,
            source="direct",
        )
        if not result.success and result.result_type not in ("policy_block",):
            log_event("heard_not_processed", level="warning", text=(text or "")[:220], reason=result.result_type)
        if result.success:
            if result.tool_name == "get_current_time":
                return f"Saat: {result.response}"
            if result.tool_name == "get_world_news":
                return result.response[:500]
            return result.response
        return result.response

    def _get_stt_health(self) -> dict[str, Any]:
        now = time.time()
        if (not self._stt_health) or (now - self._stt_last_check > self._stt_check_interval):
            self._stt_health = run_health_check()
            self._stt_last_check = now
        return self._stt_health

    def _notify_user_stt_failure(self, health: dict[str, Any]) -> None:
        msg = "Mikrofon bağlantısı kurulamadı. "
        if not health.get("pyaudio", {}).get("ok") and not health.get("sounddevice", {}).get("ok"):
            msg += "Mikrofon cihazı bulunamıyor, bağlı olduğundan emin olun."
        elif not health.get("google_stt", {}).get("ok"):
            msg += "Ses tanıma servisine ulaşılamıyor, internet bağlantınızı kontrol edin."
        else:
            msg += "Lütfen tekrar deneyin."
        self._set_toast(msg)

    def _listen_once_pyaudio(self, recognizer: sr.Recognizer) -> str | None:
        try:
            mic = sr.Microphone()
            with mic as source:
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                except Exception:
                    log_event("stt_ambient_adjust_error", level="error", backend="pyaudio", trace=traceback.format_exc(limit=4))
                audio = recognizer.listen(source, timeout=1.0, phrase_time_limit=6.0)
            return recognizer.recognize_google(audio, language="tr-TR")
        except sr.WaitTimeoutError:
            return None
        except Exception:
            log_event("stt_pyaudio_error", level="error", trace=traceback.format_exc(limit=4))
            self._stt_health = None
            return None

    def _listen_once_sounddevice(self, recognizer: sr.Recognizer) -> str | None:
        try:
            sample_rate = 16000
            frames = int(sample_rate * 4.0)
            rec = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
            sd.wait()
            audio_f32 = np.squeeze(rec)
            audio_i16 = np.clip(audio_f32 * 32767.0, -32768, 32767).astype(np.int16)
            audio = sr.AudioData(audio_i16.tobytes(), sample_rate=sample_rate, sample_width=2)
            return recognizer.recognize_google(audio, language="tr-TR")
        except sr.UnknownValueError:
            return None
        except Exception:
            log_event("stt_sounddevice_error", level="error", trace=traceback.format_exc(limit=4))
            self._stt_health = None
            return None

    def _listen_loop(self) -> None:
        recognizer = sr.Recognizer()
        self._set_toast("Yerel dinleme aktif. Konusabilirsiniz.")
        while not self._listen_stop.is_set():
            health = self._get_stt_health()
            backend = health.get("recommended")
            heard = None
            if backend == "pyaudio+google":
                log_event("direct_listen_backend", backend="pyaudio")
                heard = self._listen_once_pyaudio(recognizer)
                if heard is None:
                    # immediate fallback in the same tick
                    heard = self._listen_once_sounddevice(recognizer)
            elif backend in {"sounddevice+google", "sounddevice+offline"}:
                log_event("direct_listen_backend", backend="sounddevice")
                heard = self._listen_once_sounddevice(recognizer)
            else:
                log_event("stt_no_backend", level="critical")
                self._notify_user_stt_failure(health)
                time.sleep(1.0)
                continue

            if not heard:
                continue
            self._direct_last_text = heard
            self.statusChanged.emit()
            result = self._handle_direct_command(heard)
            self._set_toast(result)
            self._speak(result)

    @Slot()
    def toggleDirectListening(self) -> None:
        if self._direct_listening:
            self._listen_stop.set()
            self._direct_listening = False
            self._set_toast("Yerel dinleme durduruldu.")
            self.statusChanged.emit()
            log_event("direct_listen_stopped")
            return
        self._listen_stop.clear()
        self._direct_listening = True
        self.statusChanged.emit()
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        log_event("direct_listen_started")

    @Slot()
    def refreshStatus(self) -> None:
        if self._busy:
            return
        threading.Thread(target=self._refresh_status_worker, daemon=True).start()

    def _refresh_status_worker(self) -> None:
        with self._lock:
            mcp_ok = False
            panel_ok = False
            policy_text = "unknown"
            ollama_text = "unknown"
            profile_text = "unknown"
            voice_text = "unknown"
            try:
                with httpx.stream("GET", MCP_URL, timeout=httpx.Timeout(connect=0.9, read=0.9, write=0.9, pool=0.9)) as resp:
                    mcp_ok = resp.status_code == 200
            except Exception:
                log_event("status_mcp_probe_error", level="error", trace=traceback.format_exc(limit=4))
                mcp_ok = False

            try:
                resp = httpx.get(STATUS_URL, timeout=1.2)
                panel_ok = resp.status_code == 200
                if panel_ok:
                    data = resp.json()
                    self._service_online = bool(data.get("service_online", False))
                    self._pipeline_ready = bool(data.get("pipeline_ready", False))
                    pol = (data.get("policy", {}) or {}).get("armed", False)
                    ollama_ok = (data.get("ollama", {}) or {}).get("ok", False)
                    has_profile = (data.get("profile", {}) or {}).get("has_profile", False)
                    voice_state = str((data.get("voice", {}) or {}).get("state", "unknown"))
                    policy_text = "armed" if pol else "safe"
                    ollama_text = "online" if ollama_ok else "offline"
                    profile_text = "loaded" if has_profile else "empty"
                    voice_text = voice_state
            except Exception:
                log_event("status_panel_probe_error", level="error", trace=traceback.format_exc(limit=4))
                panel_ok = False

            self._service_online = self._service_online if panel_ok else bool(mcp_ok and panel_ok)
            self._running = bool(self._service_online)
            self._policy = policy_text
            self._ollama = ollama_text
            self._profile = profile_text
            self._voice = voice_text
            err = last_error()
            ok_evt = last_success()
            self._last_error_msg = str(err.get("event", "")) if err else ""
            self._last_error_ts = float(err.get("ts", 0.0)) if err else 0.0
            self._last_success_msg = str(ok_evt.get("event", "")) if ok_evt else ""
            self._recovery_action = self._compute_recovery_action()
            self.statusChanged.emit()
            if not self._running and not self._auto_start_attempted:
                QTimer.singleShot(200, self.ensureStarted)

    @Slot()
    def ensureStarted(self) -> None:
        if self._running or self._busy or self._auto_start_attempted:
            return
        self._auto_start_attempted = True
        self._set_toast("Servisler kapali gorunuyor, otomatik baslatiliyor...")
        self.startStack()

    def _run_ps(self, script: str, extra: list[str] | None = None) -> tuple[bool, str]:
        script_path = ROOT / script
        if not script_path.exists():
            return False, f"Script not found: {script_path}"
        args = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
        if extra:
            args.extend(extra)
        try:
            subprocess.Popen(args, cwd=str(ROOT))
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    @Slot()
    def startStack(self) -> None:
        self._set_busy(True)
        ok, msg = self._run_ps("start.ps1", ["-Fresh"])
        self._set_busy(False)
        if ok:
            self._set_toast("FRIDAY stack baslatildi. Simdi LiveKit odasina baglanip mikrofondan konusun.")
            QTimer.singleShot(2200, self.refreshStatus)
        else:
            self._set_toast(f"Baslatma hatasi: {msg}")
            log_event("stack_start_error", level="error", error=msg)

    @Slot()
    def stopStack(self) -> None:
        self._set_busy(True)
        ok, msg = self._run_ps("stop.ps1")
        self._set_busy(False)
        if ok:
            self._set_toast("FRIDAY stack durduruldu.")
            QTimer.singleShot(1200, self.refreshStatus)
        else:
            self._set_toast(f"Durdurma hatasi: {msg}")
            log_event("stack_stop_error", level="error", error=msg)

    @Slot(result=str)
    def blackboxPath(self) -> str:
        return str(BLACKBOX_FILE)

    @Slot(int, result=str)
    def readBlackbox(self, limit: int = 50) -> str:
        events = tail_events(limit)
        return "\n".join([str(e) for e in events])

    @Slot()
    def openControlPanel(self) -> None:
        QDesktopServices.openUrl(QUrl(PANEL_URL))
        self._set_toast("Control panel acildi.")

    @Slot()
    def openLiveKit(self) -> None:
        QDesktopServices.openUrl(QUrl("https://cloud.livekit.io/"))
        self._set_toast("LiveKit console acildi.")


def run_qt() -> int:
    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()
    bridge = FridayUiBridge()
    engine.rootContext().setContextProperty("fridayBridge", bridge)

    qml_path = ROOT / "qt_ui" / "Main.qml"
    if not qml_path.is_file():
        QMessageBox.critical(None, "JarvisBrain_v2", f"UI file not found:\n{qml_path}")
        return 1
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        QMessageBox.critical(None, "JarvisBrain_v2", "UI failed to load.")
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_qt())
