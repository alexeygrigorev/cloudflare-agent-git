"""Current coordinator wire rendering and credential redirect safety."""
import copy
import argparse
import contextlib
import io
import http.server
import os
import threading
import unittest
from unittest.mock import Mock, patch

from agent_branches.cli import format_status_result, format_task_created, handle_task_create
from agent_branches.client import AgentBranchesAPIError, AgentBranchesClient


class StatusFormattingTests(unittest.TestCase):
    def snapshot(self):
        return {"agents": [{"taskId": "task-a", "agentId": "agent-a", "ref": "refs/heads/main", "head": "aaa"},
                           {"taskId": "task-b", "agentId": "agent-b", "head": "bbb"}],
                "heads": {"agent-a": "aaa", "agent-b": "bbb"}, "warnings": [], "plannedOverlaps": [],
                "pairs": [{"pair": ["agent-a", "agent-b"], "heads": {"agent-a": "aaa", "agent-b": "bbb"},
                           "status": "clean", "stale": False, "coverage": {"tests_collected": 1}}]}

    def test_current_agent_wire_and_tested_clean(self):
        text = format_status_result(self.snapshot())
        self.assertIn("Active Tasks (2)", text)
        self.assertIn("task-a", text)
        self.assertIn("agent-a + agent-b: CLEAN (1 combined test(s) passed)", text)
        self.assertNotIn("None (Clean)", text)
        self.assertIn("plans may be undeclared", text)

    def test_missing_stale_unprocessed_and_zero_tests_never_claim_clean(self):
        snapshot = self.snapshot()
        variants = []
        for update in [{"stale": True}, {"status": "not_checked"}, {"coverage": {"tests_collected": 0}},
                       {"unprocessedReason": "push callback missing"}, {"heads": {"agent-a": "old", "agent-b": "bbb"}}]:
            item = copy.deepcopy(snapshot)
            item["pairs"][0].update(update)
            variants.append(item)
        variants.append({"agents": [], "warnings": [], "pairs": []})
        for item in variants:
            with self.subTest(item=item):
                text = format_status_result(item)
                self.assertIn("UNKNOWN", text)
                self.assertNotIn(": CLEAN", text)
                self.assertNotIn("None (Clean)", text)

    def test_conflict_files_and_planned_overlap_are_distinct(self):
        snapshot = self.snapshot()
        snapshot["pairs"][0].update(status="conflict", kind="textual",
                                     evidence={"files": ["shared.txt"], "summary": "add/add conflict"})
        snapshot["plannedOverlaps"] = [{"agents": ["agent-a", "agent-b"], "paths": ["next.py"]}]
        text = format_status_result(snapshot)
        self.assertIn("agent-a + agent-b: CONFLICT", text)
        self.assertIn("Conflicting files: shared.txt", text)
        self.assertIn("Planned overlap (not a proven conflict)", text)
        self.assertIn("Planned files: next.py", text)

    def test_safe_registration_format_does_not_print_minted_token(self):
        text = format_task_created({"taskId": "task-a", "agentId": "agent-a", "token": {"plaintext": "private-token"}})
        self.assertIn("task-a", text)
        self.assertNotIn("private-token", text)


class TaskDefaultsTests(unittest.TestCase):
    def test_explicit_arguments_override_environment_and_environment_overrides_git(self):
        cases = [
            ({"repo": "explicit-repo", "base_sha": "explicit-sha", "branch": "explicit-branch"},
             {"AGENT_BRANCHES_REPO": "env-repo", "AGENT_BRANCHES_BASE_SHA": "env-sha", "AGENT_BRANCHES_BRANCH": "env-branch"},
             ("explicit-repo", "explicit-sha", "explicit-branch")),
            ({}, {"AGENT_BRANCHES_REPO": "env-repo", "AGENT_BRANCHES_BASE_SHA": "env-sha", "AGENT_BRANCHES_BRANCH": "env-branch"},
             ("env-repo", "env-sha", "env-branch")),
            ({}, {}, ("git-repo", "git-sha", "git-branch")),
        ]
        for explicit, environment, expected in cases:
            with self.subTest(explicit=explicit, environment=environment):
                args = argparse.Namespace(repo=None, base_sha=None, branch=None, intent="Configure checkout", agent="agent-a", ttl_seconds=None, admin_token=None)
                for key, value in explicit.items():
                    setattr(args, key, value)
                client = Mock()
                client.create_task.return_value = {"taskId": "task-a"}
                with patch.dict(os.environ, environment, clear=True), \
                     patch("agent_branches.cli.get_remote_url", return_value="git-repo") as git_repo, \
                     patch("agent_branches.cli.get_current_head_sha", return_value="git-sha") as git_sha, \
                     patch("agent_branches.cli.get_current_branch", return_value="git-branch") as git_branch, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(handle_task_create(args, client, as_json=False), 0)
                actual = client.create_task.call_args.kwargs
                self.assertEqual((actual["repo"], actual["base_sha"], actual["branch"]), expected)
                if environment or explicit:
                    git_repo.assert_not_called()
                    git_sha.assert_not_called()
                    git_branch.assert_not_called()


class RedirectSafetyTests(unittest.TestCase):
    def test_client_refuses_redirect_before_sending_bearer_to_another_origin(self):
        received = []

        class Destination(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        destination = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Destination)

        class Redirect(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/status")
                self.end_headers()

            def log_message(self, *args):
                pass

        origin = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        servers = (origin, destination)
        threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
        for thread in threads:
            thread.start()
        try:
            client = AgentBranchesClient(f"http://127.0.0.1:{origin.server_port}")
            with self.assertRaises(AgentBranchesAPIError) as error:
                client.get_status(runner_token="private-bearer")
            self.assertEqual(error.exception.status_code, 302)
            self.assertEqual(received, [])
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
