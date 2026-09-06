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
Supervisor / Containers / Python envs
            │
Linux + NVIDIA/AMD drivers
```

## Current implementation

The core intentionally stays close to Python's standard library while its contracts stabilize. This keeps the developer runtime easy to inspect and install before the desktop layer is introduced.

### Core modules

- `system.py` — host telemetry
- `gpu.py` — NVIDIA discovery through `nvidia-smi`
- `models.py` — Ollama local model discovery
- `agents.py` — persistent definitions, runtime state, logs and lifecycle control
- `supervisor.py` — detached process supervisor and optional POSIX resource limits
- `projects.py` — AI project scaffolding
- `cli.py` — `tilki` command surface and JSON output

## Agent runtime

Each registered agent has a durable definition and a separate runtime state. `tilki agent run` launches a detached supervisor, and that supervisor owns the child process. This allows the original terminal to exit while the agent continues running.

Runtime state records supervisor PID, child PID, timestamps, exit code and log path. Standard output and standard error are merged into a per-agent log. State and log filenames use hashes of agent names rather than raw names.

## Security direction

The v0.0.2 supervisor is a **developer process manager, not a security sandbox**. Commands are parsed into argv and executed directly rather than implicitly through a shell. POSIX memory/CPU rlimits provide guardrails, but untrusted code still requires containers, namespaces/cgroups or another strong isolation boundary.

Future releases will add permissioned agent execution, scoped secrets, container policies and a secrets broker so credentials do not need to live in project source.
