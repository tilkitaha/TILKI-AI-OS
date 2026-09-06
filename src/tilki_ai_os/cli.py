from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .agents import add_agent, load_agents, remove_agent
from .gpu import list_nvidia_gpus
from .models import list_ollama_models
from .projects import PROJECT_TYPES, init_project
from .system import get_system_status


def _print_status() -> None:
    status = get_system_status()
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
    gpus = list_nvidia_gpus()
    print(f"GPU      {len(gpus)} NVIDIA device(s) detected")


def _print_gpu() -> None:
    gpus = list_nvidia_gpus()
    if not gpus:
        print("No NVIDIA GPU detected or nvidia-smi is unavailable.")
        return
    for gpu in gpus:
        print(
            f"GPU {gpu.index}  {gpu.name} | VRAM {gpu.memory_used_mb}/{gpu.memory_total_mb} MB "
            f"| util {gpu.utilization_percent}% | {gpu.temperature_c}°C"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tilki", description="TILKI AI OS developer CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Show system and AI runtime status")
    commands.add_parser("gpu", help="Show NVIDIA GPU/VRAM status")

    model = commands.add_parser("model", help="Manage local models")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_commands.add_parser("list", help="List models available from local Ollama")

    agent = commands.add_parser("agent", help="Manage AI agents")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    agent_commands.add_parser("list", help="List registered agents")
    add = agent_commands.add_parser("add", help="Register an agent command")
    add.add_argument("name")
    add.add_argument("--command", dest="exec_command", required=True)
    remove = agent_commands.add_parser("remove", help="Remove a registered agent")
    remove.add_argument("name")

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
            _print_status()
        elif args.command == "gpu":
            _print_gpu()
        elif args.command == "model" and args.model_command == "list":
            models = list_ollama_models()
            if not models:
                print("No Ollama models found. Is Ollama running on 127.0.0.1:11434?")
            for model in models:
                print(model.get("name") or model.get("model") or json.dumps(model))
        elif args.command == "agent" and args.agent_command == "list":
            agents = load_agents()
            if not agents:
                print("No agents registered.")
            for agent in agents:
                print(f"{agent['name']}  [{agent.get('status', 'unknown')}]  {agent['command']}")
        elif args.command == "agent" and args.agent_command == "add":
            agent = add_agent(args.name, args.exec_command)
            print(f"Registered agent: {agent['name']}")
        elif args.command == "agent" and args.agent_command == "remove":
            if not remove_agent(args.name):
                print(f"Agent not found: {args.name}")
                return 1
            print(f"Removed agent: {args.name}")
        elif args.command == "project" and args.project_command == "init":
            target = init_project(args.name, args.type, args.path)
            print(f"Created {args.type} project at {target}")
        return 0
    except (ValueError, FileExistsError) as exc:
        print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
