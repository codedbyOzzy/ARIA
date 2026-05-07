"""F.R.I.D.A.Y. — PySide6 + QML, Gemini Live Native Audio default mod."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from friday.brain import Brain
from friday.live_audio import LiveAudioThread
import friday.tts_engine as tts


_QML_PATH = Path(__file__).parent / "qt_ui" / "Main.qml"


# ── Brain Thread (yazılı komutlar için fallback) ───────────────────────────────

class BrainThread(QThread):
    response = Signal(str)
    error    = Signal(str)
    thinking = Signal(bool)

    def __init__(self, brain: Brain, text: str) -> None:
        super().__init__()
        self._brain = brain
        self._text  = text

    def run(self) -> None:
        self.thinking.emit(True)
        try:
            resp = self._brain.process(self._text)
            self.response.emit(resp)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.thinking.emit(False)


# ── Bridge ────────────────────────────────────────────────────────────────────

class Bridge(QObject):
    def __init__(self, engine: QQmlApplicationEngine) -> None:
        super().__init__()
        self._engine       = engine
        self._brain        = Brain()
        self._brain_thread: BrainThread | None = None
        self._live: LiveAudioThread | None = None
        self._muted        = False

    # ── Slots (QML → Python) ─────────────────────────────────────────────────

    @Slot(str)
    def sendText(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._qml("addMessage", text, True)

        # Live oturum açıksa oradan gönder, değilse Brain'e düş
        if self._live and self._live.isRunning():
            self._live.send_text(text)
        else:
            self._run_brain(text)

    @Slot()
    def toggleMute(self) -> None:
        self._muted = not self._muted
        if self._live:
            self._live.set_mute(self._muted)
        self._qml("setMuted", self._muted)
        self._qml("setStatus", "sessiz" if self._muted else "dinliyor")

    @Slot()
    def resetChat(self) -> None:
        self._brain.reset()
        self._qml("clearMessages")
        self._qml("setStatus", "sıfırlandı")
        self._qml("addMessage", "Konuşma geçmişi temizlendi.", False)

    # ── Live Audio yönetimi ──────────────────────────────────────────────────

    def start_live(self) -> None:
        if self._live and self._live.isRunning():
            return
        self._live = LiveAudioThread()
        self._live.transcript.connect(lambda t: self._qml("addMessage", t, True))
        self._live.assistant_text.connect(lambda t: self._qml("addMessage", t, False))
        self._live.status.connect(lambda s: self._qml("setStatus", s))
        self._live.speaking.connect(lambda s: self._qml("setSpeaking", s))
        self._live.error.connect(self._on_live_error)
        self._live.finished.connect(self._on_live_finished)
        self._live.start()
        self._qml("setLiveActive", True)

        # Hatırlatıcı ateşlenince FRIDAY sesli söylesin
        from friday.tools.reminder import register_fire_callback
        live_ref = self._live
        register_fire_callback(
            lambda msg: live_ref.send_text(
                f"Hatirlatici surest doldu: '{msg}'. Ozana sesli olarak hatırlat."
            )
        )

        # Sistem uyarıları sesli gelsin
        from friday.tools.system_alerts import register_speak_callback
        register_speak_callback(lambda msg: live_ref.send_text(msg))

    def _on_live_error(self, err: str) -> None:
        print(f"[Live] {err}", flush=True)
        self._qml("setStatus", "bağlantı hatası — yeniden deniyor…")

    def _on_live_finished(self) -> None:
        self._qml("setLiveActive", False)
        self._qml("setStatus", "bağlantı kapandı")

    # ── Brain fallback ───────────────────────────────────────────────────────

    def _run_brain(self, text: str) -> None:
        if self._brain_thread and self._brain_thread.isRunning():
            return
        t = BrainThread(self._brain, text)
        t.response.connect(self._on_brain_response)
        t.error.connect(lambda e: self._qml("addMessage", f"[Hata: {e}]", False))
        t.thinking.connect(lambda b: self._qml("setThinking", b))
        t.thinking.connect(lambda b: self._qml("setStatus", "düşünüyor…" if b else "hazır"))
        t.start()
        self._brain_thread = t

    def _on_brain_response(self, text: str) -> None:
        self._qml("addMessage", text, False)
        self._qml("setStatus", "hazır")
        threading.Thread(target=tts.speak, args=(text,), daemon=True).start()

    # ── QML yardımcıları ─────────────────────────────────────────────────────

    def _root(self):
        roots = self._engine.rootObjects()
        return roots[0] if roots else None

    def _qml(self, fn: str, *args) -> None:
        root = self._root()
        if root is None:
            return
        try:
            getattr(root, fn)(*args)
        except Exception as e:
            print(f"[bridge] {fn}: {e}", flush=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FRIDAY")

    engine = QQmlApplicationEngine()
    bridge = Bridge(engine)
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.warnings.connect(lambda w: [print("QML:", x.toString()) for x in w])
    engine.load(QUrl.fromLocalFile(str(_QML_PATH)))

    if not engine.rootObjects():
        print("[FATAL] QML yüklenemedi:", _QML_PATH, flush=True)
        sys.exit(1)

    # Live Audio'yu otomatik başlat
    from PySide6.QtCore import QTimer
    QTimer.singleShot(500, bridge.start_live)

    # FRIDAY kapanma callback'ini kaydet
    from friday.tools.system_control import register_quit_callback
    register_quit_callback(app.quit)

    # Uygulama kapanmadan önce thread'i temiz durdur (Qt aboutToQuit sinyali)
    def _cleanup_on_quit():
        live = bridge._live
        if live and live.isRunning():
            live.stop()
            # asyncio loop'u dışarıdan iptal et
            if live._loop and not live._loop.is_closed():
                live._loop.call_soon_threadsafe(live._loop.stop)
            live.wait(3000)

    app.aboutToQuit.connect(_cleanup_on_quit)

    # Proaktif sistem izlemeyi başlat
    from friday.tools.system_alerts import start_system_alerts
    start_system_alerts()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
