# Roadmap

## v0.0.1 — Core CLI ✅

- System status
- NVIDIA GPU telemetry
- Ollama model discovery
- Agent registry
- AI project scaffolding
- Automated tests and CI

## v0.0.2 — Agent Runtime ✅

- Start/stop supervised agent processes
- Persistent PID, child PID and lifecycle state
- Captured stdout/stderr logs and exit status
- Runtime duration tracking
- Optional POSIX memory and CPU-time limits
- Project/agent working-directory configuration
- Structured JSON output for UI integration
- Regression and lifecycle tests

## v0.0.3 — Model Manager ✅

- Ollama pull/list/run/preload/unload/remove
- Installed and currently-loaded model inspection
- Hugging Face Hub model metadata
- NVIDIA VRAM fit estimation with measured/estimated confidence
- Ollama API health and optional real inference health check
- `OLLAMA_HOST`, optional cloud API-key support and structured JSON output
- Full fake-API contract tests

## v0.0.4 — Secrets Vault

- OS keyring integration
- Scoped secrets per project/agent
- Redaction in logs
- Git preflight secret scan

## v0.1.0 — Developer Preview

- Local API daemon
- Command Center web/desktop UI
- Agent + model + GPU dashboard
- AI System Graph
- Installer for Linux developer machines

## v0.2+

- Dataset Vault
- Evaluation Lab
- Unified AI Gateway
- Container/sandbox policies
- One-command deployment
- Bootable Linux image research
