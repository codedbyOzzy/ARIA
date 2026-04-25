from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineResult:
    success: bool
    tool_name: str
    result_type: str
    response: str
    raw: dict[str, Any] = field(default_factory=dict)


class CommandPipeline:
    def __init__(self, policy, tools, sanitizer, blackbox) -> None:
        self.policy = policy
        self.tools = tools
        self.sanitizer = sanitizer
        self.blackbox = blackbox

    def run(self, text: str, source: str = "direct") -> PipelineResult:
        intent = self._normalize(text)
        allowed, reason = self.policy.check(intent)
        if not allowed:
            self.blackbox.log_event(
                "policy_block",
                level="warning",
                intent=intent,
                reason=reason,
                source=source,
            )
            return PipelineResult(
                success=False,
                tool_name="",
                result_type="policy_block",
                response=reason,
            )

        try:
            raw = self.tools.execute(intent)
            self.blackbox.log_event(
                "tool_ok",
                level="info",
                tool=intent.get("tool", ""),
                source=source,
            )
        except Exception as exc:
            self.blackbox.log_event(
                "tool_error",
                level="error",
                reason=str(exc),
                source=source,
            )
            return PipelineResult(
                success=False,
                tool_name=intent.get("tool", ""),
                result_type="tool_error",
                response=str(exc),
            )

        if intent.get("tool") == "get_weather_now" and isinstance(raw, dict):
            try:
                response = self.tools.format_weather_response(raw)
            except Exception:
                raw_str = str(raw)
                response = self.sanitizer.clean(raw_str)
        else:
            raw_str = raw if isinstance(raw, str) else str(raw)
            response = self.sanitizer.clean(raw_str)
        self.blackbox.log_event(
            "command_success",
            level="info",
            tool=intent.get("tool", ""),
            source=source,
        )
        return PipelineResult(
            success=True,
            tool_name=intent.get("tool", ""),
            result_type="success",
            response=response,
            raw=raw if isinstance(raw, dict) else {},
        )

    def _normalize(self, text: str) -> dict[str, Any]:
        low = (text or "").strip().lower()
        if not low:
            return {"tool": "bilinmeyen", "args": {}, "text": low}
        if low in {"list_windows_text", "open_notepad", "bilinmeyen"}:
            if low == "open_notepad":
                return {"tool": "open_application", "args": {"app_name": "notepad"}, "text": low}
            if low == "list_windows_text":
                return {"tool": "list_windows_text", "args": {"limit": 10}, "text": low}
            return {"tool": "bilinmeyen", "args": {}, "text": low}

        if ("notepad" in low or "not defter" in low) and ("aç" in low or "ac" in low):
            return {"tool": "open_application", "args": {"app_name": "notepad"}, "text": low}
        if ("notepad" in low or "not defter" in low) and ("kapat" in low):
            return {"tool": "close_application", "args": {"app_name": "notepad", "pid": 0, "confirm_token": ""}, "text": low}
        if "youtube" in low and ("aç" in low or "ac" in low):
            return {"tool": "open_website", "args": {"url": "https://www.youtube.com", "confirm_token": ""}, "text": low}
        if "chrome" in low and ("aç" in low or "ac" in low):
            return {"tool": "open_application", "args": {"app_name": "chrome"}, "text": low}
        if ("açık pencereleri" in low) or ("pencereleri liste" in low) or ("pencereleri say" in low):
            return {"tool": "list_windows_text", "args": {"limit": 10}, "text": low}
        if "saat kaç" in low:
            return {"tool": "get_current_time", "args": {}, "text": low}
        if ("dünyada ne oluyor" in low) or ("haber" in low):
            return {"tool": "get_world_news", "args": {}, "text": low}
        if ("hava" in low and ("yarın" in low or "bugün" in low or "durumu" in low)) or ("weather" in low and "istanbul" in low):
            location = "Istanbul"
            if "ankara" in low:
                location = "Ankara"
            elif "izmir" in low:
                location = "Izmir"
            elif "beijing" in low or "pekin" in low:
                location = "Beijing"
            return {"tool": "get_weather_now", "args": {"location": location}, "text": low}
        return {"tool": "bilinmeyen", "args": {}, "text": low}
