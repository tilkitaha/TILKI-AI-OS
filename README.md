# TILKI AI OS

**Build. Run. Observe. Deploy Intelligence.**

TILKI AI OS is an AI-native developer operating environment: a Linux-first control layer for local models, AI agents, GPU resources, datasets, evaluation and deployment.

> Status: **v0.0.3 — Model Manager milestone**. This is not yet a bootable Linux distribution. The project is intentionally starting as a real developer runtime before growing into a desktop and installable OS image.

## What works now

- `tilki status` — system health summary
- `tilki gpu` — NVIDIA GPU / VRAM / utilization via `nvidia-smi`
- `tilki model pull|run|stop|remove|inspect|list|running|health` — manages local Ollama models
- `tilki model hf inspect` — reads Hugging Face Hub model metadata
- Model inspection includes NVIDIA VRAM-fit estimation
- `tilki agent add|run|stop|status|logs|list|remove` — supervised persistent agent runtime
- `tilki project init` — scaffolds AI Agent, RAG, LLM, Vision, RL and multi-agent workspaces
- Zero required runtime dependencies beyond Python 3.10+

## Install from source

```bash
git clone https://github.com/tilkitaha/TILKI-AI-OS.git
cd TILKI-AI-OS
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

On Windows PowerShell, activate with `.venv\\Scripts\\Activate.ps1`.

## Try it

```bash
tilki status
tilki gpu
tilki model health
tilki model list
tilki model pull qwen3:4b
tilki model inspect qwen3:4b
tilki model run qwen3:4b
tilki model run qwen3:4b --prompt "Explain RAG in one sentence."
tilki model stop qwen3:4b
tilki model hf inspect Qwen/Qwen3-4B

tilki agent add researcher --command "python researcher.py"
tilki agent run researcher
tilki agent status researcher
tilki agent logs researcher --lines 100
tilki agent stop researcher
tilki --json agent list

tilki project init gridmind-agent --type agent
tilki project init docs-rag --type rag
```

## Product direction

TILKI AI OS will evolve through four layers:

1. **Core Runtime** — CLI, system/GPU telemetry, models, agents, secrets and projects.
2. **AI Services** — dataset vault, unified model gateway, evaluation engine and sandboxed agent runtime.
3. **Command Center** — desktop UI with live GPU/process/model/agent observability and AI System Graph.
4. **Distribution** — Linux-based installable image with NVIDIA/AMD tooling and a first-boot developer experience.

See [`docs/architecture.md`](docs/architecture.md), [`docs/runtime.md`](docs/runtime.md), [`docs/models.md`](docs/models.md) and [`docs/roadmap.md`](docs/roadmap.md).

## Philosophy

Normal operating systems organize apps and files. TILKI AI OS is designed to organize **models, agents, datasets, experiments, compute and deployment** as first-class developer objects.

## License

MIT — see [`LICENSE`](LICENSE).
