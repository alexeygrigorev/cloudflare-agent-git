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

from agent_branches.cli import format_status_result, format_task_created, format_plan_result, format_push_result, format_checks_result, format_ack_result, handle_task_create, handle_status, main
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
        self.assertIn("agent-a + agent-b: CLEAN (1 combined test(s) collected)", text)
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


class StatusWorkflowTests(unittest.TestCase):
    def test_task_status_main_refusal_and_redirect_never_change_identity(self):
        import json
        received, destination_calls = [], []
        class Destination(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                destination_calls.append(self.path)
                self.send_response(200); self.end_headers()
        destination = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Destination)
        class Origin(http.server.BaseHTTPRequestHandler):
            status_code = 403
            def log_message(self, *args): pass
            def do_GET(self):
                received.append((self.path, self.headers.get("Authorization")))
                if self.path == "/tasks/ta":
                    body = json.dumps({"taskId": "ta", "agentId": "a"}).encode()
                    self.send_response(200)
                else:
                    body = b'{"error":"refused"}'
                    self.send_response(self.status_code)
                    if self.status_code == 302:
                        self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/stolen")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body)
        origin = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Origin)
        threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (origin, destination)]
        for thread in threads: thread.start()
        url = f"http://127.0.0.1:{origin.server_port}"
        try:
            for status in (401, 403, 302):
                Origin.status_code = status; received.clear()
                with patch.dict(os.environ, {"TASK_TOKEN": "own-task"}, clear=True), \
                     patch("agent_branches.client.settings_for", return_value=(url, {"admin_token": "stronger-admin"})), \
                     contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
                    self.assertEqual(main(["status", "--task-id", "ta", "--server", url]), 1)
                self.assertEqual(received, [("/tasks/ta", "Bearer own-task"), ("/status", "Bearer own-task")])
                self.assertNotIn("own-task", output.getvalue() + errors.getvalue())
                self.assertNotIn("stronger-admin", output.getvalue() + errors.getvalue())
            self.assertEqual(destination_calls, [])
        finally:
            for server in (origin, destination): server.shutdown(); server.server_close()
            for thread in threads: thread.join(timeout=2)

    def test_saved_credentials_follow_documented_precedence_without_retry(self):
        with patch.dict(os.environ, {}, clear=True), patch("agent_branches.client.settings_for", return_value=("http://localhost:8787", {})):
            client = AgentBranchesClient()
            client.task_tokens = {"ta": "one", "tb": "two"}
            client._request = Mock(return_value={})
            client.get_status()
            client._request.assert_called_once_with("GET", "/status", headers={"Authorization": "Bearer two"})
            client._request.reset_mock()
            client.settings["admin_token"] = "saved-admin"
            with patch.dict(os.environ, {"TASK_TOKEN": "env-task"}):
                client.get_status()
            client._request.assert_called_once_with("GET", "/status", headers={"Authorization": "Bearer env-task"})

    def test_missing_agent_identity_is_an_explicit_unknown_error(self):
        for agent in (None, {}, ""):
            client = Mock()
            client.get_task.return_value = {"taskId": "ta", "agentId": agent}
            with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                handle_status(argparse.Namespace(task_id="ta"), client, False)
            client.get_status.assert_not_called()

    def test_unscopable_warnings_and_missing_snapshot_plans_stay_unknown(self):
        for warning in ({"id": "w", "status": "active"}, {"id": "w", "status": "active", "pair": "agent-ab-agent-b"}, None):
            client = Mock()
            client.get_task.return_value = {"taskId": "ta", "agentId": "agent-a",
                "plannedOverlaps": [{"agents": ["agent-a", "agent-b"], "paths": ["stale-detail.py"]}]}
            client.get_status.return_value = {"warnings": [warning], "heads": {}, "pairs": []}
            with contextlib.redirect_stdout(io.StringIO()) as output:
                handle_status(argparse.Namespace(task_id="ta"), client, False)
            text = output.getvalue()
            self.assertIn("Radar Warnings: UNKNOWN", text)
            self.assertIn("Planned overlaps: UNKNOWN", text)
            self.assertNotIn("Warnings: None", text)
            self.assertNotIn("stale-detail.py", text)

    def test_peer_controls_cannot_forge_terminal_lines(self):
        attack = "peer\nforged-CLEAN\x1b[2J\x1b]0;title\x07\x85"
        snapshot = StatusFormattingTests().snapshot()
        snapshot["agents"][0]["agentId"] = attack
        snapshot["canonical"] = {"name": attack}
        snapshot["pairs"][0].update(status="conflict", evidence={"files": [attack], "summary": attack})
        snapshot["plannedOverlaps"] = [{"agents": [attack, "b"], "paths": [attack]}]
        snapshot["warnings"] = [{"id": attack, "kind": attack, "status": "active", "pair": [attack, "b"]}]
        for text in (format_status_result(snapshot), format_status_result({**snapshot, "taskId": attack, "intent": attack, "branch": attack, "head": attack}, "ta")):
            self.assertNotIn("\nforged-CLEAN", text)
            self.assertNotIn("\x1b", text)
            self.assertNotIn("\x07", text)
            self.assertNotIn("\x85", text)
            self.assertIn("\\nforged-CLEAN", text)
        plan = format_plan_result({"agentId": attack, "plannedPaths": [attack], "plannedOverlaps": snapshot["plannedOverlaps"]})
        self.assertNotIn("\nforged-CLEAN", plan)
        self.assertNotIn("\x1b", plan)
        self.assertNotIn("\x85", plan)
        self.assertIn("UNKNOWN", format_plan_result({}))

    def test_unreadable_records_and_collected_vs_passed_counts(self):
        snapshot = StatusFormattingTests().snapshot()
        snapshot["pairs"][0]["coverage"] = {"tests_collected": 5, "passed": 1, "skipped": 4}
        self.assertIn("CLEAN (1 combined test(s) passed)", format_status_result(snapshot))
        for bad in (None, [], 4):
            self.assertIn("UNKNOWN", format_status_result({"pairs": [bad], "warnings": [bad], "plannedOverlaps": [bad], "agents": [bad]}))
        snapshot["pairs"][0]["coverage"] = []
        self.assertNotIn("CLEAN", format_status_result(snapshot))

    def test_global_status_accepts_saved_admin_and_agent_credentials(self):
        for settings, environment, expected in [
            ({"admin_token": "saved-admin"}, {}, "saved-admin"),
            ({}, {"ADMIN_TOKEN": "env-admin"}, "env-admin"),
            ({}, {"TASK_TOKEN": "env-task"}, "env-task"),
            ({"tasks": {"ta": {"token": {"plaintext": "saved-task"}}}}, {}, "saved-task"),
        ]:
            with self.subTest(expected=expected), patch.dict(os.environ, environment, clear=True), \
                 patch("agent_branches.client.settings_for", return_value=("http://localhost:8787", settings)):
                client = AgentBranchesClient()
                client._request = Mock(return_value={})
                client.get_status()
                self.assertEqual(client._request.call_args.kwargs["headers"], {"Authorization": "Bearer " + expected})

    def test_explicit_status_credential_does_not_retry_with_a_stronger_role(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "admin"}, clear=True), \
             patch("agent_branches.client.settings_for", return_value=("http://localhost:8787", {})):
            client = AgentBranchesClient()
            client._request = Mock(side_effect=AgentBranchesAPIError(401, "expired"))
            with self.assertRaises(AgentBranchesAPIError):
                client.get_status(token="selected-task")
            client._request.assert_called_once_with("GET", "/status", headers={"Authorization": "Bearer selected-task"})

    def test_task_status_shows_scoped_plans_and_current_pair_evidence(self):
        snapshot = StatusFormattingTests().snapshot()
        snapshot["agents"].append({"agentId": "agent-c", "head": "ccc"})
        snapshot["plannedOverlaps"] = [{"agents": ["agent-a", "agent-b"], "paths": ["shared.txt"]},
                                       {"agents": ["agent-b", "agent-c"], "paths": ["unrelated.txt"]}]
        snapshot["warnings"] = [{"id": "w-a", "status": "active", "pair": ["agent-a", "agent-b"]}]
        client = Mock()
        client.get_task.return_value = {"taskId": "task-a", "agentId": "agent-a", "head": "older", "warnings": []}
        client.task_token.return_value = "own-task"
        client.get_status.return_value = snapshot
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(handle_status(argparse.Namespace(task_id="task-a"), client, False), 0)
        text = output.getvalue()
        client.get_status.assert_called_once_with(token="own-task")
        self.assertIn("agent-a + agent-b: CLEAN", text)
        self.assertIn("Planned files: shared.txt", text)
        self.assertNotIn("unrelated.txt", text)
        self.assertNotIn("older", text)
        self.assertIn("w-a", text)
        self.assertNotIn("own-task", text)

    def test_task_json_keeps_raw_task_response(self):
        client = Mock()
        client.get_task.return_value = {"taskId": "task-a", "head": "aaa"}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            handle_status(argparse.Namespace(task_id="task-a"), client, True)
        self.assertEqual(__import__("json").loads(output.getvalue()), client.get_task.return_value)
        client.get_status.assert_not_called()

    def test_task_status_keeps_new_push_and_unreadable_plans_unknown(self):
        snapshot = StatusFormattingTests().snapshot()
        snapshot["heads"]["agent-a"] = "newer"
        snapshot["plannedOverlaps"] = [{"agents": ["agent-a", "agent-b", "agent-c"], "paths": ["shared.txt"]}]
        client = Mock()
        client.get_task.return_value = {"taskId": "task-a", "agentId": "agent-a", "head_sha": "old-head"}
        client.task_token.return_value = "own-task"
        client.get_status.return_value = snapshot
        with contextlib.redirect_stdout(io.StringIO()) as output:
            handle_status(argparse.Namespace(task_id="task-a"), client, False)
        text = output.getvalue()
        self.assertIn("Head SHA:  newer", text)
        self.assertIn("UNKNOWN (stale", text)
        self.assertIn("Planned overlaps: UNKNOWN", text)
        self.assertNotIn("None reported", text)
        self.assertNotIn("CLEAN", text)

    def test_nonfinite_test_count_is_not_clean(self):
        snapshot = StatusFormattingTests().snapshot()
        snapshot["pairs"][0]["coverage"] = {"tests_collected": float("inf")}
        self.assertNotIn("CLEAN", format_status_result(snapshot))


