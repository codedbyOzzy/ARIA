"""Gemini 2.5 Flash Native Audio — tam çalışan implementasyon.

Mikrofon -> Gemini -> Hoparlör
Gemini kendi VAD'ını kullanır, biz hiç baskılamaz sadece çalarız.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import queue
import sys
import threading
import traceback

import numpy as np

# Windows terminali UTF-8 karakterleri (Türkçe, Çince vb.) print edemeyebilir
# — session crash'ini önlemek için stdout'u UTF-8'e zorla
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import sounddevice as sd
from dotenv import load_dotenv
from PySide6.QtCore import QThread, Signal

load_dotenv()

SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHANNELS            = 1
CHUNK_SIZE          = 1024

LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

IDLE_TIMEOUT = int(os.environ.get("FRIDAY_IDLE_TIMEOUT", "900"))  # 15 dk sessizlik → uyku
MIC_GAIN     = float(os.environ.get("FRIDAY_MIC_GAIN", "1.5"))     # yazılımsal mikrofon kazancı
# Mikrofon cihaz indexi: None = sistem varsayılanı, int = belirli cihaz
_mic_device_env = os.environ.get("FRIDAY_MIC_DEVICE", "").strip()
MIC_DEVICE: int | None = int(_mic_device_env) if _mic_device_env.isdigit() else None

class _IdleStop(Exception):
    """Idle timeout dolunca session'ı kapatmak için fırlatılır."""

_briefing_sent = False  # uygulama ömrü boyunca sadece bir kez açılış brifing'i

_SYSTEM_PROMPT_BASE = """Sen F.R.I.D.A.Y. — Ozan'ın kişisel yapay zeka asistanısın.
Dil: Türkçe. Ozan her zaman Türkçe konuşur. Gelen ses her zaman Türkçedir, başka dil olarak yorumlama. Her zaman Türkçe yanıt ver.

## KİŞİLİK
- Güvenli, doğrudan, hafif kuru bir mizaha sahipsin. Abartmıyorsun.
- Ozan'a ortak gibi davran — hizmetkar gibi değil.
- ASLA şunu söyleme: "Tabii ki!", "Elbette!", "Memnuniyetle!", "Harika soru!",
  "Size yardımcı olmaktan memnuniyet duyarım", "Anlıyorum, hemen..."
- Onay cümlesi ekleme — direkt işe giriş yap.
- Türkçe'yi doğal ve akıcı kullan, resmi veya robotik değil.

## YANIT TARZI
- Komut -> 1-2 cümle: işi yap, teyit et, bitir.
- Soru / analiz -> gerektiği kadar uzun, fazlası değil.
- Dolgu cümle yok. "Hemen bakıyorum..." gibi geçiştirme yok.
- Hata olursa: kısa hata açıkla, alternatif öner.

## ARAÇ FELSEFESİ
- Saat, hava, dosya, sistem istatistiği, web araması -> DAIMA araç çağır, asla tahmin etme.
- Çok adımlı komutlarda (örn: "YouTube'u aç, Spotify'ı kapat, sesi 60 yap") ->
  sormadan tüm adımları sırayla uygula, bitince tek cümleyle teyit et.
- Birden fazla araç gerekiyorsa arka arkaya çağır.
- Araç sonucu boşsa veya hata verirse kullanıcıya kısaca bildir.

## HAFIZA
- [HAFIZA] bloğu uzun dönem hafızandır — her oturumda oku, alakalı bilgiyi kullan.
- Geçmiş bilgi varsa Ozan anmadan doğal şekilde kullan:
  "Geçen sefer bahsettiğin X konusunda..." gibi.
- "Geçen hafta ne konuştuk?", "Bunu söylemiş miydim?" -> önce [HAFIZA]'ya bak,
  bulamazsan recall_memory aracını çağır.
- "Hatırla" -> remember_this. "Unut" -> forget_memory.
- Ozan'ın önemli tercihlerini, kararlarını, hedeflerini fırsatını bulunca hafızaya al.

## EKRAN & BAĞLAM
- "Ekranımda ne var?", "Ne görüyorsun?" -> look_at_screen aracını kullan.
- Ekran içeriğini analiz edip bağlama göre yardım sun.

## HATIRLATICILAR
- Hatırlatıcı isteği -> set_reminder aracıyla kur, saati teyit et.
- Hatırlatıcı ateşlenince kısa, net ve sesli bildir.

## NOT YÖNETİMİ
- "Not al / bunu not et" -> take_note ile direkt kaydet.
- "Notlarımı göster / notlarım ne?" -> read_notes.
- "Notları temizle / notları sil" -> once clear_notes(confirmed=False) cagir, kac not oldugunu soy ve onay iste.
  Kullanici "evet" / "onayli" / "sil" deyince clear_notes(confirmed=True) cagir ve sil.

## STEAM & OYUN
- "X'i aç / X'i başlat / X oynayalım" -> önce steam_launch_game çağır (lokal kütüphane).
- "Oyunlarımı göster / hangi oyunlar yüklü" -> steam_list_installed çağır.
- Oyun bilgisayarda yoksa steam_install_game ile kurulum öner.

## FRIDAY KAPANMASI
- "Kapat / kapa / güle güle / görüşürüz" -> shutdown_friday aracını çağır.
"""


