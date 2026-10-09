"""Native aplexer root capsule: outbound authenticated synchronous control.

The shell capsule's whoami is bootstrap evidence, never a model tool/ACK.
Only a reviewed authority command can start the interactive Codex child.
"""
import argparse
import hashlib
import json
import pathlib
import socket
import ssl
import subprocess
import time
import contextlib
import math
import os
import secrets
import threading
import datetime
import re
import urllib.request
from urllib.parse import urlparse

from win35_quota_gate import load_private_profile
from win35_root_sink import callback_request, pin, save as raw_save
from api_root_state import persist as persist_api, event as provider_event, history as provider_history
from win35_root_job import WindowsJob, recorded_process_state, current_process_binding, verify_backend_connection, drain_recorded_job
from win35_root_rpc import AppServerRPC
from api_root_custody import API_ENDPOINT, observe as observe_api, owned_api_custody, dispatch_clear, validate_latest_history

PROFILE = pathlib.Path("C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap/api-runtime.private.json")
ADMISSION_PROFILE = pathlib.Path("C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap/admission.private.json")
SMOKE_DISABLED_FEATURES = ("shell_tool", "unified_exec", "multi_agent", "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use", "in_app_browser", "apps", "plugins", "remote_plugin", "plugin_sharing", "skill_mcp_dependency_install", "workspace_dependencies")

def save(path, value):
    if path.name == 'root-runtime.json' and value.get('runtime_mode') == 'api-root':
        persist_api(path, value, raw_save)
    else:
        raw_save(path, value)

def smoke_overrides(profile):
    names = profile.get("smoke_mcp_servers")
    if not isinstance(names, list) or len(names) != len(set(names)) or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in names):
        raise RuntimeError("missing reviewed native MCP inventory")
    argv = ["-c", 'web_search="disabled"']
    for feature in SMOKE_DISABLED_FEATURES:
        argv += ["--disable", feature]
    for name in names:
        argv += ["-c", "mcp_servers." + name + ".enabled=false"]
    return argv

def verify_smoke_config(profile, config, status):
    if config.get("web_search") != "disabled":
        raise RuntimeError("native hosted web search remains enabled")
    servers = config.get("mcp_servers")
    if not isinstance(servers, dict) or set(servers) != set(profile["smoke_mcp_servers"]) or any(not isinstance(value, dict) or value.get("enabled") is not False for value in servers.values()):
        raise RuntimeError("native MCP capability inventory drift or enabled server")
    if any(config.get("features", {}).get(feature) is not False for feature in SMOKE_DISABLED_FEATURES):
        raise RuntimeError("native mutating remote capability enabled")
    if not isinstance(status.get("data"), list) or status.get("nextCursor") is not None or any(server.get("tools") for server in status["data"]):
        raise RuntimeError("native MCP tool capability remains available")

def verify_native_readonly_policy(result):
    policy=result.get("sandbox")
    if not isinstance(policy,dict) or policy.get("type")!="readOnly" or policy.get("networkAccess") is not False or result.get("approvalPolicy")!="never":
        raise RuntimeError("actual native explicit read-only/network-denied policy not confirmed")

def validate_thread_binding(thread, workspace, expected_id=None):
    if not isinstance(thread, dict) or not isinstance(thread.get("id"), str) or not thread["id"] or not isinstance(thread.get("sessionId"), str) or not thread["sessionId"] or thread.get("modelProvider") != "openai":
        raise RuntimeError("missing authentic native thread binding")
    if expected_id is not None and thread["id"] != expected_id:
        raise RuntimeError("native resume thread mismatch")
    if thread.get("cwd", "").replace("\\", "/").lower() != workspace.replace("\\", "/").lower():
        raise RuntimeError("native thread workspace mismatch")

def mark_smoke_violation(profile, state, item):
    state["unapproved_smoke_tool"] = item.get("id", "unknown")
    save(pathlib.Path(profile["state_dir"])/"smoke-violation.private.json", {"owner":state.get("thread_owner"),"event_id":state["unapproved_smoke_tool"]})

