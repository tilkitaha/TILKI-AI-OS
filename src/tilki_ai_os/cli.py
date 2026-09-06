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
from .models import (
    HuggingFaceError,
    OllamaError,
    delete_ollama_model,
    generate_ollama,
    huggingface_model_info,
    inspect_ollama_model,
    list_ollama_models,
    list_running_ollama_models,
    load_ollama_model,
    ollama_health,
    pull_ollama_model,
    unload_ollama_model,
)
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

    model = commands.add_parser("model", help="Manage local Ollama models")
    model.add_argument("--host", dest="model_host", help="Override Ollama host/base URL")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_commands.add_parser("list", help="List locally installed models")
    model_commands.add_parser("running", help="List models currently loaded in memory")

    health = model_commands.add_parser("health", help="Check Ollama API and optional inference health")
    health.add_argument("--model", help="Run a tiny inference health check with this model")

    pull = model_commands.add_parser("pull", help="Download a model through Ollama")
    pull.add_argument("name")

    inspect = model_commands.add_parser("inspect", help="Show model metadata and VRAM-fit estimate")
    inspect.add_argument("name")

    run_model = model_commands.add_parser("run", help="Preload a model or run one prompt")
    run_model.add_argument("name")
    run_model.add_argument("--prompt", help="If supplied, generate a response instead of only preloading")
    run_model.add_argument("--keep-alive", default="-1", help="Ollama keep_alive value (default: -1)")

    stop_model = model_commands.add_parser("stop", help="Unload a model from memory")
    stop_model.add_argument("name")

    remove_model = model_commands.add_parser("remove", help="Delete a locally installed model")
    remove_model.add_argument("name")

    hf = model_commands.add_parser("hf", help="Inspect Hugging Face Hub model metadata")
    hf_commands = hf.add_subparsers(dest="hf_command", required=True)
    hf_inspect = hf_commands.add_parser("inspect", help="Fetch metadata for owner/model")
    hf_inspect.add_argument("repo_id")

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
            models = list_ollama_models(base_url=args.model_host, strict=True)
            if args.json:
                _emit_json(models)
            elif not models:
                print("No Ollama models installed.")
            else:
                for model in models:
                    name = model.get("name") or model.get("model") or "unknown"
                    details = model.get("details") if isinstance(model.get("details"), dict) else {}
                    size = model.get("size")
                    size_gb = f"{int(size) / (1024**3):.2f} GB" if isinstance(size, int) else "size n/a"
                    params = details.get("parameter_size", "?")
                    quant = details.get("quantization_level", "?")
                    print(f"{name}  {size_gb}  params={params}  quant={quant}")
        elif args.command == "model" and args.model_command == "running":
            models = list_running_ollama_models(base_url=args.model_host)
            if args.json:
                _emit_json(models)
            elif not models:
                print("No Ollama models currently loaded.")
            else:
                for model in models:
                    name = model.get("name") or model.get("model") or "unknown"
                    vram = model.get("size_vram")
                    vram_gb = f"{int(vram) / (1024**3):.2f} GB VRAM" if isinstance(vram, int) else "VRAM n/a"
                    print(f"{name}  {vram_gb}  context={model.get('context_length', '?')}")
        elif args.command == "model" and args.model_command == "health":
            payload = ollama_health(base_url=args.model_host, model=args.model)
            if args.json:
                _emit_json(payload)
            else:
                print(f"Ollama: {payload['status']}  {payload.get('version', '')}".rstrip())
                print(f"Endpoint: {payload['base_url']}")
                if payload.get("error"):
                    print(f"Error: {payload['error']}")
                else:
                    print(f"Installed: {payload['installed_models']}  Running: {payload['running_models']}")
                    if payload.get("inference"):
                        inference = payload["inference"]
                        print(f"Inference: {inference['status']}  {inference['latency_ms']} ms  response={inference['response']!r}")
            if payload["status"] != "ok":
                return 1
        elif args.command == "model" and args.model_command == "pull":
            payload = pull_ollama_model(args.name, base_url=args.model_host)
            if args.json:
                _emit_json(payload)
            else:
                print(f"Pulled {args.name}: {payload.get('status', 'success')}")
        elif args.command == "model" and args.model_command == "inspect":
            payload = inspect_ollama_model(args.name, base_url=args.model_host)
            if args.json:
                _emit_json(payload)
            else:
                details = payload.get("details", {})
                fit = payload.get("vram_fit", {})
                installed = payload.get("installed") or {}
                print(f"Model       {payload['name']}")
                print(f"Family      {details.get('family', '?')}")
                print(f"Parameters  {details.get('parameter_size', '?')}")
                print(f"Quant       {details.get('quantization_level', '?')}")
                print(f"Size        {int(installed.get('size', 0)) / (1024**3):.2f} GB" if installed.get("size") else "Size        n/a")
                print(f"Capabilities {', '.join(payload.get('capabilities', [])) or 'n/a'}")
                required = fit.get("required_vram_mb")
                free = fit.get("free_vram_mb")
                verdict = fit.get("fits_free_vram")
                print(f"VRAM est.   {required} MB" if required is not None else "VRAM est.   unknown")
                print(f"VRAM free   {free} MB" if free is not None else "VRAM free   no NVIDIA telemetry")
                print(f"Fits now    {verdict}" if verdict is not None else "Fits now    unknown")
                print("Note        VRAM fit is an estimate, not a guarantee.")
        elif args.command == "model" and args.model_command == "run":
            keep_alive: str | int = args.keep_alive
            try:
                keep_alive = int(keep_alive)
            except ValueError:
                pass
            if args.prompt is None:
                payload = load_ollama_model(args.name, base_url=args.model_host, keep_alive=keep_alive)
                if args.json:
                    _emit_json(payload)
                else:
                    print(f"Loaded model: {args.name} (keep_alive={args.keep_alive})")
            else:
                payload = generate_ollama(args.name, args.prompt, base_url=args.model_host, keep_alive=keep_alive)
                if args.json:
                    _emit_json(payload)
                else:
                    print(payload.get("response", ""))
        elif args.command == "model" and args.model_command == "stop":
            payload = unload_ollama_model(args.name, base_url=args.model_host)
            if args.json:
                _emit_json(payload)
            else:
                print(f"Unloaded model: {args.name}")
        elif args.command == "model" and args.model_command == "remove":
            delete_ollama_model(args.name, base_url=args.model_host)
            if args.json:
                _emit_json({"name": args.name, "status": "removed"})
            else:
                print(f"Removed model: {args.name}")
        elif args.command == "model" and args.model_command == "hf" and args.hf_command == "inspect":
            payload = huggingface_model_info(args.repo_id)
            if args.json:
                _emit_json(payload)
            else:
                print(f"Model       {payload['id']}")
                print(f"Pipeline    {payload.get('pipeline_tag') or 'n/a'}")
                print(f"Library     {payload.get('library_name') or 'n/a'}")
                print(f"Downloads   {payload.get('downloads') if payload.get('downloads') is not None else 'n/a'}")
                print(f"Likes       {payload.get('likes') if payload.get('likes') is not None else 'n/a'}")
                print(f"Gated       {payload.get('gated')}")
                size = payload.get("estimated_repository_bytes")
                print(f"Repo size   {size / (1024**3):.2f} GB" if isinstance(size, int) else "Repo size   n/a")
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
            agent = add_agent(args.name, args.exec_command, cwd=args.cwd, max_memory_mb=args.max_memory_mb, max_cpu_seconds=args.max_cpu_seconds)
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
    except (ValueError, FileExistsError, OSError, OllamaError, HuggingFaceError) as exc:
        if getattr(args, "json", False):
            _emit_json({"error": str(exc), "type": type(exc).__name__})
        else:
            print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
