"""STT (Speech-to-Text) modülü.

Öncelik zinciri:
  1. Google STT (SpeechRecognition, internet) — hızlı
  2. faster-whisper (offline, CPU) — internet yoksa / Google başarısız

Mikrofon seçimi:
  - FRIDAY_MIC_DEVICE env var (sayı → doğrudan ID, "auto" veya boş → akıllı algılama)
  - Akıllı algılama: WDM-KS → WASAPI → sys.default sırası, Nahimic/Sonar bypass
"""

from __future__ import annotations

import os
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


# ── Mikrofon algılama ──────────────────────────────────────────────────────────

def _find_best_mic() -> tuple[int | None, int]:
    """En iyi mikrofon cihazını bul. (device_id, sample_rate) döndürür."""
    env_val = os.getenv("FRIDAY_MIC_DEVICE", "auto").strip()
    if env_val.isdigit():
        dev_id = int(env_val)
        try:
            info = sd.query_devices(dev_id)
            rate = int(info["default_samplerate"])
            print(f"[STT] env device={dev_id} name='{info['name']}' rate={rate}", flush=True)
            return dev_id, rate
        except Exception as e:
            print(f"[STT] env device={dev_id} geçersiz: {e} — otomatik algılamaya düşülüyor", flush=True)

    # WDM-KS öncelikli — Nahimic/Sonar gibi overlay yazılımlarını atlar
    try:
        apis = sd.query_hostapis()
        priority = ["WDM", "WASAPI", "MME"]
        for pname in priority:
            api_idx = next((i for i, a in enumerate(apis) if pname in a["name"].upper()), None)
            if api_idx is None:
                continue
            for i, d in enumerate(sd.query_devices()):
                if d["hostapi"] != api_idx or d["max_input_channels"] < 1:
                    continue
                name_low = d["name"].lower()
                blocked = ("sonar", "nahimic", "output", "stereo mix", "loopback", "virtual")
                if any(b in name_low for b in blocked):
                    continue
                rate = int(d["default_samplerate"])
                print(f"[STT] auto device={i} api={pname} name='{d['name']}' rate={rate}", flush=True)
                return i, rate
    except Exception as e:
        print(f"[STT] cihaz tarama hatası: {e}", flush=True)

    # sys.default
    try:
        dev = sd.default.device[0]
        info = sd.query_devices(dev)
        rate = int(info["default_samplerate"])
        print(f"[STT] sys.default device={dev} name='{info['name']}' rate={rate}", flush=True)
        return dev, rate
    except Exception:
        pass

    print("[STT] mikrofon bulunamadı — None döndürülüyor", flush=True)
    return None, 16000


# ── Whisper lazy-loader ────────────────────────────────────────────────────────

_whisper_model = None
_whisper_lock = threading.Lock()


def _get_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        try:
            from faster_whisper import WhisperModel
            model_size = os.getenv("FRIDAY_WHISPER_MODEL", "base")
            device = os.getenv("FRIDAY_WHISPER_DEVICE", "cpu")
            print(f"[STT] faster-whisper yükleniyor model={model_size} device={device}", flush=True)
            _whisper_model = WhisperModel(model_size, device=device, compute_type="int8")
            print("[STT] faster-whisper hazır", flush=True)
        except Exception as e:
            print(f"[STT] faster-whisper yüklenemedi: {e}", flush=True)
            _whisper_model = None
    return _whisper_model


# ── Ses yakalama ───────────────────────────────────────────────────────────────

