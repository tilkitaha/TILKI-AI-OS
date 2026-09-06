from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .agents import log_path, runtime_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _resource_limiter(memory_mb: int | None, cpu_seconds: int | None) -> Callable[[], None] | None:
    if os.name == "nt" or (memory_mb is None and cpu_seconds is None):
        return None

    def apply_limits() -> None:
        import resource

        if memory_mb is not None:
            limit = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        if cpu_seconds is not None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))

    return apply_limits


def _parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def run_supervisor(
    *,
    name: str,
    home: Path,
    command: str,
    cwd: Path,
    max_memory_mb: int | None = None,
    max_cpu_seconds: int | None = None,
) -> int:
    state_file = runtime_path(name, home)
    log_file = log_path(name, home)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "name": name,
        "command": command,
        "status": "starting",
        "started_at": _utc_now(),
        "cwd": str(cwd),
        "log_path": str(log_file),
        "supervisor_pid": os.getpid(),
        "child_pid": None,
        "exit_code": None,
    }
    _write_state(state_file, state)

    child: subprocess.Popen[str] | None = None
    stop_requested = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True
        if child is None or child.poll() is not None:
            return
        try:
            if os.name != "nt":
                os.killpg(child.pid, signal.SIGTERM)
            else:
                child.terminate()
        except (ProcessLookupError, OSError):
            pass

    signal.signal(signal.SIGTERM, request_stop)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, request_stop)

    try:
        argv = _parse_command(command)
        if not argv:
            raise ValueError("Agent command is empty")
        with log_file.open("a", encoding="utf-8", buffering=1) as log:
            log.write(f"[{_utc_now()}] TILKI supervisor starting: {command}\n")
            if os.name == "nt" and (max_memory_mb is not None or max_cpu_seconds is not None):
                log.write(f"[{_utc_now()}] Resource limits are not yet enforced on Windows.\n")

            kwargs: dict[str, Any] = {
                "cwd": str(cwd),
                "stdin": subprocess.DEVNULL,
                "stdout": log,
                "stderr": subprocess.STDOUT,
                "text": True,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
                limiter = _resource_limiter(max_memory_mb, max_cpu_seconds)
                if limiter is not None:
                    kwargs["preexec_fn"] = limiter

            child = subprocess.Popen(argv, **kwargs)
            state["status"] = "running"
            state["child_pid"] = child.pid
            _write_state(state_file, state)
            log.write(f"[{_utc_now()}] Agent child PID {child.pid}\n")
            if stop_requested and child.poll() is None:
                try:
                    if os.name != "nt":
                        os.killpg(child.pid, signal.SIGTERM)
                    else:
                        child.terminate()
                except (ProcessLookupError, OSError):
                    pass
            exit_code = child.wait()
            state["exit_code"] = exit_code
            state["finished_at"] = _utc_now()
            state["status"] = "stopped" if stop_requested else ("completed" if exit_code == 0 else "failed")
            _write_state(state_file, state)
            log.write(f"[{_utc_now()}] Agent finished with exit code {exit_code}\n")
            return exit_code
    except Exception as exc:
        state["status"] = "failed"
        state["finished_at"] = _utc_now()
        state["error"] = f"{type(exc).__name__}: {exc}"
        _write_state(state_file, state)
        try:
            with log_file.open("a", encoding="utf-8") as log:
                log.write(f"[{_utc_now()}] Supervisor error: {type(exc).__name__}: {exc}\n")
        except OSError:
            pass
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tilki-supervisor")
    parser.add_argument("--name", required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--max-memory-mb", type=int)
    parser.add_argument("--max-cpu-seconds", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_supervisor(
        name=args.name,
        home=args.home,
        command=args.command,
        cwd=args.cwd,
        max_memory_mb=args.max_memory_mb,
        max_cpu_seconds=args.max_cpu_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
