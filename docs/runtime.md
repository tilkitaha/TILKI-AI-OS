# Agent Runtime

TILKI AI OS v0.0.2 introduces a persistent local supervisor for developer agents.

## Lifecycle

1. `tilki agent add` stores an agent definition under `~/.tilki-ai-os/agents.json`.
2. `tilki agent run NAME` launches a detached TILKI supervisor.
3. The supervisor launches the configured command, captures stdout/stderr and writes runtime state.
4. `tilki agent status`, `logs` and `stop` communicate through persisted state rather than requiring the original terminal to stay open.

Runtime metadata lives under `~/.tilki-ai-os/runtime/` and logs under `~/.tilki-ai-os/logs/`. Filenames are derived from a hash of the agent name so agent names cannot escape the state directory.

## Commands

```bash
tilki agent add researcher --command "python researcher.py" --cwd ./agents/researcher
tilki agent run researcher
tilki agent status researcher
tilki agent logs researcher --lines 100
tilki agent stop researcher
```

Machine-readable output is available by putting `--json` before the command:

```bash
tilki --json agent status researcher
tilki --json agent list
```

## Resource limits

On POSIX systems, optional CPU-time and address-space limits are inherited by the agent process:

```bash
tilki agent add bounded \
  --command "python worker.py" \
  --max-memory-mb 4096 \
  --max-cpu-seconds 600
```

Windows records these settings but does not enforce them yet. A future runtime will use native Windows job objects and container/cgroup policies for stronger isolation.

## Command execution model

Registered commands are tokenized and executed directly; TILKI does **not** implicitly invoke a shell. This avoids accidental shell expansion. If shell syntax is intentionally required, register the shell explicitly, for example `bash -lc "..."`.

This supervisor is a developer-process manager, not yet a security sandbox. Untrusted agent code should still be run inside a container or other isolation boundary.
