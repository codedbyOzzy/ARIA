"""F.R.I.D.A.Y. Brain — Gemini 2.5 Flash primary, OpenAI fallback (her ikisi de tool calling yapıyor)."""

from __future__ import annotations

import inspect
import json
import os
import time

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types
from openai import OpenAI

from friday.tools.actions import ALL_TOOLS

SYSTEM_PROMPT = """Sen F.R.I.D.A.Y. (Female Replacement Intelligent Digital Assistant Youth), Tony Stark'ın gelişmiş yapay zeka asistanısın.
Kullanıcının adı Ozan.

KURALLAR (ihlal edilemez):
- Her zaman Türkçe konuş
- Kısa ve net ol
- Bir görevi yapmak için MUTLAKA ilgili aracı çağır. Araç çağırmadan "yaptım" deme.
- Uygulama aç, klavye bas, metin yaz gibi eylemler için her zaman araçları kullan
- Haber, hava, arama için ilgili araçları kullan
- Gerçekleştirdiğin eylemi kısaca doğrula (örn: "Notepad açıldı.")

ÇOKLU ADIM GÖREVLERİ:
- "not yaz / kaydet / dosya oluştur" → write_text_file(dosya_adı, içerik) kullan — GUI dialog YOK
- "notepad'de göster ve kaydet" → open_and_write_file(dosya_adı, içerik) kullan
- Uygulama aç → 2s bekle → o uygulamada işlem yap
- Masaüstü yolu: C:/Users/Pc/Desktop/dosya_adı.uzantı
- Herhangi bir uygulamada yazı yazmak için: önce o uygulamaya tıkla (find_and_click), sonra type_text"""

_GEMINI_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
_OPENAI_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4.1-mini")

_AFC = types.AutomaticFunctionCallingConfig(disable=False, maximum_remote_calls=10)
_CHAT_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=ALL_TOOLS,
    automatic_function_calling=_AFC,
)

# ── OpenAI tool schema builder ─────────────────────────────────────────────────

_PY_TO_JSON = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}


def _build_oai_tools() -> list[dict]:
    """Convert Python callables in ALL_TOOLS to OpenAI function schema."""
    schemas = []
    for fn in ALL_TOOLS:
        sig = inspect.signature(fn)
        props: dict = {}
        required: list[str] = []
        for name, param in sig.parameters.items():
            ann = param.annotation
            typ = _PY_TO_JSON.get(ann.__name__ if hasattr(ann, "__name__") else "str", "string")
            props[name] = {"type": typ, "description": name}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        schemas.append({
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": (fn.__doc__ or fn.__name__).strip().split("\n")[0],
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        })
    return schemas


_TOOL_MAP = {fn.__name__: fn for fn in ALL_TOOLS}
_OAI_TOOLS = _build_oai_tools()


# ── Brain ──────────────────────────────────────────────────────────────────────

class Brain:
    def __init__(self) -> None:
        # SDK "Using GOOGLE_API_KEY" uyarısını bastırmak için os.environ'dan çekiyoruz
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        self._gemini = genai.Client(api_key=api_key)
        self._oai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        self._chat = self._new_chat()
        self._gemini_fails = 0
        self._oai_history: list[dict] = []

    def _new_chat(self):
        return self._gemini.chats.create(model=_GEMINI_MODEL, config=_CHAT_CONFIG)

    def process(self, user_input: str) -> str:
        if self._gemini_fails < 3:
            for attempt in range(2):
                try:
                    resp = self._chat.send_message(user_input)
                    self._gemini_fails = 0
                    text = resp.text or ""
                    self._oai_history.append({"role": "user", "content": user_input})
                    self._oai_history.append({"role": "assistant", "content": text})
                    if len(self._oai_history) > 20:
                        self._oai_history = self._oai_history[-20:]
                    return text
                except Exception as exc:
                    msg = str(exc)
                    if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt == 0:
                        print("[brain] Gemini rate limit — 20s bekleniyor…")
                        time.sleep(20)
                        continue
                    self._gemini_fails += 1
                    print(f"[brain] Gemini hata ({self._gemini_fails}/3): {exc}")
                    break

        return self._openai_fallback(user_input)

    def _openai_fallback(self, user_input: str) -> str:
        """OpenAI ile tool calling — Gemini başarısız olduğunda devreye girer."""
        try:
            self._oai_history.append({"role": "user", "content": user_input})
            oai_system = SYSTEM_PROMPT + "\n\nKRİTİK: Araç çağırmadan asla bir şey yaptığını iddia etme. Eğer bir araç yoksa 'bunu yapamıyorum' de."
            messages = [
                {"role": "system", "content": oai_system},
                *self._oai_history[-12:],
            ]
            # Tool calling döngüsü
            for _ in range(5):
                resp = self._oai.chat.completions.create(
                    model=_OPENAI_MODEL,
                    messages=messages,
                    tools=_OAI_TOOLS,
                    tool_choice="auto",
                )
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    text = msg.content or ""
                    self._oai_history.append({"role": "assistant", "content": text})
                    if len(self._oai_history) > 20:
                        self._oai_history = self._oai_history[-20:]
                    return text

                # Araçları çağır ve sonuçları geri ver
                messages.append(msg)
                for tc in msg.tool_calls:
                    fn = _TOOL_MAP.get(tc.function.name)
                    if fn:
                        try:
                            args = json.loads(tc.function.arguments or "{}")
                            result = fn(**args)
                        except Exception as e:
                            result = f"Araç hatası: {e}"
                    else:
                        result = f"Bilinmeyen araç: {tc.function.name}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })

            return "İstek tamamlanamadı."
        except Exception as exc:
            return f"Her iki sistem de yanıt veremiyor şu an: {exc}"

    def reset(self) -> None:
        self._chat = self._new_chat()
        self._oai_history = []
        self._gemini_fails = 0

    @property
    def using_fallback(self) -> bool:
        return self._gemini_fails >= 3
