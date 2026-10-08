import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from coordination.bus import FileBus
from coordination.role_failover import RoleAuthority, Fenced
import coordination.role_failover as dependency
import coordination.bus as bus_dependency
from role_fence import CoordinatorFence, Owner
from role_fence_cli import handle, durable_sink


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        self.bus = FileBus(self.p / "bus")
        identity, token = self.bus.register(agent_name="TEST-root", device_id="TEST", project_id="TEST")
        self.controller, self.controller_token = self.bus.register(agent_name="TEST-authority", device_id="TEST", project_id="TEST")
        self.a = RoleAuthority(self.p / "roles.db")
        self.a.configure("TEST", "root", ["native-A", "native-B"])
        self.a.observe("native-A", "TEST", "session-A", ready=True, draft=False, quota_ok=True, priority=0)
        self.a.observe("native-B", "TEST", "session-B", ready=True, draft=False, quota_ok=True, priority=1)
        self.a.tick("TEST", "root")
        self.a.activation("TEST", "root", "native-A", "session-A", 1, role_ack="fixture-ack", first_action="fixture-tool")
        self.count = self.p / "count"
        helper = self.p / "sink.py"
        helper.write_text("import json,sys,pathlib\nr=json.load(sys.stdin)\np=pathlib.Path(sys.argv[1])\np.write_text(str(int(p.read_text())+1) if p.exists() else '1')\nprint(json.dumps({'key':r['key'],'state':'queued'}))\n")
        journal = self.p / "sinks.db"
        journal.touch(mode=0o600)
        executable = Path(sys.executable).resolve()
        self.config = {
            "authority_source": str(Path(dependency.__file__).resolve()),
            "authority_sha256": sha(dependency.__file__),
            "bus_source": str(Path(bus_dependency.__file__).resolve()), "bus_sha256": sha(bus_dependency.__file__),
            "authority_db": self.a.path, "bus_store": str(self.bus.root),
            "sink_journal": str(journal),
            "control_bus_identity": self.controller.identity_id,
            "bindings": {"native-A": {"project": "TEST", "role": "root",
                         "generation": "session-A", "host": "TEST", "bus_identity": identity.identity_id}},
            "operations": [{"role": "root", "name": "root-ping",
                "argv": [str(executable), str(helper), str(self.count)],
                "executable_sha256": sha(executable), "file_pins": {str(helper): sha(helper)},
                "idempotency_contract": "key-durable-v1", "timeout": 5, "payload": {"target": "TEST"}}]}
        self.request = {"v": 1, "op": "execute", "project": "TEST", "role": "root",
            "actor": "native-A", "generation": "session-A", "epoch": 1,
            "credential": {"identity_id": identity.identity_id, "token": token},
            "key": "TEST-ping", "operation": "root-ping", "payload": {"target": "TEST"}}

    def test_activation_requires_real_guarded_action_and_authentic_ack(self):
        # New epoch has no activation receipts; cannot fabricate them in request.
        self.a = RoleAuthority(self.a.path)
        with sqlite3.connect(self.a.path) as db:
            db.execute("DELETE FROM activation_receipts")
        with self.assertRaises(PermissionError):
            handle(self.config, self.request)
        req = {**self.request, "op": "activate", "ack_message": "invented",
               "first_action_key": "invented", "model_evidence_key": "invented", "quota_ok": True}
        with self.assertRaises(PermissionError):
            handle(self.config, req)
        self.assertFalse(self.count.exists())

    def test_authentic_bus_ack_and_native_fence_activation_receipt(self):
        with sqlite3.connect(self.a.path) as db:
            db.execute("DELETE FROM activation_receipts")
        operation = self.config["operations"][0]
        helper = Path(operation["argv"][1])
        helper.write_text("import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({'v':1,'key':r['key'],'state':'completed','evidence':{'fence_activation':r['owner']}}))\n")
        operation.update(name="root-fence-activate", first_action=True,
                         file_pins={str(helper): sha(helper)})
        result = handle(self.config, {**self.request, "op": "first_action",
                                      "operation": "root-fence-activate"})
        data = {"action": "role-ack", "model_thread_id": "TEST-CID", **{k: self.request[k] for k in (
            "project", "role", "actor", "generation", "epoch")}}
        message = self.bus.send(sender_id=self.request["credential"]["identity_id"],
            token=self.request["credential"]["token"], recipient_id=self.controller.identity_id,
            body="TEST fixture semantic root custody accepted", data=data, kind="role-control")
        activation_request = {**self.request, "op": "activate", "ack_message": message.message_id,
            "first_action_key": result["result"]["first_action_key"], "model_evidence_key": "actual-model-tool"}
        with self.assertRaises(PermissionError):
            handle(self.config, activation_request)  # Native capsule alone is not model custody.
        from datetime import datetime, timezone
        model = {"native_actor": "native-A", "thread_id": "TEST-CID", "first_tool": {
            "event_id": "TEST-provider-event", "exit_code": 0, "ack_message_id": message.message_id,
            "completed_at": datetime.now(timezone.utc).isoformat()}}
        helper.write_text("import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({'v':1,'key':r['key'],'state':'completed','evidence':{'model':" + repr(model) + "}}))\n")
        model_operation = {**operation, "name": "root-model-evidence", "first_action": False,
            "file_pins": {str(helper): sha(helper)}}
        self.config["operations"] = [model_operation]
        handle(self.config, {**self.request, "op": "model_evidence", "key": "actual-model-tool"})
        activated = handle(self.config, activation_request)
        self.assertEqual(activated["result"]["role_ack"], message.message_id)

    def test_authenticated_checkpoint_successor_ack_and_handback_cas(self):
        successor, successor_token = self.bus.register(agent_name="TEST-successor", device_id="TEST", project_id="TEST")
        self.config["bindings"]["native-B"] = {"project": "TEST", "role": "root",
            "generation": "session-B", "host": "TEST", "bus_identity": successor.identity_id}
        new = {"project": "TEST", "role": "root", "actor": "native-B", "generation": "session-B", "epoch": 2}
        old = {k: self.request[k] for k in ("project", "role", "actor", "generation", "epoch")}
        credential = self.request["credential"]
        checkpoint = self.bus.send(sender_id=credential["identity_id"], token=credential["token"],
            recipient_id=self.controller.identity_id, body="TEST actor checkpoint", data={"action": "handover-checkpoint", **old}, kind="role-control")
        wrong_ack = self.bus.send(sender_id=credential["identity_id"], token=credential["token"],
            recipient_id=self.controller.identity_id, body="wrong sender", data={"action": "handover-ack", **new}, kind="role-control")
        request = {**self.request, "op": "handback", "successor": new,
                   "evidence": {"checkpoint": checkpoint.message_id, "ack": wrong_ack.message_id}}
        with self.assertRaises(PermissionError):
            handle(self.config, request)
        ack = self.bus.send(sender_id=successor.identity_id, token=successor_token,
            recipient_id=self.controller.identity_id, body="TEST successor custody ACK",
            data={"action": "handover-ack", **new}, kind="role-control")
        request["evidence"]["ack"] = ack.message_id
        request["evidence"]["raw_log"] = "must never persist"
        self.assertEqual(handle(self.config, request)["result"]["epoch"], 2)
        self.assertNotIn("raw_log", self.a.events()[-1]["payload"])
        with self.assertRaises(Fenced):
            handle(self.config, request)

    def test_semantic_receipt_recipient_kind_and_freshness(self):
        from role_fence_cli import build
        credential = self.request["credential"]
        owner = Owner("TEST", "root", "native-A", "session-A", 1)
        data = {"action": "handover-checkpoint", **dict(zip(
            ("project", "role", "actor", "generation", "epoch"), owner.args()))}
        message = self.bus.send(sender_id=credential["identity_id"], token=credential["token"],
            recipient_id=self.controller.identity_id, body="TEST semantic checkpoint", data=data, kind="role-control")
        authority, fence = build(self.config)
        self.assertTrue(fence.semantic_message(message.message_id, owner, "handover-checkpoint"))
        original = self.bus._read(self.bus._messages, {})
        for field, bad in (("recipient_id", credential["identity_id"]), ("kind", "note"),
                           ("created_at", "2000-01-01T00:00:00Z")):
            records = copy.deepcopy(original)
            records[message.message_id][field] = bad
            self.bus._write(self.bus._messages, records)
            self.assertFalse(fence.semantic_message(message.message_id, owner, "handover-checkpoint"))

    def test_own_identity_model_ack_uses_fixed_control_recipient(self):
        request = {**self.request, "op": "bus_send", "action": "role-ack",
            "model_thread_id": "TEST-CID", "body": "TEST model owns this role", "key": "TEST-ACK",
            "recipient_id": "caller-cannot-choose-recipient"}
        result = handle(self.config, request)
        messages = self.bus.inbox(self.controller.identity_id, self.controller_token)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_id, result["result"]["message_id"])
        self.assertEqual(messages[0].data["model_thread_id"], "TEST-CID")
        self.assertEqual(messages[0].kind, "role-control")
        self.assertEqual(handle(self.config, {**self.request, "op": "bus_inbox"})["result"]["messages"], [])
        with self.assertRaises(PermissionError):
            handle(self.config, {**request, "action": "arbitrary-dispatch"})

    def test_real_fixed_sink_and_durable_receipt(self):
        self.assertEqual(handle(self.config, self.request)["status"], "ok")
        self.assertEqual(handle(self.config, self.request)["result"]["state"], "already_enqueued")
        self.assertEqual(self.count.read_text(), "1")

    def test_external_effect_then_authority_transaction_crash_retry(self):
        with sqlite3.connect(self.a.path) as db:
            db.execute("CREATE TRIGGER test_crash BEFORE INSERT ON actions BEGIN SELECT RAISE(ABORT,'TEST'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            handle(self.config, self.request)
        self.assertEqual(self.count.read_text(), "1")
        with sqlite3.connect(self.a.path) as db:
            db.execute("DROP TRIGGER test_crash")
        self.assertEqual(handle(self.config, self.request)["status"], "ok")
        self.assertEqual(self.count.read_text(), "1")

    def test_crash_between_effect_and_sink_receipt_stays_uncertain(self):
        calls = []
        def effect():
            calls.append("actual mutation")
            raise SystemExit("TEST process death before receipt")
        with self.assertRaises(SystemExit):
            durable_sink(self.config["sink_journal"], "crash", {"intent": 1}, effect)
        result = durable_sink(self.config["sink_journal"], "crash", {"intent": 1}, effect)
        self.assertEqual(result["state"], "uncertain")
        self.assertEqual(calls, ["actual mutation"])

    def test_queued_old_request_rechecks_at_final_native_sink(self):
        queued = copy.deepcopy(self.request)  # Captured while A was valid.
        fence = CoordinatorFence(self.a, lambda *_: True, {}, lambda *_: True)
        fence.handback(None, Owner("TEST", "root", "native-A", "session-A", 1),
                       Owner("TEST", "root", "native-B", "session-B", 2), {"checkpoint": "TEST-C", "ack": "TEST-A"})
        with self.assertRaises(Fenced):
            handle(self.config, queued)
        self.assertFalse(self.count.exists())

    def test_untrusted_identity_eligibility_and_commands_cannot_override(self):
        for replacement in ({"actor": "native-B"}, {"generation": "invented"},
                            {"credential": {"identity_id": "unknown", "token": "unknown"}},
                            {"payload": {"argv": ["touch", str(self.count)], "quota_ok": True}},
                            {"operation": "arbitrary-shell"}):
            request = {**self.request, **replacement}
            with self.assertRaises((PermissionError, ValueError)):
                handle(self.config, request)
        request = {**self.request, "argv": ["touch", "untrusted"],
                   "authority_db": "/untrusted", "ready": True, "quota_ok": True}
        handle(self.config, request)  # Extra request fields cannot override trusted config.
        self.assertEqual(self.count.read_text(), "1")

    def test_missing_authority_never_creates_local_fallback(self):
        self.config["authority_db"] = str(self.p / "absent.db")
        with self.assertRaises(PermissionError):
            handle(self.config, self.request)
        self.assertFalse((self.p / "absent.db").exists())


if __name__ == "__main__":
    unittest.main()
