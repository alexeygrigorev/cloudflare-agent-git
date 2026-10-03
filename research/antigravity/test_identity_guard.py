#!/usr/bin/env python3
"""
Unit tests for the first-model whoami identity and binding guard.

Verifies:
1. Exact match on FIRST JSON object's `id` against expected receiver UUID (no substring pass).
2. Exact match on FIRST JSON object's `workspace` against expected workspace path.
3. Fail-closed verification of `binding_check`:
   - Must be present as a dictionary with `binding_check.get("ok") is True`.
   - Missing `binding_check` fails closed.
   - `binding_check: null` fails closed.
   - Non-dict `binding_check` fails closed.
   - `binding_check.ok != True` fails closed.
4. Rejection of foreign session IDs, wrong workspaces, malformed JSON, and binding check failures even if expected strings appear later in trailing text (awareness bootstrap, echoed commands, logs).
5. Retained positive regression tests on authentic tool outputs from Run 8 and Run 9.
"""

import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest

# Import the implementation from continuation_trial_runner
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from continuation_trial_runner import (
    verify_whoami_identity,
    get_receiver_opencode_session_id,
)

RECEIVER_UUID = "11111111-2222-4333-8444-555555555555"
FOREIGN_UUID  = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
WORKSPACE     = "/home/alexey/git/cloudflare-agent-git/.local/continuation-trial/workspace"
WRONG_WS      = "/tmp/other-workspace"


