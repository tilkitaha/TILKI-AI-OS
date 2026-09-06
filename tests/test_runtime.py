from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from tilki_ai_os.agents import (
    add_agent,
    get_runtime,
    list_agent_statuses,
    log_path,
    remove_agent,
    start_agent,
    stop_agent,
    tail_agent_logs,
)


def wait_for_state(name: str, home: Path, terminal: set[str], timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict | None = None
    while time.monotonic() < deadline:
        state = get_runtime(name, home)
        if state:
            last = state
            if state.get("status") in terminal:
                return state
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {terminal}; last state={last}")


class RuntimeTests(unittest.TestCase):
    def test_agent_runs_to_completion_and_captures_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            work = Path(tmp) / "work"
            work.mkdir()
            script = work / "hello_agent.py"
            script.write_text('print("hello from agent", flush=True)\n', encoding="utf-8")
            command = f'"{sys.executable}" "{script}"'
            add_agent("hello", command, home, cwd=str(work))

            started = start_agent("hello", home)
            self.assertEqual(started["status"], "starting")
            self.assertGreater(int(started["supervisor_pid"]), 0)

            finished = wait_for_state("hello", home, {"completed", "failed"})
            self.assertEqual(finished["status"], "completed", finished)
            self.assertEqual(finished["exit_code"], 0)
            self.assertIn("hello from agent", "\n".join(tail_agent_logs("hello", home, lines=20)))
            self.assertTrue(log_path("hello", home).exists())

    def test_running_agent_can_be_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            work = Path(tmp) / "work"
            work.mkdir()
            script = work / "sleep_agent.py"
            script.write_text(
                'import time\nprint("agent ready", flush=True)\ntime.sleep(30)\n',
                encoding="utf-8",
            )
            command = f'"{sys.executable}" "{script}"'
            add_agent("sleeper", command, home, cwd=str(work))
            start_agent("sleeper", home)
            running = wait_for_state("sleeper", home, {"running", "completed", "failed"})
            self.assertEqual(running["status"], "running", running)

            stopped = stop_agent("sleeper", home, wait_seconds=5.0)
            if stopped["status"] == "stopping":
                stopped = wait_for_state("sleeper", home, {"stopped", "failed"})
            self.assertEqual(stopped["status"], "stopped", stopped)
            self.assertIsNotNone(stopped["exit_code"])

    def test_running_agent_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            work = Path(tmp) / "work"
            work.mkdir()
            script = work / "sleep_agent.py"
            script.write_text('import time\ntime.sleep(30)\n', encoding="utf-8")
            add_agent("protected", f'"{sys.executable}" "{script}"', home, cwd=str(work))
            start_agent("protected", home)
            wait_for_state("protected", home, {"running"})
            try:
                with self.assertRaises(ValueError):
                    remove_agent("protected", home)
            finally:
                stop_agent("protected", home, wait_seconds=5.0)

    def test_registry_persists_runtime_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            work = Path(tmp) / "work"
            work.mkdir()
            agent = add_agent(
                "bounded",
                f'"{sys.executable}" -c "print(1)"',
                home,
                cwd=str(work),
                max_memory_mb=512,
                max_cpu_seconds=5,
            )
            self.assertEqual(agent["max_memory_mb"], 512)
            self.assertEqual(agent["max_cpu_seconds"], 5)
            self.assertEqual(agent["cwd"], str(work.resolve()))
            statuses = list_agent_statuses(home)
            self.assertEqual(statuses[0]["status"], "registered")
            self.assertIsNone(statuses[0]["uptime_seconds"])


if __name__ == "__main__":
    unittest.main()
