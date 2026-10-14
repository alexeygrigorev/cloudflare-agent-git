"""Authenticated watcher/configuration safety and real CLI planning contracts."""
import contextlib
import concurrent.futures
import io
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
import stat
import zipfile
import types
from unittest.mock import Mock, patch

from agent_branches.checker import Watcher, harness_invocation, scratch_bytes, structured_results, validated_remote, watch
from agent_branches.client import AgentBranchesClient, StaleVectorError
from agent_branches.config import load_config, save_settings, settings_for
from agent_branches.cli import handle_publish, main


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="branches-unit-")
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "USERPROFILE")}
        environment["AGENT_BRANCHES_CONFIG"] = str(Path(self.temporary.name) / "private.json")
        self.env = patch.dict(os.environ, environment, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temporary.cleanup()

    def test_server_bound_private_task_credentials_and_explicit_environment_precedence(self):
        save_settings("https://one.invalid", {"runner_token": "private-one", "repo": "configured"},
                      {"taskId": "task-a", "agentId": "a", "token": {"plaintext": "private-task"}})
        server, settings = settings_for()
        self.assertEqual(server, "https://one.invalid")
        self.assertEqual(settings["tasks"]["task-a"]["token"]["plaintext"], "private-task")
        self.assertEqual(settings_for("https://two.invalid")[1], {})
        with patch.dict(os.environ, {"AGENT_BRANCHES_SERVER": "https://env.invalid"}):
            self.assertEqual(settings_for()[0], "https://env.invalid")
            self.assertEqual(settings_for("https://explicit.invalid")[0], "https://explicit.invalid")
        self.assertEqual(load_config()["server"], "https://one.invalid")
        if os.name != "nt":
            self.assertEqual(Path(os.environ["AGENT_BRANCHES_CONFIG"]).stat().st_mode & 0o777, 0o600)

    def evaluate_files(self, files, command=None):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={}, settings={})
        checker = Watcher(client, command or [sys.executable, "-m", "unittest", "discover", "-v"], emit=lambda message: None)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as data:
            for name, value in files.items():
                data.writestr(name, value)
        def git(arguments, *args, **kwargs):
            if arguments[0] == "archive":
                return 0, archive.getvalue(), b""
            if arguments[0] == "merge-tree":
                return 0, b"f" * 40 + b"\n", b""
            return 0, b"", b""
        try:
            with patch.object(checker, "_git", side_effect=git):
                return checker._pair(("a", "b"), {"a": {"taskId": "ta", "forkRemote": "/git/a.git"},
                                                      "b": {"taskId": "tb", "forkRemote": "/git/b.git"}},
                                     {"a": "a" * 40, "b": "b" * 40}, {"ta": "private-a", "tb": "private-b"})
        finally:
            checker.close()

    def test_stdout_spoof_commands_and_real_unittest_zero_collection_never_clean(self):
        spoof = [sys.executable, "-c", "print('Ran 1 test in 0.0s\\nOK\\n1 passed')"]
        result = self.evaluate_files({}, spoof)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["evidence"]["tests_collected"], 0)
        result = self.evaluate_files({"test_empty.py": "print('Ran 1 test in 0.0s\\nOK\\n1 passed')\n"})
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["evidence"]["tests_collected"], 0)

    def test_actual_structured_unittest_pass_failure_error_and_skip(self):
        cases = [
            ("import unittest\nclass T(unittest.TestCase):\n def test_one(self): self.assertTrue(True)\n", "clean", 1),
            ("import unittest\nclass T(unittest.TestCase):\n def test_one(self): self.assertTrue(False)\n", "conflict", 1),
            ("raise RuntimeError('cannot import tests')\n", "unknown", 1),
            ("import unittest\nclass T(unittest.TestCase):\n @unittest.skip('not runnable')\n def test_one(self): pass\n", "unknown", 1),
            ("import unittest\nclass T(unittest.TestCase):\n @unittest.expectedFailure\n def test_one(self): self.fail('expected')\n", "unknown", 1),
        ]
        for source, expected, count in cases:
            with self.subTest(expected=expected, source=source):
                result = self.evaluate_files({"test_count.py": source})
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["evidence"]["tests_collected"], count)

    def test_junit_only_skipped_or_xfailed_cases_have_no_passed_tests(self):
        report = Path(self.temporary.name) / "junit.xml"
        report.write_text('<testsuites><testsuite tests="999"><testcase name="skip"><skipped/></testcase><testcase name="xfail"><skipped type="pytest.xfail"/></testcase></testsuite></testsuites>')
        result = structured_results(report, "pytest")
        self.assertEqual(result["collected"], 2)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["skipped"], 2)
        command, framework = harness_invocation([sys.executable, "-m", "pytest", "-q"], report)
        self.assertEqual(framework, "pytest")
        self.assertIn("--junitxml=" + str(report), command)

    def test_nonfinite_and_nonpositive_limits_refuse_before_work_starts(self):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={}, settings={})
        for value in (float("nan"), float("inf"), -float("inf"), 0, -1):
            for key in ("test_timeout", "git_timeout", "max_scratch_mb"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    Watcher(client, [sys.executable, "-m", "unittest"], **{key: value})
            for key in ("poll_interval", "duration", "test_timeout"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    watch(client, [sys.executable, "-m", "unittest"], once=True, **{key: value})
            with self.subTest(http=value), self.assertRaises(ValueError):
                AgentBranchesClient(timeout=value)

    def test_zip_expansion_member_count_and_path_guards_run_before_extracting(self):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={}, settings={})
        checker = Watcher(client, [sys.executable, "-m", "unittest"], emit=lambda message: None)
        work = checker.root / "extract"
        work.mkdir()
        def archive(entries):
            result = io.BytesIO()
            with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as data:
                for name, content in entries:
                    data.writestr(name, content)
            return result.getvalue()
        try:
            existing = sum(path.stat().st_size for path in checker.root.rglob("*") if path.is_file())
            checker.max_bytes = existing + 1024
            bomb = archive([("expanded", b"0" * (2 * 1024 * 1024))])
            self.assertLess(len(bomb), 4096)
            with self.assertRaisesRegex(ValueError, "Expanded archive"):
                checker._extract_archive(bomb, work)
            self.assertEqual(list(work.iterdir()), [])
            checker.max_bytes = 256 * 1024 * 1024
            for path in ("../outside", "/absolute", "C:/absolute", "a/../../escape", "a/./b"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    checker._extract_archive(archive([(path, b"x")]), work)
            # zipfile normalizes Windows separators while creating names. Patch
            # both ZIP headers to exercise the actual original malformed name.
            backslash = archive([("back/slash", b"x")]).replace(b"back/slash", b"back\\slash")
            with self.assertRaises(ValueError):
                checker._extract_archive(backslash, work)
            link = zipfile.ZipInfo("link")
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with self.assertRaises(ValueError):
                checker._extract_archive(archive([(link, b"../outside")]), work)
            with self.assertRaises(ValueError):
                checker._extract_archive(archive([(f"item-{index}", b"") for index in range(10001)]), work)
            self.assertEqual(list(work.iterdir()), [])
            lying = zipfile.ZipInfo("lying")
            lying.file_size = 1
            fake = Mock()
            fake.infolist.return_value = [lying]
            fake.open.return_value = io.BytesIO(b"much larger than declared")
            fake.__enter__ = Mock(return_value=fake)
            fake.__exit__ = Mock(return_value=False)
            with patch("agent_branches.checker.zipfile.ZipFile", return_value=fake), self.assertRaisesRegex(ValueError, "Actual expanded"):
                checker._extract_archive(b"offline", work)
            self.assertEqual((work / "lying").stat().st_size, 0)
        finally:
            checker.close()

    def test_simultaneous_task_registrations_do_not_lose_private_credentials(self):
        def register(name):
            save_settings("https://one.invalid", task={"taskId": name, "agentId": name, "token": {"plaintext": "private-" + name}})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(register, ["a", "b"]))
        self.assertEqual(set(settings_for("https://one.invalid")[1]["tasks"]), {"a", "b"})

    def test_remote_scope_prevents_github_and_encoded_traversal(self):
        for remote in ("https://github.com/person/project.git", "/git/../secret.git", "/git/%2e%2e.git",
                       "https://user:password@coordinator.invalid/git/fork.git"):
            with self.subTest(remote=remote), self.assertRaises(ValueError):
                validated_remote("https://coordinator.invalid", remote)
        self.assertEqual(validated_remote("http://127.0.0.1:8787", "http://127.0.0.1:9000/git/fork.git"),
                         "http://127.0.0.1:9000/git/fork.git")

    def test_missing_fork_credentials_is_unknown_and_not_retried_every_poll(self):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={})
        client.get_status.return_value = {"heads": {"a": "a" * 40, "b": "b" * 40},
            "agents": [{"agentId": "a", "taskId": "ta", "forkRemote": "/git/a.git"},
                       {"agentId": "b", "taskId": "tb", "forkRemote": "/git/b.git"}]}
        checker = Watcher(client, ["python", "-m", "unittest"], emit=lambda message: None)
        root = checker.root
        try:
            checker.tick()
            payload = client.send_checks.call_args.args[0]
            self.assertEqual(payload["results"][0]["status"], "unknown")
            self.assertEqual(payload["coverage"]["tests_collected"], 0)
            checker.tick()
            self.assertEqual(client.send_checks.call_count, 1)
        finally:
            checker.close()
        self.assertFalse(root.exists())

    def test_stale_submission_discards_evidence_and_recomputes_new_heads(self):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={})
        records = [{"agentId": "a", "taskId": "ta"}, {"agentId": "b", "taskId": "tb"}]
        client.get_status.side_effect = [{"agents": records, "heads": {"a": "a" * 40, "b": "b" * 40}},
                                         {"agents": records, "heads": {"a": "c" * 40, "b": "b" * 40}}]
        client.send_checks.side_effect = [StaleVectorError(409, "stale"), {"accepted": 1}]
        checker = Watcher(client, ["python", "-m", "unittest"], emit=lambda message: None)
        try:
            def evaluate(pair, records, vector, tokens):
                return {"pair": list(pair), "heads": {agent: vector[agent] for agent in pair}, "status": "unknown",
                        "kind": None, "evidence": {"tests_collected": 0, "summary": "unit evaluation"}}
            with patch.object(checker, "_pair", side_effect=evaluate) as recompute:
                checker.tick()
                checker.tick()
                self.assertEqual(recompute.call_count, 2)
            submitted = client.send_checks.call_args_list
            self.assertEqual(submitted[0].args[0]["vector"]["a"], "a" * 40)
            self.assertEqual(submitted[1].args[0]["results"][0]["heads"]["a"], "c" * 40)
        finally:
            checker.close()

    def test_missing_command_refuses_and_releases_lock(self):
        client = Mock(server_url="http://127.0.0.1:8787")
        with self.assertRaises(ValueError):
            watch(client, None, once=True, emit=lambda message: None)
        self.assertFalse(Path(os.environ["AGENT_BRANCHES_CONFIG"]).with_suffix(".watch.lock").exists())

    def test_configured_command_timeout_is_bounded_and_child_is_reaped(self):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={})
        checker = Watcher(client, [sys.executable, "-m", "unittest"], emit=lambda message: None)
        try:
            with self.assertRaises(TimeoutError):
                checker._run([sys.executable, "-c", "import time; time.sleep(10)"], checker.root, 0.1)
            self.assertEqual(list(checker.root.glob("*.out")), [])
            self.assertEqual(list(checker.root.glob("*.err")), [])
        finally:
            checker.close()

    def test_scratch_measurement_skips_only_entries_removed_by_running_git(self):
        stable = Mock()
        stable.stat.return_value = types.SimpleNamespace(st_mode=stat.S_IFREG, st_size=123)
        removed_lock = Mock()
        removed_lock.stat.side_effect = FileNotFoundError("config.lock removed")
        directory = Mock()
        directory.stat.return_value = types.SimpleNamespace(st_mode=stat.S_IFDIR, st_size=4096)
        root = Mock()
        root.rglob.return_value = [stable, removed_lock, directory]
        self.assertEqual(scratch_bytes(root), 123)
        stable.stat.assert_called_once_with()
        removed_lock.stat.assert_called_once_with()
        root.rglob.return_value = [removed_lock]
        removed_lock.stat.side_effect = PermissionError("unreadable")
        with self.assertRaises(PermissionError):
            scratch_bytes(root)

    def test_publish_refuses_a_github_origin_before_any_git_push(self):
        client = Mock(server_url="http://127.0.0.1:8787", task_tokens={"task-a": "private-task"})
        client.get_task.return_value = {"agentId": "a", "forkRemote": "http://127.0.0.1:9000/git/a.git"}
        with patch("agent_branches.cli.get_remote_url", return_value="https://github.com/person/repo.git"), \
             patch("agent_branches.cli.subprocess.run") as execute:
            with self.assertRaises(ValueError):
                handle_publish(Mock(task_id="task-a"), client, False)
            execute.assert_not_called()

    def test_shared_ack_auth_and_agent_resolution_and_cli_plan(self):
        save_settings("http://127.0.0.1:8787", {"admin_token": "private-admin"})
        client = AgentBranchesClient()
        client._request = Mock(side_effect=[{"taskId": "task-a", "agentId": "agent-a"}, {"warning": {}}])
        client.ack_warning("warning-a", "task-a", "rebased_locally")
        method, path, payload = client._request.call_args.args
        self.assertEqual(payload["agent"], "agent-a")
        self.assertEqual(payload["note"], "rebased_locally")
        self.assertEqual(client._request.call_args.kwargs["headers"]["Authorization"], "Bearer private-admin")
        with patch.object(AgentBranchesClient, "plan_task", return_value={"agentId": "a", "plannedPaths": ["x.py"], "plannedOverlaps": []}) as plan, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["plan", "--task-id", "task-a", "--files", "x.py"]), 0)
            plan.assert_called_once_with("task-a", ["x.py"])
        self.assertNotIn("private-admin", output.getvalue())


if __name__ == "__main__":
    unittest.main()