class TestIdentityGuard(unittest.TestCase):

    def test_fixture_a_correct_dict_binding(self):
        """Fixture (a): exact match on id, workspace, and dict binding_check ok=True."""
        raw = json.dumps({
            "schema_version": 1,
            "id": RECEIVER_UUID,
            "workspace": WORKSPACE,
            "tag": "continuation-receiver-123",
            "binding_check": {"ok": True, "issues": []}
        }) + "\n\nAplexer awareness bootstrap: session ready."
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertTrue(ok, f"Expected PASS, got: {msg}")
        self.assertEqual(obj["id"], RECEIVER_UUID)
        self.assertEqual(obj["workspace"], WORKSPACE)
        self.assertTrue(obj["binding_check"]["ok"])

    def test_binding_check_missing_fails_closed(self):
        """Negative: binding_check missing entirely -> FAIL."""
        raw = json.dumps({
            "schema_version": 1,
            "id": RECEIVER_UUID,
            "workspace": WORKSPACE,
            "tag": "continuation-receiver"
        })
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("missing or null", msg)

    def test_binding_check_null_fails_closed(self):
        """Negative: binding_check is null -> FAIL."""
        raw = json.dumps({
            "schema_version": 1,
            "id": RECEIVER_UUID,
            "workspace": WORKSPACE,
            "tag": "continuation-receiver",
            "binding_check": None
        })
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("missing or null", msg)

    def test_binding_check_not_dict_fails_closed(self):
        """Negative: binding_check is boolean True instead of dict -> FAIL."""
        raw = json.dumps({
            "schema_version": 1,
            "id": RECEIVER_UUID,
            "workspace": WORKSPACE,
            "tag": "continuation-receiver",
            "binding_check": True
        })
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("not a dict", msg)

    def test_fixture_d2_binding_check_ok_false(self):
        """Fixture (d2): binding_check dict has ok=False -> REJECT."""
        raw = json.dumps({
            "schema_version": 1,
            "id": RECEIVER_UUID,
            "workspace": WORKSPACE,
            "tag": "continuation-receiver",
            "binding_check": {"ok": False, "issues": ["peer mismatch"]}
        })
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("binding_check.ok is not True", msg)

    def test_fixture_b_foreign_id_receiver_later(self):
        """Fixture (b): foreign first JSON id; receiver UUID appears later in text -> REJECT."""
        raw = json.dumps({
            "schema_version": 1,
            "id": FOREIGN_UUID,
            "workspace": WORKSPACE,
            "tag": "continuation-receiver",
            "binding_check": {"ok": True, "issues": []}
        }) + f"\n\n[bootstrap] receiver session {RECEIVER_UUID} ready"
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("first JSON id mismatch", msg)

    def test_fixture_c_wrong_ws_expected_later(self):
        """Fixture (c): wrong actual workspace; expected WS appears later in echoed command -> REJECT."""
        raw = json.dumps({
            "schema_version": 1,
            "id": RECEIVER_UUID,
            "workspace": WRONG_WS,
            "tag": "continuation-receiver",
            "binding_check": {"ok": True, "issues": []}
        }) + f"\n\n$ aplexer start --workspace {WORKSPACE} --json"
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("first JSON workspace mismatch", msg)

    def test_fixture_e_foreign_id_and_wrong_ws_both_later(self):
        """Fixture (e): foreign id AND wrong ws; both expected values appear later -> REJECT."""
        raw = json.dumps({
            "schema_version": 1,
            "id": FOREIGN_UUID,
            "workspace": WRONG_WS,
            "tag": "other-agent",
            "binding_check": {"ok": True, "issues": []}
        }) + f"\nnote: for receiver {RECEIVER_UUID} in {WORKSPACE}"
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)
        self.assertIn("first JSON id mismatch", msg)

    def test_fixture_d1_malformed_json(self):
        """Fixture (d1): malformed JSON -> REJECT."""
        raw = "whoami: command not found\n{truncated json"
        ok, msg, obj = verify_whoami_identity(raw, RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok)

    def test_empty_or_whitespace_output(self):
        """Empty or whitespace-only output -> REJECT."""
        ok1, msg1, _ = verify_whoami_identity("", RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok1)
        ok2, msg2, _ = verify_whoami_identity("   \n\t  ", RECEIVER_UUID, WORKSPACE)
        self.assertFalse(ok2)

    def test_retained_run8_native_whoami(self):
        """Verify authentic tool output recorded in Run 8 log (commit 2c20b81)."""
        run8_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.local/failed-runs/run-8-2c20b81/run.log")
        self.assertTrue(os.path.exists(run8_log), f"Missing Run 8 log at {run8_log}")
        with open(run8_log) as f:
            content = f.read()
        m = re.search(r"Baseline whoami tool output: (\{.*)", content, re.DOTALL)
        self.assertIsNotNone(m, "Could not find baseline whoami output in Run 8 log")
        whoami_output = m.group(1)
        expected_uuid = "3aef6deb-bbc1-4d00-83de-eefc587797c9"
        expected_ws = "/home/alexey/git/cloudflare-agent-git/.local/continuation-trial/workspace"
        ok, msg, obj = verify_whoami_identity(whoami_output, expected_uuid, expected_ws)
        self.assertTrue(ok, f"Run 8 output failed verification: {msg}")
        self.assertEqual(obj["id"], expected_uuid)
        self.assertEqual(obj["workspace"], expected_ws)
        self.assertTrue(obj["binding_check"]["ok"])

    def test_retained_run9_native_whoami(self):
        """Verify authentic tool output recorded in Run 9 log (commit 9764583)."""
        run9_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.local/failed-runs/run-9-9764583/run.log")
        self.assertTrue(os.path.exists(run9_log), f"Missing Run 9 log at {run9_log}")
        with open(run9_log) as f:
            content = f.read()
        m = re.search(r"Baseline whoami tool output: (\{.*)", content, re.DOTALL)
        self.assertIsNotNone(m, "Could not find baseline whoami output in Run 9 log")
        whoami_output = m.group(1)
        expected_uuid = "5408ff66-86a6-4f09-ad78-8ecdbd2f0892"
        expected_ws = "/home/alexey/git/cloudflare-agent-git/.local/continuation-trial/workspace"
        ok, msg, obj = verify_whoami_identity(whoami_output, expected_uuid, expected_ws)
        self.assertTrue(ok, f"Run 9 output failed verification: {msg}")
        self.assertEqual(obj["id"], expected_uuid)
        self.assertEqual(obj["workspace"], expected_ws)
        self.assertTrue(obj["binding_check"]["ok"])


