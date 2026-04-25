"""Deterministic weather tool using wttr.in JSON API."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from blackbox import log_event

WTTR_URL = "https://wttr.in/{location}?format=j1"


def get_weather(location: str) -> dict:
    """Return strict weather contract for location."""
    loc = (location or "").strip() or "Istanbul"
    try:
        url = WTTR_URL.format(location=urllib.parse.quote(loc))
        with urllib.request.urlopen(url, timeout=5) as resp:  # nosec B310
            data = json.loads(resp.read())

        current = data["current_condition"][0]
        result = {
            "location": loc,
            "temp_c": float(current["temp_C"]),
            "feels_like_c": float(current["FeelsLikeC"]),
            "condition": str(current["weatherDesc"][0]["value"]),
            "humidity_pct": int(current["humidity"]),
            "wind_kmh": float(current["windspeedKmph"]),
            "updated_at": time.time(),
        }
        log_event("tool_ok", level="info", tool="get_weather", location=loc)
        return result
    except Exception as exc:
        log_event("tool_error", level="error", tool="get_weather", reason=str(exc))
        raise


def format_weather_response(data: dict) -> str:
    """Format weather as short strict voice-safe text."""
    return (
        f"{data['location']}: {data['temp_c']:.0f}°C, "
        f"{data['condition']}, "
        f"nem %{data['humidity_pct']}, "
        f"ruzgar {data['wind_kmh']:.0f} km/s"
    )


def register(mcp) -> None:
    @mcp.tool()
    def get_weather_now(location: str = "Istanbul") -> dict:
        return get_weather(location)
