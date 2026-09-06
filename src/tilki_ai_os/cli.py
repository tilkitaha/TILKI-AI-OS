from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import __version__
from .agents import (
    add_agent,
    get_agent,
    get_runtime,
    list_agent_statuses,
    remove_agent,
    start_agent,
    stop_agent,
    tail_agent_logs,
)
from .gpu import list_nvidia_gpus
from .models import list_ollama_models
from .projects import PROJECT_TYPES, init_project
from .system import get_system_status


def _emit_json(value: Any) -> None:
    if hasattr(value, "__dict__"):
        value = value.__dict__
    print(json.dumps(value, indent=2, default=str))


def _print_status(as_json: bool = False) -> None:
    status = get_system_status()
    gpus = list_nvidia_gpus()
    if as_json:
        payload = dict(status.__dict__)
        payload["nvidia_gpus"] = [gpu.__dict__ for gpu in gpus]
        _emit_json(payload)
        return
    print("TILKI AI OS — SYSTEM STATUS")
    print(f"OS       {status.os} {status.kernel} ({status.machine})")
    print(f"Python   {status.python}")
    print(f"CPU      {status.cpu_count} logical cores")
    print(f"Load     {status.load_1m:.2f}" if status.load_1m is not None else "Load     n/a")
    if status.memory_total_gb is not None:
        used = status.memory_total_gb - (status.memory_available_gb or 0)
        print(f"Memory   {used:.1f} / {status.memory_total_gb:.1f} GB")
    else:
        print("Memory   n/a")
    print(f"GPU      {len(gpus)} NVIDIA device(s) detected")


def _print_gpu(as_json: bool = False) -> None:
    gpus = list_nvidia_gpus()
    if as_json:
        _emit_json([gpu.__dict__ for gpu in gpus])
        return
    if not gpus:
        print("No NVIDIA GPU detected or nvidia-smi is unavailable.")
        return
    for gpu in gpus:
        print(
            f"GPU {gpu.index}  {gpu.name} | VRAM {gpu.memory_used_mb}/{gpu.memory_total_mb} MB "
            f"| util {gpu.utilization_percent}% | {gpu.temperature_c}°C"
        )


def _agent_status_payload(name: str) -> dict[str, Any]:
    agent = get_agent(name)
    if not agent:
        raise ValueError(f"Agent '{name}' is not registered")
    runtime = get_runtime(name)
    return {
        "name": name,
        "command": agent["command"],
        "status": runtime.get("status", "registered") if runtime else "registered",
        "supervisor_pid": runtime.get("supervisor_pid") if runtime else None,
        "child_pid": runtime.get("child_pid") if runtime else None,
        "started_at": runtime.get("started_at") if runtime else None,
        "finished_at": runtime.get("finished_at") if runtime else None,
        "exit_code": runtime.get("exit_code") if runtime else None,
        "log_path": runtime.get("log_path") if runtime else None,
        "error": runtime.get("error") if runtime else None,
        "uptime_seconds": next(
            (item.get("uptime_seconds") for item in list_agent_statuses() if item.get("name") == name),
            None,
        ),
    }