def record_model_event(profile, state, message):
    if message.get("method") != "item/completed":
        return
    params = message.get("params", {})
    item = params.get("item", {})
    if params.get("threadId") != state.get("conversation_id"):
        return
    if item.get("type") == "commandExecution":
        mark_smoke_violation(profile,state,item)
        return
    if item.get("type") != "dynamicToolCall":
        if item.get("type") in ("fileChange", "mcpToolCall", "webSearch", "collabAgentToolCall"):
            mark_smoke_violation(profile,state,item)
        return
    if item.get("tool") == "root_read_instructions":
        read = state.get("native_instruction_calls", {}).get(item.get("id"))
        if item.get("status") == "completed" and item.get("success") is True and item.get("arguments") == {} and item.get("namespace") in (None, "") and read and item.get("contentItems") == read["contentItems"]:
            state["instruction_reads"] = {path: item["id"] for path in read["paths"]}
        else:
            mark_smoke_violation(profile,state,item)
        return
    if item.get("tool") != "root_role_ack" or item.get("namespace") not in (None, "") or item.get("arguments") != {"accept_custody": True} or item.get("status") != "completed" or item.get("success") is not True or not item.get("id"):
        mark_smoke_violation(profile,state,item)
        return
    receipt = state.get("native_ack_calls", {}).get(item["id"])
    if not receipt or receipt.get("helper_exit_code") != 0 or state.get("unapproved_smoke_tool"):
        return
    output = receipt["output"]
    content = [part.get("text") for part in item.get("contentItems", []) if part.get("type") == "inputText"]
    if json.dumps(output, sort_keys=True) not in content or output.get("thread_id") != state["conversation_id"] or not output.get("ack_message_id"):
        return
    evidence = {"native_actor": profile["actor"], "thread_id": state["conversation_id"],
                "first_tool": {"event_id": item["id"], "exit_code": receipt["helper_exit_code"], "ack_message_id": output["ack_message_id"],
                               "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                "completion_time_source": "native-item-completed-receipt",
                "event_type": "dynamicToolCall", "source": "provider-item-completed+owned-helper-exit",
                "instruction_read_events": list(state.get("instruction_reads", {}).values()), "helper_kernel": receipt["helper_kernel"]}
    # Maintained authority wire name; this is the first custody action AFTER
    # required reads, not the model's first native tool.
    evidence["first_tool_kind"]="first-custody-action-after-required-reads"
    save(pathlib.Path(profile["state_dir"]) / "model-evidence.private.json", {"owner": state["thread_owner"], "model": evidence})


class RootRuntime:
    def __init__(self, profile, native, smoke_only=True):
        self.profile = profile
        self.native = native
        self.process = None
        self.job = None
        self.frontend = None
        self.viewer = None
        self.observer = None
        self.rpc = None
        self.directory = pathlib.Path(profile["state_dir"])
        self.deadlines = {}
        self.smoke_only = smoke_only

    def model_tool(self, state, message):
        params = message.get("params", {})
        if message.get("method") == "item/tool/call" and params.get("threadId") == state.get("conversation_id") and params.get("namespace") in (None, "") and params.get("tool") == "root_read_instructions" and params.get("arguments") == {} and params.get("callId"):
            files = self.profile.get("instruction_read_files")
            if not isinstance(files, list) or not files or state.get("unapproved_smoke_tool"):
                raise RuntimeError("missing approved instruction bundle")
            parts=[]
            for entry in files:
                path=pin(entry["path"],entry["sha256"])
                parts.append({"type":"inputText","text":pathlib.Path(path).read_text(encoding="utf-8")})
            state.setdefault("native_instruction_calls",{})[params["callId"]]={"contentItems":parts,"paths":[entry["path"] for entry in files]}
            return {"contentItems":parts,"success":True}
        if message.get("method") != "item/tool/call" or params.get("namespace") not in (None, "") or params.get("threadId") != state.get("conversation_id") or params.get("tool") != "root_role_ack" or params.get("arguments") != {"accept_custody": True} or not params.get("callId"):
            raise RuntimeError("unapproved native model tool")
        required = [entry["path"] for entry in self.profile.get("instruction_read_files", [])]
        if not required or any(command not in state.get("instruction_reads", {}) for command in required) or state.get("unapproved_smoke_tool"):
            raise RuntimeError("instruction reads pending or unapproved tool")
        python = pin(self.profile["python_exe"], self.profile["python_sha256"])
        control = pin(self.profile["control_script"], self.profile["control_sha256"])
        helper = self.job.start([python, control, "Ack"], self.profile["workspace"])
        code = helper.wait(70)
        if code != 0:
            raise RuntimeError("actual owned ACK helper failed")
        owner, thread = state["thread_owner"], state["conversation_id"]
        stem = hashlib.sha256(json.dumps([owner, thread], sort_keys=True).encode()).hexdigest()
        receipt = load_private_profile(self.directory / ("ack-helper-" + stem + ".private.json"))
        if receipt.get("owner") != owner or receipt.get("thread_id") != thread or receipt.get("helper_kernel") != {"pid": helper.pid, "creation_filetime": helper.creation_filetime}:
            raise RuntimeError("owned ACK helper incarnation mismatch")
        output = {"ack_message_id": receipt["ack_message_id"], "thread_id": thread}
        state.setdefault("native_ack_calls", {})[params["callId"]] = {"output": output, "helper_exit_code": code, "helper_kernel": receipt["helper_kernel"]}
        return {"contentItems": [{"type": "inputText", "text": json.dumps(output, sort_keys=True)}], "success": True}

    def fresh_admission(self):
        # Current way-of-working rule: measure RAM, do not impose the retired
        # RAM refusal floor; retain disk >=20GiB after promised growth and
        # scoped scratch <=512MiB. Unknown native measurements hold.
        script = "$ErrorActionPreference='Stop';$o=Get-CimInstance Win32_OperatingSystem;$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\";@{disk_free=[long]$d.FreeSpace;ram_free=[long]$o.FreePhysicalMemory*1024}|ConvertTo-Json -Compress"
        measurement = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                     capture_output=True, text=True, check=True, timeout=10)
        resource = json.loads(measurement.stdout)
        if any(isinstance(resource.get(field), bool) or not isinstance(resource.get(field), int) or resource[field] <= 0
               for field in ("disk_free", "ram_free")):
            raise RuntimeError("unknown physical resource reading")
        obligation=None
        if resource["disk_free"] < 30 * 1024 ** 3:
            obligation_path=self.directory/"scratch-cleanup-obligation.private.json"
            observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            obligation=json.loads(obligation_path.read_text()) if obligation_path.exists() else {
                "kind":"disposable-scratch-cleanup", "owner_role":"principal", "status":"pending-owner-reconciliation",
                "action":"Root relays measured shortage to current principal; reuse one existing owned disposable-scratch cleanup effort and verify its ACK/action. Do not dispatch a duplicate or remove unrelated work.",
                "ownership_ack":None, "created_at":observed_at}
            obligation["latest_observation"]={"observed_at":observed_at,"below_30_gib":True,"above_hard_floor_after_growth":resource["disk_free"]-1024**3 >= 20*1024**3}
            save(obligation_path,obligation)
        scratch = 0
        scratch_directory=PROFILE.parent/'runtime' if self.profile.get('runtime_mode')=='api-root' else self.directory
        for path in scratch_directory.rglob("*"):
            if path.is_symlink() or (getattr(path.stat(), "st_file_attributes", 0) & 0x400):
                raise RuntimeError("scratch reparse path; hold")
            if path.is_file():
                scratch += path.stat().st_size
        if scratch > 512 * 1024 * 1024 or resource["disk_free"] - 1024 ** 3 < 20 * 1024 ** 3:
            raise RuntimeError("physical disk or scratch budget denied")
        gate = pin(self.profile["admission_script"], self.profile["admission_script_sha256"])
        python = pin(self.profile["python_exe"], self.profile["python_sha256"])
        job = WindowsJob()
        evidence = job.query()
        evidence.update(physical_source="Windows CIM", measured_ram=True,
                        disk_after_promised_growth_above_floor=True, scratch_within_limit=True,
                        promised_growth_bytes=1024 ** 3, measured_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        evidence.update(disk_free_bytes=resource["disk_free"], ram_free_bytes=resource["ram_free"],
                        scoped_scratch_bytes=scratch, cleanup_required=resource["disk_free"] < 30 * 1024 ** 3)
        if obligation:
            evidence["cleanup_obligation"]={"durable":True,"owner_role":obligation["owner_role"],"status":obligation["status"],"actual_owner_ack":"known" if obligation.get("ownership_ack") else "pending"}
        try:
            probe = job.start([python, gate, "--profile", str(ADMISSION_PROFILE)], self.profile["workspace"])
            allowed = probe.wait(timeout=65) == 0
            return allowed, evidence
        finally:
            job.kill()
            job.wait_empty()
            job.close()

    def protected_draft(self, state, allow_dead_backend=False):
        if self.profile.get('runtime_mode')=='api-root':
            if not state.get('pid') and not state.get('launch_pending') and not any(state.get(k) for k in ('frontend_pid','viewer_pid','frontend_attempt_pending')):
                return False  # Pinned API runtime has never created an input surface.
            if not owned_api_custody(self.profile,state,state.get('fence_owner'),self.process,recorded_process_state):
                raise RuntimeError('API model custody unknown; preserve')
            if self.frontend is not None or self.viewer is not None or self.job is None:
                raise RuntimeError('API runtime has unexpected UI/containment')
            self.job.query()
            return False
        if not state.get("pid") and not state.get("launch_pending"):
            return False  # Newly owned capsule has not launched any model UI.
        # History-first bootstrap deliberately has no editable frontend yet.
        # Admit only this exact retained live backend, not a crashed/cached PID
        # or an unidentified partial launch. A recorded frontend always falls
        # through to the native composer inspection below.
        if (self.process is not None and self.frontend is None and self.viewer is None
                and self.job is not None and self.process.poll() is None
                and state.get('pid') == self.process.pid
                and state.get('process_creation_filetime') == self.process.creation_filetime
                and recorded_process_state(self.process.pid,self.process.creation_filetime) == 'alive'
                and state.get('initial_turn_submitted') is True
                and state.get('frontend_pending') is True
                and state.get('model_launch_complete') is False
                and not state.get('launch_pending') and not state.get('frontend_attempt_pending')
                and not state.get('frontend_pid') and not state.get('viewer_pid')
                and state.get('conversation_id') and state.get('native_session_id')
                and isinstance(state.get('initial_turn_receipt'),dict)
                and state['initial_turn_receipt'].get('turn',{}).get('id')
                and state.get('native_policy') == {'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'}
                and state.get('thread_owner') == state.get('fence_owner')
                and state.get('guardian_binding') == current_process_binding()):
            self.job.query()  # Actual owned containment must still be valid.
            return False
        if self.process and self.frontend:
            if (self.process.poll() is not None and not allow_dead_backend) or self.frontend.poll() is not None:
                raise RuntimeError("model composer custody unknown")
        elif not all(state.get(pid) and state.get(stamp) and recorded_process_state(state[pid], state[stamp]) == "alive"
                     for pid, stamp in (("pid", "process_creation_filetime"), ("frontend_pid", "frontend_creation_filetime"))):
            raise RuntimeError("model composer incarnation unknown")
        executable = pin(self.profile["aplexer_exe"], self.profile["aplexer_sha256"])
        actor = state.get("fence_owner", {}).get("actor")
        if not actor:
            raise RuntimeError("model composer actor unknown")
        capture = subprocess.run([executable, "capture", actor, "--screen", "--plain"],
                                 capture_output=True, text=True, check=True, timeout=8).stdout
        prompts = [line.lstrip()[1:].strip() for line in capture.splitlines() if line.lstrip().startswith("›")]
        if not prompts:
            raise RuntimeError("model composer absent or unrecognized")
        # Text and placeholders are conservatively protected. Only an observed
        # empty composer is admitted; no guessed busy-state or pane injection.
        return prompts[-1] != ""

    def refresh_api_history(self,state,state_path):
        if self.profile.get('runtime_mode')!='api-root':return
        if not owned_api_custody(self.profile,state,state.get('thread_owner'),self.process,recorded_process_state) or self.rpc is None:
            raise RuntimeError('current API history custody unknown')
        result=self.rpc.call('thread/read',{'threadId':state['conversation_id'],'includeTurns':True})
        thread=result['thread'];validate_thread_binding(thread,self.profile['workspace'],state['conversation_id'])
        def receipt_writer(current):
            receipt={'owner':current['thread_owner'],'thread_id':current['conversation_id'],'turn_id':current['provider_turn_id'],'turn_status':'completed','source':'authenticated-native-thread-read-legacy'}
            save(self.directory/'api-history.private.json',receipt)
            return hashlib.sha256(json.dumps(receipt,sort_keys=True).encode()).hexdigest()
        current=provider_history(state_path,(state['conversation_id'],state['thread_owner']),thread,validate_latest_history,raw_save,receipt_writer)
        state.clear();state.update(current)

    def require_api_dispatch(self,state,state_path):
        self.refresh_api_history(state,state_path)
        if not dispatch_clear(state):raise RuntimeError('API provider busy, tool pending or current history unknown; preserve')

    def native_successor(self, command, state):
        exit_receipt = state.get("last_model_exit", {})
        if state.get("pid") or state.get("frontend_pid") or exit_receipt.get("job", {}).get("active_processes") != 0 or exit_receipt.get("owner") != command["owner"]:
            raise RuntimeError("exact managed root death/drain not proved")
        factory = self.directory / "native-successor.private.json"
        record = json.loads(factory.read_text()) if factory.exists() else {}
        if record.get("completed"):
            if record["predecessor_owner"] == command["owner"]:
                return record["completed"]
            # Only the actual enrolled successor can advance the factory.
            # Preserve the previous receipt before a second recovery attempt.
            previous = record["completed"]
            if previous.get("actor") != self.native["id"] or previous.get("generation") != command["owner"]["generation"] or state.get("fence_owner") != command["owner"]:
                raise RuntimeError("successor factory custody conflict")
            archive = self.directory / ("native-successor-" + previous["actor"] + ".private.json")
            save(archive, record)
            record = {}
        if record.get("pending"):
            raise RuntimeError("uncertain capsule launch; no duplicate")
        counter = int(state.get("capsule_counter", 0)) + 1
        tag = self.profile["root_tag"].split("-generation-")[0] + "-generation-" + str(counter)
        record = {"pending": command["key"], "tag": tag, "predecessor_owner": command["owner"]}
        save(factory, record)
        executable = pin(self.profile["aplexer_exe"], self.profile["aplexer_sha256"])
        python = pin(self.profile["python_exe"], self.profile["python_sha256"])
        host = pin(self.profile["host_script"], self.profile["host_script_sha256"])
        response = subprocess.run([executable, "start", "--workspace", self.profile["workspace"], "--tag", tag,
                                   "--engine", "shell", "--no-skip-permissions", "--memory", "1500M", "--pids", "100",
                                   "--json", "--", python, host], capture_output=True, text=True, check=True, timeout=15)
        actor = json.loads(response.stdout)["id"]
        __import__("uuid").UUID(actor)
        if actor == self.native["id"]:
            raise RuntimeError("native factory did not create new capsule")
        record["started_actor"] = actor
        save(factory, record)
        path = self.directory / ("native-startup-" + actor + ".private.json")
        until = time.monotonic() + 10
        while not path.exists() and time.monotonic() < until:
            time.sleep(.1)
        observed = load_private_profile(path)
        native, kernel = observed["native"], observed["kernel"]
        if native["id"] != actor or native["tag"] != tag or native["workspace"].replace("\\", "/").lower() != self.profile["workspace"].lower() or observed["host"] != __import__("platform").node():
            raise RuntimeError("actual successor WHOAMI mismatch")
        if recorded_process_state(kernel["pid"], kernel["creation_filetime"]) != "alive":
            raise RuntimeError("successor native incarnation not alive")
        generation = "win32:" + str(kernel["pid"]) + ":" + str(kernel["creation_filetime"])
        if observed["generation"] != generation or observed["model_started"] is not False:
            raise RuntimeError("successor incarnation or pre-model custody mismatch")
        result = {"actor": actor, "host": observed["host"], "generation": generation, "whoami": native,
                  "root_tag": tag,
                  "kernel": kernel, "predecessor_owner": command["owner"],
                  "owned_model_exit": dict(exit_receipt, verified_dead=True)}
        record.update(pending=None, completed=result)
        save(factory, record)
        state["capsule_counter"] = counter
        return result

    def launch_native(self, executable, state, state_path, command):
        # Refuse any already occupied endpoint; never connect to the desktop's
        # shared daemon or an unidentified process as our owned backend.
        api_mode=self.profile.get('runtime_mode')=='api-root'
        endpoint = API_ENDPOINT if api_mode else "ws://127.0.0.1:8803"
        if api_mode and state.get('conversation_id'):
            raise RuntimeError('new API incarnation cannot inherit a prior model CID')
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", 8813 if api_mode else 8803))
        finally:
            probe.close()
        token = secrets.token_urlsafe(48)
        token_path = self.directory / "backend-capability.private"
        save(token_path, {"token": token})
        # Parent directory has the provisioner-owned ACL; verify the actual
        # resulting file before exposing a listener.
        if load_private_profile(token_path).get("token") != token:
            raise RuntimeError("private backend capability binding changed")
        state["job_name"] = "Local\\Win35Root-" + secrets.token_hex(16)
        save(state_path, state)
        self.job = WindowsJob(state["job_name"])
        backend = self.job.start([executable, *smoke_overrides(self.profile), "app-server", "--listen", endpoint,
                                  "--ws-auth", "capability-token", "--ws-token-sha256", hashlib.sha256(token.encode()).hexdigest()],
                                 self.profile["workspace"])
        self.process = backend
        state.update(pid=backend.pid, process_creation_filetime=backend.creation_filetime,
                     containment=self.job.query(), guardian_binding=current_process_binding(),
                     launched_epoch=command["owner"]["epoch"])
        save(state_path, state)  # Still launch_pending until all native binding completes.
        until = time.monotonic() + 8
        rpc = None
        while time.monotonic() < until:
            if backend.poll() is not None:
                raise RuntimeError("owned backend exited before native binding")
            try:
                rpc = AppServerRPC(endpoint, token, lambda sock: verify_backend_connection(sock, backend,8813 if api_mode else 8803), timeout=5)
                break
            except ConnectionRefusedError:
                time.sleep(.1)
        if rpc is None:
            raise RuntimeError("owned backend unavailable")
        try:
            if rpc.call("windowsSandbox/readiness", {}) != {"status": "ready"}:
                raise RuntimeError("actual native Windows sandbox not ready")
            verify_smoke_config(self.profile, rpc.call("config/read", {"cwd": self.profile["workspace"], "includeLayers": False})["config"], rpc.call("mcpServerStatus/list", {}))
            state.update(instruction_reads={}, native_instruction_calls={}, native_ack_calls={}, unapproved_smoke_tool=None,
                         runtime_mode=self.profile.get('runtime_mode'),provider_turn_state='unknown',provider_pending_tools={})
            config = {"web_search":"disabled","features": {feature: False for feature in SMOKE_DISABLED_FEATURES}, "mcp_servers": {name: {"enabled": False} for name in self.profile["smoke_mcp_servers"]}}
            tools = [{"type": "function", "name": "root_role_ack", "description": "Accept this actual root's own operational custody after reading required instructions; no other mutation is authorized in smoke.",
                      "inputSchema": {"type": "object", "properties": {"accept_custody": {"type": "boolean", "const": True}}, "required": ["accept_custody"], "additionalProperties": False}}]
            tools.append({"type":"function","name":"root_read_instructions","description":"Read the complete fixed provisioner-pinned root instruction bundle before accepting custody. No caller-selected paths.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}})
            binding = {"sandbox": "read-only", "approvalPolicy": "never", "config": config, "dynamicTools": tools}
            if state.get("conversation_id"):
                result = rpc.call("thread/resume", dict(binding, threadId=state["conversation_id"]))
            else:
                result = rpc.call("thread/start", dict(binding, cwd=self.profile["workspace"], modelProvider="openai", historyMode="legacy"))
            thread = result["thread"]
            verify_native_readonly_policy(result)
            state['native_policy']={'sandbox':result['sandbox'],'approvalPolicy':result['approvalPolicy']}
            validate_thread_binding(thread, self.profile["workspace"], state.get("conversation_id"))
            state.update(conversation_id=thread["id"], native_session_id=thread["sessionId"],
                         thread_owner=command["owner"], thread_binding_source="thread/start-or-resume")
            save(state_path, state)
            self.check_deadline(command)
            # Metadata creation above starts no model turn. Final sink guard
            # remains fresh at the actual interactive frontend/model launch.
            self.final_guard(command)
            def observed(message):
                if api_mode:
                    provider_event(state_path,(thread['id'],command['owner']),message,observe_api,raw_save)
                record_model_event(self.profile, state, message)
            rpc.start_reader(observed, lambda message: self.model_tool(state, message))
            self.rpc = rpc
            self.final_guard(command)
            # This original owned RPC starts the model turn and receives its
            # native dynamic tool request; the viewer only attaches/displays.
            prompt_path = pin(self.profile["root_prompt"], self.profile["root_prompt_sha256"])
            turn = rpc.call("turn/start", {"threadId": thread["id"], "input": [{"type": "text", "text": pathlib.Path(prompt_path).read_text(encoding="utf-8")}]})
            # The authority holds its effect transaction during this callback.
            # Return after submission so the model's separate custody ACK can
            # acquire that transaction. Empty threads have no resumable rollout.
            if api_mode:
                notified=json.loads(state_path.read_text())
                for name in ('provider_turn_id','provider_turn_state','provider_pending_tools'):
                    if name in notified:state[name]=notified[name]
            state.update(initial_turn_submitted=True, initial_turn_receipt=turn,
                         frontend_pending=True, model_launch_complete=False)
            save(state_path, state)
        except BaseException:
            rpc.close()
            raise
        return backend

    def attach_materialized_frontend(self, state, state_path, command):
        """Attach only after real provider custody proof and saved native history."""
        if state.get('frontend_attempt_pending'):
            raise RuntimeError('uncertain prior frontend attempt; reconcile exact native incarnation')
        if self.process is None or self.process.poll() is not None or self.job is None or self.rpc is None:
            raise RuntimeError("owned bootstrap backend unavailable")
        if not state.get("initial_turn_submitted") or state.get("thread_owner") != command["owner"]:
            raise RuntimeError("owned initial turn not submitted")
        self.final_guard(command)
        result = self.rpc.call("thread/read", {"threadId": state["conversation_id"], "includeTurns": True})
        thread = result["thread"]
        validate_thread_binding(thread, self.profile["workspace"], state["conversation_id"])
        if thread.get("historyMode") != "legacy" or not isinstance(thread.get("turns"), list) or not thread["turns"]:
            raise RuntimeError("native legacy history not materialized")
        if self.profile.get('runtime_mode')=='api-root':
            if self.frontend is not None or self.viewer is not None or any(state.get(k) for k in ('frontend_pid','viewer_pid','frontend_attempt_pending')):
                raise RuntimeError('API runtime cannot adopt an old frontend')
            if not validate_latest_history(state,thread):
                raise RuntimeError('API current provider turn/tool/history remains pending')
            state.update(frontend_pending=False,model_launch_complete=True)
            save(state_path,state)
            return
        executable = pin(self.profile["codex_exe"], self.profile["codex_sha256"])
        token = load_private_profile(self.directory / "backend-capability.private")["token"]
        argv = [executable, *smoke_overrides(self.profile), "--remote", "ws://127.0.0.1:8803",
                "--remote-auth-token-env", "WIN35_ROOT_BACKEND_TOKEN", "--disable", "shell_snapshot",
                "-C", self.profile["workspace"], "--sandbox", "read-only", "--ask-for-approval", "never",
                "resume", state["conversation_id"]]
        if self.frontend is not None:
            raise RuntimeError("frontend attempt already exists; reconcile exact owned handle")
        state["frontend_attempt_pending"] = command["key"]
        save(state_path, state)
        self.frontend = self.job.start(argv, self.profile["workspace"], dict(os.environ, WIN35_ROOT_BACKEND_TOKEN=token))
        state.update(frontend_pid=self.frontend.pid, frontend_creation_filetime=self.frontend.creation_filetime)
        save(state_path, state)
        # Confirm the frontend remains alive through its initial native resume;
        # a failed attach stays incomplete and cannot activate root custody.
        until = time.monotonic() + 2
        while time.monotonic() < until:
            if self.frontend.poll() is not None:
                raise RuntimeError("owned frontend exited during native resume")
            time.sleep(.05)
        aplexer = pin(self.profile["aplexer_exe"], self.profile["aplexer_sha256"])
        self.final_guard(command)
        self.viewer = self.job.start([aplexer, "attach", self.native["id"]], self.profile["workspace"], new_console=True)
        state.update(viewer_pid=self.viewer.pid, viewer_creation_filetime=self.viewer.creation_filetime,
                     frontend_pending=False, frontend_attempt_pending=None, model_launch_complete=True)
        save(state_path, state)

    def check_deadline(self, command):
        wall = time.time()
        deadline = command.get("deadline")
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
            raise RuntimeError("invalid authority deadline")
        clock_path = self.directory / "clock-highwater.json"
        highwater = json.loads(clock_path.read_text()) if clock_path.exists() else {}
        if wall < highwater.get("wall", wall):
            raise RuntimeError("clock rollback; authority reconciliation required")
        save(clock_path, {"wall": wall})
        remaining = deadline - wall
        if remaining <= 0 or remaining > 60:
            raise RuntimeError("expired or unbounded authority command")
        stamp = (command["key"], deadline)
        if stamp not in self.deadlines:
            self.deadlines[stamp] = time.monotonic() + remaining
        if time.monotonic() >= self.deadlines[stamp]:
            raise RuntimeError("monotonic authority deadline expired")

    @contextlib.contextmanager
    def action_lock(self):
        lock_directory=PROFILE.parent/'runtime' if self.profile.get('runtime_mode')=='api-root' else self.directory
        with (lock_directory / "native-action.lock").open("a+b") as stream:
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0"); stream.flush()
            stream.seek(0)
            if __import__("os").name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    yield
                finally:
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def final_guard(self, command):
        context = ssl.create_default_context(cafile=self.profile["ca_certificate"])
        context.load_cert_chain(self.profile["client_certificate"], self.profile["client_key"])
        owner = command["owner"]
        body = dict(owner, v=1, op="sink-proof", key=command["key"], operation=command["operation"],
                    payload=command.get("payload", {}), credential=self.profile["credential"])
        request = urllib.request.Request(self.profile["authority_url"].rstrip("/") + "/v1/sink-proof",
                                         data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, context=context, timeout=10) as response:
            proof = json.load(response)
        if proof.get("v") != 1 or proof.get("status") != "ok":
            raise RuntimeError("authority unavailable or fenced")
        for key in ("key", "owner", "operation", "payload"):
            if proof.get(key) != command.get(key, {} if key == "payload" else None):
                raise RuntimeError("final sink proof mismatch")
        self.check_deadline(command)

    def execute(self, command):
        # A new generation's native activation must take this same lock and
        # ACK its high-water update before the authority enables new effects.
        with self.action_lock():
            return self.execute_locked(command)

    def execute_locked(self, command):
        if self.smoke_only and command.get("operation") not in ("root-admission", "root-fence-activate", "root-start", "root-status", "root-model-evidence", "root-stop", "root-test-kill", "root-native-successor", "root-recover"):
            raise RuntimeError("bounded smoke: normal operational effects unavailable")
        request = callback_request(self.profile, command, command["operation"])
        self.check_deadline(command)
        path = self.directory / (hashlib.sha256(request["key"].encode()).hexdigest() + ".json")
        state_path = self.directory / "root-runtime.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if command["operation"] == "root-native-successor" and self.process is not None and self.process.poll() is not None:
            self.final_guard(command)
            if self.frontend is not None and self.frontend.poll() is None and self.protected_draft(state, allow_dead_backend=True):
                raise RuntimeError("protected composer after backend failure; preserve")
            if self.job is None:
                # root-test-kill already closed this exact drained Job. Reuse
                # its completed owner/kernel-bound receipt; never treat loss
                # of an unrecorded handle as proof that descendants died.
                previous=state.get('last_model_exit',{})
                if (previous.get('owner')!=command['owner'] or previous.get('backend_pid')!=self.process.pid
                    or previous.get('backend_creation_filetime')!=self.process.creation_filetime
                    or previous.get('job')!={'active_processes':0,'source':'QueryInformationJobObject'}
                    or state.get('pid') or state.get('frontend_pid')
                    or recorded_process_state(self.process.pid,self.process.creation_filetime) not in ('exited','original-exited-pid-reused')):
                    raise RuntimeError('lost managed containment without exact completed drain; preserve')
            else:
                self.job.kill()
                drained = self.job.wait_empty()
                self.job.close()
                state["last_model_exit"] = {"owner": state.get("thread_owner"), "job": drained,
                                            "backend_pid": self.process.pid, "backend_creation_filetime": self.process.creation_filetime,
                                            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            state.update(pid=None, frontend_pid=None, viewer_pid=None, launch_pending=None, model_launch_complete=False)
            save(state_path, state)
            self.job = self.process = self.frontend = None
        if command["operation"] == "root-admission":
            quota, resources = self.fresh_admission()
            draft = self.protected_draft(state)
            ready=True
            if self.profile.get('runtime_mode')=='api-root' and state.get('pid'):
                self.refresh_api_history(state,state_path)
                ready=dispatch_clear(state)
            admission = {"actor": self.native["id"], "host": __import__("platform").node(),
                         "generation": self.profile["generation"], "ready": ready, "draft": draft,
                         "quota_ok": quota, "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         "resources": resources, "source": "native-quota-exit-and-owned-composer"}
            return {"v": 1, "key": command["key"], "owner": command["owner"], "operation": command["operation"],
                    "payload": {}, "state": "completed", "native_actor": self.native, "evidence": {"admission": admission}}
        if request["epoch"] < state.get("highest_epoch", 0):
            raise RuntimeError("stale epoch")
        if command["operation"] != "root-fence-activate" and state.get("fence_owner") != command["owner"]:
            raise RuntimeError("native generation activation missing or stale")
        if path.exists():
            return json.loads(path.read_text())
        running = (self.process is not None and self.process.poll() is None and
                   self.frontend is not None and self.frontend.poll() is None and
                   self.viewer is not None and self.viewer.poll() is None and
                   state.get("model_launch_complete") is True and not state.get("launch_pending"))
        if self.profile.get('runtime_mode')=='api-root':
            running=owned_api_custody(self.profile,state,command['owner'],self.process,recorded_process_state) and state.get('model_launch_complete') is True
        # Capsule restart loses the owned kernel handle. Persisted PID is never
        # interpreted as absence or used to kill a possibly reused process.
        # Reconciliation must prove the recorded backend/session exited before
        # any new launch; unknown state preserves the existing root.
        detached = self.process is None and (state.get("pid") is not None or state.get("launch_pending"))
        if detached and state.get("pid") and state.get("process_creation_filetime") and state.get("guardian_binding") and state.get("containment", {}).get("source") == "QueryInformationJobObject":
            observation = recorded_process_state(state["pid"], state["process_creation_filetime"])
            guardian = state["guardian_binding"]
            guardian_observation = recorded_process_state(guardian["pid"], guardian["creation_filetime"])
            frontend_observation = "exited"
            if state.get("frontend_pid"):
                if not state.get("frontend_creation_filetime"):
                    raise RuntimeError("missing frontend incarnation; hold")
                frontend_observation = recorded_process_state(state["frontend_pid"], state["frontend_creation_filetime"])
            if all(value in ("exited", "original-exited-pid-reused") for value in (observation, guardian_observation, frontend_observation)):
                # Native job kill-on-close guarantees the previous guardian's
                # children die with it. No rights to kill a reused PID.
                state.update(pid=None, frontend_pid=None, launch_pending=None,
                             reconciliation={"source": "kernel-exact-creation", "observation": observation})
                save(state_path, state)
                detached = False
        op = command["operation"]
        if self.profile.get('runtime_mode')=='api-root' and op in ('root-check','root-standup-ping','root-writeup-ping','root-stop','root-test-kill'):
            self.require_api_dispatch(state,state_path)
        if self.profile.get('runtime_mode')=='api-root' and op=='root-native-successor':
            checkpoint=state.get('last_model_exit',{}).get('api_checkpoint',{})
            if (checkpoint.get('owner')!=command['owner'] or checkpoint.get('provider_turn_state')!='completed'
                    or checkpoint.get('pending_tool_count')!=0 or not checkpoint.get('history_receipt_sha256')
                    or checkpoint.get('history_receipt_sha256')!=state.get('api_history_receipt_sha256')):
                raise RuntimeError('API predecessor quiescent checkpoint unavailable')
        if op == "root-fence-activate":
            self.final_guard(command)
            if state.get("fence_owner") and state["fence_owner"] != command["owner"] and state.get("pid"):
                if self.protected_draft(state):
                    raise RuntimeError("protected model draft; takeover holds")
                # New ownership cannot become active while an old managed model
                # retains raw native tools. Preserve its CID/checkpoint, prove
                # exact Job membership, terminate and drain before activation.
                drained = drain_recorded_job(state)
                state.update(pid=None, frontend_pid=None, launch_pending=None, model_launch_complete=False,
                             prior_managed_job_drain=drained)
                self.process = self.frontend = None
            state["highest_epoch"] = request["epoch"]
            state["fence_owner"] = command["owner"]
            save(state_path, state)
            result = {"fence_activation": command["owner"], "model_first_action": "pending"}
        elif op == "root-status":
            result = {"running": running if not detached else "unknown", "reconciliation_required": bool(detached),
                      "pid": self.process.pid if running else None}
        elif op == "root-model-evidence":
            self.final_guard(command)
            proof = json.loads((self.directory / "model-evidence.private.json").read_text())
            if (self.directory/"smoke-violation.private.json").exists() or state.get("unapproved_smoke_tool") or proof.get("owner") != command["owner"] or proof.get("model", {}).get("thread_id") != state.get("conversation_id"):
                raise RuntimeError("actual owner-bound model tool evidence unavailable")
            if not running:
                self.attach_materialized_frontend(state, state_path, command)
            if self.profile.get('runtime_mode')!='api-root' and (self.frontend is None or self.frontend.poll() is not None or self.viewer is None or self.viewer.poll() is not None):
                raise RuntimeError("interactive root custody incomplete")
            result = {"model": proof["model"]}
        elif op == "root-native-successor":
            self.final_guard(command)
            result = {"successor": self.native_successor(command, state)}
            save(state_path, state)
        elif op in ("root-start", "root-recover"):
            if state.get("last_model_exit", {}).get("owner") == command["owner"]:
                raise RuntimeError("replacement model requires genuine successor/new epoch")
            if running:
                result = {"running": True, "created": False, "pid": self.process.pid}
            elif op == "root-recover" and self.process is not None and self.process.poll() is None and self.frontend is not None and self.frontend.poll() is None and state.get("model_launch_complete") is True:
                # Closing the owned viewer is not model death. Restore only
                # that console under the current fence, never a second model.
                self.final_guard(command)
                aplexer = pin(self.profile["aplexer_exe"], self.profile["aplexer_sha256"])
                self.viewer = self.job.start([aplexer, "attach", self.native["id"]], self.profile["workspace"], new_console=True)
                state.update(viewer_pid=self.viewer.pid, viewer_creation_filetime=self.viewer.creation_filetime)
                save(state_path, state)
                result = {"running": True, "created": False, "viewer_restored": True}
            else:
                if detached or state.get("launch_pending") or state.get("pid"):
                    raise RuntimeError("uncertain launch; reconcile before retry")
                gate = pin(self.profile["admission_script"], self.profile["admission_script_sha256"])
                if not self.fresh_admission()[0]:
                    raise RuntimeError("fresh native admission denied")
                self.check_deadline(command)
                executable = pin(self.profile["codex_exe"], self.profile["codex_sha256"])
                self.final_guard(command)
                state["launch_pending"] = request["key"]
                save(state_path, state)
                try:
                    self.process = self.launch_native(executable, state, state_path, command)
                except BaseException:
                    # A backend without its validated native thread/frontend is
                    # an incomplete launch. Clean only this retained owned job;
                    # preserve pending state for explicit authority reconciliation.
                    if self.job is not None:
                        self.job.kill()
                        self.job.wait_empty()
                        self.job.close()
                        self.job = None
                    self.process = self.frontend = None
                    state["model_launch_complete"] = False
                    save(state_path, state)
                    raise
                state.update(launch_pending=None, pid=self.process.pid, launched_epoch=request["epoch"], model_launch_complete=False)
                save(state_path, state)
                result = {"created": True, "pid": self.process.pid, "native_turn_submitted": True,
                          "interactive_root_complete": False, "model_first_action": "pending"}
        elif op in ("root-stop", "root-test-kill"):
            if not running or state.get("launched_epoch") != request["epoch"]:
                raise RuntimeError("not the newly owned running root")
            if state.get("pid") != self.process.pid or state.get("process_creation_filetime") != self.process.creation_filetime:
                raise RuntimeError("exact root process incarnation mismatch")
            if self.protected_draft(state):
                raise RuntimeError("protected root composer; preserve")
            self.final_guard(command)
            # Exact retained Popen handle; no name-based or guessed PID kill.
            self.process.kill()
            self.process.wait(timeout=10)
            drained = None
            if self.job is not None:
                drained = self.job.wait_empty()
                self.job.close()
                self.job = None
            if drained is None:
                raise RuntimeError("managed Job drainage not proved")
            state["last_model_exit"] = {"owner": command["owner"], "job": drained,
                                        "backend_pid": self.process.pid, "backend_creation_filetime": state.get("process_creation_filetime"),
                                        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            if self.profile.get('runtime_mode')=='api-root':
                state['last_model_exit']['api_checkpoint']={'owner':command['owner'],'provider_turn_state':state['provider_turn_state'],
                    'pending_tool_count':len(state['provider_pending_tools']),'history_receipt_sha256':state['api_history_receipt_sha256']}
            state.update(pid=None, frontend_pid=None, launch_pending=None)
            save(state_path, state)
            result = {"terminated_pid": self.process.pid, "restart_acceptance": "pending-external-supervisor"}
        elif op in ("root-check", "root-standup-ping", "root-writeup-ping"):
            if not running or not state.get("conversation_id") or state.get("thread_owner") != command["owner"]:
                raise RuntimeError("genuine root thread binding not yet accepted")
            body = self.profile[{"root-check": "check_prompt", "root-standup-ping": "standup_prompt", "root-writeup-ping": "writeup_prompt"}[op]]
            if self.protected_draft(state) or not self.fresh_admission()[0]:
                raise RuntimeError("protected composer or fresh admission denied")
            self.final_guard(command)
            state["pending_ping"] = {"owner": command["owner"], "operation": op, "key": command["key"]}
            save(state_path, state)
            token = load_private_profile(self.directory / "backend-capability.private")["token"]
            if self.profile.get('runtime_mode')=='api-root':
                if self.rpc is None:raise RuntimeError('observed owned API connection absent')
                state.update(api_history_validated=False,provider_turn_state='starting')
                save(state_path,state)
                self.rpc.call("turn/start", {"threadId": state["conversation_id"], "input": [{"type": "text", "text": body}]})
            else:
                rpc = AppServerRPC("ws://127.0.0.1:8803", token,
                                   lambda sock: verify_backend_connection(sock, self.process), timeout=10)
                try:
                    rpc.call("turn/start", {"threadId": state["conversation_id"], "input": [{"type": "text", "text": body}]})
                finally:
                    rpc.close()
            result = {"native_turn_submitted": True, "model_ACK": "pending"}
        else:
            raise ValueError("unapproved operation")
        receipt = {"v": 1, "key": command["key"], "owner": command["owner"],
                   "operation": command["operation"], "payload": command.get("payload", {}),
                   "state": "completed", "native_actor": self.native,
                   "evidence": result}
        save(path, receipt)
        return receipt


def channel(profile, native, runtime):
    endpoint = urlparse(profile["authority_url"])
    if endpoint.scheme != "https" or endpoint.path not in ("", "/") or not endpoint.hostname:
        raise ValueError("invalid authority endpoint")
    context = ssl.create_default_context(cafile=profile["ca_certificate"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(profile["client_certificate"], profile["client_key"])
    raw = socket.create_connection((endpoint.hostname, endpoint.port or 443), timeout=10)
    with context.wrap_socket(raw, server_hostname=endpoint.hostname) as connection:
        body = json.dumps({"v": 1, "op": "inspect", "project": profile["project"], "role": "root",
                           "actor": native["id"], "generation": profile["generation"],
                           "credential": profile["credential"]}).encode()
        headers = ("POST /v1/native-channel HTTP/1.1\r\nHost: " + endpoint.netloc +
                   "\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)) + "\r\n\r\n").encode()
        connection.sendall(headers + body)
        stream = connection.makefile("rwb")
        response = stream.readline(4096)
        if not response.startswith(b"HTTP/1.1 101 "):
            raise RuntimeError("authority channel unavailable")
        while stream.readline(4096) != b"\r\n":
            pass
        connection.settimeout(90)
        while True:
            line = stream.readline(16385)
            if not line or len(line) > 16384:
                raise RuntimeError("control channel disconnected")
            command = json.loads(line)
            try:
                receipt = runtime.execute(command)
            except Exception:
                receipt = {"v": 1, "key": command.get("key"), "owner": command.get("owner"),
                           "operation": command.get("operation"), "payload": command.get("payload", {}),
                           "state": "uncertain",
                           "native_actor": native, "evidence": {"reconcile_required": True}}
            stream.write(json.dumps(receipt).encode() + b"\n")
            stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    profile = load_private_profile(PROFILE)
    if profile.get('runtime_mode')!='api-root':raise RuntimeError('next8 requires explicit approved API mode')
    api_root=(PROFILE.parent/'runtime/api-root').resolve()
    if not pathlib.Path(profile['state_dir']).resolve().is_relative_to(api_root):
        raise RuntimeError('API state cannot overwrite the protected predecessor')
    executable = pin(profile["aplexer_exe"], profile["aplexer_sha256"])
    native = json.loads(subprocess.check_output([executable, "whoami", "--json"], text=True))
    factory_path = pathlib.Path(profile["state_dir"]) / "native-successor.private.json"
    factory = load_private_profile(factory_path) if factory_path.exists() else {}
    if native["workspace"].replace("\\", "/").lower() != profile["workspace"].lower() or native["tag"] not in (profile["root_tag"], factory.get("tag")):
        raise RuntimeError("wrong genuine capsule binding")
    kernel = current_process_binding()
    generation = "win32:" + str(kernel["pid"]) + ":" + str(kernel["creation_filetime"])
    save(pathlib.Path(profile["state_dir"]) / ("native-startup-" + native["id"] + ".private.json"),
         {"native": native, "model_started": False, "host": __import__("platform").node(), "kernel": kernel, "generation": generation})
    # Provisioner enrolls this actual whoami before setting actor; never synthesize
    # an aplexer UUID or count the shell binder as an active model root.
    while profile["actor"] != native["id"] or profile["generation"] != generation:
        time.sleep(1)
        profile = load_private_profile(PROFILE)
    runtime = RootRuntime(profile, native)
    while True:
        try:
            channel(profile, native, runtime)
        except Exception:
            # No unguarded dispatch while offline; retain any productive root.
            time.sleep(5)


if __name__ == "__main__":
    main()
