"""F.R.I.D.A.Y. — PySide6 + QML arayüz, Gemini 2.5 Flash + OpenAI fallback."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from friday.brain import Brain
from friday.live_audio import LiveAudioThread
from friday.stt import SttThread
import friday.tts_engine as tts


_QML_PATH = Path(__file__).parent / "qt_ui" / "Main.qml"


# ── Brain Thread ───────────────────────────────────────────────────────────────

class BrainThread(QThread):
    response = Signal(str)
    error = Signal(str)
    thinking = Signal(bool)

    def __init__(self, brain: Brain, text: str) -> None:
        super().__init__()
        self._brain = brain
        self._text = text

    def run(self) -> None:
        self.thinking.emit(True)
        try:
            resp = self._brain.process(self._text)
            self.response.emit(resp)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.thinking.emit(False)


# ── QML ↔ Python köprüsü ─────────────────────────────────────────────────────

class Bridge(QObject):
    """QML'den Python'a çağrılar bu sınıf üzerinden gelir."""

    def __init__(self, engine: QQmlApplicationEngine) -> None:
        super().__init__()
        self._engine = engine
        self._brain = Brain()
        self._stt: SttThread | None = None
        self._brain_thread: BrainThread | None = None
        self._live_thread: LiveAudioThread | None = None
        self._live_active = False

    # ── QML'den çağrılacak slot'lar ──────────────────────────────────────────

    @Slot(str)
    def sendText(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._qml("addMessage", text, True)
        self._run_brain(text)

    @Slot()
    def toggleListen(self) -> None:
        if self._stt and self._stt.isRunning():
            return
        self._stt = SttThread()
        self._stt.listening.connect(self._on_listening)
        self._stt.result.connect(self._on_stt_result)
        self._stt.error.connect(self._on_stt_error)
        self._stt.start()

    @Slot()
    def toggleLive(self) -> None:
        if self._live_active:
            self._stop_live()
        else:
            self._start_live()

    @Slot()
    def resetChat(self) -> None:
        self._brain.reset()
        self._qml("clearMessages")
        self._qml("setStatus", "sıfırlandı")
        self._qml("addMessage", "Konuşma geçmişi temizlendi.", False)

    # ── İç yardımcılar ───────────────────────────────────────────────────────

    def _run_brain(self, text: str) -> None:
        if self._brain_thread and self._brain_thread.isRunning():
            return
        t = BrainThread(self._brain, text)
        t.response.connect(self._on_brain_response)
        t.error.connect(self._on_brain_error)
        t.thinking.connect(lambda b: self._qml("setThinking", b))
        t.thinking.connect(lambda b: self._qml("setStatus", "düşünüyor…" if b else "hazır"))
        t.start()
        self._brain_thread = t

    def _start_live(self) -> None:
        self._live_active = True
        self._qml("setLiveActive", True)
        self._qml("setStatus", "Live başlıyor…")
        self._qml("addMessage", "⚡ Gemini Native Audio başlatılıyor — konuşmaya hazırlanın.", False)

        lt = LiveAudioThread()
        lt.transcript.connect(lambda t: self._qml("addMessage", t, True))
        lt.assistant_text.connect(lambda t: self._qml("addMessage", t, False))
        lt.status.connect(lambda s: self._qml("setStatus", s))
        lt.error.connect(self._on_live_error)
        lt.speaking.connect(lambda s: self._qml("setStatus", "konuşuyor…" if s else "dinliyor…"))
        lt.finished.connect(self._on_live_finished)
        lt.start()
        self._live_thread = lt

    def _stop_live(self) -> None:
        if self._live_thread:
            self._live_thread.stop()
        self._live_active = False
        self._qml("setLiveActive", False)

    def _greeting(self) -> None:
        self._run_brain("Merhaba, kısaca kendini tanıt.")

    # ── Slot'lar ─────────────────────────────────────────────────────────────

    def _on_listening(self, active: bool) -> None:
        self._qml("setListening", active)
        self._qml("setStatus", "dinliyor…" if active else "hazır")

    def _on_stt_result(self, text: str) -> None:
        self._qml("setStatus", "anlaşıldı")
        self._qml("addMessage", text, True)
        self._run_brain(text)

    def _on_stt_error(self, err: str) -> None:
        self._qml("setStatus", "ses alınamadı")
        if "timeout" not in err.lower():
            self._qml("addMessage", f"[STT hatası: {err}]", False)

    def _on_brain_response(self, text: str) -> None:
        self._qml("addMessage", text, False)
        self._qml("setStatus", "hazır")
        self._qml("setFallback", self._brain.using_fallback)
        threading.Thread(target=tts.speak, args=(text,), daemon=True).start()

    def _on_brain_error(self, err: str) -> None:
        self._qml("addMessage", f"[Hata: {err}]", False)
        self._qml("setStatus", "hata")

    def _on_live_error(self, err: str) -> None:
        self._qml("addMessage", f"[Live hata: {err}]", False)
        self._stop_live()
        self._qml("setStatus", "Live hata")

    def _on_live_finished(self) -> None:
        self._live_active = False
        self._qml("setLiveActive", False)
        self._qml("setStatus", "Live mod kapandı")

    # ── QML erişim yardımcıları ───────────────────────────────────────────────

    def _root(self):
        roots = self._engine.rootObjects()
        return roots[0] if roots else None

    def _qml(self, fn_name: str, *args) -> None:
        root = self._root()
        if root is None:
            return
        try:
            getattr(root, fn_name)(*args)
        except Exception as e:
            print(f"[bridge] QML çağrı hatası {fn_name}: {e}", flush=True)



# ── Giriş noktası ────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FRIDAY")
    app.setOrganizationName("Ozan")

    engine = QQmlApplicationEngine()

    bridge = Bridge(engine)
    engine.rootContext().setContextProperty("bridge", bridge)

    engine.load(QUrl.fromLocalFile(str(_QML_PATH)))

    if not engine.rootObjects():
        print("[FATAL] QML yüklenemedi:", _QML_PATH, flush=True)
        sys.exit(1)

    # Startup selamlama
    from PySide6.QtCore import QTimer
    QTimer.singleShot(700, bridge._greeting)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
