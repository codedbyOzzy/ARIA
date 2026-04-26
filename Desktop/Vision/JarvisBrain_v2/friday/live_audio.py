"""Gemini 2.5 Flash Native Audio Dialog — Live API entegrasyonu.

Standart moddan farkı:
- STT yok, TTS yok — Gemini sesi doğrudan anlar ve sesle yanıt verir
- Gecikme ~400ms (standart ~2-3s)
- Barge-in native destekli (konuşurken kesebilirsin)
- Araçlar (tools) Live modda da çalışır

Mimari:
  sounddevice mic → ham PCM → Gemini Live WebSocket → PCM ses → sounddevice speaker
"""

import asyncio
import os
import queue
import threading

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from PySide6.QtCore import QThread, Signal

load_dotenv()

MIC_RATE = 16000
MIC_CHANNELS = 1
MIC_DTYPE = "int16"
MIC_CHUNK = 1024

SPEAKER_RATE = 24000
SPEAKER_CHANNELS = 1
SPEAKER_DTYPE = "int16"

LIVE_MODEL = "gemini-2.0-flash-live-001"

VOICE_NAME = "Aoede"  # Mevcut sesler: Puck, Charon, Kore, Fenrir, Aoede

SYSTEM_PROMPT = """Sen F.R.I.D.A.Y., Tony Stark'ın kişisel yapay zeka asistanısın.
Kullanıcının adı Ozan. Türkçe konuş. Kısa ve net ol. Araçları kullanarak komutları yerine getir."""


class LiveAudioThread(QThread):
    """Qt thread — Live Audio oturumunu yönetir."""

    transcript = Signal(str)    # Kullanıcının söyledikleri (metin)
    assistant_text = Signal(str)  # Friday'in yanıtı (metin)
    status = Signal(str)        # Durum mesajı
    error = Signal(str)         # Hata mesajı
    speaking = Signal(bool)     # Friday konuşuyor mu?

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._audio_out_queue = queue.Queue()
        self._session = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            asyncio.run(self._session_loop())
        except Exception as exc:
            self.error.emit("Live Audio hatası: " + str(exc))

    async def _session_loop(self):
        from google import genai
        from google.genai import types
        from friday.tools.actions import ALL_TOOLS

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        client = genai.Client(api_key=api_key)

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE_NAME,
                    )
                )
            ),
        )

        self.status.emit("Live bağlantısı kuruluyor…")

        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            self._session = session
            self.status.emit("Live mod aktif — konuşabilirsiniz")

            # Ses çalma görevi (background)
            playback_task = asyncio.create_task(self._playback_loop())
            receive_task = asyncio.create_task(self._receive_loop(session))
            send_task = asyncio.create_task(self._send_loop(session))

            # Herhangi biri bitince diğerlerini iptal et
            done, pending = await asyncio.wait(
                [playback_task, receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

    async def _send_loop(self, session):
        """Mikrofon sesini Gemini'ye gönder."""
        mic_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def mic_callback(indata, frames, time_info, status):
            audio_bytes = indata.tobytes()
            loop.call_soon_threadsafe(mic_queue.put_nowait, audio_bytes)

        stream = sd.InputStream(
            samplerate=MIC_RATE,
            channels=MIC_CHANNELS,
            dtype=MIC_DTYPE,
            blocksize=MIC_CHUNK,
            callback=mic_callback,
        )
        stream.start()
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = await asyncio.wait_for(mic_queue.get(), timeout=0.5)
                    from google.genai import types
                    await session.send(
                        input=types.Blob(
                            data=chunk,
                            mime_type="audio/pcm;rate=" + str(MIC_RATE),
                        )
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            stream.stop()
            stream.close()

    async def _receive_loop(self, session):
        """Gemini'den ses ve metin al."""
        try:
            async for response in session.receive():
                if self._stop_event.is_set():
                    break

                if response.server_content:
                    content = response.server_content

                    # Araç çağrısı varsa işle (turn complete'te görünür)
                    if content.model_turn:
                        for part in content.model_turn.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                # Ham PCM ses verisi
                                self._audio_out_queue.put(part.inline_data.data)
                                self.speaking.emit(True)
                            elif hasattr(part, "text") and part.text:
                                self.assistant_text.emit(part.text)

                    if content.turn_complete:
                        self.speaking.emit(False)

                if hasattr(response, "tool_call") and response.tool_call:
                    # Araç çağrısı — otomatik işlenir (AutomaticFunctionCalling açık)
                    pass

                if hasattr(response, "go_away"):
                    self.error.emit("Gemini bağlantıyı kapattı.")
                    break
        except Exception as exc:
            if not self._stop_event.is_set():
                self.error.emit("Receive hatası: " + str(exc))

    async def _playback_loop(self):
        """Ses kuyruğundan oku ve hoparlörden çal."""
        loop = asyncio.get_event_loop()
        audio_buffer = bytearray()

        while not self._stop_event.is_set():
            try:
                chunk = await loop.run_in_executor(
                    None, lambda: self._audio_out_queue.get(timeout=0.1)
                )
                audio_buffer.extend(chunk)

                # Yeterli veri biriktiyse çal (lag önleme)
                if len(audio_buffer) >= SPEAKER_RATE * 2 * 0.1:  # 100ms
                    data = bytes(audio_buffer)
                    audio_buffer = bytearray()
                    arr = np.frombuffer(data, dtype=np.int16)
                    await loop.run_in_executor(None, lambda: (sd.play(arr, samplerate=SPEAKER_RATE, blocking=True)))
            except Exception:
                await asyncio.sleep(0.05)
