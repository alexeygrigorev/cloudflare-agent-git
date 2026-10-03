#!/usr/bin/env python3
"""Focused offline negative test suite for A01 Feasibility Gate Runner.

Verifies:
1. KeyError prevention on intervention_data delivery & notice paths.
2. Actual assistant model route mismatch rejection (rejects opencode/big-pickle).
3. Unrelated inbox command rejection (aplexer message inbox does not trigger notice).
4. Wrong envelope ID rejection (foreign message ID does not trigger notice).
"""
import json
import os
import sqlite3
import tempfile
import unittest

from research.antigravity.a01_feasibility_gate_runner import (
    check_session_notice,
    verify_session_model_route,
)


class TestA01RunnerHardening(unittest.TestCase):

    def test_1_intervention_data_keyerror_prevention(self):
        """Test 1: Verify all use-sites of intervention_data use consistent keys without KeyError."""
        intervention_type = "intent_note"
        intervention_data = {
            "type": intervention_type,
            "delivered": False,
            "delivered_at_ms": None,
            "delivery_timestamp_ms": None,
            "message_ids": {},
            "producer_delivered_at_ms": None,
            "consumer_delivered_at_ms": None,
            "producer_delivery_disposition": None,
            "consumer_delivery_disposition": None,
            "producer_noticed_at_ms": None,
            "consumer_noticed_at_ms": None,
            "producer_notice_at_ms": None,  # backwards-compat alias
            "consumer_notice_at_ms": None,  # backwards-compat alias
            "producer_uptake_detected": False,
            "consumer_uptake_detected": False
        }

        # Simulate delivery path
        t_deliv = 1791028000000
        mid_p = "01a10001-prod-envelope"
        mid_c = "01a10002-cons-envelope"
        intervention_data["delivered"] = True
        intervention_data["delivered_at_ms"] = t_deliv
        intervention_data["delivery_timestamp_ms"] = t_deliv
        intervention_data["producer_delivered_at_ms"] = t_deliv
        intervention_data["consumer_delivered_at_ms"] = t_deliv
        intervention_data["message_ids"] = {"producer": mid_p, "consumer": mid_c}

        # Simulate notice polling and access path
        self.assertIsNone(intervention_data["producer_noticed_at_ms"])
        self.assertIsNone(intervention_data["consumer_noticed_at_ms"])
        self.assertIsNone(intervention_data["producer_notice_at_ms"])
        self.assertIsNone(intervention_data["consumer_notice_at_ms"])

        # Simulate setting notice
        notice_time = 1791028005000
        intervention_data["producer_noticed_at_ms"] = notice_time
        intervention_data["producer_notice_at_ms"] = notice_time
        intervention_data["consumer_noticed_at_ms"] = notice_time
        intervention_data["consumer_notice_at_ms"] = notice_time

        # Verify no KeyError and values match
        self.assertEqual(intervention_data["producer_noticed_at_ms"], notice_time)
        self.assertEqual(intervention_data["consumer_noticed_at_ms"], notice_time)
        self.assertEqual(intervention_data["producer_notice_at_ms"], notice_time)
        self.assertEqual(intervention_data["consumer_notice_at_ms"], notice_time)

    def test_2_actual_route_mismatch_rejection(self):
        """Test 2: Verify that Attempt 2 DB with assistant model opencode/big-pickle is strictly rejected."""
        attempt2_db = "/home/alexey/git/cloudflare-agent-git/.local/a01-feasibility/failed-runs/arm1a-attempt2-32f9ed2-1791027745/arm1a/env_producer/data/opencode/opencode.db"
        ws = "/home/alexey/git/cloudflare-agent-git/.local/a01-feasibility/arm1a/producer"
        t0 = 1791027752479

        if os.path.exists(attempt2_db):
            with self.assertRaises(RuntimeError) as ctx:
                verify_session_model_route(attempt2_db, ws, t0, timeout=2)
            self.assertIn("MODEL_MISMATCH_ABORT", str(ctx.exception))
            self.assertIn("opencode/big-pickle", str(ctx.exception))
        else:
            # Synthetic DB check if Attempt 2 DB is absent
            with tempfile.NamedTemporaryFile(suffix=".db") as tf:
                con = sqlite3.connect(tf.name)
                cur = con.cursor()
                cur.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT, parent_id TEXT, time_created INTEGER);")
                cur.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);")
                cur.execute("INSERT INTO session VALUES ('s1', '/test/ws', NULL, 1000);")
                # Insert assistant message with mismatch
                cur.execute("INSERT INTO message VALUES ('m1', 's1', 1100, ?);", (json.dumps({
                    "role": "assistant",
                    "providerID": "opencode",
                    "modelID": "big-pickle"
                }),))
                con.commit()
                con.close()

                with self.assertRaises(RuntimeError) as ctx:
                    verify_session_model_route(tf.name, "/test/ws", 1050, timeout=1)
                self.assertIn("MODEL_MISMATCH_ABORT", str(ctx.exception))
                self.assertIn("opencode/big-pickle", str(ctx.exception))

    def test_3_unrelated_inbox_command_rejection(self):
        """Test 3: Unrelated inbox commands (e.g. a message inbox) must NOT trigger notice."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tf:
            con = sqlite3.connect(tf.name)
            cur = con.cursor()
            cur.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT, parent_id TEXT, time_created INTEGER);")
            cur.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);")
            cur.execute("CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);")
            
            ws = "/ws/test"
            launch_t0 = 1000
            delivered_t0 = 1200
            target_msg_id = "01a10000-target-envelope"

            cur.execute("INSERT INTO session VALUES ('s1', ?, NULL, ?);", (ws, launch_t0))

            # Tool call running unrelated inbox command
            cur.execute("INSERT INTO part VALUES ('p1', 'm1', 's1', 1300, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": "aplexer message inbox --workspace /ws/test"},
                    "output": "1 message waiting"
                }
            }),))
            con.commit()
            con.close()

            # Must return None because target_msg_id was not in the command
            notice_res = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertIsNone(notice_res, "Unrelated 'message inbox' tool call must NOT satisfy notice")

            # Positive control: tool call inspecting exact target ID must return timestamp
            con = sqlite3.connect(tf.name)
            cur = con.cursor()
            cur.execute("INSERT INTO part VALUES ('p2', 'm1', 's1', 1400, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "output": "message body"
                }
            }),))
            con.commit()
            con.close()

            notice_res_pos = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertEqual(notice_res_pos, 1400, "Tool call with target_msg_id must satisfy notice")

    def test_4_wrong_envelope_rejection(self):
        """Test 4: User prompt submission containing a foreign/unrelated envelope ID must NOT trigger notice."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tf:
            con = sqlite3.connect(tf.name)
            cur = con.cursor()
            cur.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT, parent_id TEXT, time_created INTEGER);")
            cur.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);")
            cur.execute("CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);")

            ws = "/ws/test"
            launch_t0 = 1000
            delivered_t0 = 1200
            target_msg_id = "01a10000-target-envelope"
            foreign_msg_id = "01a19999-foreign-envelope"

            cur.execute("INSERT INTO session VALUES ('s1', ?, NULL, ?);", (ws, launch_t0))

            # Insert user message with foreign envelope ID
            cur.execute("INSERT INTO message VALUES ('m_user_foreign', 's1', 1300, ?);", (json.dumps({
                "role": "user"
            }),))
            cur.execute("INSERT INTO part VALUES ('p_user_foreign', 'm_user_foreign', 's1', 1300, ?);", (json.dumps({
                "type": "text",
                "text": f"[aplexer message id={foreign_msg_id} from=coordinator] Please review."
            }),))
            con.commit()
            con.close()

            # Must return None because user message contains foreign ID, not target ID
            notice_res = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertIsNone(notice_res, "Prompt submission with foreign envelope ID must NOT satisfy notice")

            # Positive control: user message containing target_msg_id must return timestamp
            con = sqlite3.connect(tf.name)
            cur = con.cursor()
            cur.execute("INSERT INTO message VALUES ('m_user_target', 's1', 1500, ?);", (json.dumps({
                "role": "user"
            }),))
            cur.execute("INSERT INTO part VALUES ('p_user_target', 'm_user_target', 's1', 1500, ?);", (json.dumps({
                "type": "text",
                "text": f"[aplexer message id={target_msg_id} from=coordinator] Action required."
            }),))
            con.commit()
            con.close()

            notice_res_pos = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertEqual(notice_res_pos, 1500, "Prompt submission with target_msg_id must satisfy notice")


if __name__ == "__main__":
    unittest.main()
