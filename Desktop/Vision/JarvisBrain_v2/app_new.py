"""F.R.I.D.A.Y. — Yeni, sade uygulama (Gemini 2.5 Flash + OpenAI fallback)."""

from __future__ import annotations

import sys
import threading
from dotenv import load_dotenv

load_dotenv()

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPalette, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from friday.brain import Brain
from friday.live_audio import LiveAudioThread
import friday.tts_engine as tts

# ── STT Thread ─────────────────────────────────────────────────────────────────

class SttThread(QThread):
    result = Signal(str)
    error = Signal(str)
    listening = Signal(bool)

    def run(self) -> None:
        import io
        import wave
        import numpy as np
        import sounddevice as sd
        import speech_recognition as sr

        # Sabit WDM-KS cihaz — Nahimic/Sonar bypass (Realtek HD Audio Mic input)
        MIC_DEVICE = 25
        RATE = 44100
        THRESH = 80
        SILENCE_SEC = 1.5
        MAX_SEC = 10
        CHUNK_SECS = 0.3
        N = int(CHUNK_SECS * RATE)
        MAX_SILENCE = int(SILENCE_SEC / CHUNK_SECS)
        MAX_LOOPS = int(MAX_SEC / CHUNK_SECS)

        self.listening.emit(True)
        frames = []
        started = False
        silence = 0

        try:
            for _ in range(MAX_LOOPS):
                data = sd.rec(N, samplerate=RATE, channels=1, dtype="int16", device=MIC_DEVICE)
                sd.wait()
                flat = data.flatten()
                rms = float(np.sqrt(np.mean(flat.astype(np.float32) ** 2)))
                if rms > THRESH:
                    started = True
                    silence = 0
                    frames.append(flat.tobytes())
                elif started:
                    frames.append(flat.tobytes())
                    silence += 1
                    if silence >= MAX_SILENCE:
                        break

            if not frames:
                self.error.emit("timeout")
                return

            # 44100 → 16000 resample
            raw = b"".join(frames)
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            new_len = int(len(arr) * 16000 / RATE)
            resampled = np.interp(
                np.linspace(0, len(arr) - 1, new_len),
                np.arange(len(arr)), arr,
            ).astype(np.int16)

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(resampled.tobytes())

            audio = sr.AudioData(buf.getvalue(), 16000, 2)
            text = sr.Recognizer().recognize_google(audio, language="tr-TR")
            self.result.emit(text)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.listening.emit(False)


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


# ── Message Bubble ─────────────────────────────────────────────────────────────

