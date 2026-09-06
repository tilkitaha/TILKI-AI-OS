# TILKI AI OS

**Build. Run. Observe. Deploy Intelligence.**

TILKI AI OS is an AI-native developer operating environment: a Linux-first control layer for local models, AI agents, GPU resources, datasets, evaluation and deployment.

> Status: **v0.0.1 — Core CLI milestone**. This is not yet a bootable Linux distribution. The project is intentionally starting as a real developer runtime before growing into a desktop and installable OS image.

## What works now

- `tilki status` — system health summary
- `tilki gpu` — NVIDIA GPU / VRAM / utilization via `nvidia-smi`
- `tilki model list` — discovers local Ollama models
- `tilki agent add|list|remove` — persistent local agent registry
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
tilki model list

tilki agent add researcher --command "python researcher.py"
tilki agent list

tilki project init gridmind-agent --type agent
tilki project init docs-rag --type rag
```

## Product direction

TILKI AI OS will evolve through four layers:

1. **Core Runtime** — CLI, system/GPU telemetry, models, agents, secrets and projects.
2. **AI Services** — dataset vault, unified model gateway, evaluation engine and sandboxed agent runtime.
3. **Command Center** — desktop UI with live GPU/process/model/agent observability and AI System Graph.
4. **Distribution** — Linux-based installable image with NVIDIA/AMD tooling and a first-boot developer experience.

See [`docs/architecture.md`](docs/architecture.md) and [`docs/roadmap.md`](docs/roadmap.md).

## Philosophy

Normal operating systems organize apps and files. TILKI AI OS is designed to organize **models, agents, datasets, experiments, compute and deployment** as first-class developer objects.

## License

MIT — see [`LICENSE`](LICENSE).
