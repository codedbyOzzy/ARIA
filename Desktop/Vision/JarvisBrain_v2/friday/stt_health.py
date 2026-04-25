from __future__ import annotations

import time
import urllib.request

from blackbox import log_event


def probe_pyaudio() -> tuple[bool, str]:
    """Check whether PyAudio is installed and has input devices."""
    try:
        import pyaudio  # type: ignore

        pa = pyaudio.PyAudio()
        count = pa.get_device_count()
        pa.terminate()
        if count == 0:
            return False, "PyAudio kurulu ama mikrofon cihazı bulunamadı"
        return True, "ok"
    except ImportError:
        return False, "PyAudio kurulu değil"
    except Exception as exc:
        return False, f"PyAudio hata: {exc}"


def probe_sounddevice() -> tuple[bool, str]:
    """Check whether sounddevice is available with at least one input."""
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        inputs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        if not inputs:
            return False, "sounddevice kurulu ama input cihazı bulunamadı"
        return True, "ok"
    except ImportError:
        return False, "sounddevice kurulu değil"
    except Exception as exc:
        return False, f"sounddevice hata: {exc}"


def probe_google_stt() -> tuple[bool, str]:
    """Basic internet reachability check for Google STT path."""
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)  # nosec B310
        return True, "ok"
    except Exception as exc:
        return False, f"Google STT erişim hatası: {exc}"


def _recommend(pyaudio_ok: bool, sounddevice_ok: bool, google_ok: bool) -> str | None:
    if pyaudio_ok and google_ok:
        return "pyaudio+google"
    if sounddevice_ok and google_ok:
        return "sounddevice+google"
    if sounddevice_ok:
        return "sounddevice+offline"
    return None


def run_health_check() -> dict:
    """Probe STT backends and return recommended route."""
    pyaudio_ok, pyaudio_msg = probe_pyaudio()
    sounddevice_ok, sd_msg = probe_sounddevice()
    google_ok, google_msg = probe_google_stt()

    result = {
        "pyaudio": {"ok": pyaudio_ok, "msg": pyaudio_msg},
        "sounddevice": {"ok": sounddevice_ok, "msg": sd_msg},
        "google_stt": {"ok": google_ok, "msg": google_msg},
        "recommended": _recommend(pyaudio_ok, sounddevice_ok, google_ok),
        "ts": time.time(),
    }

    if not result["recommended"]:
        log_event(
            "stt_no_backend",
            level="critical",
            pyaudio=pyaudio_msg,
            sounddevice=sd_msg,
            google=google_msg,
        )
    else:
        log_event("stt_health_ok", level="info", recommended=result["recommended"])
    return result
