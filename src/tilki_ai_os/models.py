from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .gpu import GPUInfo, list_nvidia_gpus

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/api"
_MIB = 1024 * 1024


class OllamaError(RuntimeError):
    """Raised when the local Ollama API cannot complete a request."""


def ollama_base_url(base_url: str | None = None) -> str:
    value = (base_url or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_BASE_URL).strip()
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    value = value.rstrip("/")
    if not value.endswith("/api"):
        value += "/api"
    return value


def _request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    base_url: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    url = f"{ollama_base_url(base_url)}/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"

    api_key = os.environ.get("OLLAMA_API_KEY")
    if api_key and url.startswith("https://ollama.com/"):
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            detail = str(parsed.get("error") or body).strip()
        except (OSError, json.JSONDecodeError):
            detail = str(exc.reason or "")
        suffix = f": {detail}" if detail else ""
        raise OllamaError(f"Ollama HTTP {exc.code}{suffix}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise OllamaError(f"Ollama is unavailable at {ollama_base_url(base_url)}: {exc}") from exc

    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OllamaError("Ollama returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise OllamaError("Ollama returned an unexpected response")
    if parsed.get("error"):
        raise OllamaError(str(parsed["error"]))
    return parsed


def get_ollama_version(base_url: str | None = None) -> str:
    payload = _request_json("version", base_url=base_url, timeout=2.0)
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise OllamaError("Ollama version response did not include a version")
    return version


def ollama_health(base_url: str | None = None, model: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        version = get_ollama_version(base_url)
        models = list_ollama_models(base_url=base_url, strict=True)
        running = list_running_ollama_models(base_url=base_url)
        result: dict[str, Any] = {
            "status": "ok",
            "base_url": ollama_base_url(base_url),
            "version": version,
            "installed_models": len(models),
            "running_models": len(running),
        }
        if model:
            inference_started = time.perf_counter()
            response = generate_ollama(model, "Reply with OK only.", base_url=base_url, keep_alive="30s")
            result["inference"] = {
                "model": model,
                "status": "ok",
                "response": response.get("response", ""),
                "latency_ms": round((time.perf_counter() - inference_started) * 1000, 1),
                "eval_count": response.get("eval_count"),
                "total_duration_ns": response.get("total_duration"),
            }
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result
    except OllamaError as exc:
        return {
            "status": "unavailable",
            "base_url": ollama_base_url(base_url),
            "error": str(exc),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }


def list_ollama_models(
    endpoint: str | None = None,
    *,
    base_url: str | None = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    try:
        if endpoint and endpoint.rstrip("/").endswith("/api/tags"):
            request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=1.5) as response:
                payload = json.load(response)
        else:
            payload = _request_json("tags", base_url=base_url, timeout=2.0)
    except (OllamaError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        if strict:
            if isinstance(exc, OllamaError):
                raise
            raise OllamaError(str(exc)) from exc
        return []

    models = payload.get("models", []) if isinstance(payload, dict) else []
    return models if isinstance(models, list) else []


def list_running_ollama_models(base_url: str | None = None) -> list[dict[str, Any]]:
    payload = _request_json("ps", base_url=base_url, timeout=2.0)
    models = payload.get("models", [])
    return models if isinstance(models, list) else []


def pull_ollama_model(model: str, base_url: str | None = None) -> dict[str, Any]:
    _validate_model_name(model)
    return _request_json("pull", method="POST", payload={"model": model, "stream": False}, base_url=base_url, timeout=3600.0)


def show_ollama_model(model: str, base_url: str | None = None) -> dict[str, Any]:
    _validate_model_name(model)
    return _request_json("show", method="POST", payload={"model": model, "verbose": False}, base_url=base_url, timeout=10.0)


def delete_ollama_model(model: str, base_url: str | None = None) -> None:
    _validate_model_name(model)
    _request_json("delete", method="DELETE", payload={"model": model}, base_url=base_url, timeout=30.0)


def generate_ollama(model: str, prompt: str, *, base_url: str | None = None, keep_alive: str | int = "5m") -> dict[str, Any]:
    _validate_model_name(model)
    return _request_json(
        "generate",
        method="POST",
        payload={"model": model, "prompt": prompt, "stream": False, "keep_alive": keep_alive},
        base_url=base_url,
        timeout=3600.0,
    )


def load_ollama_model(model: str, *, base_url: str | None = None, keep_alive: str | int = -1) -> dict[str, Any]:
    return generate_ollama(model, "", base_url=base_url, keep_alive=keep_alive)


def unload_ollama_model(model: str, base_url: str | None = None) -> dict[str, Any]:
    return generate_ollama(model, "", base_url=base_url, keep_alive=0)


def inspect_ollama_model(model: str, base_url: str | None = None) -> dict[str, Any]:
    details = show_ollama_model(model, base_url=base_url)
    installed = _find_model(model, list_ollama_models(base_url=base_url, strict=True))
    running = _find_model(model, list_running_ollama_models(base_url=base_url))
    fit = estimate_vram_fit(installed, running=running)
    return {
        "name": model,
        "installed": installed,
        "running": running,
        "details": details.get("details", {}),
        "capabilities": details.get("capabilities", []),
        "modified_at": details.get("modified_at"),
        "model_info": _compact_model_info(details.get("model_info", {})),
        "vram_fit": fit,
    }


def estimate_vram_fit(installed: dict[str, Any] | None, *, running: dict[str, Any] | None = None, gpus: list[GPUInfo] | None = None) -> dict[str, Any]:
    gpus = list_nvidia_gpus() if gpus is None else gpus
    total_mb = sum(gpu.memory_total_mb for gpu in gpus)
    free_mb = sum(gpu.memory_free_mb for gpu in gpus)
    actual_vram_bytes = _int_value((running or {}).get("size_vram"))
    artifact_bytes = _int_value((installed or {}).get("size"))
    if actual_vram_bytes:
        required_mb = math.ceil(actual_vram_bytes / _MIB)
        source, confidence = "running_size_vram", "measured"
    elif artifact_bytes:
        required_mb = math.ceil((artifact_bytes / _MIB) * 1.20 + 512)
        source, confidence = "artifact_size_plus_overhead", "estimate"
    else:
        required_mb = None
        source, confidence = "unknown", "unknown"
    return {
        "gpu_count": len(gpus),
        "total_vram_mb": total_mb if gpus else None,
        "free_vram_mb": free_mb if gpus else None,
        "required_vram_mb": required_mb,
        "fits_free_vram": (free_mb >= required_mb) if gpus and required_mb is not None else None,
        "source": source,
        "confidence": confidence,
        "note": "Estimate only; context length, KV cache, offload and backend behavior can change real VRAM use.",
    }


def _validate_model_name(model: str) -> None:
    if not model or not model.strip():
        raise ValueError("Model name is required")
    if any(ord(char) < 32 for char in model):
        raise ValueError("Model name contains control characters")


def _find_model(name: str, models: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = name.casefold()
    for model in models:
        for key in ("name", "model"):
            value = model.get(key)
            if isinstance(value, str) and value.casefold() == wanted:
                return model
    return None


def _int_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _compact_model_info(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for key, item in value.items():
        if key.endswith(".context_length") or key.endswith(".block_count"):
            compact[str(key)] = item
    return compact


class HuggingFaceError(RuntimeError):
    """Raised when Hugging Face model metadata cannot be retrieved."""


def huggingface_model_info(repo_id: str, *, endpoint: str = "https://huggingface.co/api/models", timeout: float = 8.0) -> dict[str, Any]:
    from urllib.parse import quote

    repo_id = repo_id.strip()
    if not repo_id or "/" not in repo_id:
        raise ValueError("Hugging Face repo id must look like 'owner/model'")
    url = f"{endpoint.rstrip('/')}/{quote(repo_id, safe='/')}"
    headers = {"Accept": "application/json", "User-Agent": "TILKI-AI-OS/0.0.3"}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            pass
        suffix = f": {detail[:200]}" if detail else ""
        raise HuggingFaceError(f"Hugging Face HTTP {exc.code}{suffix}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise HuggingFaceError(f"Hugging Face is unavailable: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HuggingFaceError("Hugging Face returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HuggingFaceError("Hugging Face returned an unexpected response")
    siblings = payload.get("siblings")
    total_size = 0
    if isinstance(siblings, list):
        for item in siblings:
            if isinstance(item, dict):
                size = item.get("size")
                if isinstance(size, int) and size > 0:
                    total_size += size
                lfs = item.get("lfs")
                if isinstance(lfs, dict) and isinstance(lfs.get("size"), int):
                    total_size += int(lfs["size"]) if not isinstance(size, int) else 0
    return {
        "id": payload.get("id") or payload.get("modelId") or repo_id,
        "author": payload.get("author"),
        "pipeline_tag": payload.get("pipeline_tag"),
        "library_name": payload.get("library_name"),
        "downloads": payload.get("downloads"),
        "likes": payload.get("likes"),
        "private": payload.get("private"),
        "gated": payload.get("gated"),
        "last_modified": payload.get("lastModified"),
        "tags": payload.get("tags", []),
        "estimated_repository_bytes": total_size or None,
    }
