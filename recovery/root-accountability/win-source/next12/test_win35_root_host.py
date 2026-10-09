"""Simulation tests only. No fixture is real enrollment or model execution."""
import json
import multiprocessing
import os
import io
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/"scripts"/"recovery"))
import win35_root_host as host
import win35_root_sink as sink
import win35_root_rpc as rpc_module
import win35_root_job as job_module

def paused_process_callback(profile, command, ready, release, results):
    runtime = host.RootRuntime(profile, {"id": "fixture-A"}, smoke_only=False)
    runtime.final_guard = mock.Mock()
    runtime.launch_native = mock.Mock(side_effect=AssertionError("old native mutation reached"))
    ready.set()
    release.wait(10)
    try:
        runtime.execute(command)
        results.put("unexpected-success")
    except Exception as exc:
        results.put(type(exc).__name__ + ":" + str(exc))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        directory = pathlib.Path(self.temp.name)
        prompt = directory / "prompt"
        prompt.write_text("Fixture only")
        self.profile = dict(state_dir=str(directory), project="fixture", actor="fixture-A", generation="fixture-g1",
                            admission_script="fixed-gate", admission_script_sha256="pin",
                            python_exe="fixed-python", admission_profile="fixed-private-profile",
                            python_sha256="pin",
                            codex_exe="fixed-codex", codex_sha256="pin", root_prompt=str(prompt), workspace=str(directory))
        self.runtime = host.RootRuntime(self.profile, {"id": "fixture-A"}, smoke_only=False)
        self.runtime.final_guard = mock.Mock()
        self.runtime.fresh_admission = mock.Mock(return_value=(True, {}))
        self.admission = mock.patch.object(host, "WindowsJob")
        job = self.admission.start().return_value
        job.start.return_value.wait.return_value = 0

    def tearDown(self):
        self.admission.stop()
        self.temp.cleanup()

    def command(self, operation, epoch=1, generation="fixture-g1", key=None, payload=None):
        return {"v": 1, "key": key or operation + ":" + generation, "operation": operation,
                "owner": {"project": "fixture", "role": "root", "actor": "fixture-A", "generation": generation, "epoch": epoch},
                "payload": payload or {}, "deadline": time.time() + 45}

    def activate(self):
        return self.runtime.execute(self.command("root-fence-activate"))

    def test_no_activation_denies_dispatch(self):
        with mock.patch.object(host.subprocess, "Popen") as launch:
            with self.assertRaises(RuntimeError):
                self.runtime.execute(self.command("root-start"))
        launch.assert_not_called()

    def test_caller_cannot_override_private_admission_profile(self):
        self.activate()
        command = self.command("root-start", payload={"admission_profile": "attacker-file"})
        with mock.patch.object(host.subprocess, "Popen") as launch:
            with self.assertRaises(ValueError):
                self.runtime.execute(command)
        launch.assert_not_called()

    def test_authority_outage_denies_native_effect(self):
        self.activate()
        self.runtime.final_guard.side_effect = OSError("fixture partition")
        with mock.patch.object(host, "pin", side_effect=lambda p, h: p), mock.patch.object(host.subprocess, "run"), mock.patch.object(host.subprocess, "Popen") as launch:
            with self.assertRaises(OSError):
                self.runtime.execute(self.command("root-start"))
        launch.assert_not_called()

    def test_expired_already_delivered_command_denies_before_mutation(self):
        self.activate()
        command = self.command("root-start")
        command["deadline"] = time.time() - 1
        with mock.patch.object(host.subprocess, "Popen") as launch:
            with self.assertRaises(RuntimeError):
                self.runtime.execute(command)
        launch.assert_not_called()

    def test_pause_after_proof_blocks_native_generation_takeover(self):
        self.activate()
        paused = threading.Event()
        release = threading.Event()
        failures = []
        child = mock.Mock(pid=1234)
        child.creation_filetime = 123456
        child.poll.return_value = None

        def delayed_launch(*args, **kwargs):
            paused.set()
            if not release.wait(5):
                raise TimeoutError("fixture release")
            return child

        def run_old():
            try:
                self.runtime.execute(self.command("root-start"))
            except Exception as exc:
                failures.append(exc)

        next_profile = dict(self.profile, generation="fixture-g2")
        successor = host.RootRuntime(next_profile, {"id": "fixture-A"}, smoke_only=False)
        successor.final_guard = mock.Mock()
        with mock.patch.object(host, "pin", side_effect=lambda p, h: p), mock.patch.object(host.subprocess, "run"), mock.patch.object(self.runtime, "launch_native", side_effect=delayed_launch):
            thread = threading.Thread(target=run_old)
            thread.start()
            self.assertTrue(paused.wait(5))
            try:
                with self.assertRaises(OSError):
                    successor.execute(self.command("root-fence-activate", epoch=2, generation="fixture-g2"))
            finally:
                release.set()
                thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertFalse(failures)
        successor.protected_draft = mock.Mock(return_value=False)
        with mock.patch.object(host, "drain_recorded_job", return_value={"active_processes": 0}) as drain:
            receipt = successor.execute(self.command("root-fence-activate", epoch=2, generation="fixture-g2"))
        drain.assert_called_once()
        self.assertEqual(receipt["evidence"]["fence_activation"]["epoch"], 2)
        with self.assertRaises(RuntimeError):
            self.runtime.execute(self.command("root-start"))

    def test_exact_owned_root_handle_required_for_kill(self):
        self.activate()
        child = mock.Mock(pid=1234)
        child.creation_filetime = 123456
        child.poll.return_value = None
        self.runtime.process = child
        self.runtime.frontend = child
        self.runtime.viewer = child
        state_path = pathlib.Path(self.profile["state_dir"]) / "root-runtime.json"
        state = json.loads(state_path.read_text())
        state["launched_epoch"] = 1
        state["model_launch_complete"] = True
        state.update(pid=1234, process_creation_filetime=123456)
        host.save(state_path, state)
        self.runtime.job = mock.Mock()
        self.runtime.job.wait_empty.return_value = {"active_processes": 0, "source": "QueryInformationJobObject"}
        self.runtime.protected_draft = mock.Mock(return_value=False)
        with self.assertRaises(ValueError):
            self.runtime.execute(self.command("root-test-kill", payload={"target_pid": 9999}))
        child.kill.assert_not_called()
        self.runtime.execute(self.command("root-test-kill", key="correct-kill"))
        child.kill.assert_called_once()
        child.wait.assert_called_once()

    def killed_runtime(self):
        self.activate()
        child = mock.Mock(pid=1234, creation_filetime=123456)
        child.poll.return_value = None
        self.runtime.process = self.runtime.frontend = self.runtime.viewer = child
        state_path = pathlib.Path(self.profile["state_dir"]) / "root-runtime.json"
        state = json.loads(state_path.read_text())
        state.update(launched_epoch=1, model_launch_complete=True, pid=1234, process_creation_filetime=123456)
        host.save(state_path, state)
        self.runtime.job = mock.Mock()
        self.runtime.job.wait_empty.return_value = {"active_processes": 0, "source": "QueryInformationJobObject"}
        self.runtime.protected_draft = mock.Mock(return_value=False)
        self.runtime.execute(self.command("root-test-kill", key="owned-kill"))
        child.poll.return_value = 0
        return child, state_path

    def test_kill_then_successor_reuses_exact_completed_drain(self):
        child, _ = self.killed_runtime()
        with mock.patch.object(host, "recorded_process_state", return_value="exited"), mock.patch.object(self.runtime, "native_successor", return_value={"actor": "fixture-successor"}) as factory:
            receipt = self.runtime.execute(self.command("root-native-successor", key="after-kill"))
        factory.assert_called_once()
        self.assertEqual(receipt["evidence"]["successor"]["actor"], "fixture-successor")
        child.kill.assert_called_once()
        self.assertIsNone(self.runtime.process)

    def test_successor_denies_wrong_drain_or_unknown_death(self):
        _, state_path = self.killed_runtime()
        original = json.loads(state_path.read_text())
        for wrong_owner, process_state in ((True, "exited"), (False, "unknown")):
            state = json.loads(json.dumps(original))
            if wrong_owner:
                state["last_model_exit"]["owner"]["epoch"] = 999
            host.save(state_path, state)
            with mock.patch.object(host, "recorded_process_state", return_value=process_state), mock.patch.object(self.runtime, "native_successor") as factory:
                with self.assertRaisesRegex(RuntimeError, "exact completed drain"):
                    self.runtime.execute(self.command("root-native-successor", key="held-successor"))
            factory.assert_not_called()

    def test_crash_after_process_state_before_receipt_denies_duplicate(self):
        self.activate()
        state_path = pathlib.Path(self.profile["state_dir"]) / "root-runtime.json"
        state = json.loads(state_path.read_text())
        state.update(pid=1234, launched_epoch=1, launch_pending=None)
        host.save(state_path, state)
        restarted = host.RootRuntime(self.profile, {"id": "fixture-A"}, smoke_only=False)
        restarted.final_guard = mock.Mock()
        with mock.patch.object(host.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(RuntimeError, "uncertain launch"):
                restarted.execute(self.command("root-recover", key="new-recovery-key"))
        launch.assert_not_called()
        restarted.final_guard.assert_not_called()

    def test_pause_before_action_lock_then_takeover_denies_old_effect(self):
        self.activate()
        old = self.command("root-start")
        paused, release = threading.Event(), threading.Event()
        failures = []
        def delayed_callback():
            paused.set()
            release.wait(5)
            try:
                self.runtime.execute(old)
            except Exception as exc:
                failures.append(exc)
        thread = threading.Thread(target=delayed_callback)
        thread.start()
        self.assertTrue(paused.wait(5))
        successor = host.RootRuntime(dict(self.profile, generation="fixture-g2"), {"id": "fixture-A"}, smoke_only=False)
        successor.final_guard = mock.Mock()
        successor.execute(self.command("root-fence-activate", epoch=2, generation="fixture-g2"))
        with mock.patch.object(host.subprocess, "Popen") as launch:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIn("stale epoch", str(failures[0]))
        launch.assert_not_called()

    def test_wall_clock_rollback_fails_closed(self):
        command = self.command("root-status")
        self.runtime.check_deadline(command)
        with mock.patch.object(host.time, "time", return_value=time.time() - 30):
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                self.runtime.check_deadline(command)

    def test_monotonic_expiry_cannot_be_extended(self):
        command = self.command("root-status")
        self.runtime.check_deadline(command)
        with mock.patch.object(host.time, "monotonic", return_value=time.monotonic() + 90):
            with self.assertRaisesRegex(RuntimeError, "monotonic"):
                self.runtime.check_deadline(command)

    @unittest.skipUnless(os.name == "nt", "actual Windows process/lock test")
    def test_cross_process_delayed_old_callback_denied_after_takeover(self):
        self.activate()
        context = multiprocessing.get_context("spawn")
        ready, release, results = context.Event(), context.Event(), context.Queue()
        child = context.Process(target=paused_process_callback, args=(self.profile, self.command("root-start"), ready, release, results))
        child.start()
        try:
            self.assertTrue(ready.wait(10))
            successor = host.RootRuntime(dict(self.profile, generation="fixture-g2"), {"id": "fixture-A"}, smoke_only=False)
            successor.final_guard = mock.Mock()
            successor.execute(self.command("root-fence-activate", epoch=2, generation="fixture-g2"))
            release.set()
            child.join(10)
            self.assertFalse(child.is_alive())
            self.assertEqual(child.exitcode, 0)
            self.assertIn("stale epoch", results.get(timeout=2))
        finally:
            release.set()
            child.join(10)
            if child.is_alive():
                child.terminate(); child.join(5)  # Exact fixture child only.

    def test_partial_backend_launch_not_reported_healthy(self):
        self.activate()
        owned_job = mock.Mock()
        def partial(*args):
            self.runtime.job = owned_job
            self.runtime.process = mock.Mock(pid=1234)
            self.runtime.process.poll.return_value = None
            raise RuntimeError("fixture missing native thread/frontend")
        with mock.patch.object(host, "pin", side_effect=lambda p, h: p), mock.patch.object(host.subprocess, "run"), mock.patch.object(self.runtime, "launch_native", side_effect=partial):
            with self.assertRaises(RuntimeError):
                self.runtime.execute(self.command("root-start"))
        owned_job.kill.assert_called_once()
        owned_job.close.assert_called_once()
        status = self.runtime.execute(self.command("root-status"))
        self.assertNotEqual(status["evidence"]["running"], True)
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            self.runtime.execute(self.command("root-recover"))

    def test_native_thread_binding_rejects_hostile_or_missing_fields(self):
        good = dict(id="fixture-thread", sessionId="fixture-session", modelProvider="openai", cwd=self.profile["workspace"])
        host.validate_thread_binding(good, self.profile["workspace"], "fixture-thread")
        for field, value in (("id", "other"), ("sessionId", None), ("modelProvider", "apikey"), ("cwd", "unrelated-workspace")):
            with self.assertRaises(RuntimeError):
                host.validate_thread_binding(dict(good, **{field: value}), self.profile["workspace"], "fixture-thread")

    def test_host_cli_cannot_select_profile(self):
        with mock.patch.object(sys, "argv", ["host", "--profile", "untrusted"]), mock.patch.object(host, "load_private_profile") as read:
            with self.assertRaises(SystemExit) as denial:
                host.main()
        self.assertEqual(denial.exception.code, 2)
        read.assert_not_called()

    def test_foreign_backend_socket_gets_no_capability_token(self):
        connection = mock.Mock()
        connection.makefile.return_value = io.BytesIO()
        owner = mock.Mock(side_effect=RuntimeError("foreign listener"))
        with mock.patch.object(rpc_module.socket, "create_connection", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "foreign listener"):
                rpc_module.AppServerRPC("ws://127.0.0.1:8803", "fixture-private-token", owner)
        connection.sendall.assert_not_called()
        connection.close.assert_called_once()

    def test_hostile_websocket_accept_cannot_supply_thread_binding(self):
        connection = mock.Mock()
        connection.makefile.return_value = io.BytesIO(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nSec-WebSocket-Accept: hostile\r\n\r\n")
        with mock.patch.object(rpc_module.socket, "create_connection", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "handshake"):
                rpc_module.AppServerRPC("ws://127.0.0.1:8803", "fixture-private-token", mock.Mock())
        connection.close.assert_called_once()

    def test_accepted_socket_foreign_pid_or_query_failure_denied(self):
        backend = mock.Mock(pid=1234)
        backend.poll.return_value = None
        connection = mock.Mock()
        connection.getsockname.return_value = ("127.0.0.1", 45678)
        with mock.patch.object(job_module.subprocess, "run", return_value=mock.Mock(stdout="[9999]")):
            with self.assertRaises(RuntimeError):
                job_module.verify_backend_connection(connection, backend)

    def test_model_evidence_only_actual_completed_matching_tool(self):
        output={"thread_id":"fixture-CID","ack_message_id":"actual-Bus-receipt"}
        state = {"conversation_id": "fixture-CID", "thread_owner": self.command("root-start")["owner"],
                 "instruction_reads":{"required-read":"provider-read-item"},
                 "native_ack_calls":{"native-item":{"output":output,"helper_exit_code":0,"helper_kernel":{"pid":123,"creation_filetime":456}}}}
        item = dict(id="native-item", type="dynamicToolCall", status="completed", success=True,tool="root_role_ack",arguments={"accept_custody":True},
                    contentItems=[{"type":"inputText","text":json.dumps(output,sort_keys=True)}])
        event = {"method": "item/completed", "params": {"threadId": "fixture-CID", "item": item}}
        path = pathlib.Path(self.profile["state_dir"]) / "model-evidence.private.json"
        for wrong in ({"method": "thread/started"}, {"params": {"threadId": "another-CID", "item": item}},
                      {"params": {"threadId": "fixture-CID", "item": dict(item, success=False)}},
                      {"params": {"threadId": "fixture-CID", "item": dict(item, tool="echo fabricated evidence")}}):
            host.record_model_event(self.profile, dict(state), dict(event, **wrong))
            self.assertFalse(path.exists())
        host.record_model_event(self.profile, state, event)
        proof = json.loads(path.read_text())
        self.assertEqual(proof["model"]["first_tool"]["event_id"], "native-item")
        self.assertEqual(proof["model"]["completion_time_source"], "native-item-completed-receipt")
        self.assertEqual(proof["model"]["event_type"],"dynamicToolCall")

    def test_smoke_ack_rejects_without_instruction_reads_or_other_thread(self):
        self.profile["instruction_read_files"]=[{"path":"required-read","sha256":"fixture"}]
        state=dict(conversation_id="actual-cid",thread_owner=self.command("root-start")["owner"])
        request={"method":"item/tool/call","params":{"threadId":"actual-cid","callId":"actual-provider-call","tool":"root_role_ack","arguments":{"accept_custody":True}}}
        self.runtime.job=mock.Mock()
        with self.assertRaises(RuntimeError):self.runtime.model_tool(state,request)
        self.runtime.job.start.assert_not_called()
        state["instruction_reads"]={"required-read":"provider-item"}
        request["params"]["threadId"]="another-cid"
        with self.assertRaises(RuntimeError):self.runtime.model_tool(state,request)
        self.runtime.job.start.assert_not_called()

    def test_instruction_read_allowed_but_unapproved_command_blocks_ack(self):
        self.profile["instruction_read_files"]=[{"path":"required-read","sha256":"fixture"}]
        state=dict(conversation_id="actual-cid")
        event={"method":"item/completed","params":{"threadId":"actual-cid","item":{"id":"read-item","type":"commandExecution","status":"completed","exitCode":0,"command":"required-read"}}}
        host.record_model_event(self.profile,state,event)
        self.assertEqual(state["unapproved_smoke_tool"],"read-item")
        event["params"]["item"]["command"]="mutate-or-unapproved"
        host.record_model_event(self.profile,state,event)
        self.assertEqual(state["unapproved_smoke_tool"],"read-item")

    def test_readonly_admission_without_lease_and_unknown_draft_hold(self):
        self.runtime.protected_draft = mock.Mock(return_value=False)
        receipt = self.runtime.execute(self.command("root-admission"))
        self.assertTrue(receipt["evidence"]["admission"]["quota_ok"])
        self.runtime.final_guard.assert_not_called()
        self.runtime.protected_draft.side_effect = RuntimeError("unknown composer")
        with self.assertRaises(RuntimeError):
            self.runtime.execute(self.command("root-admission", key="unknown-draft"))

    def test_native_smoke_capabilities_fail_closed_on_inventory_or_enabled_tools(self):
        profile={"smoke_mcp_servers":["actual_server"]}
        config={"web_search":"disabled","mcp_servers":{"actual_server":{"enabled":False}},"features":{feature:False for feature in host.SMOKE_DISABLED_FEATURES}}
        status={"data":[],"nextCursor":None}
        host.verify_smoke_config(profile,config,status)
        for setting in (None,"cached","live"):
            config["web_search"]=setting
            with self.assertRaises(RuntimeError):host.verify_smoke_config(profile,config,status)
        del config["web_search"]
        with self.assertRaises(RuntimeError):host.verify_smoke_config(profile,config,status)
        config["web_search"]="disabled"
        self.assertIn("mcp_servers.actual_server.enabled=false",host.smoke_overrides(profile))
        for wrong in ({"data":[{"tools":{"mutation":{}}}]}, {"data":[],"nextCursor":"more"}, {}):
            with self.assertRaises(RuntimeError):host.verify_smoke_config(profile,config,wrong)
        config["mcp_servers"]["new_unreviewed"]={"enabled":False}
        with self.assertRaises(RuntimeError):host.verify_smoke_config(profile,config,status)
        del config["mcp_servers"]["new_unreviewed"]
        config["features"]["computer_use"]=True
        with self.assertRaises(RuntimeError):host.verify_smoke_config(profile,config,status)
        with self.assertRaises(RuntimeError):host.smoke_overrides({"smoke_mcp_servers":["quoted.name"]})

    def test_typed_instruction_read_is_pinned_and_requires_actual_completed_event(self):
        path=pathlib.Path(self.profile["state_dir"])/"instruction.md"
        path.write_text("public root instructions")
        self.profile["instruction_read_files"]=[{"path":str(path),"sha256":host.hashlib.sha256(path.read_bytes()).hexdigest()}]
        state={"conversation_id":"native-cid"}
        request={"method":"item/tool/call","params":{"threadId":"native-cid","callId":"native-read-item","tool":"root_read_instructions","arguments":{}}}
        response=self.runtime.model_tool(state,request)
        self.assertNotIn("instruction_reads",state)
        event={"method":"item/completed","params":{"threadId":"native-cid","item":{"id":"native-read-item","type":"dynamicToolCall","tool":"root_read_instructions","arguments":{},"status":"completed","success":True,"contentItems":response["contentItems"]}}}
        host.record_model_event(self.profile,state,event)
        self.assertEqual(state["instruction_reads"],{str(path):"native-read-item"})
        path.write_text("changed")
        with self.assertRaises(Exception):self.runtime.model_tool(state,request)

    def test_ack_requires_exact_owned_helper_incarnation_and_success(self):
        self.profile["instruction_read_files"]=[{"path":"required","sha256":"unused"}]
        self.profile.update(python_exe="python",python_sha256="pin",control_script="control",control_sha256="pin")
        owner=self.command("root-start")["owner"]
        state={"conversation_id":"native-cid","thread_owner":owner,"instruction_reads":{"required":"native-read-item"}}
        request={"method":"item/tool/call","params":{"threadId":"native-cid","callId":"native-ack-item","tool":"root_role_ack","arguments":{"accept_custody":True}}}
        helper=mock.Mock(pid=123,creation_filetime=456);helper.wait.return_value=0
        self.runtime.job=mock.Mock();self.runtime.job.start.return_value=helper
        receipt={"owner":owner,"thread_id":"native-cid","ack_message_id":"native-Bus-receipt","helper_kernel":{"pid":123,"creation_filetime":456}}
        with mock.patch.object(host,"pin",side_effect=lambda path,digest:path),mock.patch.object(host,"load_private_profile",return_value=receipt):
            response=self.runtime.model_tool(state,request)
            self.assertTrue(response["success"])
            receipt["helper_kernel"]["creation_filetime"]=999
            with self.assertRaisesRegex(RuntimeError,"incarnation"):self.runtime.model_tool(state,request)
            helper.wait.return_value=1
            with self.assertRaisesRegex(RuntimeError,"failed"):self.runtime.model_tool(state,request)

    def test_lifecycle_candidate_cannot_run_checks_or_pings(self):
        bounded=host.RootRuntime(self.profile,{"id":"fixture-A"})
        for operation in ("root-check","root-writeup-ping","root-standup-ping"):
            with self.assertRaisesRegex(RuntimeError,"bounded smoke"):
                bounded.execute_locked(self.command(operation))

    def test_below_30_records_one_obligation_and_keeps_launch_admitted(self):
        native=host.RootRuntime(self.profile,{"id":"fixture-A"})
        host.WindowsJob.return_value.query.return_value={}
        measurement=mock.Mock(stdout=json.dumps({"disk_free":25*1024**3,"ram_free":1024**3}))
        with mock.patch.object(host,"pin",side_effect=lambda path,digest:path),mock.patch.object(host.subprocess,"run",return_value=measurement):
            allowed,evidence=native.fresh_admission()
            self.assertTrue(allowed)
            self.assertEqual(evidence["cleanup_obligation"]["actual_owner_ack"],"pending")
            path=pathlib.Path(self.profile["state_dir"])/"scratch-cleanup-obligation.private.json"
            first=json.loads(path.read_text())
            first.update(ownership_ack="fixture-existing-owner-ACK",status="existing-owned-cleanup")
            host.save(path,first)
            allowed,evidence=native.fresh_admission()
            self.assertTrue(allowed)
            second=json.loads(path.read_text())
            self.assertEqual(second["created_at"],first["created_at"])
            self.assertEqual(second["ownership_ack"],"fixture-existing-owner-ACK")
            measurement.stdout=json.dumps({"disk_free":19*1024**3,"ram_free":1024**3})
            path.unlink() # Isolated fixture only: exercise first observation below hard floor.
            with self.assertRaises(RuntimeError):native.fresh_admission()
            below_floor=json.loads(path.read_text())
            self.assertEqual(below_floor["status"],"pending-owner-reconciliation")
            self.assertFalse(below_floor["latest_observation"]["above_hard_floor_after_growth"])

    def test_native_network_denial_must_be_explicit_not_missing_default(self):
        host.verify_native_readonly_policy({"sandbox":{"type":"readOnly","networkAccess":False},"approvalPolicy":"never"})
        for policy in (None,{}, {"type":"readOnly"}, {"type":"readOnly","networkAccess":None}, {"type":"readOnly","networkAccess":True},{"type":"dangerFullAccess","networkAccess":False}):
            with self.assertRaises(RuntimeError):host.verify_native_readonly_policy({"sandbox":policy,"approvalPolicy":"never"})

    def test_successor_factory_requires_genuine_job_exit_receipt(self):
        with mock.patch.object(host.subprocess, "run") as launch:
            with self.assertRaisesRegex(RuntimeError, "death/drain"):
                self.runtime.native_successor(self.command("root-native-successor"), {})
        launch.assert_not_called()

    def test_replacement_cannot_reuse_old_epoch(self):
        self.activate()
        path = pathlib.Path(self.profile["state_dir"]) / "root-runtime.json"
        state = json.loads(path.read_text())
        state["last_model_exit"] = {"owner": self.command("root-start")["owner"], "job": {"active_processes": 0}}
        host.save(path, state)
        with self.assertRaisesRegex(RuntimeError, "successor/new epoch"):
            self.runtime.execute(self.command("root-recover"))


class StartupOrderingTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    tearDown=RuntimeTests.tearDown
    command=RuntimeTests.command
    activate=RuntimeTests.activate
    def test_first_turn_submitted_before_any_frontend_and_returns_without_ack(self):
        self.profile.update(smoke_mcp_servers=[], root_prompt_sha256="pin")
        state={}
        path=pathlib.Path(self.profile["state_dir"])/"root-runtime.json"
        rpc=mock.Mock()
        thread={"id":"actual-fixture-cid","sessionId":"actual-fixture-session","cwd":self.profile["workspace"],"modelProvider":"openai","historyMode":"legacy"}
        config={"web_search":"disabled","mcp_servers":{},"features":{name:False for name in host.SMOKE_DISABLED_FEATURES}}
        def call(method, params):
            if method=="windowsSandbox/readiness":return {"status":"ready"}
            if method=="config/read":return {"config":config}
            if method=="mcpServerStatus/list":return {"data":[],"nextCursor":None}
            if method=="thread/start":
                self.assertEqual(params["historyMode"],"legacy")
                return {"thread":thread,"sandbox":{"type":"readOnly","networkAccess":False},"approvalPolicy":"never"}
            if method=="turn/start":
                self.assertIsNone(self.runtime.frontend)
                self.assertEqual(self.runtime.job.start.call_count,1)
                return {"turn":{"id":"fixture-provider-turn"}}
            self.fail("unexpected native call "+method)
        rpc.call.side_effect=call
        job=host.WindowsJob.return_value
        job.query.return_value={"source":"QueryInformationJobObject"}
        backend=job.start.return_value
        backend.pid=101;backend.creation_filetime=123;backend.poll.return_value=None
        with mock.patch.object(host.socket,"socket"),mock.patch.object(host,"AppServerRPC",return_value=rpc),mock.patch.object(host,"current_process_binding",return_value={"pid":202,"creation_filetime":456}),mock.patch.object(host,"load_private_profile",side_effect=lambda p:json.loads(pathlib.Path(p).read_text())),mock.patch.object(host,"pin",side_effect=lambda p,h:p):
            result=self.runtime.launch_native("fixed-exe",state,path,self.command("root-start"))
        self.assertIs(result,backend)
        self.assertTrue(state["initial_turn_submitted"])
        self.assertTrue(state["frontend_pending"])
        self.assertFalse(state["model_launch_complete"])
        rpc.start_reader.assert_called_once()

    def test_empty_legacy_history_never_starts_frontend(self):
        self.runtime.process=mock.Mock();self.runtime.process.poll.return_value=None
        self.runtime.job=mock.Mock();self.runtime.rpc=mock.Mock()
        owner=self.command("root-model-evidence")["owner"]
        state={"thread_owner":owner,"conversation_id":"fixture-cid","initial_turn_submitted":True}
        self.runtime.rpc.call.return_value={"thread":{"id":"fixture-cid","sessionId":"fixture-session","cwd":self.profile["workspace"],"modelProvider":"openai","historyMode":"legacy","turns":[]}}
        with self.assertRaisesRegex(RuntimeError,"history not materialized"):
            self.runtime.attach_materialized_frontend(state,pathlib.Path(self.profile["state_dir"])/"root-runtime.json",self.command("root-model-evidence"))
        self.runtime.job.start.assert_not_called()
        self.assertIsNone(self.runtime.frontend)

    def test_wrong_owner_proof_denies_before_frontend_or_history_read(self):
        self.activate()
        host.save(pathlib.Path(self.profile["state_dir"])/"model-evidence.private.json",{"owner":{"actor":"other"},"model":{"thread_id":"wrong"}})
        self.runtime.attach_materialized_frontend=mock.Mock()
        with self.assertRaisesRegex(RuntimeError,"owner-bound model"):
            self.runtime.execute(self.command("root-model-evidence"))
        self.runtime.attach_materialized_frontend.assert_not_called()


if __name__ == "__main__":
    unittest.main()




