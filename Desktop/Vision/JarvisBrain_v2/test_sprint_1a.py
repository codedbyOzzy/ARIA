from __future__ import annotations

import json
import time


VALID_STATES = {"booting", "ready", "listening", "executing", "error"}
VOICE_STATUS_TTL = 10


def write_status(filepath: str, state: str, offset_seconds: float = 0.0, **kwargs):
    payload = {
        "state": state,
        "written_at": time.time() + offset_seconds,
        **kwargs,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def read_status_with_ttl(filepath: str, ttl: float = VOICE_STATUS_TTL):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        age = time.time() - data.get("written_at", 0)
        data["voice_fresh"] = age < ttl
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"state": "booting", "voice_fresh": False}


def test_file_not_found_returns_safe_default(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    result = read_status_with_ttl(status_path)
    assert result["state"] == "booting"
    assert result["voice_fresh"] is False


def test_invalid_json_returns_safe_default(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        f.write("broken {{{")
    result = read_status_with_ttl(status_path)
    assert result["state"] == "booting"
    assert result["voice_fresh"] is False


def test_valid_states_accepted(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    for state in VALID_STATES:
        write_status(status_path, state)
        result = read_status_with_ttl(status_path)
        assert result["state"] == state


def test_written_at_present(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    write_status(status_path, "ready")
    with open(status_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "written_at" in data
    assert isinstance(data["written_at"], float)


def test_freshness_within_ttl(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    write_status(status_path, "ready")
    result = read_status_with_ttl(status_path)
    assert result["voice_fresh"] is True


def test_freshness_expired(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    write_status(status_path, "ready", offset_seconds=-15)
    result = read_status_with_ttl(status_path)
    assert result["voice_fresh"] is False


def test_ten_heartbeats_stable(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    write_status(status_path, "ready")
    for _ in range(10):
        result = read_status_with_ttl(status_path)
        assert result["voice_fresh"] is True
        time.sleep(0.05)


def test_error_state_pipeline_not_ready(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    write_status(status_path, "error")
    voice = read_status_with_ttl(status_path)
    pipeline_ready = voice["state"] == "ready" and voice["voice_fresh"]
    assert pipeline_ready is False


def test_stale_ready_pipeline_not_ready(tmp_path):
    status_path = str(tmp_path / ".friday_voice_status.json")
    write_status(status_path, "ready", offset_seconds=-15)
    voice = read_status_with_ttl(status_path)
    pipeline_ready = voice["state"] == "ready" and voice["voice_fresh"]
    assert pipeline_ready is False


def test_control_panel_get_status_fields(monkeypatch):
    import control_panel

    monkeypatch.setattr(control_panel, "_read_voice_status", lambda: {"state": "ready", "voice_fresh": True})

    class _Resp:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Httpx:
        class Timeout:
            def __init__(self, **_kwargs):
                pass

        @staticmethod
        def stream(*_args, **_kwargs):
            return _Resp()

    monkeypatch.setitem(control_panel.get_status.__globals__, "httpx", _Httpx)
    status = control_panel.get_status()
    assert "service_online" in status
    assert "pipeline_ready" in status
    assert isinstance(status["service_online"], bool)
    assert isinstance(status["pipeline_ready"], bool)
    assert status["pipeline_ready"] is True
