"""Isolated enrollment protocol fixtures; never create/kill real model actors."""
import copy
import json
import os
import sqlite3
import unittest
from unittest.mock import patch

import test_role_fence_cli as fixture
from role_fence import Owner
from role_fence_cli import handle, durable_sink
from role_fence_enrollment import enroll_successor, successor_key, reconcile_successors


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture.AdapterTests("runTest")
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.owner = Owner("TEST", "root", "native-A", "session-A", 1)
        self.path = self.base.p / "authority.json"
        self.base.config["tls_clients"] = {"TEST-cert-pin": {"actor": "native-A", "role": "root",
            "project": "TEST", "bus_identity": self.base.request["credential"]["identity_id"]}}
        self.path.write_text(json.dumps(self.base.config))
        os.chmod(self.path, 0o600)
        self.actor = "76b9f3a8-b2ac-43ba-b767-0010cd6ae223"
        old = dict(zip(("project", "role", "actor", "generation", "epoch"), self.owner.args()))
        self.receipt = {"v": 1, "key": successor_key(self.owner), "owner": old,
            "operation": "root-native-successor", "payload": {}, "state": "completed", "evidence": {
                "successor": {"actor": self.actor, "host": "TEST", "generation": "win32:42:123456789",
                    "whoami": {"id": self.actor, "tag": "win35-root-capsule-TEST2"},
                    "root_tag": "win35-root-capsule-TEST2", "kernel": {"pid": 42, "creation_filetime": 123456789},
                    "predecessor_owner": old, "owned_model_exit": {"verified_dead": True, "owner": old}}}}

    def test_enrollment_held_old_actor_readonly_and_private_retry(self):
        self.base.config["operations"].append({"role": "root", "name": "root-native-successor",
            "transport": "native-channel", "timeout": 5, "payload": {}})
        self.path.write_text(json.dumps(self.base.config))
        calls = []
        def native(owner, message, timeout):
            calls.append(message)
            return copy.deepcopy(self.receipt)
        with patch("role_fence_cli.CANONICAL_CONFIG", self.path):
            response = handle(self.base.config, {**self.base.request, "op": "recovery_successor",
                "actor_override": "fake", "successor": {"actor": "fake"}}, native, private_delivery=True)
            config = json.loads(self.path.read_text())
            before_profile = self.path.read_bytes()
            with sqlite3.connect(self.base.a.path) as db:
                before_agents = db.execute("SELECT * FROM agents ORDER BY id").fetchall()
            retry = handle(config, {**self.base.request, "op": "successor_status"}, private_delivery=True)
            self.assertEqual(retry["result"], response["result"])
            self.assertEqual(self.path.read_bytes(), before_profile)
            with sqlite3.connect(self.base.a.path) as db:
                self.assertEqual(db.execute("SELECT * FROM agents ORDER BY id").fetchall(), before_agents)
            with self.assertRaises(PermissionError):
                handle(config, self.base.request, native)
        self.assertEqual(len(calls), 1)
        self.assertTrue(config["bindings"][self.owner.actor]["retired"])
        self.assertEqual(response["result"]["actor"], self.actor)
        self.assertEqual(len(config["tls_clients"]["TEST-cert-pin"]["actors"]), 2)
        with sqlite3.connect(self.base.a.path) as db:
            new = db.execute("SELECT ready,draft,quota,priority FROM agents WHERE id=?", (self.actor,)).fetchone()
            old = db.execute("SELECT ready,draft,quota FROM agents WHERE id='native-A'").fetchone()
        self.assertEqual(new, (0, 1, 0, 0))
        self.assertEqual(old, (0, 1, 0))

    def test_cross_role_actor_collision_preserves_shared_authority_and_bus(self):
        self.base.a.configure("OTHER", "head:product", [self.actor])
        self.base.a.observe(self.actor, "OTHERHOST", "other-incarnation", ready=True, draft=False, quota_ok=True, priority=7)
        before_profile = self.path.read_bytes()
        before_bus = self.base.bus._read(self.base.bus._identities, {})
        with self.assertRaises(PermissionError):
            enroll_successor(self.path, self.base.a, self.owner, self.receipt)
        self.assertEqual(self.path.read_bytes(), before_profile)
        self.assertEqual(self.base.bus._read(self.base.bus._identities, {}), before_bus)
        with sqlite3.connect(self.base.a.path) as db:
            row = db.execute("SELECT host,generation,ready,priority FROM agents WHERE id=?", (self.actor,)).fetchone()
        self.assertEqual(row, ("OTHERHOST", "other-incarnation", 1, 7))

    def test_generic_cli_transport_cannot_export_successor_credential(self):
        with self.assertRaises(PermissionError):
            handle(self.base.config, {**self.base.request, "op": "recovery_successor", "private_delivery": True})

    def test_recorded_reconciliation_preserves_foreign_holder_without_agent_row(self):
        intent = {k: self.receipt[k] for k in ("v", "key", "owner", "operation", "payload")}
        durable_sink(self.base.config["sink_journal"], successor_key(self.owner), intent, lambda: self.receipt)
        with sqlite3.connect(self.base.a.path) as db:
            db.execute("CREATE TRIGGER crash_successor BEFORE INSERT ON agents WHEN NEW.id='" + self.actor + "' BEGIN SELECT RAISE(ABORT,'TEST crash'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            enroll_successor(self.path, self.base.a, self.owner, self.receipt)
        self.base.a.configure("OTHER", "principal", [])
        with sqlite3.connect(self.base.a.path) as db:
            db.execute("DROP TRIGGER crash_successor")
            db.execute("UPDATE roles SET holder=?,generation='OTHER-incarnation',epoch=1 WHERE project='OTHER' AND role='principal'", (self.actor,))
            before = {table: db.execute("SELECT * FROM " + table).fetchall() for table in ("roles", "agents", "candidates")}
        before_profile = self.path.read_bytes()
        before_bus = self.base.bus._read(self.base.bus._identities, {})
        with self.assertRaises(PermissionError):
            reconcile_successors(self.path, self.base.a)
        self.assertEqual(self.path.read_bytes(), before_profile)
        self.assertEqual(self.base.bus._read(self.base.bus._identities, {}), before_bus)
        with sqlite3.connect(self.base.a.path) as db:
            after = {table: db.execute("SELECT * FROM " + table).fetchall() for table in ("roles", "agents", "candidates")}
        self.assertEqual(after, before)

    def test_wrong_whoami_kernel_host_or_death_never_enrolls(self):
        for field, bad in (("actor", self.owner.actor), ("host", "other-host"),
                           ("generation", "caller-random"), ("whoami", {"id": "other"}),
                           ("owned_model_exit", {"verified_dead": False})):
            receipt = copy.deepcopy(self.receipt)
            receipt["evidence"]["successor"][field] = bad
            with self.assertRaises((PermissionError, ValueError)):
                enroll_successor(self.path, self.base.a, self.owner, receipt)
        self.assertNotIn(self.actor, json.loads(self.path.read_text())["bindings"])

    def test_profile_survives_authority_commit_crash_no_duplicate_registration(self):
        intent = {k: self.receipt[k] for k in ("v", "key", "owner", "operation", "payload")}
        durable_sink(self.base.config["sink_journal"], successor_key(self.owner), intent, lambda: self.receipt)
        with sqlite3.connect(self.base.a.path) as db:
            db.execute("CREATE TRIGGER crash_successor BEFORE INSERT ON agents WHEN NEW.id='" + self.actor + "' BEGIN SELECT RAISE(ABORT,'TEST crash'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            enroll_successor(self.path, self.base.a, self.owner, self.receipt)
        identities_before = self.base.bus._read(self.base.bus._identities, {})
        config = json.loads(self.path.read_text())
        pending = handle(config, {**self.base.request, "op": "successor_status"}, private_delivery=True)
        self.assertEqual(pending["status"], "pending")
        self.assertNotIn("credential", pending["result"])
        with sqlite3.connect(self.base.a.path) as db:
            db.execute("DROP TRIGGER crash_successor")
        reconcile_successors(self.path, self.base.a)
        recovered = json.loads(self.path.read_text())["successors"][successor_key(self.owner)]
        self.assertEqual(self.base.bus._read(self.base.bus._identities, {}), identities_before)
        self.assertEqual(recovered["actor"], self.actor)
        with sqlite3.connect(self.base.a.path) as db:
            self.assertEqual(db.execute("SELECT ready,draft,quota FROM agents WHERE id=?", (self.actor,)).fetchone(), (0, 1, 0))


if __name__ == "__main__":
    unittest.main()
