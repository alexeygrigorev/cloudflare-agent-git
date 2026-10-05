import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock

import scripts.coordination.git_handoff as gh

class TestGitHandoff(unittest.TestCase):
    def test_cli_help_invocations(self):
        """Verify that CLI --help commands execute cleanly with exit code 0."""
        script_path = os.path.abspath(gh.__file__)
        for args in [["--help"], ["send", "--help"], ["accept", "--help"]]:
            res = subprocess.run([sys.executable, script_path] + args, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Failed on args: {args}, stderr: {res.stderr}")
            self.assertIn("usage: git_handoff.py", res.stdout + res.stderr)

    @patch("subprocess.run")
    def test_send_payload_binding(self, mock_run):
        """Verify cmd_send binds current_head, task, acceptance_policy, fork, base, and idempotency_key."""
        mock_run.return_value = MagicMock(returncode=0, stdout="msg-id-123\n", stderr="")
        
        args = MagicMock(
            to="agent-reviewer",
            task="TASK-99",
            policy="Policy: Clean head",
            fork="https://github.com/example/fork",
            base="main",
            head="deadbeef" * 5,
            idempotency_key="key-abc",
            text="Please take over the session."
        )
        
        gh.cmd_send(args)
        
        # Verify subprocess.run call
        self.assertTrue(mock_run.called)
        cmd_called = mock_run.call_args[0][0]
        
        # Inspect --data payload
        self.assertIn("--data", cmd_called)
        data_idx = cmd_called.index("--data") + 1
        payload = json.loads(cmd_called[data_idx])
        
        self.assertEqual(payload["task"], "TASK-99")
        self.assertEqual(payload["acceptance_policy"], "Policy: Clean head")
        self.assertEqual(payload["fork"], "https://github.com/example/fork")
        self.assertEqual(payload["base"], "main")
        self.assertEqual(payload["current_head"], "deadbeef" * 5)
        self.assertEqual(payload["idempotency_key"], "key-abc")

    @patch("scripts.coordination.git_handoff.get_git_head")
    @patch("subprocess.run")
    def test_send_infers_current_head_if_omitted(self, mock_run, mock_get_head):
        """Verify cmd_send infers current_head from git if --head is omitted."""
        mock_get_head.return_value = "11223344" * 5
        mock_run.return_value = MagicMock(returncode=0, stdout="msg-id-456\n", stderr="")
        
        args = MagicMock(
            to="agent-reviewer",
            task="TASK-100",
            policy="Policy: Test",
            fork="origin",
            base="main",
            head=None,
            idempotency_key=None,
            text="Inferred head task"
        )
        
        gh.cmd_send(args)
        mock_get_head.assert_called_once()
        
        cmd_called = mock_run.call_args[0][0]
        data_idx = cmd_called.index("--data") + 1
        payload = json.loads(cmd_called[data_idx])
        self.assertEqual(payload["current_head"], "11223344" * 5)

    @patch("scripts.coordination.git_handoff.run_cmd")
    @patch("scripts.coordination.git_handoff.check_git_clean")
    @patch("scripts.coordination.git_handoff.get_git_head")
    def test_accept_clean_and_matching_head(self, mock_get_head, mock_check_clean, mock_run_cmd):
        """Verify cmd_accept succeeds and acknowledges message when git is clean and heads match."""
        expected_sha = "abcdef01" * 5
        mock_check_clean.return_value = True
        mock_get_head.return_value = expected_sha
        
        fake_msg = {
            "kind": "handoff",
            "data": {
                "task": "TASK-101",
                "acceptance_policy": "All tests pass",
                "current_head": expected_sha
            }
        }
        
        # run_cmd is called for message show and message ack
        mock_run_cmd.side_effect = [
            MagicMock(stdout=json.dumps(fake_msg)), # message show
            MagicMock(stdout="Acked\n")             # message ack
        ]
        
        args = MagicMock(message_id="msg-uuid-101")
        gh.cmd_accept(args)
        
        # Verify ack was called
        ack_call = mock_run_cmd.call_args_list[1][0][0]
        self.assertIn("ack", ack_call)
        self.assertIn("msg-uuid-101", ack_call)

    @patch("scripts.coordination.git_handoff.run_cmd")
    @patch("scripts.coordination.git_handoff.check_git_clean")
    def test_accept_drift_dirty_workspace(self, mock_check_clean, mock_run_cmd):
        """Verify cmd_accept fails closed when workspace has uncommitted changes."""
        mock_check_clean.return_value = False
        
        fake_msg = {
            "kind": "handoff",
            "data": {
                "task": "TASK-102",
                "acceptance_policy": "Strict",
                "current_head": "123456" * 6
            }
        }
        mock_run_cmd.return_value = MagicMock(stdout=json.dumps(fake_msg))
        
        args = MagicMock(message_id="msg-uuid-102")
        with self.assertRaises(SystemExit) as cm:
            gh.cmd_accept(args)
        self.assertEqual(cm.exception.code, 1)

    @patch("scripts.coordination.git_handoff.run_cmd")
    @patch("scripts.coordination.git_handoff.check_git_clean")
    @patch("scripts.coordination.git_handoff.get_git_head")
    def test_accept_drift_head_mismatch(self, mock_get_head, mock_check_clean, mock_run_cmd):
        """Verify cmd_accept fails closed when local head drifted from expected head."""
        mock_check_clean.return_value = True
        mock_get_head.return_value = "local_head_111"
        
        fake_msg = {
            "kind": "handoff",
            "data": {
                "task": "TASK-103",
                "acceptance_policy": "Strict",
                "current_head": "expected_head_999"
            }
        }
        mock_run_cmd.return_value = MagicMock(stdout=json.dumps(fake_msg))
        
        args = MagicMock(message_id="msg-uuid-103")
        with self.assertRaises(SystemExit) as cm:
            gh.cmd_accept(args)
        self.assertEqual(cm.exception.code, 1)

    @patch("scripts.coordination.git_handoff.run_cmd")
    @patch("scripts.coordination.git_handoff.check_git_clean")
    @patch("scripts.coordination.git_handoff.get_git_head")
    def test_accept_stringified_json_data(self, mock_get_head, mock_check_clean, mock_run_cmd):
        """Verify cmd_accept handles stringified JSON in msg.data."""
        expected_sha = "aabbccdd" * 5
        mock_check_clean.return_value = True
        mock_get_head.return_value = expected_sha
        
        inner_data = {
            "task": "TASK-104",
            "acceptance_policy": "Strict",
            "current_head": expected_sha
        }
        fake_msg = {
            "kind": "handoff",
            "data": json.dumps(inner_data) # stringified payload
        }
        mock_run_cmd.side_effect = [
            MagicMock(stdout=json.dumps(fake_msg)),
            MagicMock(stdout="Acked\n")
        ]
        
        args = MagicMock(message_id="msg-uuid-104")
        gh.cmd_accept(args)
        
        # Verify ack was called
        ack_call = mock_run_cmd.call_args_list[1][0][0]
        self.assertIn("ack", ack_call)

    @patch("scripts.coordination.git_handoff.run_cmd")
    def test_accept_non_handoff_kind_rejected(self, mock_run_cmd):
        """Verify messages that are not of kind 'handoff' are rejected."""
        fake_msg = {
            "kind": "note",
            "body": "Just a casual note"
        }
        mock_run_cmd.return_value = MagicMock(stdout=json.dumps(fake_msg))
        args = MagicMock(message_id="msg-uuid-105")
        with self.assertRaises(SystemExit) as cm:
            gh.cmd_accept(args)
        self.assertEqual(cm.exception.code, 1)

    @patch("subprocess.run")
    def test_aplexer_supports_idempotency_key_detection(self, mock_run):
        """Verify detection of --idempotency-key support in aplexer binary."""
        mock_run.return_value = MagicMock(stdout="--idempotency-key <KEY> Idempotency key\n")
        self.assertTrue(gh.aplexer_supports_idempotency_key("/dummy/bin/a"))
        
        mock_run.return_value = MagicMock(stdout="--queue Allow sending\n")
        self.assertFalse(gh.aplexer_supports_idempotency_key("/dummy/bin/a"))


if __name__ == "__main__":
    unittest.main()