class TaskDefaultsTests(unittest.TestCase):
    def test_explicit_environment_private_precedence_without_cwd_git_defaults(self):
        cases = [
            ({"repo": "explicit-repo", "base_sha": "explicit-sha", "branch": "explicit-branch"},
             {"AGENT_BRANCHES_REPO": "env-repo", "AGENT_BRANCHES_BASE_SHA": "env-sha", "AGENT_BRANCHES_BRANCH": "env-branch"},
             ("explicit-repo", "explicit-sha", "explicit-branch")),
            ({}, {"AGENT_BRANCHES_REPO": "env-repo", "AGENT_BRANCHES_BASE_SHA": "env-sha", "AGENT_BRANCHES_BRANCH": "env-branch"},
             ("env-repo", "env-sha", "env-branch")),
            ({}, {}, (None, None, None)),
        ]
        for explicit, environment, expected in cases:
            with self.subTest(explicit=explicit, environment=environment):
                args = argparse.Namespace(repo=None, base_sha=None, branch=None, intent="Configure checkout", agent="agent-a", ttl_seconds=None, admin_token=None)
                for key, value in explicit.items():
                    setattr(args, key, value)
                client = Mock()
                client.settings = ({"repo": "private-repo", "base_sha": "private-sha", "branch": "private-branch"}
                                   if environment or explicit else {})
                client.create_task.return_value = {"taskId": "task-a"}
                with patch.dict(os.environ, environment, clear=True), \
                     patch("agent_branches.cli.get_remote_url", return_value="git-repo") as git_repo, \
                     patch("agent_branches.cli.get_current_head_sha", return_value="git-sha") as git_sha, \
                     patch("agent_branches.cli.get_current_branch", return_value="git-branch") as git_branch, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(handle_task_create(args, client, as_json=False), 0)
                actual = client.create_task.call_args.kwargs
                self.assertEqual((actual["repo"], actual["base_sha"], actual["branch"]), expected)
                git_repo.assert_not_called()
                git_sha.assert_not_called()
                git_branch.assert_not_called()
                client.remember_task.assert_called_once_with({"taskId": "task-a"})
                client.settings = {"repo": "private-repo", "base_sha": "private-sha", "branch": "private-branch"}
                if not environment and not explicit:
                    with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                        handle_task_create(args, client, as_json=False)
                    actual = client.create_task.call_args.kwargs
                    self.assertEqual((actual["repo"], actual["base_sha"], actual["branch"]),
                                     ("private-repo", "private-sha", "private-branch"))

    def test_client_omits_unknown_context_and_preserves_explicit_library_arguments(self):
        from agent_branches.client import AgentBranchesClient
        client = AgentBranchesClient("https://coordinator.invalid")
        client._request = Mock(return_value={})
        with patch.dict(os.environ, {}, clear=True):
            client.create_task(agent="a", intent="Configure checkout")
            self.assertEqual(client._request.call_args.args[2], {"agent": "a", "intent": "Configure checkout"})
            client.create_task("repo", "a" * 40, "intent", "branch")
            self.assertEqual(client._request.call_args.args[2],
                             {"repo": "repo", "base_sha": "a" * 40, "intent": "intent", "branch": "branch"})


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




