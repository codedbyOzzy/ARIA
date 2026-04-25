from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
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
from friday.tools import desktop_control, local_llm, memory, ollama_runtime, policy, system, task_executor, utils, web
from blackbox import BLACKBOX_FILE, log_event, tail_events


ROOT = Path(__file__).resolve().parent
MCP_URL = "http://127.0.0.1:8010/sse"
PANEL_URL = "http://127.0.0.1:8030"
STATUS_URL = f"{PANEL_URL}/api/status"


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
        self._direct_listening = False
        self._direct_last_text = ""
        self._toast = "FRIDAY arayuzu hazir."
        self._auto_start_attempted = False
        self._lock = threading.Lock()
        self._listen_stop = threading.Event()
        self._listen_thread: threading.Thread | None = None
        self._tools = _build_local_tools()
        self._tts = pyttsx3.init()
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

    def _speak(self, text: str) -> None:
        msg = str(text or "").strip()
        if not msg:
            return
        try:
            self._tts.say(msg)
            self._tts.runAndWait()
            log_event("tts_spoken", text=msg[:220])
        except Exception:
            log_event("tts_error", trace=traceback.format_exc(limit=5))

    def _run_tool(self, name: str, *args) -> str:
        fn = self._tools.get(name)
        if not fn:
            return f"Tool not found: {name}"
        try:
            if asyncio.iscoroutinefunction(fn):
                out = str(asyncio.run(fn(*args)))
            else:
                out = str(fn(*args))
            log_event("tool_ok", tool=name, result=out[:260])
            return out
        except Exception as exc:
            log_event("tool_error", tool=name, error=str(exc), trace=traceback.format_exc(limit=6))
            return f"{name}_failed: {exc}"

    def _handle_direct_command(self, text: str) -> str:
        low = (text or "").strip().lower()
        log_event("direct_command_received", text=(text or "")[:220])
        if not low:
            return "Komutu alamadim."

        if ("notepad" in low or "not defter" in low) and ("aç" in low or "ac" in low):
            return self._run_tool("open_application", "notepad")
        if ("notepad" in low or "not defter" in low) and ("kapat" in low):
            return self._run_tool("close_application", "notepad", 0, "")
        if "youtube" in low and ("aç" in low or "ac" in low):
            return self._run_tool("open_website", "https://www.youtube.com", "")
        if "chrome" in low and ("aç" in low or "ac" in low):
            return self._run_tool("open_application", "chrome")
        if ("açık pencereleri" in low) or ("pencereleri liste" in low) or ("pencereleri say" in low):
            return self._run_tool("list_windows_text", 10)
        if "saat kaç" in low:
            now = self._run_tool("get_current_time")
            return f"Saat: {now}"
        if ("dünyada ne oluyor" in low) or ("haber" in low):
            news = self._run_tool("get_world_news")
            short = self._run_tool("clean_voice_text", news)
            return short[:500]
        return "Bu komutu yerel modda anlayamadim. Notepad aç, YouTube aç veya pencereleri listele gibi deneyin."

    def _listen_loop(self) -> None:
        r = sr.Recognizer()
        try:
            mic = sr.Microphone()
            log_event("direct_listen_backend", backend="pyaudio")
        except Exception:
            self._set_toast("PyAudio bulunamadi, sounddevice fallback aktif.")
            log_event("direct_listen_backend_fallback", backend="sounddevice")
            self._listen_loop_sounddevice(r)
            return

        with mic as source:
            try:
                r.adjust_for_ambient_noise(source, duration=0.8)
            except Exception:
                pass
            self._set_toast("Yerel dinleme aktif. Konusabilirsiniz.")
            while not self._listen_stop.is_set():
                try:
                    audio = r.listen(source, timeout=1.0, phrase_time_limit=6.0)
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    continue
                try:
                    heard = r.recognize_google(audio, language="tr-TR")
                except Exception:
                    log_event("stt_error", backend="pyaudio", trace=traceback.format_exc(limit=4))
                    continue
                self._direct_last_text = heard
                self.statusChanged.emit()
                result = self._handle_direct_command(heard)
                self._set_toast(result)
                self._speak(result)

    def _listen_loop_sounddevice(self, recognizer: sr.Recognizer) -> None:
        sample_rate = 16000
        chunk_sec = 4.0
        self._set_toast("Yerel dinleme aktif (sounddevice). Konusabilirsiniz.")
        while not self._listen_stop.is_set():
            try:
                frames = int(sample_rate * chunk_sec)
                rec = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
                sd.wait()
                audio_f32 = np.squeeze(rec)
                audio_i16 = np.clip(audio_f32 * 32767.0, -32768, 32767).astype(np.int16)
                audio = sr.AudioData(audio_i16.tobytes(), sample_rate=sample_rate, sample_width=2)
                heard = recognizer.recognize_google(audio, language="tr-TR")
            except sr.UnknownValueError:
                continue
            except Exception:
                log_event("stt_error", backend="sounddevice", trace=traceback.format_exc(limit=4))
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
                panel_ok = False

            # Sprint 1a: keep service_online and pipeline_ready as separate signals.
            # UI visual split will be implemented in Sprint 1b.
            self._service_online = self._service_online if panel_ok else bool(mcp_ok and panel_ok)
            self._running = bool(self._service_online)
            self._policy = policy_text
            self._ollama = ollama_text
            self._profile = profile_text
            self._voice = voice_text
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
            log_event("stack_start_error", error=msg)

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
            log_event("stack_stop_error", error=msg)

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
