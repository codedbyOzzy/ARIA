from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from friday.stt_health import _recommend, run_health_check
from friday.tools.weather import format_weather_response, get_weather


def test_recommend_pyaudio_preferred():
    assert _recommend(True, True, True) == "pyaudio+google"


def test_recommend_sounddevice_fallback():
    assert _recommend(False, True, True) == "sounddevice+google"


def test_recommend_no_backend():
    assert _recommend(False, False, True) is None


def test_recommend_no_google():
    assert _recommend(False, True, False) == "sounddevice+offline"


def test_health_check_returns_required_keys():
    with patch("friday.stt_health.probe_pyaudio", return_value=(True, "ok")), patch(
        "friday.stt_health.probe_sounddevice", return_value=(True, "ok")
    ), patch("friday.stt_health.probe_google_stt", return_value=(True, "ok")):
        result = run_health_check()
    for key in ("pyaudio", "sounddevice", "google_stt", "recommended", "ts"):
        assert key in result


def test_health_check_logs_critical_when_no_backend(monkeypatch):
    events = []
    monkeypatch.setattr("friday.stt_health.log_event", lambda event, **kw: events.append({"event": event, **kw}))
    with patch("friday.stt_health.probe_pyaudio", return_value=(False, "yok")), patch(
        "friday.stt_health.probe_sounddevice", return_value=(False, "yok")
    ), patch("friday.stt_health.probe_google_stt", return_value=(False, "yok")):
        run_health_check()
    assert any(e["event"] == "stt_no_backend" and e.get("level") == "critical" for e in events)


MOCK_WTTR_RESPONSE = {
    "current_condition": [
        {
            "temp_C": "18",
            "FeelsLikeC": "16",
            "weatherDesc": [{"value": "Partly cloudy"}],
            "humidity": "72",
            "windspeedKmph": "15",
        }
    ]
}


def test_get_weather_returns_contract_fields():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.read = lambda: json.dumps(MOCK_WTTR_RESPONSE).encode()
        result = get_weather("Istanbul")
    for key in ("location", "temp_c", "feels_like_c", "condition", "humidity_pct", "wind_kmh", "updated_at"):
        assert key in result
    assert result["temp_c"] == 18.0
    assert result["humidity_pct"] == 72


def test_format_weather_response_no_markdown():
    data = {
        "location": "Istanbul",
        "temp_c": 18.0,
        "condition": "Parçalı bulutlu",
        "humidity_pct": 72,
        "wind_kmh": 15.0,
    }
    response = format_weather_response(data)
    assert "[" not in response
    assert "http" not in response
    assert "Istanbul" in response
    assert "18" in response


def test_format_weather_response_short():
    data = {
        "location": "Istanbul",
        "temp_c": 18.0,
        "condition": "Parçalı bulutlu",
        "humidity_pct": 72,
        "wind_kmh": 15.0,
    }
    assert len(format_weather_response(data)) < 120


def test_sprint_1_regression():
    r = subprocess.run(
        ["python", "-m", "pytest", "-q", "test_sprint_1a.py", "test_sprint_1b.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "18 passed" in r.stdout


def test_sprint_2_regression():
    r = subprocess.run(
        ["python", "-m", "pytest", "-q", "test_sprint_2.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "13 passed" in r.stdout