class ReviewRecoveryTests(unittest.TestCase):
    def test_real_invalidated_warning_is_history_not_unknown(self):
        snapshot = StatusFormattingTests().snapshot()
        warning = {"id": "w1", "pair": ["agent-a", "agent-b"], "kind": "textual",
                   "headsAtIssue": {"agent-a": "old-a", "agent-b": "old-b"}, "acks": []}
        for status in ("invalidated", "acknowledged", "resolved"):
            snapshot["warnings"] = [{**warning, "status": status}]
            for task in (None, "ta"):
                text = format_status_result(snapshot, task)
                self.assertNotIn("Warnings: UNKNOWN", text)
                self.assertIn("Warnings: None", text)
                self.assertIn("CLEAN", text)
        snapshot["warnings"][0]["status"] = "unrecognized"
        self.assertIn("Warnings: UNKNOWN", format_status_result(snapshot))

    def test_selected_task_without_credential_never_uses_generic_fallback(self):
        client = Mock()
        client.get_task.return_value = {"taskId": "ta", "agentId": "agent-a"}
        client.task_token.return_value = None
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            handle_status(argparse.Namespace(task_id="ta"), client, False)
        client.get_status.assert_not_called()

    def test_remaining_formatters_escape_peer_controls(self):
        attack = "peer\nFORGED\x1b[2J\x07"
        values = [format_task_created({"taskId": attack, "agentId": attack, "intent": attack, "forkUrl": attack}),
                  format_push_result({"taskId": attack, "newWarnings": [{"id": attack, "kind": attack,
                     "pair": [attack, "b"], "evidence": {"conflicting_files": [attack], "details": attack}}]}),
                  format_checks_result({"createdWarnings": [{"id": attack, "status": attack, "reason": attack}]}),
                  format_ack_result({"id": attack, "taskId": attack, "action": attack, "acknowledged_at": attack})]
        for text in values:
            self.assertNotIn("\nFORGED", text)
            self.assertNotIn("\x1b", text)
            self.assertNotIn("\x07", text)
            self.assertIn("\\nFORGED", text)

    def test_only_readable_plan_overlap_gets_coordination_advice_and_string_evidence_is_visible(self):
        text = format_plan_result({"plannedPaths": [], "plannedOverlaps": [None]})
        self.assertIn("UNKNOWN", text)
        self.assertNotIn("This overlap", text)
        snapshot = StatusFormattingTests().snapshot()
        snapshot["pairs"][0].update(status="conflict", evidence="legacy\nsummary")
        text = format_status_result(snapshot)
        self.assertIn("legacy\\nsummary", text)
        self.assertNotIn("legacy\nsummary", text)


