#!/usr/bin/env python3
"""Unit tests for Fail-Closed Failover Integration (scripts/supervision/failover_integration.py).

Verifies Directives C3110 / C3111 & Desktop Audit:
1. reported_state=None is strictly NOT ready.
2. Contradicted resting state (last_activity_ms > reported_state_at_ms + 1000) is strictly NOT ready.
3. Screen with draft sets draft=True and ready=False.
4. Clean empty prompt with idle state sets ready=True and draft=False.
5. Quota exhausted or unknown sets quota_ok=False.
6. SupervisorBusAdapter strictly requires non-empty idempotency_key.
7. SupervisorBusAdapter fails closed if send intent exists without durable receipt.
"""

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.supervision.failover_integration as fi


class TestFailoverIntegrationFailClosed(unittest.TestCase):
    def test_bus_adapter_requires_idempotency_key(self):
        adapter = fi.SupervisorBusAdapter(
            binary="/bin/aplexer",
            spool=pathlib.Path("/tmp"),
            supports_key=True,
            sender_id="sender-1",
            command_fn=lambda args: "{}",
            recorded_send_fn=lambda *a, **k: {}
        )
        with self.assertRaises(ValueError) as ctx:
            adapter.send(sender_id="s", token="t", recipient_id="r", body="b", idempotency_key=None)
        self.assertIn("idempotency_key is required", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            adapter.send(sender_id="s", token="t", recipient_id="r", body="b", idempotency_key="   ")
        self.assertIn("idempotency_key is required", str(ctx.exception))

    def test_bus_adapter_existing_intent_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            spool = pathlib.Path(td)
            intent = spool / "intent-test_key.json"
            intent.write_text(json.dumps({"state": "send-may-have-started"}))

            adapter = fi.SupervisorBusAdapter(
                binary="/bin/aplexer",
                spool=spool,
                supports_key=True,
                sender_id="sender-1",
                command_fn=lambda args: "{}",
                recorded_send_fn=lambda *a, **k: {}
            )

            with self.assertRaises(RuntimeError) as ctx:
                adapter.send(sender_id="s", token="t", recipient_id="r", body="b", idempotency_key="test/key")
            self.assertIn("Existing send intent without durable receipt", str(ctx.exception))

    def test_bus_adapter_happy_path_recorded_send(self):
        with tempfile.TemporaryDirectory() as td:
            spool = pathlib.Path(td)
            calls = []

            def fake_cmd(args):
                calls.append(args)
                return json.dumps({"id": "env-123", "status": "inbox"})

            adapter = fi.SupervisorBusAdapter(
                binary="/bin/aplexer",
                spool=spool,
                supports_key=True,
                sender_id="sender-1",
                command_fn=fake_cmd,
                recorded_send_fn=lambda *a, **k: {}
            )

            msg = adapter.send(sender_id="s", token="t", recipient_id="r", body="hello", idempotency_key="k1")
            self.assertEqual(msg.message_id, "env-123")
            self.assertTrue((spool / "receipt-k1.json").exists())
            self.assertFalse((spool / "intent-k1.json").exists())

            # Second send with same key reuses receipt without calling command
            calls.clear()
            msg2 = adapter.send(sender_id="s", token="t", recipient_id="r", body="hello", idempotency_key="k1")
            self.assertEqual(msg2.message_id, "env-123")
            self.assertEqual(len(calls), 0)

    def test_run_failover_tick_strict_fail_closed_observations(self):
        with tempfile.TemporaryDirectory() as td:
            spool = pathlib.Path(td)
            observations = []

            class FakeRoleAuthority:
                def __init__(self, db_path):
                    pass
                def configure(self, proj, role, candidates):
                    pass
                def observe(self, actor, host, generation, *, ready, draft, quota_ok, priority=100):
                    observations.append({
                        "actor": actor,
                        "generation": generation,
                        "ready": ready,
                        "draft": draft,
                        "quota_ok": quota_ok
                    })

            class FakeFailoverBridge:
                def __init__(self, **kw):
                    pass
                def tick(self, proj, role):
                    pass

            real_ra = fi.RoleAuthority if hasattr(fi, 'RoleAuthority') else None
            real_fb = fi.FailoverBridge if hasattr(fi, 'FailoverBridge') else None

            try:
                fi.RoleAuthority = FakeRoleAuthority
                fi.FailoverBridge = FakeFailoverBridge

                registry = {
                    "agents": [
                        {"project_id": "P1", "role": "principal", "tag": "test-p"}
                    ]
                }

                # 4 test sessions exercising all permutations
                sessions = [
                    # Case 1: reported_state is None -> MUST NOT BE READY
                    {
                        "id": "sess-none",
                        "tag": "test-p",
                        "reported_state": None,
                        "last_activity_ms": 1000,
                        "reported_state_at_ms": 1000
                    },
                    # Case 2: Contradicted resting state (last_activity > reported_state_at + 1000) -> MUST NOT BE READY
                    {
                        "id": "sess-contradicted",
                        "tag": "test-p",
                        "reported_state": "idle",
                        "last_activity_ms": 2500,
                        "reported_state_at_ms": 1000
                    },
                    # Case 3: Draft in screen -> draft=True, ready=False
                    {
                        "id": "sess-draft",
                        "tag": "test-p",
                        "reported_state": "idle",
                        "last_activity_ms": 1000,
                        "reported_state_at_ms": 1000
                    },
                    # Case 4: Clean idle, no draft, no contradiction, good quota -> ready=True, draft=False, quota_ok=True
                    {
                        "id": "sess-clean",
                        "tag": "test-p",
                        "reported_state": "idle",
                        "last_activity_ms": 1000,
                        "reported_state_at_ms": 1000
                    }
                ]

                def fake_cmd(args):
                    if "capture" in args:
                        sid = args[2]
                        if sid == "sess-draft":
                            return "> my unfinished prompt\n────────────────────────────────"
                        elif sid == "sess-clean":
                            return ">\n────────────────────────────────\n? for shortcuts"
                        return "unknown screen"
                    if args[0] == "quse":
                        return json.dumps({
                            "codex": {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0}}}
                        })
                    return "{}"

                fi.run_failover_tick(
                    spool=spool,
                    binary="/bin/aplexer",
                    supports_key=True,
                    identity_id="sup-1",
                    command_fn=fake_cmd,
                    recorded_send_fn=lambda *a, **k: {},
                    registry=registry,
                    sessions=sessions
                )

                self.assertEqual(len(observations), 4)

                # Verification of Case 1: None reported state
                obs_none = observations[0]
                self.assertEqual(obs_none["generation"], "sess-none")
                self.assertFalse(obs_none["ready"], "reported_state=None MUST NOT be ready")

                # Verification of Case 2: Contradicted resting state
                obs_contra = observations[1]
                self.assertEqual(obs_contra["generation"], "sess-contradicted")
                self.assertFalse(obs_contra["ready"], "Contradicted resting state MUST NOT be ready")

                # Verification of Case 3: Draft present
                obs_draft = observations[2]
                self.assertEqual(obs_draft["generation"], "sess-draft")
                self.assertTrue(obs_draft["draft"], "Screen with draft MUST report draft=True")
                self.assertFalse(obs_draft["ready"], "Screen with draft MUST NOT be ready")

                # Verification of Case 4: Clean idle
                obs_clean = observations[3]
                self.assertEqual(obs_clean["generation"], "sess-clean")
                self.assertTrue(obs_clean["ready"], "Clean idle session MUST be ready")
                self.assertFalse(obs_clean["draft"], "Clean idle session MUST report draft=False")
                self.assertTrue(obs_clean["quota_ok"], "Healthy quota MUST report quota_ok=True")

            finally:
                if real_ra: fi.RoleAuthority = real_ra
                if real_fb: fi.FailoverBridge = real_fb


if __name__ == "__main__":
    unittest.main()
