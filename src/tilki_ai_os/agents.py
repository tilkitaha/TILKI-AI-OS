from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ACTIVE_STATES = {"starting", "running", "stopping"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_root(home: Path | None = None) -> Path:
    base = home or Path.home()
    return base / ".tilki-ai-os"


def registry_path(home: Path | None = None) -> Path:
    return _state_root(home) / "agents.json"


def _agent_key(name: str) -> str:
    return sha256(name.encode("utf-8")).hexdigest()[:16]


def runtime_path(name: str, home: Path | None = None) -> Path:
    return _state_root(home) / "runtime" / f"{_agent_key(name)}.json"


def log_path(name: str, home: Path | None = None) -> Path:
    return _state_root(home) / "logs" / f"{_agent_key(name)}.log"


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_agents(home: Path | None = None) -> list[dict[str, Any]]:
    path = registry_path(home)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def get_agent(name: str, home: Path | None = None) -> dict[str, Any] | None:
    return next((agent for agent in load_agents(home) if agent.get("name") == name), None)


def add_agent(
    name: str,
    command: str,
    home: Path | None = None,
    *,
    cwd: str | None = None,
    max_memory_mb: int | None = None,
    max_cpu_seconds: int | None = None,
) -> dict[str, Any]:
    name = name.strip()
    command = command.strip()
    if not name or not command:
        raise ValueError("Agent name and command are required")
    if max_memory_mb is not None and max_memory_mb <= 0:
        raise ValueError("max_memory_mb must be greater than zero")
    if max_cpu_seconds is not None and max_cpu_seconds <= 0:
        raise ValueError("max_cpu_seconds must be greater than zero")

    agents = load_agents(home)
    if any(agent.get("name") == name for agent in agents):
        raise ValueError(f"Agent '{name}' already exists")

    agent: dict[str, Any] = {"name": name, "command": command, "status": "registered"}
    if cwd:
        agent["cwd"] = str(Path(cwd).expanduser().resolve())
    if max_memory_mb is not None:
        agent["max_memory_mb"] = max_memory_mb
    if max_cpu_seconds is not None:
        agent["max_cpu_seconds"] = max_cpu_seconds
    agents.append(agent)
    _write_json(registry_path(home), agents)
    return agent


def remove_agent(name: str, home: Path | None = None) -> bool:
    status = get_runtime(name, home, refresh=True)
    if status and status.get("status") in ACTIVE_STATES:
        raise ValueError(f"Agent '{name}' is running; stop it before removing it")
    agents = load_agents(home)
    filtered = [agent for agent in agents if agent.get("name") != name]
    if len(filtered) == len(agents):
        return False
    _write_json(registry_path(home), filtered)
    return True


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def get_runtime(name: str, home: Path | None = None, *, refresh: bool = True) -> dict[str, Any] | None:
    path = runtime_path(name, home)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None

    if refresh and state.get("status") in ACTIVE_STATES:
        supervisor_pid = state.get("supervisor_pid")
        if supervisor_pid and not _pid_alive(int(supervisor_pid)):
            state["status"] = "failed"
            state.setdefault("finished_at", _utc_now())
            state.setdefault("error", "Supervisor process disappeared")
            _write_json(path, state)
    return state


def _elapsed_seconds(state: dict[str, Any]) -> float | None:
    started = state.get("started_at")
    if not started:
        return None
    try:
        start_dt = datetime.fromisoformat(str(started))
        end_raw = state.get("finished_at")
        end_dt = datetime.fromisoformat(str(end_raw)) if end_raw else datetime.now(timezone.utc)
        return max(0.0, round((end_dt - start_dt).total_seconds(), 3))
    except (TypeError, ValueError):
        return None


def list_agent_statuses(home: Path | None = None) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for agent in load_agents(home):
        state = get_runtime(str(agent["name"]), home)
        statuses.append(
            {
                "name": agent["name"],
                "command": agent["command"],
                "status": state.get("status", "registered") if state else "registered",
                "supervisor_pid": state.get("supervisor_pid") if state else None,
                "child_pid": state.get("child_pid") if state else None,
                "started_at": state.get("started_at") if state else None,
                "finished_at": state.get("finished_at") if state else None,
                "exit_code": state.get("exit_code") if state else None,
                "uptime_seconds": _elapsed_seconds(state) if state else None,
            }
        )
    return statuses


def start_agent(
    name: str,
    home: Path | None = None,
    *,
    cwd: Path | None = None,
) -> dict[str, Any]:
    agent = get_agent(name, home)
    if not agent:
        raise ValueError(f"Agent '{name}' is not registered")

    existing = get_runtime(name, home)
    if existing and existing.get("status") in ACTIVE_STATES:
        raise ValueError(f"Agent '{name}' is already {existing['status']}")

    resolved_home = (home or Path.home()).expanduser().resolve()
    configured_cwd = cwd or (Path(agent["cwd"]) if agent.get("cwd") else Path.cwd())
    configured_cwd = configured_cwd.expanduser().resolve()
    if not configured_cwd.exists() or not configured_cwd.is_dir():
        raise ValueError(f"Agent working directory does not exist: {configured_cwd}")

    state: dict[str, Any] = {
        "name": name,
        "command": agent["command"],
        "status": "starting",
        "started_at": _utc_now(),
        "cwd": str(configured_cwd),
        "log_path": str(log_path(name, resolved_home)),
        "supervisor_pid": None,
        "child_pid": None,
        "exit_code": None,
    }
    _write_json(runtime_path(name, resolved_home), state)

    args = [
        sys.executable,
        "-m",
        "tilki_ai_os.supervisor",
        "--name",
        name,
        "--home",
        str(resolved_home),
        "--command",
        str(agent["command"]),
        "--cwd",
        str(configured_cwd),
    ]
    if agent.get("max_memory_mb") is not None:
        args += ["--max-memory-mb", str(agent["max_memory_mb"])]
    if agent.get("max_cpu_seconds") is not None:
        args += ["--max-cpu-seconds", str(agent["max_cpu_seconds"])]

    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(configured_cwd),
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        popen_kwargs["start_new_session"] = True

    try:
        supervisor = subprocess.Popen(args, **popen_kwargs)
    except OSError as exc:
        state["status"] = "failed"
        state["finished_at"] = _utc_now()
        state["error"] = str(exc)
        _write_json(runtime_path(name, resolved_home), state)
        raise ValueError(f"Could not start agent supervisor: {exc}") from exc

    state["supervisor_pid"] = supervisor.pid
    # This Popen object is intentionally detached: the long-lived supervisor owns
    # the agent lifecycle. Mark the local handle as released so Python does not
    # emit a ResourceWarning when the short-lived CLI process discards it.
    supervisor.returncode = 0
    # The supervisor will replace this state with authoritative child/process data.
    # Avoid clobbering it if it has already advanced past 'starting'.
    current = get_runtime(name, resolved_home, refresh=False)
    if current and current.get("status") == "starting":
        _write_json(runtime_path(name, resolved_home), state)
    return state


def stop_agent(name: str, home: Path | None = None, *, wait_seconds: float = 3.0) -> dict[str, Any]:
    if not get_agent(name, home):
        raise ValueError(f"Agent '{name}' is not registered")

    deadline = time.monotonic() + max(wait_seconds, 0.1)
    state = get_runtime(name, home)
    while state and state.get("status") == "starting" and not state.get("supervisor_pid") and time.monotonic() < deadline:
        time.sleep(0.05)
        state = get_runtime(name, home)

    if not state or state.get("status") not in ACTIVE_STATES:
        raise ValueError(f"Agent '{name}' is not running")
    pid = int(state.get("supervisor_pid") or 0)
    if not _pid_alive(pid):
        state["status"] = "failed"
        state.setdefault("finished_at", _utc_now())
        state.setdefault("error", "Supervisor process disappeared")
        _write_json(runtime_path(name, home), state)
        return state

    state["status"] = "stopping"
    state["stop_requested_at"] = _utc_now()
    _write_json(runtime_path(name, home), state)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    while time.monotonic() < deadline:
        time.sleep(0.05)
        latest = get_runtime(name, home)
        if latest and latest.get("status") not in ACTIVE_STATES:
            return latest
    return get_runtime(name, home) or state


def tail_agent_logs(name: str, home: Path | None = None, *, lines: int = 50) -> list[str]:
    if lines <= 0:
        raise ValueError("lines must be greater than zero")
    if not get_agent(name, home):
        raise ValueError(f"Agent '{name}' is not registered")
    path = log_path(name, home)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return list(deque((line.rstrip("\n") for line in handle), maxlen=lines))
    except OSError:
        return []
