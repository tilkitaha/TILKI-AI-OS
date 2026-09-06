# Architecture

## Layers

```text
TILKI Command Center (desktop UI)
            │
TILKI Core API / Event Bus
            │
┌───────────┼────────────┬─────────────┐
│ Models    │ Agents     │ Projects    │
│ GPU       │ Secrets    │ Evaluation  │
│ Datasets  │ Gateway    │ Deployment  │
└───────────┴────────────┴─────────────┘
            │
Containers / Python envs / local runtimes
            │
Linux + NVIDIA/AMD drivers
```

## v0.0.1 implementation

The first milestone deliberately uses Python's standard library. This keeps installation simple while the contracts for system telemetry, model discovery, agent registration and project creation stabilize.

### Core modules

- `system.py` — host telemetry
- `gpu.py` — NVIDIA discovery through `nvidia-smi`
- `models.py` — Ollama local model discovery
- `agents.py` — local persistent agent registry
- `projects.py` — AI project scaffolding
- `cli.py` — `tilki` command surface

## Security direction

Future agent execution will be permissioned and sandboxed. API credentials will be held by a secrets broker instead of copied into project source. The OS must never treat arbitrary agent code as trusted by default.
