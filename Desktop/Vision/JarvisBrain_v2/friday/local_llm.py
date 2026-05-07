"""Optional local text model client.

The client talks to an OpenAI-compatible local endpoint such as:
- llama.cpp `llama-server`
- `llama-cpp-python` server
- Ollama's OpenAI-compatible `/v1` endpoint

This module is safe-by-default: if the server is unavailable or errors, callers
should fall back to the existing cloud Brain.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Iterator

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from friday.brain import _OAI_TOOLS, _TOOL_MAP
from friday.prompt_builder import build_local_system_prompt

# Cümle sonu tespiti: nokta/ünlem/soru işareti ardından boşluk veya satır sonu
_SENT_SPLIT = re.compile(r'(?<=[.!?…\n])\s+')

load_dotenv()


class LocalLLMClient:
    """Thin wrapper around an OpenAI-compatible local text endpoint."""

    def __init__(self) -> None:
        base_url = (
            os.getenv("FRIDAY_LOCAL_BASE_URL", "").strip()
            or os.getenv("OLLAMA_BASE_URL", "").strip()
            or "http://127.0.0.1:8080/v1"
        )
        api_key = (
            os.getenv("FRIDAY_LOCAL_API_KEY", "").strip()
            or os.getenv("OLLAMA_API_KEY", "").strip()
            or "local"
        )
        model = (
            os.getenv("FRIDAY_LOCAL_MODEL", "").strip()
            or os.getenv("OLLAMA_MODEL", "").strip()
            or "local-model"
        )
        timeout = float(os.getenv("FRIDAY_LOCAL_TIMEOUT_SEC", "12"))

        self._base_url = base_url.rstrip("/")
        self._native_base_url = self._derive_native_base_url(self._base_url)
        self._model = model
        self._timeout = timeout
        self._client = OpenAI(api_key=api_key, base_url=self._base_url + "/")
        self._history: list[dict] = []
        self._health_ok = False
        self._health_checked_at = 0.0
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_stop = threading.Event()

    def reset(self) -> None:
        self._history = []

    def healthcheck(self, force: bool = False) -> bool:
        """Probe the local endpoint and cache the result briefly."""
        now = time.time()
        if not force and (now - self._health_checked_at) < 20:
            return self._health_ok

        self._health_checked_at = now
        models_url = self._base_url + "/models"
        try:
            with httpx.Client(timeout=min(self._timeout, 4.0)) as client:
                resp = client.get(models_url)
            self._health_ok = resp.status_code < 500
        except Exception as exc:
            print(f"[local] healthcheck basarisiz: {exc}", flush=True)
            self._health_ok = False
        return self._health_ok

    def warmup(self) -> bool:
        """Warm the local model if the backend supports it.

        Ollama understands keep_alive on its native /api/generate endpoint.
        Other OpenAI-compatible backends fall back to a plain health check.
        """
        keep_alive = os.getenv("FRIDAY_LOCAL_KEEPALIVE", "30m").strip() or "30m"
        payload = {
            "model": self._model,
            "prompt": "Hazir misin?",
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_predict": 1},
        }
        try:
            with httpx.Client(timeout=min(self._timeout, 8.0)) as client:
                resp = client.post(self._native_base_url + "/api/generate", json=payload)
            if resp.status_code < 400:
                self._health_ok = True
                self._health_checked_at = time.time()
                print("[local] model warmup tamamlandi.", flush=True)
                return True
            print(
                f"[local] warmup desteklenmiyor ya da basarisiz: {resp.status_code}",
                flush=True,
            )
        except Exception as exc:
            print(f"[local] warmup basarisiz: {exc}", flush=True)
        return self.healthcheck(force=True)

    def start_keepalive(self) -> None:
        """Keep the local model warm in the background when enabled."""
        enabled = os.getenv("FRIDAY_LOCAL_KEEPALIVE_ENABLE", "0").strip() == "1"
        if not enabled or self._keepalive_thread is not None:
            return

        interval = max(30, int(os.getenv("FRIDAY_LOCAL_KEEPALIVE_INTERVAL_SEC", "600")))
        self._keepalive_stop.clear()

        def _runner() -> None:
            self.warmup()
            while not self._keepalive_stop.wait(interval):
                self.warmup()

        self._keepalive_thread = threading.Thread(
            target=_runner,
            daemon=True,
            name="friday-local-keepalive",
        )
        self._keepalive_thread.start()
        print("[local] keepalive baslatildi.", flush=True)

    def stop_keepalive(self) -> None:
        if self._keepalive_thread is None:
            return
        self._keepalive_stop.set()
        self._keepalive_thread.join(timeout=3)
        self._keepalive_thread = None
        print("[local] keepalive durduruldu.", flush=True)

    def shutdown(self) -> None:
        self.stop_keepalive()

    def chat(
        self,
        user_input: str,
        commit_history: bool = True,
        allow_tools: bool = False,
    ) -> str:
        """Run a chat completion, text-only by default for safety."""
        return self._run_chat(
            user_input,
            commit_history=commit_history,
            allow_tools=allow_tools,
        )

    def stream_chat(self, user_input: str) -> Iterator[str]:
        """Streaming LLM: cümle tamamlandıkça yield eder — düşük gecikmeli TTS için.

        İlk cümle ~300-600ms içinde gelir; TTS o cümleyi seslendiririken LLM
        sonraki cümleyi üretmeye devam eder. Fallback olarak history commit
        try/finally ile garantilenir.
        """
        system_prompt = build_local_system_prompt(user_input)
        prior = self._history[-12:]
        messages: list = [
            {"role": "system", "content": system_prompt},
            *prior,
            {"role": "user", "content": user_input},
        ]

        buffer   = ""
        full_text = ""
        committed = False

        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.2,
                timeout=self._timeout,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                buffer    += delta
                full_text += delta

                # Tamamlanmış cümleleri yield et
                while True:
                    m = _SENT_SPLIT.search(buffer)
                    if not m:
                        break
                    sentence = buffer[: m.start() + 1].strip()
                    buffer   = buffer[m.end():]
                    if sentence:
                        yield sentence

            # Kalan parçayı flush et
            remaining = buffer.strip()
            if remaining:
                yield remaining

            self._remember_turn(user_input, full_text.strip())
            committed = True

        except Exception as exc:
            print(f"[local] stream_chat hatası: {exc}", flush=True)
            if not committed and full_text.strip():
                self._remember_turn(user_input, full_text.strip())

    def preview(self, user_input: str) -> str:
        """Run a non-committing, no-tool probe for shadow mode.

        Shadow mode must never trigger real desktop/tool side effects, so tool
        declarations are omitted entirely here.
        """
        return self._run_chat(
            user_input,
            commit_history=False,
            allow_tools=False,
        )

    def _run_chat(
        self,
        user_input: str,
        *,
        commit_history: bool,
        allow_tools: bool,
    ) -> str:
        """Run a chat completion with optional tool-calling."""
        system_prompt = build_local_system_prompt(user_input)
        prior = self._history[-12:] if commit_history else []
        messages: list = [
            {"role": "system", "content": system_prompt},
            *prior,
            {"role": "user", "content": user_input},
        ]

        for _ in range(5):
            request = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.2,
            }
            if allow_tools:
                request["tools"] = _OAI_TOOLS
                request["tool_choice"] = "auto"

            response = self._client.chat.completions.create(
                **request,
                timeout=self._timeout,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                text = (msg.content or "").strip()
                if commit_history:
                    self._remember_turn(user_input, text)
                return text

            if not allow_tools:
                raise RuntimeError("Shadow preview arac cagirmaya calisti.")

            messages.append(msg)
            for tool_call in msg.tool_calls:
                tool_fn = _TOOL_MAP.get(tool_call.function.name)
                if tool_fn:
                    try:
                        args = json.loads(tool_call.function.arguments or "{}")
                        result = tool_fn(**args)
                    except Exception as exc:
                        result = f"Arac hatasi: {exc}"
                else:
                    result = f"Bilinmeyen arac: {tool_call.function.name}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    }
                )

        raise RuntimeError("Yerel model tamamlanamayan bir arac dongusune girdi.")

    def _remember_turn(self, user_input: str, answer: str) -> None:
        self._history.append({"role": "user", "content": user_input})
        self._history.append({"role": "assistant", "content": answer})
        if len(self._history) > 20:
            self._history = self._history[-20:]

    @staticmethod
    def _derive_native_base_url(base_url: str) -> str:
        if base_url.endswith("/v1"):
            return base_url[:-3]
        return base_url
