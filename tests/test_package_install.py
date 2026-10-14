"""Exercise the installed CLI outside the checkout, without a Python path override."""

import json
import http.server
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

from tests.mock_l1_server import start_mock_l1_server


@unittest.skipUnless(shutil.which("uv"), "uv is required for the package installation check")
class InstalledCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.workspace = tempfile.TemporaryDirectory(prefix="ab-package-install-")
        cls.project = Path(cls.workspace.name)
        cls.env = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT",
                    "AGENT_BRANCHES_SERVER", "ADMIN_TOKEN", "RUNNER_TOKEN", "TASK_TOKEN"):
            cls.env.pop(key, None)
        cls.env["UV_NO_PROGRESS"] = "1"
        (cls.project / "pyproject.toml").write_text(
            '[project]\nname = "installed-client-check"\nversion = "0.0.0"\n'
            'requires-python = ">=3.10"\ndependencies = ["agent-branches"]\n\n'
            '[tool.uv]\npackage = false\n\n[tool.uv.sources]\n'
            'agent-branches = { path = ' + json.dumps(cls.root.as_posix()) + ', editable = true }\n',
            encoding="utf-8",
        )
        installed = subprocess.run(
            ["uv", "sync", "--project", str(cls.project)],
            cwd=cls.project, env=cls.env, text=True, capture_output=True, timeout=180,
        )
        if installed.returncode:
            cls.workspace.cleanup()
            raise RuntimeError("Isolated uv sync failed:\n" + installed.stderr)
        cls.server, cls.thread, cls.server_url, cls.state = start_mock_l1_server(
            expected_admin_token="package-test-admin", expected_runner_token="package-test-runner"
        )
        cls.env.update(ADMIN_TOKEN="package-test-admin", RUNNER_TOKEN="package-test-runner")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.workspace.cleanup()

    def run_installed(self, args, *, module=False):
        command = ["uv", "run", "--project", str(self.project), "--locked"]
        command += ["python", "-m", "agent_branches"] if module else ["branches"]
        return subprocess.run(
            command + args, cwd=self.project, env=self.env,
            text=True, capture_output=True, timeout=30,
        )

    def test_console_and_module_status_use_authenticated_shared_client(self):
        for module in (False, True):
            with self.subTest(module=module):
                result = self.run_installed(["status", "--server", self.server_url, "--json"], module=module)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsInstance(json.loads(result.stdout), dict)

    def test_installed_task_create_reaches_coordinator(self):
        result = self.run_installed([
            "task", "create", "--server", self.server_url,
            "--repo", "https://example.invalid/project.git", "--base-sha", "a" * 40,
            "--branch", "packaging-check", "--agent", "package-test",
            "--intent", "Exercise the installed client", "--json",
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        created = json.loads(result.stdout)
        task_id = created.get("taskId") or created.get("task_id") or created.get("id")
        self.assertIn(task_id, self.state.tasks)
        self.assertEqual(self.state.tasks[task_id]["intent"], "Exercise the installed client")

    def test_prototype_project_runs_branches_without_a_python_path_override(self):
        result = subprocess.run(
            ["uv", "run", "--locked", "branches", "status", "--server", self.server_url, "--json"],
            cwd=self.root / "prototype", env=self.env,
            text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)

    def test_distribution_exposes_existing_cli_and_no_unrelated_packages(self):
        script = (
            "import importlib.metadata as m,json; d=m.distribution('agent-branches'); "
            "print(json.dumps({'entrypoints':{e.name:e.value for e in d.entry_points},"
            "'top_level':d.read_text('top_level.txt').splitlines()}))"
        )
        result = subprocess.run(
            ["uv", "run", "--project", str(self.project), "--locked", "python", "-c", script],
            cwd=self.project, env=self.env, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        self.assertEqual(metadata["entrypoints"]["branches"], "agent_branches.cli:main")
        self.assertEqual(metadata["top_level"], ["agent_branches"])

    def test_authenticated_ack_is_identical_for_console_module_and_legacy_script(self):
        calls = []

        class AckHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.respond({"taskId": "task-packaging", "agentId": "agent-packaging"})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                calls.append((self.path, self.headers.get("Authorization"), payload))
                self.respond({"acknowledged": True, "warning_id": "warning-packaging"})

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), AckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        args = ["ack", "--server", f"http://127.0.0.1:{server.server_port}",
                "--task-id", "task-packaging", "--warning-id", "warning-packaging",
                "--action", "manual_merge", "--json"]
        try:
            for module in (False, True):
                result = self.run_installed(args, module=module)
                self.assertEqual(result.returncode, 0, result.stderr)
            legacy = subprocess.run(
                ["uv", "run", "--project", str(self.project), "--locked", "python",
                 str(self.root / "agent-branches")] + args,
                cwd=self.project, env=self.env, text=True, capture_output=True, timeout=30,
            )
            self.assertEqual(legacy.returncode, 0, legacy.stderr)
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0], calls[1])
            self.assertEqual(calls[1], calls[2])
            self.assertEqual(calls[0][0], "/warnings/warning-packaging/ack")
            self.assertEqual(calls[0][1], "Bearer package-test-admin")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