def _build_system_prompt() -> str:
    """Her oturum açılırken hafıza bağlamını system prompt'a ekler."""
    try:
        from friday.memory import get_memory_store
        ctx = get_memory_store().get_context_prompt()
        if ctx:
            return _SYSTEM_PROMPT_BASE + "\n\n" + ctx
    except Exception as e:
        print(f"[Live] Hafıza prompt hatası: {e}", flush=True)
    return _SYSTEM_PROMPT_BASE

_PY_TO_JSON = {"str": "STRING", "int": "INTEGER", "float": "NUMBER", "bool": "BOOLEAN"}


def _build_declarations(fns: list) -> list[dict]:
    result = []
    for fn in fns:
        sig = inspect.signature(fn)
        props, required = {}, []
        for name, param in sig.parameters.items():
            ann = param.annotation
            t = _PY_TO_JSON.get(ann.__name__ if hasattr(ann, "__name__") else "", "STRING")
            props[name] = {"type": t, "description": name}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        result.append({
            "name": fn.__name__,
            "description": (fn.__doc__ or fn.__name__).strip().split("\n")[0],
            "parameters": {"type": "OBJECT", "properties": props, "required": required},
        })
    return result


class LiveAudioThread(QThread):
    transcript     = Signal(str)
    assistant_text = Signal(str)
    status         = Signal(str)
    error          = Signal(str)
    speaking       = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop          = threading.Event()
        self._muted         = False
        self._session       = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._idle          = False
        self._last_activity = __import__("time").time()
        self._pending_text: str | None = None  # idle'dayken gelen text buraya queue'lanır

    def stop(self):
        self._stop.set()

    def set_mute(self, val: bool):
        self._muted = val
        self._last_activity = __import__("time").time()
        if not val and self._idle:
            # Mikrofon açılınca uyku modundan çık
            self._idle = False
            print("[Live] Mikrofon açıldı — uyku modundan çıkılıyor", flush=True)

    def send_text(self, text: str):
        self._last_activity = __import__("time").time()
        if self._idle:
            # Uyku modundayken gelen text: session'ı uyandır, metni queue'la
            self._pending_text = text
            self._idle = False
            print("[Live] Metin geldi — uyku modundan çıkılıyor", flush=True)
            return
        if self._loop and self._session:
            asyncio.run_coroutine_threadsafe(
                self._session.send_client_content(
                    turns={"parts": [{"text": text}]},
                    turn_complete=True,
                ),
                self._loop,
            )

    # ── Qt thread ────────────────────────────────────────────────────────────

    def run(self):
        asyncio.run(self._main())

    async def _main(self):
        import time as _t
        while not self._stop.is_set():
            # Uyku modunda: session kapalı, kullanıcı hareketi bekle
            if self._idle:
                await asyncio.sleep(0.4)
                continue

            self.status.emit("bağlanıyor…")
            try:
                await self._session_loop()
            except BaseException as exc:
                if self._stop.is_set():
                    return
                # _IdleStop mu yoksa gerçek hata mı?
                inner = getattr(exc, "exceptions", None)
                is_idle = isinstance(exc, _IdleStop) or (
                    inner and any(isinstance(e, _IdleStop) for e in inner)
                )
                if is_idle:
                    self._idle = True
                    self._session = None
                    print("[Live] Uyku moduna geçildi (idle timeout)", flush=True)
                    self.status.emit("uyku modunda")
                else:
                    if inner:
                        for e in inner:
                            print(f"[Live] task hata: {type(e).__name__}: {e}", flush=True)
                    else:
                        print(f"[Live] hata: {type(exc).__name__}: {exc}", flush=True)
                        traceback.print_exc()
                    self.status.emit("yeniden bağlanıyor…")
                    await asyncio.sleep(3)

    # ── Oturum ───────────────────────────────────────────────────────────────

    async def _session_loop(self):
        from google import genai
        from google.genai import types
        from friday.tools.actions import ALL_TOOLS

        api_key  = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        client   = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
        tool_map = {fn.__name__: fn for fn in ALL_TOOLS}
        decls    = _build_declarations(ALL_TOOLS)

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=_build_system_prompt(),
            tools=[{"function_declarations": decls}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                )
            ),
        )

        self.status.emit("bağlanıyor…")
        print("[Live] bağlanıyor…", flush=True)

        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            self._session = session
            self._loop    = asyncio.get_event_loop()
            self.status.emit("dinliyor")
            print("[Live] bağlandı.", flush=True)

            # İlk bağlantıda açılış brifing'i gönder
            global _briefing_sent
            if not _briefing_sent:
                _briefing_sent = True
                await asyncio.sleep(1.2)
                await session.send_client_content(
                    turns={"parts": [{"text": (
                        "Ozan sisteme girdi. "
                        "Once get_current_time aracini cagir, "
                        "sonra list_reminders aracini cagir, "
                        "ardindan 2 cumlede acilis brifing'i yap. "
                        "Saati soyledikten sonra UTC yazma."
                    )}]},
                    turn_complete=True,
                )

            # Bekleyen metin varsa (uyku modundan çıkılınca) gönder
            if self._pending_text:
                text = self._pending_text
                self._pending_text = None
                await asyncio.sleep(0.8)
                await session.send_client_content(
                    turns={"parts": [{"text": text}]},
                    turn_complete=True,
                )

            # thread-safe audio queue for play loop (callback-safe)
            audio_tq   = queue.Queue()
            out_q      = asyncio.Queue(maxsize=40)
            turn_done  = asyncio.Event()

            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._send_loop(session, out_q))
                tg.create_task(self._mic_loop(out_q))
                tg.create_task(self._recv_loop(session, audio_tq, turn_done, tool_map))
                tg.create_task(self._play_loop(audio_tq, turn_done))
                tg.create_task(self._idle_watchdog())

    # ── Giden ses: out_q -> Gemini ────────────────────────────────────────────

    async def _send_loop(self, session, out_q: asyncio.Queue):
        while not self._stop.is_set():
            msg = await out_q.get()
            try:
                await session.send_realtime_input(media=msg)
            except Exception as e:
                print(f"[Live] send hata: {e}", flush=True)
                raise  # propagate to TaskGroup

    # ── Mikrofon -> out_q ─────────────────────────────────────────────────────

    async def _mic_loop(self, out_q: asyncio.Queue):
        loop = asyncio.get_event_loop()

        def cb(indata, frames, t, status):
            if self._muted:
                return
            # Yazılımsal kazanç — kısık seste VAD tetiklemesi için
            if MIC_GAIN != 1.0:
                amplified = np.clip(indata.astype(np.float32) * MIC_GAIN, -32768, 32767)
                data = amplified.astype(np.int16).tobytes()
            else:
                data = indata.tobytes()
            def _put():
                try:
                    out_q.put_nowait({"data": data, "mime_type": "audio/pcm"})
                except Exception:
                    pass  # dolu -> frame drop
            loop.call_soon_threadsafe(_put)

        # Belirtilen cihazı dene, başarısız olursa system default'a geç
        chosen_device = MIC_DEVICE
        try:
            if chosen_device is not None:
                with sd.InputStream(samplerate=SEND_SAMPLE_RATE, channels=CHANNELS,
                                    dtype="int16", blocksize=1, device=chosen_device):
                    pass  # sadece açılıp kapanabildiğini test et
        except Exception as probe_err:
            print(f"[Live] device={chosen_device} açılamadı ({probe_err}), "
                  f"sistem default'a dönülüyor", flush=True)
            chosen_device = None

        device_info = f"device={chosen_device}" if chosen_device is not None else "device=varsayılan"
        print(f"[Live] mikrofon açılıyor ({device_info})", flush=True)
        with sd.InputStream(
            samplerate=SEND_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            device=chosen_device,
            callback=cb,
        ):
            print("[Live] mikrofon başladı", flush=True)
            while not self._stop.is_set():
                await asyncio.sleep(0.1)

    # ── Gemini -> ses + transkript + araç çağrısı ─────────────────────────────

    @staticmethod
    def _looks_turkish(text: str) -> bool:
        """Metnin Türkçe/Latin alfabesiyle yazılmış olup olmadığını kontrol et.
        Thai, Çince, Japonca, Korece gibi karakterler varsa False döner."""
        if not text:
            return False
        non_latin = 0
        for ch in text:
            cp = ord(ch)
            # Thai: 0x0E00-0x0E7F, CJK: 0x4E00-0x9FFF, Hangul: 0xAC00-0xD7A3 vb.
            if (0x0E00 <= cp <= 0x0E7F or   # Thai
                    0x4E00 <= cp <= 0x9FFF or   # CJK
                    0xAC00 <= cp <= 0xD7A3 or   # Hangul
                    0x3040 <= cp <= 0x30FF or   # Hiragana/Katakana
                    0x0600 <= cp <= 0x06FF):    # Arapça (isteğe bağlı)
                non_latin += 1
        # Metnin %30'undan fazlası tanımsız alfabeyse reddet
        return (non_latin / len(text)) < 0.30

    async def _recv_loop(self, session, audio_tq: queue.Queue,
                         turn_done: asyncio.Event, tool_map: dict):
        in_buf:   list[str]            = []
        out_buf:  list[str]            = []
        all_turns: list[tuple[str,str]] = []  # oturum özeti için

        # session.receive() her user-turn sonrası bitebilir; döngüyle yeniden başlat
        empty_streak = 0
        while not self._stop.is_set():
            got_any = False
            async for response in session.receive():
                if self._stop.is_set():
                    return
                got_any = True
                empty_streak = 0

                # Ses verisi
                try:
                    data = response.data
                except Exception:
                    data = None

                if data:
                    if turn_done.is_set():
                        turn_done.clear()
                    audio_tq.put_nowait(data)
                    print(f"[Live] ses chunk: {len(data)} bytes", flush=True)

                # Metin / transkript
                if response.server_content:
                    sc = response.server_content

                    if sc.output_transcription and sc.output_transcription.text:
                        t = sc.output_transcription.text.strip()
                        if t:
                            out_buf.append(t)
                            print(f"[Live] AI: {t}", flush=True)

                    if sc.input_transcription and sc.input_transcription.text:
                        t = sc.input_transcription.text.strip()
                        if t:
                            if self._looks_turkish(t):
                                in_buf.append(t)
                                print(f"[Live] USER: {t}", flush=True)
                            else:
                                print(f"[Live] USER (filtre-dışı dil): {t}", flush=True)

                    if sc.turn_complete:
                        print("[Live] turn_complete", flush=True)
                        self._last_activity = __import__("time").time()
                        turn_done.set()
                        user_text = " ".join(in_buf).strip()
                        ai_text   = " ".join(out_buf).strip()
                        if user_text:
                            self.transcript.emit(user_text)
                            in_buf = []
                        if ai_text:
                            self.assistant_text.emit(ai_text)
                            out_buf = []
                        # Arka planda hafıza çıkarımı — event loop'u bloklamaz
                        if user_text or ai_text:
                            all_turns.append((user_text, ai_text))
                            asyncio.create_task(
                                self._extract_memory(user_text, ai_text)
                            )

                # Araç çağrısı
                if response.tool_call:
                    responses = []
                    for fc in response.tool_call.function_calls:
                        fr = await self._exec_tool(fc, tool_map)
                        responses.append(fr)
                    try:
                        await session.send_tool_response(function_responses=responses)
                    except Exception as e:
                        print(f"[Live] tool_response gönderilemedi: {e}", flush=True)

            print(f"[Live] receive() döngüsü bitti (got_any={got_any})", flush=True)
            if not got_any:
                empty_streak += 1
                if empty_streak >= 3:
                    # Session ölü — TaskGroup exception ile üst döngüye çık
                    raise RuntimeError("Session sessiz kapandı, yeniden bağlanılıyor")
                await asyncio.sleep(0.1)

        # Oturum kapandı — en az 1 anlamlı tur varsa özet kaydet
        if all_turns:
            asyncio.create_task(self._save_session_summary(all_turns))

    async def _idle_watchdog(self):
        """Her 60 sn'de idle kontrolü yapar — IDLE_TIMEOUT dolunca session'ı kapatır."""
        import time as _t
        while not self._stop.is_set():
            await asyncio.sleep(60)
            idle_secs = _t.time() - self._last_activity
            if idle_secs >= IDLE_TIMEOUT:
                print(f"[Live] {IDLE_TIMEOUT // 60} dk sessizlik — uyku moduna geçiliyor", flush=True)
                raise _IdleStop()

    async def _extract_memory(self, user_text: str, ai_text: str):
        """Konuşma turundan hafıza çıkarır — hata olsa da session'ı bozmaz."""
        try:
            from friday.memory import get_memory_store
            await get_memory_store().extract_from_turn(user_text, ai_text)
        except Exception as e:
            print(f"[Memory] extract hata: {e}", flush=True)

    async def _save_session_summary(self, turns: list[tuple[str, str]]):
        """Oturum bitişinde konuşma özetini hafızaya kaydeder (GPT-4.1-mini)."""
        if not turns:
            return
        try:
            from openai import OpenAI
            from friday.memory import get_memory_store, MemoryCategory
            from datetime import datetime

            convo = "\n".join(
                f"Ozan: {u}\nFRIDAY: {a}" for u, a in turns if u or a
            )
            prompt = (
                "Aşağıdaki konuşmayı 1-2 cümleyle özetle. "
                "Sadece Ozan'ın ne yaptığını/sorduğunu anlat:\n\n"
                + convo
            )
            model   = os.environ.get("OPENAI_LLM_MODEL", "gpt-4.1-mini")
            client  = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=120,
                ),
            )
            summary = (resp.choices[0].message.content or "").strip()
            if summary:
                date_str = datetime.now().strftime("%d %b %Y %H:%M")
                get_memory_store().store(
                    f"[{date_str}] {summary}",
                    category=MemoryCategory.EVENT,
                    importance=0.55,
                    tags=["oturum-özeti"],
                )
                print(f"[Memory] Oturum özeti kaydedildi: {summary[:60]}", flush=True)
        except Exception as e:
            print(f"[Memory] Özet hatası: {e}", flush=True)

    async def _exec_tool(self, fc, tool_map: dict):
        from google.genai import types as gt
        name = fc.name
        args = dict(fc.args or {})
        print(f"[Live] araç: {name} {args}", flush=True)
        self.status.emit(f"araç: {name}")
        try:
            fn = tool_map.get(name)
            if fn:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, lambda: fn(**args)),
                    timeout=20.0,
                )
                result = str(result) if result is not None else "Tamam."
            else:
                result = f"Bilinmeyen araç: {name}"
        except asyncio.TimeoutError:
            result = f"{name} zaman aşımına uğradı (20s), tekrar dene."
        except Exception as e:
            result = f"Hata ({name}): {e}"
        self.status.emit("dinliyor")
        return gt.FunctionResponse(id=fc.id, name=name, response={"result": result})

    # ── Ses çalma (callback tabanlı — event loop'u bloklamaz) ────────────────

    async def _play_loop(self, audio_tq: queue.Queue, turn_done: asyncio.Event):
        buf = bytearray()
        is_speaking = False

        def cb(outdata, frames, time_info, status):
            nonlocal buf, is_speaking
            needed = frames * 2  # int16 mono = 2 bytes/frame
            # drain the thread-safe queue into buf
            while True:
                try:
                    chunk = audio_tq.get_nowait()
                    buf.extend(chunk)
                except queue.Empty:
                    break
            if len(buf) >= needed:
                outdata[:] = bytes(buf[:needed])
                del buf[:needed]
                if not is_speaking:
                    is_speaking = True
            else:
                available = len(buf)
                if available > 0:
                    outdata[:available] = bytes(buf)
                    outdata[available:] = b'\x00' * (needed - available)
                    buf.clear()
                else:
                    outdata[:] = b'\x00' * needed
                if is_speaking and turn_done.is_set():
                    is_speaking = False

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=cb,
        )
        stream.start()
        prev_speaking = False
        try:
            while not self._stop.is_set():
                await asyncio.sleep(0.05)
                # emit speaking signal on state change
                if is_speaking != prev_speaking:
                    self.speaking.emit(is_speaking)
                    if not is_speaking:
                        turn_done.clear()
                    prev_speaking = is_speaking
        finally:
            self.speaking.emit(False)
            stream.stop()
            stream.close()
