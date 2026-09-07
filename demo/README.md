# TILKI AI OS — Command Center Demo

A dependency-free interactive browser demo for TILKI AI OS v0.0.3.

## Run locally

```bash
cd demo
python -m http.server 8080
```

Open `http://localhost:8080`.

## What is real in this demo

The UI state machine is functional: models can be pulled/loaded/unloaded/removed, agents can be registered/started/stopped/removed, VRAM pressure is calculated, terminal commands mutate the same state, and browser state persists in `localStorage`.

The public browser build intentionally runs in **sandbox mode**. It does not claim to access the visitor's real GPU, processes, Ollama installation, or filesystem. Those capabilities belong to the local TILKI AI OS CLI/runtime in the main repository.

## Useful terminal commands

```text
status
gpu
model list
model running
model pull llama3.2:3b
model run qwen3:4b
model inspect qwen3:4b
model stop qwen3:4b
agent list
agent add analyst --command "python analyst.py"
agent run analyst
agent status analyst
agent logs analyst
agent stop analyst
help
```
