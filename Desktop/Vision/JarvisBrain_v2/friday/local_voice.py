"""Optional local voice pipeline.

This is a conservative phase-1 backend:
- offline/local STT via friday.stt
- local text router via SafeBrainRouter
- existing TTS engine for speaking

It is intentionally sequential and opt-in so the default cloud live path stays
untouched unless explicitly enabled.
"""

from __future__ import annotations

import os
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from friday.router import SafeBrainRouter
from friday.stt import get_preferred_mic, transcribe_once
import friday.tts_engine as tts


class LocalVoiceThread(QThread):
    transcript = Signal(str)
    assistant_text = Signal(str)
    status = Signal(str)
    error = Signal(str)
    speaking = Signal(bool)

    def __init__(
        self,
        router: SafeBrainRouter | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._router = router if router is not None else SafeBrainRouter()
        self._stop = threading.Event()
        self._muted = False
        self._pending: queue.Queue[tuple[str, bool]] = queue.Queue()
        self._device, self._rate = get_preferred_mic()

    def stop(self) -> None:
        self._stop.set()
        tts.stop()

    def set_mute(self, val: bool) -> None:
        self._muted = val
        if val:
            tts.stop()
            self.status.emit("sessiz")
        else:
            self.status.emit("dinliyor")

    def send_text(self, text: str) -> None:
        text = (text or "").strip()
        if text:
            self._pending.put((text, False))

    def run(self) -> None:
        self.status.emit("dinliyor")
        while not self._stop.is_set():
            queued = self._drain_pending()
            if queued:
                text, emit_user = queued
                self._process_text(text, emit_user=emit_user)
                continue

            if self._muted:
                time.sleep(0.1)
                continue

            try:
                text = transcribe_once(device=self._device, rate=self._rate)
            except Exception as exc:
                if not self._stop.is_set():
                    self.error.emit(str(exc))
                    self.status.emit("stt hatasi")
                time.sleep(0.5)
                continue

            if self._stop.is_set():
                break
            if not text:
                self.status.emit("dinliyor")
                continue

            self._process_text(text, emit_user=True)

        self.speaking.emit(False)
        self.status.emit("baglanti kapandi")

    def _drain_pending(self) -> tuple[str, bool] | None:
        try:
            return self._pending.get_nowait()
        except queue.Empty:
            return None

    def _process_text(self, text: str, *, emit_user: bool) -> None:
        """Streaming LLM: cümle gelir gelmez TTS'e verir — düşük gecikmeli tepki."""
        clean = (text or "").strip()
        if not clean:
            return

        if emit_user:
            self.transcript.emit(clean)

        self.status.emit("dusunuyor...")
        first_chunk = True

        try:
            for sentence in self._router.stream_process(clean):
                if self._stop.is_set():
                    break

                self.assistant_text.emit(sentence)

                if first_chunk:
                    self.status.emit("konusuyor")
                    self.speaking.emit(True)
                    first_chunk = False
                    # Barge-in monitörünü başlat — TTS çalarken yeni ses kessin
                    self._start_barge_monitor()

                if not self._muted and not self._stop.is_set():
                    tts.speak(sentence)   # cümle biter → bir sonrakine geç

        except Exception as exc:
            self.error.emit(str(exc))
            self.status.emit("hata")
            return
        finally:
            self.speaking.emit(False)
            if not self._stop.is_set():
                self.status.emit("dinliyor")

    def _start_barge_monitor(self) -> None:
        """TTS çalarken arka planda mikrofon izle.

        Kullanıcı konuşmaya başlarsa TTS'i kes — insan benzeri kesişen konuşma.
        """
        # Barge-in eşiği: normal konuşma RMS eşiğinin 1.4 katı (yanlış pozitif azaltır)
        rms_thresh = float(os.getenv("FRIDAY_STT_RMS", "200")) * 1.4
        chunk_sz   = int(0.12 * self._rate)   # 120ms chunk
        device     = self._device
        rate       = self._rate

        def _monitor() -> None:
            while tts.is_speaking() and not self._stop.is_set():
                try:
                    data = sd.rec(chunk_sz, samplerate=rate, channels=1,
                                  dtype="int16", device=device)
                    sd.wait()
                    rms = float(np.sqrt(np.mean(data.flatten().astype(np.float32) ** 2)))
                    if rms > rms_thresh:
                        print(f"[local] barge-in rms={rms:.0f} → TTS kesiliyor", flush=True)
                        tts.stop()
                        break
                except Exception:
                    break

        threading.Thread(target=_monitor, daemon=True, name="friday-barge-in").start()