class MsgBubble(QWidget):
    def __init__(self, text: str, is_user: bool, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setFont(QFont("Consolas", 10))
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        if is_user:
            label.setStyleSheet(
                "background:#1a2a3a; color:#80d4ff; border-radius:8px; padding:8px 12px;"
            )
            layout.addStretch()
            layout.addWidget(label)
        else:
            label.setStyleSheet(
                "background:#0d1f0d; color:#80ff90; border-radius:8px; padding:8px 12px;"
            )
            layout.addWidget(label)
            layout.addStretch()


# ── Main Window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.brain = Brain()
        self._stt_thread = None
        self._brain_thread = None
        self._live_thread = None
        self._live_active = False

        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()

        QTimer.singleShot(600, self._greeting)

    # ── Window setup ────────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("F.R.I.D.A.Y.")
        self.setMinimumSize(720, 560)
        self.resize(860, 640)

        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#0a0a0a"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

    def _setup_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root.setStyleSheet("background:#0a0a0a;")
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("background:#050f1a; border-bottom:1px solid #003366;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        title = QLabel("● F.R.I.D.A.Y.")
        title.setFont(QFont("Consolas", 14, QFont.Bold))
        title.setStyleSheet("color:#00aaff;")
        h_lay.addWidget(title)
        h_lay.addStretch()

        self._status = QLabel("hazır")
        self._status.setFont(QFont("Consolas", 9))
        self._status.setStyleSheet("color:#336699;")
        h_lay.addWidget(self._status)

        self._fallback_lbl = QLabel("● OpenAI")
        self._fallback_lbl.setFont(QFont("Consolas", 9))
        self._fallback_lbl.setStyleSheet("color:#555;")
        h_lay.addWidget(self._fallback_lbl)

        vbox.addWidget(header)

        # ── Conversation area ────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea{background:#0a0a0a; border:none;}"
            "QScrollBar:vertical{background:#0a0a0a; width:6px;}"
            "QScrollBar::handle:vertical{background:#003366; border-radius:3px;}"
        )

        self._conv_widget = QWidget()
        self._conv_widget.setStyleSheet("background:#0a0a0a;")
        self._conv_layout = QVBoxLayout(self._conv_widget)
        self._conv_layout.setContentsMargins(12, 12, 12, 12)
        self._conv_layout.setSpacing(6)
        self._conv_layout.addStretch()

        self._scroll.setWidget(self._conv_widget)
        vbox.addWidget(self._scroll, 1)

        # ── Input bar ────────────────────────────────────────────────────────────
        bar = QWidget()
        bar.setFixedHeight(62)
        bar.setStyleSheet("background:#050f1a; border-top:1px solid #003366;")
        b_lay = QHBoxLayout(bar)
        b_lay.setContentsMargins(12, 8, 12, 8)
        b_lay.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Komut yaz veya mikrofona bas…")
        self._input.setFont(QFont("Consolas", 11))
        self._input.setStyleSheet(
            "QLineEdit{"
            "  background:#0d1a2a; color:#c8e8ff;"
            "  border:1px solid #003366; border-radius:6px; padding:6px 12px;"
            "}"
            "QLineEdit:focus{border:1px solid #0066cc;}"
        )
        self._input.returnPressed.connect(self._send_text)
        b_lay.addWidget(self._input, 1)

        self._send_btn = QPushButton("Gönder")
        self._send_btn.setFixedWidth(80)
        self._send_btn.setFont(QFont("Consolas", 10))
        self._send_btn.setStyleSheet(self._btn_style("#004499", "#0055bb"))
        self._send_btn.clicked.connect(self._send_text)
        b_lay.addWidget(self._send_btn)

        self._mic_btn = QPushButton("🎤 Dinle")
        self._mic_btn.setFixedWidth(90)
        self._mic_btn.setFont(QFont("Consolas", 10))
        self._mic_btn.setStyleSheet(self._btn_style("#004422", "#006633"))
        self._mic_btn.clicked.connect(self._toggle_listen)
        b_lay.addWidget(self._mic_btn)

        self._live_btn = QPushButton("⚡ Live")
        self._live_btn.setFixedWidth(80)
        self._live_btn.setFont(QFont("Consolas", 10))
        self._live_btn.setToolTip("Gemini Native Audio — düşük gecikme, barge-in destekli")
        self._live_btn.setStyleSheet(self._btn_style("#2a1a00", "#554400"))
        self._live_btn.clicked.connect(self._toggle_live)
        b_lay.addWidget(self._live_btn)

        self._reset_btn = QPushButton("↺")
        self._reset_btn.setFixedWidth(36)
        self._reset_btn.setToolTip("Konuşmayı sıfırla")
        self._reset_btn.setFont(QFont("Consolas", 12))
        self._reset_btn.setStyleSheet(self._btn_style("#1a1a1a", "#2a2a2a"))
        self._reset_btn.clicked.connect(self._reset_chat)
        b_lay.addWidget(self._reset_btn)

        vbox.addWidget(bar)

    def _btn_style(self, bg: str, hover: str) -> str:
        return (
            f"QPushButton{{background:{bg}; color:#c8e8ff; border:1px solid #003366;"
            f"  border-radius:6px; padding:4px 8px;}}"
            f"QPushButton:hover{{background:{hover};}}"
            f"QPushButton:pressed{{background:#001122;}}"
        )

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._toggle_listen)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._reset_chat)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self).activated.connect(self._toggle_live)

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _add_msg(self, text: str, is_user: bool) -> None:
        bubble = MsgBubble(text, is_user)
        self._conv_layout.insertWidget(self._conv_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def _update_fallback_label(self) -> None:
        if self.brain.using_fallback:
            self._fallback_lbl.setStyleSheet("color:#ffaa44;")
            self._fallback_lbl.setText("● OpenAI (fallback)")
        else:
            self._fallback_lbl.setStyleSheet("color:#555;")
            self._fallback_lbl.setText("● Gemini")

    def _set_busy(self, busy: bool) -> None:
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)

    # ── Actions ─────────────────────────────────────────────────────────────────

    def _greeting(self) -> None:
        self._run_brain("Merhaba, kısaca kendini tanıt.")

    def _send_text(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._add_msg(text, is_user=True)
        self._run_brain(text)

    def _toggle_listen(self) -> None:
        if self._stt_thread and self._stt_thread.isRunning():
            return
        self._stt_thread = SttThread()
        self._stt_thread.listening.connect(self._on_listening)
        self._stt_thread.result.connect(self._on_stt_result)
        self._stt_thread.error.connect(self._on_stt_error)
        self._stt_thread.start()

    def _reset_chat(self) -> None:
        self.brain.reset()
        for i in reversed(range(self._conv_layout.count() - 1)):
            item = self._conv_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        self._set_status("sıfırlandı")
        self._add_msg("Konuşma geçmişi temizlendi.", is_user=False)

    def _toggle_live(self) -> None:
        if self._live_active:
            self._stop_live()
        else:
            self._start_live()

    def _start_live(self) -> None:
        if self._live_active:
            return
        self._live_active = True
        self._live_btn.setText("⏹ Live")
        self._live_btn.setStyleSheet(self._btn_style("#442200", "#884400"))
        self._set_status("Live mod başlıyor…")
        self._add_msg("⚡ Gemini Native Audio başlatılıyor — konuşmaya hazırlanın.", is_user=False)

        self._live_thread = LiveAudioThread()
        self._live_thread.transcript.connect(lambda t: self._add_msg(t, is_user=True))
        self._live_thread.assistant_text.connect(lambda t: self._add_msg(t, is_user=False))
        self._live_thread.status.connect(self._set_status)
        self._live_thread.error.connect(self._on_live_error)
        self._live_thread.speaking.connect(lambda s: self._set_status("konuşuyor…" if s else "dinliyor…"))
        self._live_thread.finished.connect(self._on_live_finished)
        self._live_thread.start()

    def _stop_live(self) -> None:
        if self._live_thread:
            self._live_thread.stop()
        self._live_active = False
        self._live_btn.setText("⚡ Live")
        self._live_btn.setStyleSheet(self._btn_style("#2a1a00", "#554400"))

    def _on_live_error(self, err: str) -> None:
        self._add_msg("[Live hata: " + err + "]", is_user=False)
        self._stop_live()
        self._set_status("Live hata")

    def _on_live_finished(self) -> None:
        self._live_active = False
        self._live_btn.setText("⚡ Live")
        self._live_btn.setStyleSheet(self._btn_style("#2a1a00", "#554400"))
        self._set_status("Live mod kapandı")

    def _run_brain(self, text: str) -> None:
        if self._brain_thread and self._brain_thread.isRunning():
            return
        self._set_busy(True)
        self._set_status("düşünüyor…")
        self._brain_thread = BrainThread(self.brain, text)
        self._brain_thread.response.connect(self._on_brain_response)
        self._brain_thread.error.connect(self._on_brain_error)
        self._brain_thread.finished.connect(lambda: self._set_busy(False))
        self._brain_thread.start()

    # ── Slots ────────────────────────────────────────────────────────────────────

    def _on_listening(self, active: bool) -> None:
        if active:
            self._mic_btn.setText("⏹ Dinliyor")
            self._mic_btn.setStyleSheet(self._btn_style("#440000", "#660000"))
            self._set_status("dinliyor…")
        else:
            self._mic_btn.setText("🎤 Dinle")
            self._mic_btn.setStyleSheet(self._btn_style("#004422", "#006633"))

    def _on_stt_result(self, text: str) -> None:
        self._set_status("anlaşıldı")
        self._add_msg(text, is_user=True)
        self._run_brain(text)

    def _on_stt_error(self, err: str) -> None:
        self._set_status("ses alınamadı")
        if "timeout" not in err.lower() and "unrecognized" not in err.lower():
            self._add_msg(f"[STT hatası: {err}]", is_user=False)

    def _on_brain_response(self, text: str) -> None:
        self._add_msg(text, is_user=False)
        self._set_status("hazır")
        self._update_fallback_label()
        threading.Thread(target=tts.speak, args=(text,), daemon=True).start()

    def _on_brain_error(self, err: str) -> None:
        self._add_msg(f"[Hata: {err}]", is_user=False)
        self._set_status("hata")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FRIDAY")
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#0a0a0a"))
    pal.setColor(QPalette.WindowText, QColor("#c8e8ff"))
    pal.setColor(QPalette.Base, QColor("#0d1a2a"))
    pal.setColor(QPalette.Text, QColor("#c8e8ff"))
    pal.setColor(QPalette.Button, QColor("#0d1a2a"))
    pal.setColor(QPalette.ButtonText, QColor("#c8e8ff"))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