def _record_audio(device: int | None, rate: int) -> np.ndarray | None:
    """VAD ile ses kaydet. Başarısız olursa None döndür."""
    thresh = float(os.getenv("FRIDAY_STT_RMS", "200"))
    silence_sec = float(os.getenv("FRIDAY_STT_SILENCE_SEC", "0.65"))   # eskiden 1.2
    max_sec = float(os.getenv("FRIDAY_STT_MAX_SPEECH_SEC", "8.0"))
    chunk_secs = 0.2   # eskiden 0.3 — daha hızlı VAD döngüsü

    n_chunk = int(chunk_secs * rate)
    max_silence = int(silence_sec / chunk_secs)
    max_loops = int(max_sec / chunk_secs)

    frames: list[bytes] = []
    started = False
    silence_count = 0
    peak_rms = 0.0

    try:
        for _ in range(max_loops):
            data = sd.rec(n_chunk, samplerate=rate, channels=1, dtype="int16", device=device)
            sd.wait()
            flat = data.flatten()
            rms = float(np.sqrt(np.mean(flat.astype(np.float32) ** 2)))
            peak_rms = max(peak_rms, rms)

            if rms > thresh:
                started = True
                silence_count = 0
                frames.append(flat.tobytes())
            elif started:
                frames.append(flat.tobytes())
                silence_count += 1
                if silence_count >= max_silence:
                    break
    except Exception as e:
        print(f"[STT] kayıt hatası: {e}", flush=True)
        return None

    if not frames:
        print(f"[STT] ses algılanamadı peak_rms={peak_rms:.1f} thresh={thresh}", flush=True)
        return None

    raw = b"".join(frames)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    print(f"[STT] yakalandı chunks={len(frames)} peak_rms={peak_rms:.1f}", flush=True)

    # Hedef: 16000 Hz (Google STT + Whisper için)
    if rate != 16000:
        new_len = int(len(arr) * 16000 / rate)
        arr = np.interp(
            np.linspace(0, len(arr) - 1, new_len),
            np.arange(len(arr)), arr,
        )

    return arr.astype(np.int16)


def _transcribe_google(pcm16: np.ndarray) -> str:
    import speech_recognition as sr
    audio = sr.AudioData(pcm16.tobytes(), 16000, 2)
    text = sr.Recognizer().recognize_google(audio, language="tr-TR")
    return text


def _transcribe_whisper(pcm16: np.ndarray) -> str:
    model = _get_whisper()
    if model is None:
        raise RuntimeError("faster-whisper mevcut değil")
    float_arr = pcm16.astype(np.float32) / 32768.0
    segments, _ = model.transcribe(float_arr, language="tr", beam_size=2)
    return " ".join(s.text.strip() for s in segments).strip()


def get_preferred_mic() -> tuple[int | None, int]:
    """Public helper for voice pipelines that need the chosen mic."""
    return _find_best_mic()


def transcribe_once(
    device: int | None = None,
    rate: int | None = None,
) -> str | None:
    """Record one utterance and return Turkish text, or None on silence."""
    dev = device
    sample_rate = rate
    if sample_rate is None:
        dev, sample_rate = _find_best_mic() if device is None else (device, 16000)
    if sample_rate is None:
        sample_rate = 16000
    if dev is None and device is not None:
        dev = device

    pcm = _record_audio(dev, sample_rate)
    if pcm is None:
        return None
    text = _transcribe_whisper(pcm)
    return text.strip() or None


# ── QObject wrapper ────────────────────────────────────────────────────────────

class SttThread(QObject):
    """Mikrofon dinle → metne çevir → sonucu sinyal ile gönder."""

    result = Signal(str)
    error = Signal(str)
    listening = Signal(bool)
    rms_peak = Signal(float)    # UI'da mikrofon seviyesi göstermek için

    def __init__(self) -> None:
        super().__init__()
        self._thread: threading.Thread | None = None
        # Cihazı bir kez bul, tekrar sormaya gerek yok
        self._device, self._rate = _find_best_mic()

    def start(self) -> None:
        if self.isRunning():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        self.listening.emit(True)
        try:
            if self._device is None:
                self.error.emit("Mikrofon bulunamadı. Ses ayarlarını kontrol edin.")
                return

            pcm = _record_audio(self._device, self._rate)
            if pcm is None:
                self.error.emit("timeout")
                return

            # Direkt Whisper (Google STT endpoint bozuk)
            try:
                text = _transcribe_whisper(pcm)
                if text:
                    self.result.emit(text)
                else:
                    self.error.emit("Konuşma anlaşılamadı.")
            except Exception as w_err:
                print(f"[STT] Whisper başarısız: {w_err}", flush=True)
                self.error.emit("Konuşma anlaşılamadı.")

        except Exception as exc:
            print(f"[STT] genel hata: {exc!r}", flush=True)
            self.error.emit(str(exc))
        finally:
            self.listening.emit(False)
            self._thread = None
