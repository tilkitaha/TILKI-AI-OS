from __future__ import annotations

import json
import urllib.error
import urllib.request


def list_ollama_models(endpoint: str = "http://127.0.0.1:11434/api/tags") -> list[dict[str, object]]:
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []

    models = payload.get("models", [])
    return models if isinstance(models, list) else []
