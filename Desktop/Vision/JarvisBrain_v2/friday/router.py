"""Safe, flag-driven local text router.

Modes:
- off: current API path only
- shadow: current API answer is used, local model is probed in background only
- auto: use local only for short, non-action, non-web text queries
- force_local: always try local first, then fall back to API
"""

from __future__ import annotations

import os
import re
import threading
from typing import Any, Iterator

from friday.brain import Brain
from friday.local_llm import LocalLLMClient

_MODE_OFF = "off"
_MODE_SHADOW = "shadow"
_MODE_AUTO = "auto"
_MODE_FORCE = "force_local"
_VALID_MODES = {_MODE_OFF, _MODE_SHADOW, _MODE_AUTO, _MODE_FORCE}

_RISKY_PATTERNS = (
    "sil",
    "shutdown",
    "yeniden baslat",
    "process oldur",
    "geri donusum",
    "kill process",
)
_WEB_PATTERNS = ("haber", "hava", "bugun", "guncel", "son durum")
_VISION_PATTERNS = ("ekranda", "ne goruyorsun", "butonu bul", "ekrana bak")
_ACTION_HINTS = (
    "ac",
    "kapat",
    "saat",
    "ses",
    "not al",
    "hatirlat",
    "spotify",
    "youtube",
    "chrome",
    "discord",
)


class SafeBrainRouter:
    """Drop-in replacement for the current Brain with safe local routing."""

    def __init__(
        self,
        api_brain: Any | None = None,
        local_client: Any | None = None,
    ) -> None:
        self._api_brain = api_brain if api_brain is not None else Brain()
        self._local = local_client if local_client is not None else LocalLLMClient()

    def process(self, user_input: str) -> str:
        mode = self._mode()
        if mode == _MODE_OFF:
            return self._api_brain.process(user_input)

        if mode == _MODE_SHADOW:
            self._spawn_shadow_probe(user_input)
            return self._api_brain.process(user_input)

        if mode == _MODE_FORCE:
            return self._local_first(user_input, forced=True)

        if self._should_try_local(user_input) and self._local.healthcheck():
            return self._local_first(user_input, forced=False)

        return self._api_brain.process(user_input)

    def stream_process(self, user_input: str) -> Iterator[str]:
        """Cevabı cümle bazlı yield eder — lokal path veya API fallback (tek chunk).

        LocalVoiceThread bu generator'ı tüketir; her cümleyi TTS'e gönderir.
        Yerel model uygun değilse API'den tam cevabı tek chunk olarak verir.
        """
        mode = self._mode()
        use_local = (
            mode not in (_MODE_OFF, _MODE_SHADOW)
            and (mode == _MODE_FORCE or self._should_try_local(user_input))
            and self._local.healthcheck()
        )

        if use_local:
            yielded_any = False
            try:
                for sentence in self._local.stream_chat(user_input):
                    yielded_any = True
                    yield sentence
                if yielded_any:
                    return
                print("[router] stream_chat boş döndü, API fallback.", flush=True)
            except Exception as exc:
                print(f"[router] stream hatası: {exc}", flush=True)
                if yielded_any:
                    return  # kısmi cevap zaten verildi

        # API fallback — tek chunk
        try:
            resp = self._api_brain.process(user_input)
            yield resp
        except Exception as exc:
            print(f"[router] API hatası: {exc}", flush=True)

    def reset(self) -> None:
        self._api_brain.reset()
        self._local.reset()

    def warm_local_if_enabled(self) -> None:
        mode = self._mode()
        if mode == _MODE_OFF:
            return
        if not self._local.healthcheck(force=True):
            print("[router] Yerel endpoint hazir degil, warmup atlandi.", flush=True)
            return
        start_keepalive = getattr(self._local, "start_keepalive", None)
        if callable(start_keepalive):
            start_keepalive()

    def shutdown(self) -> None:
        shutdown = getattr(self._local, "shutdown", None)
        if callable(shutdown):
            shutdown()

    @property
    def using_fallback(self) -> bool:
        return self._api_brain.using_fallback

    def _local_first(self, user_input: str, forced: bool) -> str:
        try:
            text = self._local.chat(user_input, allow_tools=False)
            if text.strip():
                print(
                    f"[router] Yerel model cevabi kullanildi (forced={forced}).",
                    flush=True,
                )
                return text
            print("[router] Yerel model bos cevap verdi, API'ye dusuluyor.", flush=True)
        except Exception as exc:
            print(f"[router] Yerel model hatasi, API'ye dusuluyor: {exc}", flush=True)
        return self._api_brain.process(user_input)

    def _spawn_shadow_probe(self, user_input: str) -> None:
        def _probe() -> None:
            if not self._local.healthcheck():
                print("[shadow] Yerel endpoint ulasilamiyor, probe atlandi.", flush=True)
                return
            try:
                preview = self._local.preview(user_input)
                preview = preview.replace("\n", " ").strip()
                if len(preview) > 180:
                    preview = preview[:180] + "..."
                print(f"[shadow] Yerel preview: {preview}", flush=True)
            except Exception as exc:
                print(f"[shadow] Yerel preview hatasi: {exc}", flush=True)

        threading.Thread(target=_probe, daemon=True).start()

    def _should_try_local(self, user_input: str) -> bool:
        text = (user_input or "").strip().lower()
        tokens = set(re.findall(r"\w+", text))
        if not text:
            return False
        if self._matches_any(text, tokens, _RISKY_PATTERNS):
            return False
        if self._matches_any(text, tokens, _WEB_PATTERNS):
            return False
        if self._matches_any(text, tokens, _VISION_PATTERNS):
            return False
        if self._matches_any(text, tokens, _ACTION_HINTS):
            return False
        return len(text) <= 120

    def _mode(self) -> str:
        value = os.getenv("FRIDAY_LOCAL_MODE", _MODE_OFF).strip().lower()
        return value if value in _VALID_MODES else _MODE_OFF

    @staticmethod
    def _matches_any(text: str, tokens: set[str], patterns: tuple[str, ...]) -> bool:
        for pattern in patterns:
            if " " in pattern:
                if pattern in text:
                    return True
            elif pattern in tokens:
                return True
        return False
