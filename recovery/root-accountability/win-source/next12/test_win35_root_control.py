"""Fixed consumer profile, Berlin trigger and uncertain replay boundaries."""
import json
import pathlib
import sys
import unittest
import tempfile
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/"scripts"/"recovery"))
import win35_root_control as control

class ControlTests(unittest.TestCase):
    def test_profile_is_fixed_not_caller_selected(self):
        owner = dict(project="fixture", role="root", actor="A", generation="g1", epoch=1)
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(control, "load_private_profile", return_value=dict(owner=owner, actor="A", generation="g1", state_dir=directory)) as read, mock.patch.object(control, "request", return_value={"status": "ok"}):
            self.assertFalse(control.run("Status")["root_running"])
        read.assert_called_once_with(control.PROFILE)
        with mock.patch.object(sys, "argv", ["control", "Status", "--profile", "attacker"]):
            with self.assertRaises(SystemExit) as denial:
                control.main()
        self.assertEqual(denial.exception.code, 2)

    def test_daily_berlin_slot_distinct_and_due(self):
        for mode, minute in (("Standup", 0), ("Writeup", 30)):
            result = mock.Mock(stdout=json.dumps(dict(date="2026-10-25", hour=9, minute=minute)))
            with mock.patch.object(control.subprocess, "run", return_value=result):
                self.assertEqual(control.scheduled_slot(mode), mode + ":2026-10-25")
            result.stdout = json.dumps(dict(date="2026-10-25", hour=8, minute=minute))
            with mock.patch.object(control.subprocess, "run", return_value=result):
                with self.assertRaises(RuntimeError):
                    control.scheduled_slot(mode)

    def test_check_slot_same_window(self):
        with mock.patch.object(control.time, "time", return_value=1801):
            self.assertEqual(control.scheduled_slot("Check"), "check:1")

    def test_manual_overdue_ping_keeps_daily_idempotency(self):
        result = mock.Mock(stdout=json.dumps(dict(date="2026-10-25", hour=12, minute=15)))
        with mock.patch.object(control.subprocess, "run", return_value=result):
            self.assertEqual(control.scheduled_slot("Writeup", scheduled=False), "Writeup:2026-10-25")
            self.assertEqual(control.scheduled_slot("Writeup", scheduled=True), "Writeup:2026-10-25")

    def test_successor_reply_cannot_select_another_native_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            native = dict(actor="actual", generation="win32:1:2", root_tag="owned-generation-2")
            control.save(pathlib.Path(directory)/"native-successor.private.json", {"completed":native})
            profile=dict(state_dir=directory, project="fixture")
            with mock.patch.object(control,"save") as write:
                with self.assertRaises(RuntimeError):
                    control.adopt_successor(profile,{},pathlib.Path(directory)/"journal",dict(native,actor="forged",project="fixture",role="root"))
                write.assert_not_called()

    def test_model_ack_uses_owner_bound_actual_thread(self):
        owner=dict(project="fixture",role="root",actor="A",generation="g1",epoch=2)
        with tempfile.TemporaryDirectory() as directory:
            control.save(pathlib.Path(directory)/"root-runtime.json",dict(thread_owner=owner,conversation_id="native-thread"))
            profile=dict(actor="A",generation="g1",state_dir=directory,aplexer_exe='fixture',aplexer_sha256='fixture',root_tag='fixture-tag',workspace='fixture-workspace')
            with mock.patch.object(control,"load_private_profile",return_value=profile), mock.patch.object(control,'recorded_api_custody',return_value=True),mock.patch.object(control,'pin',return_value='fixture'),mock.patch.object(control.subprocess,'check_output',return_value=json.dumps(dict(id='A',tag='fixture-tag',workspace='fixture-workspace'))),mock.patch.object(control,"request",return_value={"result":{"message_id":"actual-receipt"}}) as send:
                self.assertEqual(control.model_ack(),dict(ack_message_id="actual-receipt",thread_id="native-thread"))
                body=send.call_args.args[1]
                self.assertEqual(body["model_thread_id"],"native-thread")
                self.assertEqual(body["actor"],"A")
                self.assertEqual(body["op"],"bus_send")

    def test_reconcile_reuses_exact_existing_request(self):
        import contextlib
        owner=dict(project="fixture",role="root",actor="A",generation="g1",epoch=2)
        with tempfile.TemporaryDirectory() as directory:
            profile=dict(owner=owner,actor="A",generation="g1",state_dir=directory)
            pending=dict(owner,op="execute",operation="root-check",payload={},key="durable-old-key")
            path=pathlib.Path(directory)/"control-journal.private.json"
            control.save(path,dict(owner=owner,pending=pending,counter=17))
            with mock.patch.object(control,"load_private_profile",return_value=profile),mock.patch.object(control,"journal_lock",return_value=contextlib.nullcontext()),mock.patch.object(control,"request",return_value={"v":1,"status":"ok","result":{"receipt":"existing"}}) as send:
                control.run("Reconcile")
                send.assert_called_once_with(profile,pending)
            saved=json.loads(path.read_text())
            self.assertIsNone(saved["pending"])
            self.assertEqual(saved["counter"],17)

    def test_reconcile_unavailable_preserves_existing_key(self):
        import contextlib
        owner=dict(project="fixture",role="root",actor="A",generation="g1",epoch=2)
        with tempfile.TemporaryDirectory() as directory:
            profile=dict(owner=owner,actor="A",generation="g1",state_dir=directory)
            pending=dict(owner,op="execute",operation="root-check",payload={},key="durable-old-key")
            path=pathlib.Path(directory)/"control-journal.private.json"
            control.save(path,dict(owner=owner,pending=pending))
            with mock.patch.object(control,"load_private_profile",return_value=profile),mock.patch.object(control,"journal_lock",return_value=contextlib.nullcontext()),mock.patch.object(control,"request",side_effect=RuntimeError("uncertain")):
                with self.assertRaises(RuntimeError):control.run("Reconcile")
            self.assertEqual(json.loads(path.read_text())["pending"],pending)

    def test_operational_delivery_reads_exact_owner_cid_and_pending_command(self):
        owner=dict(project="fixture",role="root",actor="A",generation="g1",epoch=2)
        with tempfile.TemporaryDirectory() as directory:
            profile=dict(actor="A",generation="g1",state_dir=directory,delivery_contracts={"root-check":"focused report"})
            control.save(pathlib.Path(directory)/"root-runtime.json",dict(thread_owner=owner,conversation_id="actual-cid",pending_ping=dict(owner=owner,key="authority-key",operation="root-check")))
            with mock.patch.object(control,"load_private_profile",return_value=profile),mock.patch.object(control,"request",return_value={"result":{"deliveries":[{"actual_native_receipt":"receipt"}]}}) as send:
                control.model_proxy("Deliver")
                body=send.call_args.args[1]
                self.assertEqual((body["op"],body["action"],body["model_thread_id"],body["ping_kind"]),("bus_send","principal-ping","actual-cid","root-check"))
                first=body["key"]
                control.model_proxy("Deliver")
                self.assertEqual(send.call_args.args[1]["key"],first)
            profile["generation"]="successor"
            with mock.patch.object(control,"load_private_profile",return_value=profile),mock.patch.object(control,"request") as send:
                with self.assertRaises(RuntimeError):control.model_proxy("Deliver")
                send.assert_not_called()
        with mock.patch.object(control.time, "time", return_value=3599):
            self.assertEqual(control.scheduled_slot("Check"), "check:1")

if __name__ == "__main__":
    unittest.main()