def _print_agent_status(payload: dict[str, Any]) -> None:
    details = [payload["status"]]
    if payload.get("child_pid"):
        details.append(f"pid={payload['child_pid']}")
    if payload.get("exit_code") is not None:
        details.append(f"exit={payload['exit_code']}")
    if payload.get("uptime_seconds") is not None:
        details.append(f"time={payload['uptime_seconds']:.1f}s")
    print(f"{payload['name']}  [{' | '.join(details)}]  {payload['command']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tilki", description="TILKI AI OS developer CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON where supported")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Show system and AI runtime status")
    commands.add_parser("gpu", help="Show NVIDIA GPU/VRAM status")

    model = commands.add_parser("model", help="Manage local models")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_commands.add_parser("list", help="List models available from local Ollama")

    agent = commands.add_parser("agent", help="Manage and supervise AI agents")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    agent_commands.add_parser("list", help="List registered agents and runtime state")

    add = agent_commands.add_parser("add", help="Register an agent command")
    add.add_argument("name")
    add.add_argument("--command", dest="exec_command", required=True)
    add.add_argument("--cwd", help="Default working directory for the agent")
    add.add_argument("--max-memory-mb", type=int, help="POSIX address-space limit for the agent")
    add.add_argument("--max-cpu-seconds", type=int, help="POSIX CPU-time limit for the agent")

    remove = agent_commands.add_parser("remove", help="Remove a registered agent")
    remove.add_argument("name")

    run = agent_commands.add_parser("run", help="Start an agent under the TILKI supervisor")
    run.add_argument("name")
    run.add_argument("--cwd", type=Path, help="Override the configured working directory")

    stop = agent_commands.add_parser("stop", help="Stop a supervised agent")
    stop.add_argument("name")

    status = agent_commands.add_parser("status", help="Show one or all agent runtime states")
    status.add_argument("name", nargs="?")

    logs = agent_commands.add_parser("logs", help="Show recent agent logs")
    logs.add_argument("name")
    logs.add_argument("--lines", type=int, default=50)

    project = commands.add_parser("project", help="Create AI projects")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    init = project_commands.add_parser("init", help="Create a project workspace")
    init.add_argument("name")
    init.add_argument("--type", choices=sorted(PROJECT_TYPES), default="agent")
    init.add_argument("--path", type=Path, default=Path.cwd())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            _print_status(args.json)
        elif args.command == "gpu":
            _print_gpu(args.json)
        elif args.command == "model" and args.model_command == "list":
            models = list_ollama_models()
            if args.json:
                _emit_json(models)
            elif not models:
                print("No Ollama models found. Is Ollama running on 127.0.0.1:11434?")
            else:
                for model in models:
                    print(model.get("name") or model.get("model") or json.dumps(model))
        elif args.command == "agent" and args.agent_command == "list":
            statuses = list_agent_statuses()
            if args.json:
                _emit_json(statuses)
            elif not statuses:
                print("No agents registered.")
            else:
                for payload in statuses:
                    _print_agent_status(payload)
        elif args.command == "agent" and args.agent_command == "add":
            agent = add_agent(
                args.name,
                args.exec_command,
                cwd=args.cwd,
                max_memory_mb=args.max_memory_mb,
                max_cpu_seconds=args.max_cpu_seconds,
            )
            if args.json:
                _emit_json(agent)
            else:
                print(f"Registered agent: {agent['name']}")
        elif args.command == "agent" and args.agent_command == "remove":
            if not remove_agent(args.name):
                print(f"Agent not found: {args.name}")
                return 1
            print(f"Removed agent: {args.name}")
        elif args.command == "agent" and args.agent_command == "run":
            state = start_agent(args.name, cwd=args.cwd)
            if args.json:
                _emit_json(state)
            else:
                print(f"Started agent: {args.name} (supervisor pid {state['supervisor_pid']})")
        elif args.command == "agent" and args.agent_command == "stop":
            state = stop_agent(args.name)
            if args.json:
                _emit_json(state)
            else:
                print(f"Agent {args.name}: {state['status']}")
        elif args.command == "agent" and args.agent_command == "status":
            if args.name:
                payload = _agent_status_payload(args.name)
                if args.json:
                    _emit_json(payload)
                else:
                    _print_agent_status(payload)
            else:
                payloads = list_agent_statuses()
                if args.json:
                    _emit_json(payloads)
                elif not payloads:
                    print("No agents registered.")
                else:
                    for payload in payloads:
                        _print_agent_status(payload)
        elif args.command == "agent" and args.agent_command == "logs":
            lines = tail_agent_logs(args.name, lines=args.lines)
            if args.json:
                _emit_json({"name": args.name, "lines": lines})
            elif not lines:
                print(f"No logs for agent: {args.name}")
            else:
                print("\n".join(lines))
        elif args.command == "project" and args.project_command == "init":
            target = init_project(args.name, args.type, args.path)
            payload = {"type": args.type, "path": str(target)}
            if args.json:
                _emit_json(payload)
            else:
                print(f"Created {args.type} project at {target}")
        return 0
    except (ValueError, FileExistsError, OSError) as exc:
        if getattr(args, "json", False):
            _emit_json({"error": str(exc), "type": type(exc).__name__})
        else:
            print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
