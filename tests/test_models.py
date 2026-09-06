from __future__ import annotations

import json
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from tilki_ai_os.cli import main
from tilki_ai_os.gpu import GPUInfo
from tilki_ai_os.models import (
    delete_ollama_model,
    estimate_vram_fit,
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


class FakeHandler(BaseHTTPRequestHandler):
    requests: list[tuple[str, str, dict[str, Any] | None]] = []

    def log_message(self, format: str, *args: object) -> None:
        return

    def _body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return None
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        type(self).requests.append(("GET", self.path, None))
        if self.path == "/api/version":
            self._send({"version": "0.99.0-test"})
        elif self.path == "/api/tags":
            self._send({"models": [{"name": "qwen3:4b", "model": "qwen3:4b", "size": 3 * 1024**3, "details": {"parameter_size": "4B", "quantization_level": "Q4_K_M"}}]})
        elif self.path == "/api/ps":
            self._send({"models": [{"name": "qwen3:4b", "model": "qwen3:4b", "size_vram": 2800 * 1024**2, "context_length": 4096}]})
        elif self.path == "/hf/owner/model":
            self._send({
                "id": "owner/model", "author": "owner", "pipeline_tag": "text-generation", "library_name": "transformers",
                "downloads": 1234, "likes": 42, "private": False, "gated": False, "lastModified": "2026-09-01T00:00:00Z",
                "tags": ["transformers", "text-generation"],
                "siblings": [{"rfilename": "weights.safetensors", "size": 1024}, {"rfilename": "config.json", "size": 256}],
            })
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self) -> None:
        body = self._body()
        type(self).requests.append(("POST", self.path, body))
        if self.path == "/api/show":
            self._send({
                "details": {"family": "qwen3", "parameter_size": "4B", "quantization_level": "Q4_K_M"},
                "capabilities": ["completion", "tools"],
                "modified_at": "2026-09-01T00:00:00Z",
                "model_info": {"qwen3.context_length": 32768, "qwen3.block_count": 36},
            })
        elif self.path == "/api/pull":
            self._send({"status": "success"})
        elif self.path == "/api/generate":
            self._send({"model": body.get("model") if body else None, "response": "OK" if body and body.get("prompt") else "", "done": True, "eval_count": 1, "total_duration": 1000})
        else:
            self._send({"error": "not found"}, 404)

    def do_DELETE(self) -> None:
        body = self._body()
        type(self).requests.append(("DELETE", self.path, body))
        if self.path == "/api/delete":
            self._send({})
        else:
            self._send({"error": "not found"}, 404)


class ModelManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), FakeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api = f"http://127.0.0.1:{cls.server.server_port}/api"
        cls.hf = f"http://127.0.0.1:{cls.server.server_port}/hf"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        FakeHandler.requests.clear()

    def test_list_and_running_models(self) -> None:
        self.assertEqual(list_ollama_models(base_url=self.api, strict=True)[0]["name"], "qwen3:4b")
        self.assertEqual(list_running_ollama_models(self.api)[0]["context_length"], 4096)

    def test_pull_load_generate_unload_delete_contracts(self) -> None:
        self.assertEqual(pull_ollama_model("qwen3:4b", self.api)["status"], "success")
        load_ollama_model("qwen3:4b", base_url=self.api, keep_alive=-1)
        response = generate_ollama("qwen3:4b", "hello", base_url=self.api, keep_alive="1m")
        self.assertEqual(response["response"], "OK")
        unload_ollama_model("qwen3:4b", self.api)
        delete_ollama_model("qwen3:4b", self.api)
        generate_bodies = [body for method, path, body in FakeHandler.requests if path == "/api/generate"]
        self.assertEqual(generate_bodies[0]["keep_alive"], -1)
        self.assertEqual(generate_bodies[1]["prompt"], "hello")
        self.assertEqual(generate_bodies[2]["keep_alive"], 0)
        delete = [item for item in FakeHandler.requests if item[1] == "/api/delete"][-1]
        self.assertEqual(delete[2], {"model": "qwen3:4b"})

    def test_health_can_validate_real_inference_path(self) -> None:
        result = ollama_health(self.api, model="qwen3:4b")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["version"], "0.99.0-test")
        self.assertEqual(result["installed_models"], 1)
        self.assertEqual(result["inference"]["response"], "OK")

    def test_inspect_combines_metadata_and_running_state(self) -> None:
        payload = inspect_ollama_model("qwen3:4b", self.api)
        self.assertEqual(payload["details"]["family"], "qwen3")
        self.assertEqual(payload["running"]["context_length"], 4096)
        self.assertEqual(payload["vram_fit"]["source"], "running_size_vram")
        self.assertEqual(payload["model_info"]["qwen3.context_length"], 32768)

    def test_vram_fit_uses_free_gpu_memory(self) -> None:
        gpu = GPUInfo(0, "Test GPU", 2000, 12000, 0, 40)
        installed = {"size": 4 * 1024**3}
        fit = estimate_vram_fit(installed, gpus=[gpu])
        self.assertEqual(fit["confidence"], "estimate")
        self.assertTrue(fit["fits_free_vram"])
        self.assertGreater(fit["required_vram_mb"], 4096)

    def test_cli_health_and_inference_commands(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--json", "model", "--host", self.api, "health", "--model", "qwen3:4b"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "ok")
        out = StringIO()
        with redirect_stdout(out):
            code = main(["model", "--host", self.api, "run", "qwen3:4b", "--prompt", "hello"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "OK")

    def test_huggingface_metadata_is_compacted(self) -> None:
        info = huggingface_model_info("owner/model", endpoint=self.hf)
        self.assertEqual(info["id"], "owner/model")
        self.assertEqual(info["pipeline_tag"], "text-generation")
        self.assertEqual(info["estimated_repository_bytes"], 1280)


if __name__ == "__main__":
    unittest.main()
