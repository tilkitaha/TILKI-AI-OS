from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_TYPES = {"agent", "rag", "llm", "vision", "rl", "multi-agent"}


def init_project(name: str, project_type: str, root: Path | None = None) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    if not slug:
        raise ValueError("Project name is invalid")
    if project_type not in PROJECT_TYPES:
        raise ValueError(f"Unknown project type: {project_type}")

    base = root or Path.cwd()
    target = base / slug
    if target.exists():
        raise FileExistsError(f"Project already exists: {target}")

    (target / "src").mkdir(parents=True)
    (target / "tests").mkdir()
    (target / ".tilki").mkdir()
    (target / ".gitignore").write_text(".env\n.venv/\n__pycache__/\n*.pyc\n", encoding="utf-8")
    (target / "README.md").write_text(f"# {name}\n\nCreated with TILKI AI OS.\n", encoding="utf-8")
    config = {"name": name, "slug": slug, "type": project_type, "version": 1}
    (target / ".tilki" / "project.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return target
