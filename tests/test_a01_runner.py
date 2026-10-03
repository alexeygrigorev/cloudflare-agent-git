#!/usr/bin/env python3
"""Focused offline negative test suite for A01 Feasibility Gate Runner.

Verifies:
1. KeyError prevention on intervention_data delivery & notice paths via create_intervention_data factory.
2. Actual assistant model route mismatch rejection (rejects opencode/big-pickle).
3. Unrelated inbox command rejection (aplexer message inbox does not trigger notice).
4. Notice oracle precision:
   - Failed message show with error output -> returns None.
   - Unrelated echo <ID> -> returns None.
   - Genuine completed message show with read output exposure -> returns timestamp.
5. Delivery disposition mapping (malformed, missing status, uncertain -> all map to UNKNOWN).
6. R22 multiline draft negative for composer classifier (draft text above footer must NOT return 'empty').
"""
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest

from research.antigravity.a01_feasibility_gate_runner import (
    check_session_notice,
    composer_classifier,
    create_intervention_data,
    parse_delivery_disposition,
    verify_session_model_route,
)


class TestA01RunnerHardening(unittest.TestCase):

    def test_1_intervention_data_keyerror_prevention(self):
        """Test 1: Verify production create_intervention_data factory and all use-sites prevent KeyError."""
        intervention_data = create_intervention_data("intent_note")

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
        self.assertIsNone(intervention_data.get("producer_delivery_disposition"))
        self.assertIsNone(intervention_data.get("consumer_delivery_disposition"))

        # Simulate setting delivery disposition
        intervention_data["producer_delivery_disposition"] = "submitted"
        intervention_data["consumer_delivery_disposition"] = "UNKNOWN"
        self.assertEqual(intervention_data.get("producer_delivery_disposition"), "submitted")
        self.assertEqual(intervention_data.get("consumer_delivery_disposition"), "UNKNOWN")

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
            with tempfile.NamedTemporaryFile(suffix=".db") as tf:
                con = sqlite3.connect(tf.name)
                cur = con.cursor()
                cur.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT, parent_id TEXT, time_created INTEGER);")
                cur.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);")
                cur.execute("INSERT INTO session VALUES ('s1', '/test/ws', NULL, 1000);")
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
                    "status": "completed",
                    "output": "1 message waiting"
                }
            }),))
            con.commit()
            con.close()

            notice_res = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertIsNone(notice_res, "Unrelated 'message inbox' tool call must NOT satisfy notice")

    def test_4_notice_oracle_failure_and_unrelated_command_rejection(self):
        """Test 4: Notice oracle must reject failed tool executions, unrelated commands, and require envelope exposure."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tf:
            con = sqlite3.connect(tf.name)
            cur = con.cursor()
            cur.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT, parent_id TEXT, time_created INTEGER);")
            cur.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);")
            cur.execute("CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);")

            ws = "/ws/test"
            launch_t0 = 1000
            delivered_t0 = 1200
            target_msg_id = "01a1r34-target-envelope"

            cur.execute("INSERT INTO session VALUES ('s1', ?, NULL, ?);", (ws, launch_t0))

            # Case A: FAILED message show with exact target ID in command AND failure in output
            cur.execute("INSERT INTO part VALUES ('p_fail', 'm1', 's1', 1300, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "status": "completed",
                    "output": f"ERROR FAILED rc=1: message {target_msg_id} not delivered"
                }
            }),))
            con.commit()

            # Must return None because output indicates error/failure
            res_fail = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertIsNone(res_fail, "Failed tool call with error output must NOT satisfy notice")

            # Case B: Unrelated echo <ID>
            cur.execute("INSERT INTO part VALUES ('p_echo', 'm1', 's1', 1400, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"echo {target_msg_id}"},
                    "status": "completed",
                    "output": f"{target_msg_id}\n"
                }
            }),))
            con.commit()

            # Must return None because command is echo, not message show/read
            res_echo = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertIsNone(res_echo, "Unrelated 'echo <ID>' command must NOT satisfy notice")

            # Case C: Genuine completed message show with read output exposure
            cur.execute("INSERT INTO part VALUES ('p_succ', 'm1', 's1', 1500, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "status": "completed",
                    "output": json.dumps({"id": target_msg_id, "status": "delivered", "body": "Coordination Notice"})
                }
            }),))
            con.commit()

            # Must return 1500
            res_succ = check_session_notice(tf.name, ws, launch_t0, delivered_t0, target_msg_id)
            self.assertEqual(res_succ, 1500, "Genuine completed show with read output must satisfy notice")

            # Case D: Absent status (status=None or "") with valid command and envelope output -> must return None
            cur.execute("INSERT INTO part VALUES ('p_nostatus', 'm1', 's1', 1600, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "output": json.dumps({"id": target_msg_id, "status": "delivered", "body": "Coordination Notice"})
                }
            }),))
            con.commit()
            res_nostatus = check_session_notice(tf.name, ws, launch_t0, 1550, target_msg_id)
            self.assertIsNone(res_nostatus, "Absent status must NOT satisfy notice")

            # Case E: Arbitrary output mentioning ID without envelope structure -> must return None
            cur.execute("INSERT INTO part VALUES ('p_arbitrary', 'm1', 's1', 1700, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "status": "completed",
                    "output": f"Arbitrary log message mentioning {target_msg_id} somewhere in random text"
                }
            }),))
            con.commit()
            res_arbitrary = check_session_notice(tf.name, ws, launch_t0, 1650, target_msg_id)
            self.assertIsNone(res_arbitrary, "Arbitrary unstructured text containing ID must NOT satisfy notice")

            # Case F: JSON envelope output with matching id -> must return timestamp
            cur.execute("INSERT INTO part VALUES ('p_json_env', 'm1', 's1', 1800, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "status": "completed",
                    "output": json.dumps({"id": target_msg_id, "status": "delivered", "body": "Coordination Notice"})
                }
            }),))
            con.commit()
            res_json_env = check_session_notice(tf.name, ws, launch_t0, 1750, target_msg_id)
            self.assertEqual(res_json_env, 1800, "JSON envelope output with matching id must satisfy notice")

            # Case G: Formatted text output with matching id header -> must return timestamp
            formatted_text = f"id: {target_msg_id}\nfrom: coordinator\nbody: Action required\n"
            cur.execute("INSERT INTO part VALUES ('p_text_env', 'm1', 's1', 1900, ?);", (json.dumps({
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {"command": f"aplexer message show {target_msg_id}"},
                    "status": "completed",
                    "output": formatted_text
                }
            }),))
            con.commit()
            res_text_env = check_session_notice(tf.name, ws, launch_t0, 1850, target_msg_id)
            self.assertEqual(res_text_env, 1900, "Formatted text output with matching id header must satisfy notice")
            con.close()

    def test_5_delivery_disposition_mapping(self):
        """Test 5: Delivery outcome parsing must strictly map malformed, missing status, and uncertain to UNKNOWN."""
        # Helper dummy CompletedProcess
        class DummyProc:
            def __init__(self, stdout, returncode=0):
                self.stdout = stdout
                self.returncode = returncode

        # Malformed JSON -> UNKNOWN
        p_malformed = DummyProc("not a json string", returncode=0)
        self.assertEqual(parse_delivery_disposition(p_malformed), "UNKNOWN")

        # Missing status field -> UNKNOWN
        p_no_status = DummyProc(json.dumps({"id": "01a1-uuid"}), returncode=0)
        self.assertEqual(parse_delivery_disposition(p_no_status), "UNKNOWN")

        # Uncertain status -> UNKNOWN
        p_uncertain = DummyProc(json.dumps({"id": "01a1-uuid", "status": "uncertain"}), returncode=0)
        self.assertEqual(parse_delivery_disposition(p_uncertain), "UNKNOWN")

        # Empty status -> UNKNOWN
        p_empty_status = DummyProc(json.dumps({"id": "01a1-uuid", "status": ""}), returncode=0)
        self.assertEqual(parse_delivery_disposition(p_empty_status), "UNKNOWN")

        # Valid submitted -> "submitted"
        p_submitted = DummyProc(json.dumps({"id": "01a1-uuid", "status": "submitted"}), returncode=0)
        self.assertEqual(parse_delivery_disposition(p_submitted), "submitted")

        # Non-zero returncode -> "failed_rc_<code\>"
        p_failed = DummyProc("", returncode=2)
        self.assertEqual(parse_delivery_disposition(p_failed), "failed_rc_2")

    def test_6_r22_multiline_draft_not_empty(self):
        """Test 6: Multiline draft above unchanged footer must NOT classify as empty."""
        multiline_draft_screen = """
   ▣  Build · Space Bunny Free
┃  first line of user draft
┃  second line of user draft
┃
┃  Build auto · Space Bunny Free OpenCode Go
╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
 /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands
"""
        res_draft = composer_classifier(multiline_draft_screen)
        self.assertNotEqual(res_draft, "empty", "Multiline draft with text above footer must NOT return empty")
        self.assertEqual(res_draft, "draft", "Multiline draft must return 'draft'")

        # Positive control: clean empty composer
        empty_screen = """
   ▣  Build · Space Bunny Free
┃
┃  Build auto · Space Bunny Free OpenCode Go
╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
 /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands
"""
        res_empty = composer_classifier(empty_screen)
        self.assertEqual(res_empty, "empty", "Clean composer must return 'empty'")


if __name__ == "__main__":
    unittest.main()
