from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from friday.tools import (
    desktop_control,
    local_llm,
    memory,
    ollama_runtime,
    policy,
    system,
    task_executor,
    utils,
    weather,
    web,
)


class _Collector:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self):
        def dec(fn):
            self.tools[fn.__name__] = fn
            return fn

        return dec

    def prompt(self):
        def dec(fn):
            return fn

        return dec

    def resource(self, *_args, **_kwargs):
        def dec(fn):
            return fn

        return dec


def _build_tools() -> dict[str, Callable[..., Any]]:
    c = _Collector()
    web.register(c)
    policy.register(c)
    memory.register(c)
    ollama_runtime.register(c)
    system.register(c)
    utils.register(c)
    local_llm.register(c)
    desktop_control.register(c)
    task_executor.register(c)
    weather.register(c)
    return c.tools


TOOLS = _build_tools()
ROOT = Path(__file__).parent
UI_DIR = ROOT / "ui"
VOICE_STATUS_FILE = ROOT / ".friday_voice_status.json"
VOICE_STATUS_TTL_SEC = 10.0

app = FastAPI(title="JarvisBrain_v2 Control Panel", version="1.0.0")
app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    p = UI_DIR / "index.html"
    return p.read_text(encoding="utf-8")


def _read_voice_status() -> dict[str, Any]:
    try:
        data = json.loads(VOICE_STATUS_FILE.read_text(encoding="utf-8"))
        written_at = float(data.get("written_at", 0.0) or 0.0)
        age = max(0.0, time.time() - written_at) if written_at else float("inf")
        return {
            "state": str(data.get("state", "booting")).strip().lower() or "booting",
            "voice_fresh": age < VOICE_STATUS_TTL_SEC,
            "written_at": written_at,
            "room": str(data.get("room", "") or ""),
            "updated_at": str(data.get("updated_at", "") or ""),
        }
    except Exception:
        return {
            "state": "booting",
            "voice_fresh": False,
            "written_at": 0.0,
            "room": "",
            "updated_at": "",
        }


def get_status() -> dict[str, Any]:
    # If this function is executing, panel process itself is online.
    panel_ok = True
    mcp_ok = False
    try:
        with httpx.stream(
            "GET",
            "http://127.0.0.1:8010/sse",
            timeout=httpx.Timeout(connect=0.8, read=0.8, write=0.8, pool=0.8),
        ) as resp:
            mcp_ok = resp.status_code == 200
    except Exception:
        mcp_ok = False

    voice = _read_voice_status()
    service_online = bool(mcp_ok and panel_ok)
    pipeline_ready = bool(voice["state"] == "ready" and voice["voice_fresh"])
    return {
        "service_online": service_online,
        "pipeline_ready": pipeline_ready,
        "voice_state": voice["state"],
        "voice_fresh": voice["voice_fresh"],
    }


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    status = get_status()
    status.update(
        {
            "policy": TOOLS["policy_status"](),
            "ollama": TOOLS["ollama_status"](),
            "profile": TOOLS["user_profile"](),
            "voice": _read_voice_status(),
        }
    )
    return status


class PolicyArmRequest(BaseModel):
    ttl_sec: int = Field(default=180, ge=30, le=3600)


@app.post("/api/policy/arm")
def api_policy_arm(req: PolicyArmRequest) -> dict[str, Any]:
    return TOOLS["arm_desktop_control"](req.ttl_sec)


class ChallengeRequest(BaseModel):
    action_name: str
    ttl_sec: int = Field(default=120, ge=30, le=600)


@app.post("/api/policy/challenge")
def api_policy_challenge(req: ChallengeRequest) -> dict[str, Any]:
    return TOOLS["request_action_challenge"](req.action_name, req.ttl_sec)


class ChallengeConfirmRequest(BaseModel):
    challenge_code: str


@app.post("/api/policy/confirm")
def api_policy_confirm(req: ChallengeConfirmRequest) -> dict[str, Any]:
    return TOOLS["confirm_action_challenge"](req.challenge_code)


class PreferenceRequest(BaseModel):
    key: str
    value: str


@app.post("/api/memory/preference")
def api_memory_preference(req: PreferenceRequest) -> dict[str, Any]:
    result = TOOLS["remember_preference"](req.key, req.value)
    return {"ok": "Stored" in result or "stored" in result.lower(), "result": result}


class NoteRequest(BaseModel):
    topic: str
    note: str


@app.post("/api/memory/note")
def api_memory_note(req: NoteRequest) -> dict[str, Any]:
    result = TOOLS["remember_note"](req.topic, req.note)
    return {"ok": "Stored" in result or "stored" in result.lower(), "result": result}


@app.get("/api/memory/summary")
def api_memory_summary(limit: int = 20) -> list[dict[str, Any]]:
    return TOOLS["memory_summary"](limit)


class WorkflowRequest(BaseModel):
    steps: list[dict[str, Any]]
    confirm_token: str
    stop_on_error: bool = True
    dry_run: bool = False
    max_retries_per_step: int = Field(default=1, ge=0, le=3)


@app.post("/api/workflow/run")
def api_workflow_run(req: WorkflowRequest) -> dict[str, Any]:
    steps_json = json.dumps(req.steps, ensure_ascii=False)
    return TOOLS["execute_desktop_workflow"](
        steps_json,
        req.confirm_token,
        req.stop_on_error,
        req.dry_run,
        req.max_retries_per_step,
    )


@app.get("/api/workflow/history")
def api_workflow_history(limit: int = 10) -> list[dict[str, Any]]:
    return TOOLS["recent_workflow_history"](limit)


class DesktopActionRequest(BaseModel):
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/desktop/action")
def api_desktop_action(req: DesktopActionRequest) -> dict[str, Any]:
    action = (req.action or "").strip()
    if action not in TOOLS:
        raise HTTPException(status_code=404, detail=f"unknown_action:{action}")
    fn = TOOLS[action]
    try:
        result = fn(**req.params)
        return {"ok": True, "result": result}
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_params:{exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8030, reload=False)
