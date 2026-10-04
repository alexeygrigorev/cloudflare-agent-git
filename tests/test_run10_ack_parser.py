#!/usr/bin/env python3
"""Offline negative and positive unit test suite for Run 10 discrete ACK envelope parser.

Per Codex Principal C-1297 & C-1299:
1. Exact Native UUID Matching:
   - msg.from.session_id == receiver_uuid strictly enforced
   - msg.to.session_id == sender_uuid strictly enforced
   - Tags are diagnostic only; tag fallback strictly forbidden
2. Non-empty envelope ID required
3. Post-request timestamp enforced at native integer second precision (int(c_sec) >= int(m_sec))
   - min_timestamp_sec is a REQUIRED parameter (no None default)
   - Same-second float caller (e.g. min_timestamp_sec=1791028000.75 vs created_at=1791028000) is accepted
   - Previous-second envelope (e.g. created_at=1791027999 vs min_timestamp_sec=1791028000.0) is strictly rejected
4. Correlated reply_to == expected_reply_to and expected_ack_substring in body

Test cases:
- Test 1: Genuine matching reply with exact UUIDs, valid post-request timestamp, matching reply_to, and body -> accepted
- Test 2: Correct tag + wrong UUID on receiver side -> strictly rejected
- Test 3: Correct tag + wrong UUID on sender side -> strictly rejected
- Test 4: Tag-only / missing session_id on receiver or sender -> strictly rejected
- Test 5: Body echo in sender's own request message -> strictly rejected
- Test 6: Replay / wrong reply_to -> strictly rejected
- Test 7: Timestamp before request (previous second) -> strictly rejected
- Test 8: Empty or missing envelope ID -> strictly rejected
- Test 9: Helper _match_session_or_tag strictly rejects tag fallback
- Test 10: Multipart mailbox log with earlier self-request followed by valid correlated reply -> accepted
- Test 11: Same-second float caller accepted (created_at=1791028000, min_timestamp_sec=1791028000.75) -> accepted
- Test 12: Previous-second envelope rejected (created_at=1791027999, min_timestamp_sec=1791028000.0) -> strictly rejected
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
        self.req_msg_id = "01a10183-027c-7e20-9587-18301ba5a817"
        self.reply_msg_id = "01a10183-5a21-7e20-abcd-18301ba5a999"
        self.ack_str = "ACK_TURN1_1791026722"
        self.req_timestamp_sec = 1791026720.0
        self.reply_timestamp_sec = 1791026725.0

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_1_genuine_matching_reply_accepted(self, mock_exec):
        """Test 1: Genuine matching reply with exact UUIDs, valid post-request timestamp, matching reply_to, and body -> accepted."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.req_msg_id,
                "workspace": self.workspace,
                "created_at": self.req_timestamp_sec,
                "from": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "to": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "kind": "note",
                "body": f"Please complete task and reply with '{self.ack_str}'.",
            },
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Turn 1 completed. {self.ack_str}",
            }
        ]))

        ok, val = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertTrue(ok)
        self.assertEqual(val, self.reply_msg_id)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_2_correct_tag_wrong_uuid_receiver_rejected(self, mock_exec):
        """Test 2: Correct tag + wrong UUID on receiver side -> strictly rejected."""
        wrong_receiver_uuid = "e82eb89c-5f50-49f9-9dee-ffaee50b004a"
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                # Has the expected receiver tag, but a mismatched/foreign session_id!
                "from": {"session_id": wrong_receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Spoofed ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("strictly rejected", reason)
        self.assertIn("does not match expected receiver UUID", reason)
        self.assertIn("diagnostic only", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_3_correct_tag_wrong_uuid_sender_rejected(self, mock_exec):
        """Test 3: Correct tag + wrong UUID on sender side -> strictly rejected."""
        wrong_sender_uuid = "1ff2ad02-4946-4d78-b53d-10627f5b9477"
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                # Has the expected sender tag, but a mismatched session_id!
                "to": {"session_id": wrong_sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Misrouted ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("strictly rejected", reason)
        self.assertIn("does not match expected sender UUID", reason)
        self.assertIn("diagnostic only", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_4_tag_only_missing_session_id_rejected(self, mock_exec):
        """Test 4: Tag-only / missing session_id -> strictly rejected."""
        # Case A: Missing session_id on receiver side
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"tag": self.receiver_tag},  # No session_id!
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("missing from.session_id", reason)
        self.assertIn("cannot substitute for native UUID", reason)

        # Case B: Missing session_id on sender side
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"tag": self.sender_tag},  # No session_id!
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"ACK: {self.ack_str}",
            }
        ]))

        ok2, reason2 = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
        )
        self.assertFalse(ok2)
        self.assertIn("missing to.session_id", reason2)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_5_body_echo_in_sender_own_request_rejected(self, mock_exec):
        """Test 5: Body echo in sender's own request message -> strictly rejected."""
        # Exact reproduction of Run 10 false-ACK bug
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.req_msg_id,
                "workspace": self.workspace,
                "created_at": self.req_timestamp_sec,
                "from": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "to": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "kind": "note",
                "body": f"Work item: {{\"ack\": \"{self.ack_str}\"}}. Reply with '{self.ack_str}'.",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("sender-self", reason)
        self.assertIn("strictly rejecting self-request", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_6_replay_wrong_reply_to_rejected(self, mock_exec):
        """Test 6: Replay / wrong reply_to -> strictly rejected."""
        stale_request_id = "01a10000-stale-previous-request-id"
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": stale_request_id,  # Uncorrelated!
                "body": f"Done: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("reply_to", reason)
        self.assertIn("expected correlated request ID", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_7_timestamp_before_request_rejected(self, mock_exec):
        """Test 7: Timestamp before request (previous second) -> strictly rejected."""
        predated_timestamp_sec = self.req_timestamp_sec - 100.0  # Before request
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": predated_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Replayed old ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("is before minimum request timestamp", reason)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_8_empty_or_whitespace_envelope_id_rejected(self, mock_exec):
        """Test 8: Envelope with empty or whitespace ID is strictly rejected."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": "   ",  # Whitespace / empty ID!
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
        )
        self.assertFalse(ok)
        self.assertIn("missing or empty", reason)

    def test_9_match_session_or_tag_strictly_rejects_tag_fallback(self):
        """Test 9: Helper _match_session_or_tag strictly rejects tag fallback."""
        # 1. Matching tag but mismatched session_id -> MUST BE False
        self.assertFalse(
            _match_session_or_tag(
                {"session_id": "different-uuid", "tag": "my-tag"},
                "expected-uuid",
                "my-tag"
            )
        )
        # 2. Tag only without session_id -> MUST BE False
        self.assertFalse(
            _match_session_or_tag(
                {"tag": "my-tag"},
                "expected-uuid",
                "my-tag"
            )
        )
        # 3. String tag instead of dict -> MUST BE False
        self.assertFalse(
            _match_session_or_tag(
                "my-tag",
                "expected-uuid",
                "my-tag"
            )
        )
        # 4. Exact UUID matching -> MUST BE True
        self.assertTrue(
            _match_session_or_tag(
                {"session_id": "expected-uuid", "tag": "any-tag"},
                "expected-uuid",
                "any-tag"
            )
        )

    def test_10_multipart_mailbox_log_with_earlier_self_request(self):
        """Test 10: Multipart mailbox log with earlier self-request followed by valid correlated reply -> accepted."""
        raw_log = [
            # Earlier sender request containing ACK string in body
            {
                "schema_version": 1,
                "id": self.req_msg_id,
                "workspace": self.workspace,
                "created_at": self.req_timestamp_sec,
                "from": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "to": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "kind": "note",
                "body": f"Please reply with {self.ack_str}",
            },
            # Subsequent receiver reply with correlated reply_to and exact native UUIDs
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": self.reply_timestamp_sec,
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"CONFIRMED_{self.ack_str}",
            }
        ]

        ok, val = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=self.req_timestamp_sec,
            raw_log=raw_log,
        )
        self.assertTrue(ok)
        self.assertEqual(val, self.reply_msg_id)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_11_same_second_float_caller_accepted(self, mock_exec):
        """Test 11: Same-second float caller accepted (created_at=1791028000, min_timestamp_sec=1791028000.75)."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": 1791028000,  # Native integer second in envelope
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Same second ACK: {self.ack_str}",
            }
        ]))

        ok, val = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=1791028000.75,  # Subsecond float captured at request time
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertTrue(ok)
        self.assertEqual(val, self.reply_msg_id)

    @patch("research.antigravity.continuation_trial_runner.exec_in_sender")
    def test_12_previous_second_envelope_rejected(self, mock_exec):
        """Test 12: Previous-second envelope rejected (created_at=1791027999, min_timestamp_sec=1791028000.0)."""
        mock_exec.return_value = (0, json.dumps([
            {
                "schema_version": 1,
                "id": self.reply_msg_id,
                "workspace": self.workspace,
                "created_at": 1791027999,  # 1 second before minimum request time
                "from": {"session_id": self.receiver_uuid, "tag": self.receiver_tag},
                "to": {"session_id": self.sender_uuid, "tag": self.sender_tag},
                "kind": "reply",
                "reply_to": self.req_msg_id,
                "body": f"Old second ACK: {self.ack_str}",
            }
        ]))

        ok, reason = verify_durable_ack_envelope(
            sender_uuid=self.sender_uuid,
            receiver_uuid=self.receiver_uuid,
            expected_reply_to=self.req_msg_id,
            expected_ack_substring=self.ack_str,
            workspace=self.workspace,
            min_timestamp_sec=1791028000.0,
            receiver_tag=self.receiver_tag,
            sender_tag=self.sender_tag,
        )
        self.assertFalse(ok)
        self.assertIn("1791027999s is before minimum request timestamp 1791028000s", reason)


if __name__ == "__main__":
    unittest.main()