class ErrorOutputTests(unittest.TestCase):
    def test_main_error_variants_escape_server_text_and_keep_exit_codes(self):
        from agent_branches.client import (AgentBranchesConnectionError, StaleVectorError,
                                          TokenExpiredError, TokenRevokedError)
        attack = "server\nFORGED-CLEAN\x1b[2J\x1b]0;title\x07\x85\u202e"
        cases = [(AgentBranchesConnectionError(attack), 2), (StaleVectorError(409, attack), 1),
                 (TokenExpiredError(401, attack), 1), (TokenRevokedError(401, attack), 1),
                 (AgentBranchesAPIError(400, attack), 1), (ValueError(attack), 1)]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__), \
                 patch("agent_branches.cli.AgentBranchesClient") as factory, \
                 contextlib.redirect_stderr(io.StringIO()) as output:
                factory.return_value.get_status.side_effect = error
                self.assertEqual(main(["status"]), expected)
                self.assertEqual(factory.return_value.get_status.call_count, 1)
            self.assertIn("\\nFORGED-CLEAN", output.getvalue())
            for control in ("\nFORGED", "\x1b", "\x07", "\x85", "\u202e"):
                self.assertNotIn(control, output.getvalue())

    def test_checks_error_output_escapes_payload_without_altering_json_contract(self):
        from agent_branches.cli import handle_checks
        from agent_branches.client import StaleVectorError, TokenExpiredError, TokenRevokedError
        import json
        attack = "server\nFORGED-CLEAN\x1b[2J\x85"
        for error in (StaleVectorError(409, attack, attack), TokenExpiredError(401, attack),
                      TokenRevokedError(401, attack), AgentBranchesAPIError(400, attack), ValueError(attack)):
            client = Mock()
            client.send_checks.side_effect = error
            with patch("sys.stdin", io.StringIO("{}")), contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(handle_checks(argparse.Namespace(file=None, runner_token=None), client, False), 1)
            self.assertIn("\\nFORGED-CLEAN", output.getvalue())
            for control in ("\nFORGED", "\x1b", "\x85"):
                self.assertNotIn(control, output.getvalue())
        client.send_checks.side_effect = StaleVectorError(409, attack, {"details": attack})
        with patch("sys.stdin", io.StringIO("{}")), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(handle_checks(argparse.Namespace(file=None, runner_token=None), client, True), 1)
        self.assertEqual(json.loads(output.getvalue())["message"], attack)
        self.assertEqual(json.loads(output.getvalue())["details"], {"details": attack})


if __name__ == "__main__":
    unittest.main()
