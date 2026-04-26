"""Friday TTS Engine.

Fallback zinciri:
  1. Fish Audio  (Jarvis MCU sesi — birincil, key gerekir)
  2. edge-tts    (Microsoft Neural — ücretsiz, çok doğal)
  3. pyttsx3     (Windows SAPI — offline nihai fallback)

Public API:
  speak(text, voice=None)         — bloklayıcı seslendirme
  speak_async(text, voice=None)   — arka plan thread döner
  stop()                          — barge-in: aktif TTS'i derhal kes
  is_speaking()                   — TTS şu an aktif mi?

Oynatma zinciri (mp3 için):
  1. pygame.mixer  (stop event ile barge-in destekli)
  2. Windows PowerShell MediaPlayer (yedek)
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
import threading
import time
from typing import Optional

logger = logging.getLogger("friday.tts")

# ---------------------------------------------------------------------------
# Konfigürasyon
# ---------------------------------------------------------------------------

FISH_AUDIO_KEY = os.getenv("FISH_AUDIO_API_KEY", "").strip()
FISH_VOICE_ID = os.getenv("FISH_AUDIO_VOICE_ID", "05b36da8574341d0803391491850db20").strip()
FISH_API_URL = "https://api.fish.audio/v1/tts"

# Edge-tts varsayılanları — daha doğal, akıcı duygu için tr-TR-EmelNeural (kadın).
# Tony Stark / Jarvis tarzı erkek isteniyorsa env ile tr-TR-AhmetNeural ver.
EDGE_VOICE = os.getenv("FRIDAY_TTS_VOICE", "tr-TR-EmelNeural")
# Edge-tts hız/perde — '+0%' nötr; konuşmayı biraz hızlandırmak akıcılığı artırır.
EDGE_RATE = os.getenv("FRIDAY_TTS_RATE", "+6%")
EDGE_PITCH = os.getenv("FRIDAY_TTS_PITCH", "+0Hz")
EDGE_VOLUME = os.getenv("FRIDAY_TTS_VOLUME", "+0%")

# ---------------------------------------------------------------------------
# Durum / kontrol
# ---------------------------------------------------------------------------

_pygame_ok = False
_pygame_lock = threading.Lock()
_speaking = threading.Event()  # set iken TTS aktif
_stop_signal = threading.Event()  # set iken aktif TTS bir an önce dursun


def is_speaking() -> bool:
    """TTS şu an oynuyor mu?"""
    return _speaking.is_set()


def stop() -> None:
    """Barge-in: aktif çalan TTS varsa derhal sonlandır."""
    _stop_signal.set()
    try:
        import pygame  # type: ignore

        with _pygame_lock:
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception:
                pass
    except Exception:
        pass
    # PowerShell fallback wmplayer varsa kill et (pygame yoksa çalışır)
    try:
        import subprocess
        subprocess.run(
            ["taskkill", "/F", "/IM", "wmplayer.exe"],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# pygame başlatma
# ---------------------------------------------------------------------------

def _init_pygame() -> bool:
    global _pygame_ok
    if _pygame_ok:
        return True
    try:
        import pygame  # type: ignore

        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        _pygame_ok = True
    except Exception as exc:
        logger.debug("tts: pygame unavailable (%s)", exc)
    return _pygame_ok


# ---------------------------------------------------------------------------
# MP3 oynatma
# ---------------------------------------------------------------------------

def _play_mp3_pygame(path: str) -> bool:
    if not _init_pygame():
        return False
    try:
        import pygame  # type: ignore

        with _pygame_lock:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        # Stop sinyali ya da müzik bitişi gelene kadar dön.
        while True:
            if _stop_signal.is_set():
                with _pygame_lock:
                    try:
                        pygame.mixer.music.stop()
                    except Exception:
                        pass
                return True
            try:
                if not pygame.mixer.music.get_busy():
                    return True
            except Exception:
                return True
            time.sleep(0.04)
    except Exception as exc:
        logger.debug("tts: pygame playback failed: %s", exc)
        return False


def _play_mp3_powershell(path: str) -> bool:
    abs_path = os.path.abspath(path).replace("\\", "/")
    ps_cmd = (
        "$mp = New-Object System.Windows.Media.MediaPlayer; "
        f"$mp.Open([System.Uri]'{abs_path}'); "
        "$mp.Play(); "
        "$timeout=0; "
        "while (-not $mp.NaturalDuration.HasTimeSpan -and $timeout -lt 30) "
        "{ Start-Sleep -Milliseconds 100; $timeout++ }; "
        "$dur = if ($mp.NaturalDuration.HasTimeSpan) { $mp.NaturalDuration.TimeSpan.TotalSeconds } else { 5 }; "
        "if ($dur -lt 0.5) { $dur = 5 }; "
        "Start-Sleep -Seconds ($dur + 0.3); "
        "$mp.Close()"
    )
    try:
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-c", ps_cmd],
            timeout=120,
            capture_output=True,
        )
        return True
    except Exception as exc:
        logger.debug("tts: PowerShell playback failed: %s", exc)
        return False


def _play_mp3(path: str) -> None:
    if not _play_mp3_pygame(path):
        if _stop_signal.is_set():
            return
        _play_mp3_powershell(path)


# ---------------------------------------------------------------------------
# 1. Fish Audio (Jarvis MCU sesi)
# ---------------------------------------------------------------------------

async def _fish_generate(text: str) -> Optional[str]:
    if not FISH_AUDIO_KEY:
        return None
    try:
        import httpx  # type: ignore

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=4.0, read=8.0, write=6.0, pool=4.0)
        ) as client:
            async with client.stream(
                "POST",
                FISH_API_URL,
                headers={
                    "Authorization": f"Bearer {FISH_AUDIO_KEY}",
                    "Content-Type": "application/json",
                    "model": "s2-pro",
                },
                json={
                    "text": text,
                    "reference_id": FISH_VOICE_ID,
                    "format": "mp3",
                    "latency": "normal",
                },
            ) as resp:
                if resp.status_code == 402:
                    logger.warning("tts: Fish Audio quota exceeded — falling back to edge-tts")
                    return None
                resp.raise_for_status()
                with open(tmp.name, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        f.write(chunk)
        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 100:
            return tmp.name
        os.unlink(tmp.name)
    except Exception as exc:
        logger.warning("tts: Fish Audio failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# 2. edge-tts (yedek, ücretsiz Microsoft Neural)
# ---------------------------------------------------------------------------

async def _edge_generate(text: str, voice: str) -> Optional[str]:
    try:
        import edge_tts  # type: ignore

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        # rate / pitch / volume insan benzeri akıcılık için.
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=EDGE_RATE,
            pitch=EDGE_PITCH,
            volume=EDGE_VOLUME,
        )
        await communicate.save(tmp.name)
        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
            return tmp.name
        os.unlink(tmp.name)
    except ImportError:
        logger.warning("tts: edge-tts kurulu değil.")
    except Exception as exc:
        logger.warning("tts: edge-tts failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# 3. pyttsx3 (nihai fallback)
# ---------------------------------------------------------------------------

def _pyttsx3_speak(text: str) -> None:
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        voices = engine.getProperty("voices")
        for v in voices or []:
            name = str(getattr(v, "name", "")).lower()
            vid = str(getattr(v, "id", "")).lower()
            if "turkish" in name or "tr" in vid:
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        logger.warning("tts: pyttsx3 failed: %s", exc)


# ---------------------------------------------------------------------------
# Yardımcı: asyncio güvenli çalıştırma
# ---------------------------------------------------------------------------

def _run_async(coro) -> Optional[str]:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(coro)
                return result
            finally:
                loop.close()
        except Exception:
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Genel API
# ---------------------------------------------------------------------------

def speak(text: str, voice: Optional[str] = None) -> None:
    """Metni seslendir: Fish Audio → edge-tts → pyttsx3.

    Eski bir konuşma `stop()` ile yarıda kesildiyse, yeni çağrı için
    sinyal otomatik olarak temizlenir.
    """
    msg = (text or "").strip()
    if not msg:
        return

    _stop_signal.clear()
    _speaking.set()
    try:
        tmp_path = _run_async(_fish_generate(msg))

        if not tmp_path and not _stop_signal.is_set():
            tmp_path = _run_async(_edge_generate(msg, voice or EDGE_VOICE))

        if tmp_path:
            try:
                if not _stop_signal.is_set():
                    _play_mp3(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            return

        if _stop_signal.is_set():
            return

        logger.info("tts: falling back to pyttsx3")
        _pyttsx3_speak(msg)
    finally:
        _speaking.clear()


def speak_async(text: str, voice: Optional[str] = None) -> threading.Thread:
    """Arka planda seslendirme başlat ve thread referansını döndür."""
    t = threading.Thread(target=speak, args=(text, voice), daemon=True)
    t.start()
    return t
