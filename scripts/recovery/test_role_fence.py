"""Hermetic managed sink tests; never elect/kill production actors."""
import concurrent.futures
import tempfile
import threading
import unittest
from pathlib import Path
from coordination.role_failover import Fenced, RoleAuthority
from role_fence import CoordinatorFence, Owner


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = [1000.0]
        self.a = RoleAuthority(Path(self.temp.name) / "roles.db",
                               lambda: self.now[0], boot_id="TEST")
        self.calls = []
        self.owners = {}
        for role in ("root", "principal"):
            self.a.configure("TEST", role, [role + "-old", role + "-new"])
            for suffix, priority in (("old", 0), ("new", 1)):
                self.a.observe(role + "-" + suffix, "TEST", "s1", ready=True,
                               draft=False, quota_ok=True, priority=priority)
            elected = self.a.tick("TEST", role)
            self.owners[role] = Owner("TEST", role, elected["holder"], "s1", 1)
            self.a.activation(*self.owners[role].args(),
                              role_ack="genuine-test-ack", first_action="test-tool")
        self.f = CoordinatorFence(
            self.a, lambda token, owner: token == "test-token",
            {(role, operation): (
                lambda p: isinstance(p, dict) and set(p) == {"target"},
                lambda key, payload, owner: self.calls.append((key, owner, payload))
                or {"state": "queued"})
             for role in ("root", "principal") for operation in ("dispatch", "ping")},
            lambda old, new, evidence: evidence == {"checkpoint": "C", "ack": "A"})

    def execute(self, role="root", operation="ping", key="K", owner=None):
        return self.f.execute("test-token", owner or self.owners[role], key,
                              operation, {"target": "TEST"})

    def test_one_successor_under_concurrency_and_late_wake_both_sinks(self):
        self.now[0] += 181
        for role in ("root", "principal"):
            self.assertEqual(self.a.tick("TEST", role)["state"], "diagnosing")
        self.now[0] += 121
        for role in ("root", "principal"):
            self.a.observe(role + "-new", "TEST", "s1", ready=True,
                           draft=False, quota_ok=True)
            with concurrent.futures.ThreadPoolExecutor(6) as pool:
                results = list(pool.map(lambda _: self.a.tick("TEST", role), range(6)))
            self.assertEqual(sum(r["state"] == "elected" for r in results), 1)
            self.assertEqual({r["epoch"] for r in results}, {2})
            for operation in ("dispatch", "ping"):
                with self.assertRaises(Fenced):
                    self.execute(role, operation, role + operation)
            with self.assertRaises(Fenced):
                self.f.renew("test-token", self.owners[role])
        self.assertEqual(self.calls, [])

    def test_handover_cas_and_activation_gate_are_separate_per_role(self):
        for role in ("root", "principal"):
            old = self.owners[role]
            new = Owner("TEST", role, role + "-new", "s1", 2)
            result = self.f.handback("test-token", old, new,
                                    {"checkpoint": "C", "ack": "A"})
            self.assertEqual(result["activation"], "pending")
            with self.assertRaises(Fenced):
                self.execute(role, owner=old)
            with self.assertRaises(PermissionError):
                self.execute(role, owner=new)
            self.a.activation(*new.args(), role_ack="new-ack", first_action="new-tool")
            self.execute(role, key=role + "-new", owner=new)
            with self.assertRaises(Fenced):
                self.f.handback("test-token", old, new,
                                {"checkpoint": "C", "ack": "A"})
        self.assertEqual(len(self.calls), 2)

    def test_handover_missing_ack_and_unsafe_successor(self):
        old = self.owners["root"]
        new = Owner("TEST", "root", "root-new", "s1", 2)
        with self.assertRaises(PermissionError):
            self.f.handback("test-token", old, new, {"checkpoint": "C"})
        self.a.observe("root-new", "TEST", "s1", ready=True, draft=True, quota_ok=True)
        with self.assertRaises(PermissionError):
            self.f.handback("test-token", old, new, {"checkpoint": "C", "ack": "A"})
        self.assertEqual(self.a.role_state("TEST", "root")["epoch"], 1)

    def test_restart_fences_incarnation_and_authority_reboot(self):
        self.a.observe("root-old", "TEST", "s2", ready=True, draft=False, quota_ok=True)
        with self.assertRaises(Fenced):
            self.execute()
        restarted = RoleAuthority(self.a.path, lambda: self.now[0], boot_id="TEST-REBOOT")
        self.f.authority = restarted
        with self.assertRaises(Fenced):
            self.execute("principal")
        self.assertEqual(self.calls, [])

    def test_partition_does_not_fallback(self):
        class Unreachable:
            def activation(self, *args):
                raise ConnectionError("TEST partition")
        self.f.authority = Unreachable()
        with self.assertRaises(ConnectionError):
            self.execute()
        self.assertEqual(self.calls, [])

    def test_auth_role_operation_and_payload_fail_closed(self):
        with self.assertRaises(PermissionError):
            self.f.execute("wrong", self.owners["root"], "K", "ping", {"target": "TEST"})
        with self.assertRaises(PermissionError):
            self.execute(operation="arbitrary-shell")
        with self.assertRaises(ValueError):
            self.f.execute("test-token", self.owners["root"], "K", "ping", {"argv": []})
        self.assertEqual(self.calls, [])

    def test_sink_is_atomic_against_election_and_deduplicated(self):
        self.execute()
        self.assertEqual(self.execute()["state"], "already_enqueued")
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(Fenced):
            self.execute(operation="dispatch")

    def test_clock_rollback_and_reboot_hold(self):
        self.now[0] -= 1
        with self.assertRaises(Fenced):
            self.execute()
        with self.assertRaises(Fenced):
            RoleAuthority(self.a.path, lambda: self.now[0], boot_id="NEXT")
        self.assertEqual(self.calls, [])

    def test_effect_holds_election_lock_at_sink(self):
        entered, release, elected = threading.Event(), threading.Event(), threading.Event()
        def effect(key, payload, owner):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test lock wait expired")
            return {"state": "queued"}
        self.f.operations[("root", "ping")] = (lambda p: True, effect)
        def contender():
            result = self.a.tick("TEST", "root")
            elected.set()
            return result
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            running = pool.submit(self.execute)
            self.assertTrue(entered.wait(1))
            self.now[0] += 181
            waiting = pool.submit(contender)
            try:
                self.assertFalse(elected.wait(0.1))
            finally:
                release.set()
            self.assertEqual(running.result()["state"], "queued")
            self.assertEqual(waiting.result()["state"], "diagnosing")

    def test_handover_does_not_merge_root_and_principal(self):
        self.a.configure("TEST", "root", ["root-old", "principal-old"])
        successor = Owner("TEST", "root", "principal-old", "s1", 2)
        with self.assertRaises(PermissionError):
            self.f.handback("test-token", self.owners["root"], successor,
                            {"checkpoint": "C", "ack": "A"})
        self.assertEqual(self.a.role_state("TEST", "root")["holder"], "root-old")


if __name__ == "__main__":
    unittest.main()