class TestReceiverOpenCodeSessionIdQuery(unittest.TestCase):
    """
    SQL tests for OpenCode receiver session ID resolution and fail-closed binding.
    Addresses Codex C-1259, C-1260, and C-1268 directives:
    1. Positive: Single clean root session in workspace created >= since_ms is returned.
    2. Negative: Receiver first + child session later in shared workspace:
       Child session (parent_id='ses_recv') must NOT override or collide with receiver root session.
    3. Negative: Receiver first + second root session later in shared workspace (exact mapping failclosed):
       Ambiguity between multiple root sessions created >= since_ms must FAIL CLOSED (return None).
    4. Negative: Stale session created before since_ms must be ignored.
    5. Negative: Session created in foreign workspace directory must be ignored.
    """

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE session (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                directory TEXT NOT NULL,
                time_created INTEGER NOT NULL
            );
        """)
        con.commit()
        con.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _insert_session(self, sid, parent_id, directory, time_created):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            "INSERT INTO session (id, parent_id, directory, time_created) VALUES (?, ?, ?, ?)",
            (sid, parent_id, directory, time_created)
        )
        con.commit()
        con.close()

    def test_sql_positive_single_clean_session(self):
        """Positive: Exactly one matching root session in workspace returns that session ID."""
        self._insert_session("ses_recv_clean", None, WORKSPACE, 1000)
        resolved = get_receiver_opencode_session_id(WORKSPACE, since_ms=1000, db_path=self.db_path)
        self.assertEqual(resolved, "ses_recv_clean")

    def test_sql_negative_receiver_first_child_later(self):
        """
        Negative (Codex C-1268): Receiver first + child session later in shared workspace.
        Child session has parent_id='ses_recv' and time_created=2000.
        get_receiver_opencode_session_id must NOT return the later child session,
        it must correctly resolve the receiver root session 'ses_recv'.
        """
        self._insert_session("ses_recv", None, WORKSPACE, 1000)
        self._insert_session("ses_child", "ses_recv", WORKSPACE, 2000)
        resolved = get_receiver_opencode_session_id(WORKSPACE, since_ms=1000, db_path=self.db_path)
        self.assertEqual(resolved, "ses_recv")

    def test_sql_negative_exact_mapping_failclosed_multiple_root_sessions(self):
        """
        Negative (Codex C-1268): Multiple root sessions in shared workspace created >= since_ms.
        Receiver root session created at 1000, sender or foreign root session created at 2000.
        Because mapping is ambiguous (len > 1), query MUST fail closed and return None.
        """
        self._insert_session("ses_recv_1", None, WORKSPACE, 1000)
        self._insert_session("ses_sender_root_2", None, WORKSPACE, 2000)
        resolved = get_receiver_opencode_session_id(WORKSPACE, since_ms=1000, db_path=self.db_path)
        self.assertIsNone(resolved, "Ambiguous multiple root sessions did NOT fail closed!")

    def test_sql_negative_stale_session_ignored(self):
        """Negative: Prior session created before since_ms must be ignored."""
        self._insert_session("ses_stale", None, WORKSPACE, 500)
        resolved = get_receiver_opencode_session_id(WORKSPACE, since_ms=1000, db_path=self.db_path)
        self.assertIsNone(resolved, "Stale session before since_ms was wrongly matched!")

    def test_sql_negative_foreign_directory_ignored(self):
        """Negative: Session in foreign directory must be ignored even if newer."""
        self._insert_session("ses_foreign", None, WRONG_WS, 1500)
        resolved = get_receiver_opencode_session_id(WORKSPACE, since_ms=1000, db_path=self.db_path)
        self.assertIsNone(resolved, "Foreign directory session was wrongly matched!")


if __name__ == "__main__":
    unittest.main()

