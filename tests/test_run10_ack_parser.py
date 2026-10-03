#!/usr/bin/env python3
"""Offline unit test suite for Run 10 discrete ACK envelope parser and correlation verification.

Covers:
- Test 1: Genuine correlated receiver reply envelope -> returns True ((True, msg_id)).
- Test 2: Sender-self request in mailbox containing the ACK string -> returns False (strictly rejects self-request).
- Test 3: Foreign session message containing the ACK string -> returns False.
- Test 4: Message from receiver but wrong reply_to -> returns False.
- Additional edge cases:
    - Missing or null reply_to from receiver -> returns False.
    - Multipart mailbox log with earlier self-requests followed by valid correlated reply -> returns True.
    - Direct raw_log invocation (bypassing subprocess).
    - Parse errors or command failure -> returns False.
"""
import json
import unittest
from unittest.mock import patch

from research.antigravity.continuation_trial_runner import (
    verify_durable_ack_envelope,
    _match_session_or_tag,
    _parse_messages_log,
)


class TestRun10AckParser(unittest.TestCase):

    def setUp(self):
        self.workspace = "/home/alexey/git/cloudflare-agent-git/.local/continuation-trial/workspace"
        self.sender_uuid = "ccc3d41f-a78a-4896-a17b-290d23b1015a"
        self.sender_tag = "continuation-sender-1791026615"
        self.receiver_uuid = "2d8b21d8-8ad2-46b4-8899-fe9c844dea6c"
        self.receiver_tag = "continuation-receiver-1791026615"
        self.foreign_uuid = "1ff2ad02-4946-4d78-b53d-10627f5b9477"
        self.foreign_tag = "foreign-sender-1791026615"
        self.req_msg_id = "01a10183-027c-7e20-9587-18301ba5a817"
        self.reply_msg_id = "01a10183-5a21-7e20-abcd-18301ba5a999"
        self.ack_str = "ACK_TURN1_1791026722"

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_1_genuine_correlated_receiver_reply(self, mock_exec):
        """Test 1: Genuine correlated receiver reply envelope -> returns True."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.req_msg_id,
                "workspace": self.workspace,
                "from": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "to": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "kind": "note",
                "body": f"Please complete task and reply with '{self.ack_str}'.",
            },
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Turn 1 completed. {self.ack_str}",
            }
        ]))

        # Test with keyword tags
        ok, val = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertTrue(ok)
        self.assertEqual(val, self.reply_msg_id)

        # Test with 5 positional arguments (matching purely on session_ids)
        ok_pos, val_pos = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
        )
        self.assertTrue(ok_pos)
        self.assertEqual(val_pos, self.reply_msg_id)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_2_sender_self_request_in_mailbox_rejected(self, mock_exec):
        """Test 2: Sender-self request in mailbox containing the ACK string -> returns False (strictly rejects self-request)."""
        # Exactly reproduces Run 10 naive substring failure where the sender's own outgoing work item
        # prompt contains the expected ACK substring in JSON parameters.
        sender_prompt_body = (
            f"Work item for task continuation-task-1791026615: "
            f"{{\"task_id\": \"continuation-task-1791026615\", \"operation\": \"create_file\", "
            f"\"target\": \"turn1_1791026722.txt\", \"content\": \"CONTINUATION_TURN1_VERIFIED_1791026722\", "
            f"\"ack\": \"{self.ack_str}\"}}. "
            f"Please write exactly 'CONTINUATION_TURN1_VERIFIED_1791026722' to relative file turn1_1791026722.txt. "
            f"After writing the file, reply to this message with '{self.ack_str}'."
        )
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.req_msg_id,
                "workspace": self.workspace,
                "from": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "to": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "kind": "note",
                "body": sender_prompt_body,
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("sender-self", reason)
        self.assertIn("rejecting self-request", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_3_foreign_session_message_rejected(self, mock_exec):
        """Test 3: Foreign session message containing the ACK string -> returns False."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": "01a10182-foreign-injection",
                "workspace": self.workspace,
                "from": {"session_id": self.foreign_uuid, "tag": self.foreign_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Forged foreign ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("foreign session", reason)
        self.assertIn("expected receiver", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_4_receiver_message_wrong_reply_to_rejected(self, mock_exec):
        """Test 4: Message from receiver but wrong reply_to -> returns False."""
        wrong_reply_to_id = "01a10000-completely-different-req-id"
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": "01a10183-receiver-wrong-correlation",
                "workspace": self.workspace,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": wrong_reply_to_id,
                "body": f"ACK here: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("reply_to", reason)
        self.assertIn(wrong_reply_to_id, reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_5_receiver_message_missing_reply_to_rejected(self, mock_exec):
        """Test 5: Message from receiver but reply_to is None or missing -> returns False."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": "01a10183-receiver-no-reply-to",
                "workspace": self.workspace,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "note",
                "reply_to": None,
                "body": f"Uncorrelated note containing {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
        )
        self.assertFalse(ok)
        self.assertIn("reply_to", reason)

    def test_6_direct_raw_log_matching_with_multiple_entries(self):
        """Test 6: Mailbox log containing both earlier self-request AND later correlated receiver reply."""
        raw_log = [
            {
                "schema_version": 1,
                "id": self.req_msg_id,
                "workspace": self.workspace,
                "from": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "to": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "kind": "note",
                "body": f"Request body with '{self.ack_str}'",
            },
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"ACK_CONFIRMED: {self.ack_str}",
            }
        ]

        ok, val = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
            raw_log=raw_log,
        )
        self.assertTrue(ok)
        self.assertEqual(val, self.reply_msg_id)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_7_exec_failure_or_corrupt_json(self, mock_exec):
        """Test 7: Subprocess error or invalid JSON returns False with descriptive reason."""
        mock_exec.return_value = (1, "aplexer: daemon not running")
        ok, reason = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
        )
        self.assertFalse(ok)
        self.assertIn("failed with exit code 1", reason)

        # Corrupt JSON output
        mock_exec.return_value = (0, "not a json array")
        ok2, reason2 = verify_durable_ack_envelope(
            self.sender_uuid,
            self.receiver_uuid,
            self.req_msg_id,
            self.ack_str,
            self.workspace,
        )
        self.assertFalse(ok2)
        self.assertIn("Failed to parse valid JSON array", reason2)


if __name__ == "__main__":
    unittest.main()
