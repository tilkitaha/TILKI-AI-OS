# Model Manager

TILKI AI OS v0.0.3 manages local Ollama models and can inspect public Hugging Face Hub metadata without adding a runtime dependency.

## Ollama commands

```bash
tilki model health
tilki model health --model qwen3:4b

tilki model list
tilki model running

tilki model pull qwen3:4b
tilki model inspect qwen3:4b

tilki model run qwen3:4b
tilki model run qwen3:4b --prompt "Explain RAG in one sentence."
tilki model stop qwen3:4b
tilki model remove qwen3:4b
```

Use `--json` before `model` for machine-readable output:

```bash
tilki --json model inspect qwen3:4b
```

Use a non-default Ollama endpoint with `--host` or `OLLAMA_HOST`:

```bash
tilki model --host http://127.0.0.1:11434 health
```

## Run semantics

`tilki model run NAME` preloads the model through Ollama and keeps it resident using `keep_alive=-1` by default. Add `--prompt` to perform a non-streaming generation. `tilki model stop NAME` requests immediate unload with `keep_alive=0`.

## VRAM fit estimate

`tilki model inspect NAME` combines Ollama model metadata, currently loaded model state and NVIDIA telemetry.

- If the model is already running, `size_vram` is treated as measured runtime usage.
- Otherwise, TILKI estimates from the local artifact size plus a conservative runtime/context overhead.
- The result is advisory only. Context length, KV cache, GPU offload, quantization and backend behavior can materially change real memory use.

## Hugging Face metadata

```bash
tilki model hf inspect Qwen/Qwen3-4B
```

The command retrieves model repository metadata such as pipeline tag, library, downloads, likes, gated/private state and approximate repository file size. `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` is used automatically when present.

## Security and privacy

The default Ollama endpoint is local (`127.0.0.1:11434`). A remote `--host` changes the trust boundary: prompts and model operations are sent to that server. TILKI AI OS does not upload local prompts to Hugging Face when only using `model hf inspect`; that command requests repository metadata only.
