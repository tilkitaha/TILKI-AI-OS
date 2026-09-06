from __future__ import annotations

import json
from pathlib import Path


def registry_path(home: Path | None = None) -> Path:
    base = home or Path.home()
    return base / ".tilki-ai-os" / "agents.json"


def load_agents(home: Path | None = None) -> list[dict[str, str]]:
    path = registry_path(home)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def add_agent(name: str, command: str, home: Path | None = None) -> dict[str, str]:
    name = name.strip()
    command = command.strip()
    if not name or not command:
        raise ValueError("Agent name and command are required")

    agents = load_agents(home)
    if any(agent.get("name") == name for agent in agents):
        raise ValueError(f"Agent '{name}' already exists")
    agent = {"name": name, "command": command, "status": "registered"}
    agents.append(agent)
    path = registry_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(agents, indent=2) + "\n", encoding="utf-8")
    return agent


def remove_agent(name: str, home: Path | None = None) -> bool:
    agents = load_agents(home)
    filtered = [agent for agent in agents if agent.get("name") != name]
    if len(filtered) == len(agents):
        return False
    path = registry_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(filtered, indent=2) + "\n", encoding="utf-8")
    return True
