"""Offline bootstrap parity checks; these do not establish Cloudflare proof.

Execute the real helper's nested bootstrap and display functions with fake HTTP
and Git transports, so no cloud writes, external services or credentials are used.
"""
import ast
import contextlib
import copy
import io
import json
import pathlib
import shlex
import subprocess
import tempfile
import types
import unittest
import urllib.parse
import urllib.request
from unittest.mock import patch


SOURCE = pathlib.Path(__file__).with_name("pair-example.py")


class BootstrapParityTests(unittest.TestCase):
    def execute_bootstrap(self, cloud, repo_count=0):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        names = {"show", "print_output", "git", "request", "prepare_baseline"}
        functions = [copy.deepcopy(node) for node in main.body if isinstance(node, ast.FunctionDef) and node.name in names]

        class Standalone(ast.NodeTransformer):
            def visit_Nonlocal(self, node):
                return ast.copy_location(ast.Global(names=node.names), node)

        module = ast.fix_missing_locations(Standalone().visit(ast.Module(body=functions, type_ignores=[])))
        requests, git_calls = [], []
        budget = {"repoCount": repo_count, "remainingDayOps": 200, "remainingMonthOps": 6000,
                  "dailyCap": 200, "monthlyCap": 6000, "maxRepos": 4, "maxTotalBytes": 16 * 1024 * 1024,
                  "utcDayOps": 0, "calendarMonthOps": 0, "capabilities": {"ownedDemoCleanup": True}}

        def open_request(request, timeout):
            path = urllib.parse.urlsplit(request.full_url).path
            requests.append((request.method, path))
            payload = budget if path == "/cloud/budget" else {"canonical": {"name": "canonical", "remote": "https://offline.invalid/git/canonical.git"}}
            return io.BytesIO(json.dumps(payload).encode())

        def run_git(command, **kwargs):
            git_calls.append(command[1:])
            stdout = b"a" * 40 + b"\n" if command[1] == "rev-parse" else b""
            if command[1] == "commit":
                stdout = b"[main] Create shared baseline\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")

        with tempfile.TemporaryDirectory(prefix="ab-parity-test-") as temporary:
            scope = {"args": types.SimpleNamespace(verbose=False, interactive=True), "cloud": cloud,
                     "run_id": "a" * 32, "owned_processes": types.SimpleNamespace(run=run_git),
                     "state": pathlib.Path(temporary), "api": "https://offline.invalid", "initial_budget": None,
                     "credentials": {"ADMIN_TOKEN": "offline-admin"}, "git_env": {}, "internal_block": True,
                     "cloud_setup_attempted": False, "awaiting_review": False, "shlex": shlex,
                     "subprocess": subprocess, "urllib": urllib, "json": json,
                     "remote_url": lambda remote: remote,
                     "separator": lambda *args: self.fail("Bootstrap exposed a presenter block"),
                     "wait_key": lambda *args: self.fail("Bootstrap introduced a presenter pause")}
            exec(compile(module, str(SOURCE), "exec"), scope)
            visible = io.StringIO()
            with patch("urllib.request.build_opener", return_value=types.SimpleNamespace(open=open_request)), \
                 patch("subprocess.run", side_effect=run_git), contextlib.redirect_stdout(visible):
                if repo_count:
                    with self.assertRaisesRegex(RuntimeError, "inventory is not empty"):
                        scope["prepare_baseline"]()
                else:
                    result = scope["prepare_baseline"]()
                    self.assertEqual(result[2], "a" * 40)
            return visible.getvalue(), requests, git_calls

    def test_local_and_cloud_bootstrap_have_identical_quiet_presenter_output(self):
        local, local_requests, local_git = self.execute_bootstrap(False)
        cloud, cloud_requests, cloud_git = self.execute_bootstrap(True)
        self.assertEqual(local, cloud)
        self.assertEqual(cloud, "")
        self.assertEqual(local_requests, [("POST", "/setup")])
        self.assertEqual(cloud_requests, [("GET", "/cloud/budget"), ("POST", "/setup")])
        self.assertFalse(any(command[0] == "commit" for command in local_git))
        self.assertTrue(any(command[0] == "commit" for command in cloud_git))
        self.assertTrue(any(command[0] == "push" for command in cloud_git))

    def test_nonempty_cloud_inventory_refuses_before_setup_or_seed(self):
        visible, requests, git_calls = self.execute_bootstrap(True, repo_count=1)
        self.assertEqual(visible, "")
        self.assertEqual(requests, [("GET", "/cloud/budget")])
        self.assertEqual(git_calls, [])


if __name__ == "__main__":
    unittest.main()
