from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tilki_ai_os.agents import add_agent, load_agents, remove_agent
from tilki_ai_os.cli import main
from tilki_ai_os.projects import init_project
from tilki_ai_os.system import get_system_status


class CoreTests(unittest.TestCase):
    def test_system_status_has_cpu(self) -> None:
        self.assertGreaterEqual(get_system_status().cpu_count, 1)

    def test_agent_registry_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            add_agent("researcher", "python researcher.py", home)
            self.assertEqual(load_agents(home)[0]["name"], "researcher")
            self.assertTrue(remove_agent("researcher", home))
            self.assertEqual(load_agents(home), [])

    def test_duplicate_agent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            add_agent("coder", "python coder.py", home)
            with self.assertRaises(ValueError):
                add_agent("coder", "python other.py", home)

    def test_project_init_creates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = init_project("My RAG", "rag", Path(tmp))
            manifest = json.loads((target / ".tilki" / "project.json").read_text())
            self.assertEqual(manifest["slug"], "my-rag")
            self.assertEqual(manifest["type"], "rag")
            self.assertTrue((target / "src").is_dir())
            self.assertTrue((target / "tests").is_dir())

    def test_cli_agent_add_dispatches_correctly(self) -> None:
        # Regression: --command must not overwrite the top-level subcommand.
        import tilki_ai_os.cli as cli
        original_add = cli.add_agent
        captured: dict[str, str] = {}

        def fake_add(name: str, command: str) -> dict[str, str]:
            captured["name"] = name
            captured["command"] = command
            return {"name": name}

        cli.add_agent = fake_add
        try:
            out = StringIO()
            with redirect_stdout(out):
                code = main(["agent", "add", "researcher", "--command", "python researcher.py"])
            self.assertEqual(code, 0)
            self.assertEqual(captured, {"name": "researcher", "command": "python researcher.py"})
            self.assertIn("Registered agent: researcher", out.getvalue())
        finally:
            cli.add_agent = original_add


if __name__ == "__main__":
    unittest.main()
