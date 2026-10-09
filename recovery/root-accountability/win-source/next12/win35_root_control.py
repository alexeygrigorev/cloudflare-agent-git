"""Fixed-profile scheduler frontend. Never launches an unfenced local model."""
import argparse
import contextlib
import hashlib
import json
import pathlib
import ssl
import subprocess
import time
import urllib.request
from win35_quota_gate import load_private_profile
from win35_root_sink import save,pin
from win35_root_job import recorded_process_state, current_process_binding
from api_root_custody import recorded_api_custody, valid_lease_tuple, dispatch_clear

PROFILE = pathlib.Path("C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap/api-runtime.private.json")
MODES = {"Start": "root-start", "Recover": "root-recover", "Check": "root-check",
         "Standup": "root-standup-ping", "Writeup": "root-writeup-ping",
         "Stop": "root-stop", "TestKill": "root-test-kill"}

def refresh_owned(profile,owner):
    state=load_private_profile(pathlib.Path(profile['state_dir'])/'root-runtime.json')
    if not recorded_api_custody(profile,state,owner,recorded_process_state):
        raise RuntimeError('live API custody unknown; preserve')
    # Renewal is validated by the authority's current tuple and lease. A held
    # admission cannot erase still-valid custody; it still blocks new effects.
    request(profile,dict(owner,op='renew',ttl=180))
    return request(profile,dict(owner,op='admission_refresh'))

def model_ack():
    """Invoked by the actual model's custody ACK tool after instruction reads, never by guardian."""
    profile = load_private_profile(PROFILE)
    state = json.loads((pathlib.Path(profile["state_dir"]) / "root-runtime.json").read_text())
    owner, thread = state["thread_owner"], state["conversation_id"]
    if owner["actor"] != profile["actor"] or owner["generation"] != profile["generation"]:
        raise RuntimeError("model custody owner mismatch")
    if not recorded_api_custody(profile,state,owner,recorded_process_state):
        raise RuntimeError('ACK requires exact live owned API model/native custody')
    executable=pin(profile['aplexer_exe'],profile['aplexer_sha256'])
    native=json.loads(subprocess.check_output([executable,'whoami','--json'],text=True,timeout=10))
    if (native.get('id')!=owner['actor'] or native.get('tag')!=profile['root_tag']
        or str(native.get('workspace','')).replace('\\','/').lower()!=profile['workspace'].replace('\\','/').lower()):
        raise RuntimeError('ACK helper native caller is not this actual root')
    key = "model-role-ack:" + hashlib.sha256(json.dumps([owner, thread], sort_keys=True).encode()).hexdigest()
    result = request(profile, dict(owner, op="bus_send", action="role-ack", model_thread_id=thread,
                     key=key, body="Win35 root model accepts operational custody; first custody action is this authenticated role ACK after reading required instructions. Product principal remains protected."))
    receipt = {"ack_message_id": result["result"]["message_id"], "thread_id": thread,
               "owner": owner, "helper_kernel": current_process_binding()}
    save(pathlib.Path(profile["state_dir"]) / ("ack-helper-" + hashlib.sha256(json.dumps([owner, thread], sort_keys=True).encode()).hexdigest() + ".private.json"), receipt)
    return {"ack_message_id": receipt["ack_message_id"], "thread_id": thread}

def model_proxy(mode, message_id=None):
    """Actual root tools use the enrolled mTLS route; no SSH dependency."""
    profile = load_private_profile(PROFILE)
    directory = pathlib.Path(profile["state_dir"])
    state = json.loads((directory / "root-runtime.json").read_text())
    owner, thread = state["thread_owner"], state["conversation_id"]
    if owner["actor"] != profile["actor"] or owner["generation"] != profile["generation"]:
        raise RuntimeError("model proxy custody mismatch")
    if mode == "Reports":
        return request(profile, dict(owner, op="bus_inbox"))["result"]
    if mode == "Handled":
        if not message_id:
            raise RuntimeError("actual handled native report required")
        key = "handled-report:" + hashlib.sha256(json.dumps([owner, message_id], sort_keys=True).encode()).hexdigest()
        return request(profile, dict(owner, op="bus_ack", action="principal-report", key=key, message_id=message_id))["result"]
    pending = state["pending_ping"]
    if pending["owner"] != owner or pending["operation"] not in ("root-check", "root-standup-ping", "root-writeup-ping"):
        raise RuntimeError("no owner-bound operational ping")
    key = "principal-ping:" + hashlib.sha256(json.dumps([owner, pending["key"]], sort_keys=True).encode()).hexdigest()
    result = request(profile, dict(owner, op="bus_send", action="principal-ping", key=key,
                      model_thread_id=thread, ping_kind=pending["operation"],
                      body=profile["delivery_contracts"][pending["operation"]]))["result"]
    save(directory / ("principal-delivery-" + hashlib.sha256(key.encode()).hexdigest() + ".private.json"),
         dict(owner=owner, thread_id=thread, authority_command_key=pending["key"], actual_native_delivery=result))
    return result

def bootstrap(profile, journal, path):
    candidate = profile["owner"]
    request(profile, dict(candidate, op="admission_refresh"))
    response = request(profile, dict(candidate, op="acquire"))["result"]
    if response.get("read_only") is not False or response.get("holder") != candidate["actor"] or response.get("generation") != candidate["generation"]:
        raise RuntimeError("another root owns custody; preserve")
    owner = dict(candidate, epoch=response["epoch"])
    journal["owner"] = owner
    save(path, journal)
    # The next stage is persisted BEFORE its request; timeout remains held.
    def stage(name, body):
        journal["bootstrap_pending"] = {"stage": name, "request": body}
        save(path, journal)
        result = request(profile, body)
        journal["bootstrap_pending"] = None
        journal.setdefault("bootstrap_receipts", {})[name] = result
        save(path, journal)
        return result
    if journal.get("bootstrap_pending"):
        raise RuntimeError("uncertain bootstrap stage; reconcile exact prior receipt")
    fence = stage("fence", dict(owner, op="first_action", operation="root-fence-activate", payload={}))
    stage("start", dict(owner, op="bootstrap_start", operation="root-start", payload={}))
    # Actual model tool and provider item/completed are separate from native
    # capsule startup/fence activation/backend thread metadata.
    proof_path = pathlib.Path(profile["state_dir"]) / "model-evidence.private.json"
    until = time.monotonic() + 150
    proof = None
    next_refresh = time.monotonic() + 20
    while time.monotonic() < until:
        if proof_path.exists():
            candidate_proof = json.loads(proof_path.read_text())
            api_state=load_private_profile(pathlib.Path(profile['state_dir'])/'root-runtime.json')
            if candidate_proof.get("owner") == owner and (profile.get('runtime_mode')!='api-root' or (api_state.get('provider_turn_state')=='completed' and api_state.get('provider_pending_tools')=={})):
                proof = candidate_proof
                break
        if time.monotonic() >= next_refresh:
            refresh_owned(profile,owner)
            next_refresh = time.monotonic() + 20
        time.sleep(.5)
    if proof is None:
        raise RuntimeError("actual model ACK/tool not observed; remains elected-pending")
    key = "model-evidence:" + hashlib.sha256(json.dumps([owner, proof["model"]["first_tool"]["event_id"]], sort_keys=True).encode()).hexdigest()
    # The real provider may take longer than the 60s observation window.
    # Renew the pending owner and obtain fresh native resource/provider data
    # before the final fenced history/frontend mutation; no extra scheduler.
    refresh_owned(profile,owner)
    stage("model-evidence", dict(owner, op="model_evidence", key=key, payload={}))
    stage("activate", dict(owner, op="activate", ack_message=proof["model"]["first_tool"]["ack_message_id"],
          first_action_key=fence["result"]["first_action_key"], model_evidence_key=key))
    journal.update(active=True, desired_stopped=False)
    save(path, journal)
    return {"v": 1, "status": "ok", "activated": True}

def adopt_successor(profile, journal, path, result):
    native = json.loads((pathlib.Path(profile["state_dir"]) / "native-successor.private.json").read_text())["completed"]
    for key in ("actor", "generation", "root_tag"):
        if result.get(key) != native.get(key):
            raise RuntimeError("server successor does not match actual native factory")
    if result.get("project") != profile["project"] or result.get("role") != "root":
        raise RuntimeError("successor project/role mismatch")
    credential = result.get("credential", {})
    if set(credential) != {"identity_id", "token"} or not all(isinstance(value, str) and value for value in credential.values()):
        raise RuntimeError("native successor credential missing")
    owner = dict(project=profile["project"], role="root", actor=result["actor"], generation=result["generation"], epoch=1)
    # epoch1 here is an unelected candidate request field. Only acquire's actual
    # authority receipt can turn it into lease custody.
    replacement = dict(profile, actor=result["actor"], generation=result["generation"],
                       root_tag=result["root_tag"], credential=credential, owner=owner)
    journal["adoption_pending"] = replacement
    save(path, journal)
    save(PROFILE, replacement)
    journal.update(predecessor_owner=journal.get("owner"), owner=owner, active=False,
                   needs_successor=False, bootstrap_receipts={}, bootstrap_pending=None,
                   pending=None, adoption_pending=None)
    save(path, journal)
    return {"v": 1, "status": "ok", "new_native_candidate": True}

def scheduled_slot(mode, scheduled=True):
    if mode not in ("Check", "Standup", "Writeup"):
        return None
    if mode == "Check":
        return "check:" + str(int(time.time() // 1800))
    # Windows' maintained timezone database includes Berlin DST rules. No
    # caller-supplied clock, timezone or slot participates in this boundary.
    script = "$d=[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow,'W. Europe Standard Time'); @{date=$d.ToString('yyyy-MM-dd');hour=$d.Hour;minute=$d.Minute}|ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, check=True, timeout=10)
    clock = json.loads(result.stdout)
    due = 9 * 60 + (0 if mode == "Standup" else 30)
    now = clock["hour"] * 60 + clock["minute"]
    if now < due:
        raise RuntimeError("outside owned Berlin trigger")
    return mode + ":" + clock["date"]

def request(profile, body):
    context = ssl.create_default_context(cafile=profile["ca_certificate"])
    context.load_cert_chain(profile["client_certificate"], profile["client_key"])
    data = dict(body, v=1, credential=profile["credential"])
    target = profile["authority_url"].rstrip("/") + "/v1/role-control"
    req = urllib.request.Request(target, data=json.dumps(data).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=context, timeout=65) as response:
        result = json.load(response)
    if result.get("v") != 1 or result.get("status") != "ok":
        raise RuntimeError("authority pending, fenced or unavailable; preserve")
    return result

@contextlib.contextmanager
def journal_lock(directory):
    import msvcrt
    with (directory / "control.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

def run(mode, scheduled=False):
    profile = load_private_profile(PROFILE)
    owner = profile["owner"]  # Provisioned actual authority receipt, never CLI fields.
    if set(owner) != {"project", "role", "actor", "generation", "epoch"} or owner["actor"] != profile["actor"] or owner["generation"] != profile["generation"]:
        raise RuntimeError("missing exact trusted ownership binding")
    if mode == "Status":
        response = request(profile, dict(owner, op="inspect"))
        directory = pathlib.Path(profile["state_dir"])
        journal_path, state_path = directory / "control-journal.private.json", directory / "root-runtime.json"
        journal = json.loads(journal_path.read_text()) if journal_path.exists() else {}
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        current = journal.get("owner", owner)
        role = response.get("result", {})
        tuple_match=all(role.get(field) == current.get(other) for field, other in (("holder", "actor"), ("generation", "generation"), ("epoch", "epoch")))
        elected=valid_lease_tuple(role,current)
        alive = all(state.get(pid) and state.get(stamp) and recorded_process_state(state[pid], state[stamp]) == "alive"
                    for pid, stamp in (("pid", "process_creation_filetime"), ("frontend_pid", "frontend_creation_filetime"), ("viewer_pid", "viewer_creation_filetime")))
        if profile.get('runtime_mode')=='api-root':alive=recorded_api_custody(profile,state,current,recorded_process_state)
        return {"v": 1, "status": "ok", "mode": "Status", "elected_active": bool(elected and journal.get("active")),
                "owner_tuple_match":tuple_match,"lease_fresh":role.get('lease_fresh') is True,
                "root_running": bool(alive and state.get("model_launch_complete")), "reconciliation_required": bool(journal.get("pending") or journal.get("bootstrap_pending"))}
    directory = pathlib.Path(profile["state_dir"])
    with journal_lock(directory):
        path = directory / "control-journal.private.json"
        journal = json.loads(path.read_text()) if path.exists() else {}
        if mode=='Recover' and profile.get('runtime_mode')=='api-root' and journal.get('active'):
            current=journal.get('owner',owner)
            refresh_owned(profile,current)
            state=load_private_profile(directory/'root-runtime.json')
            return {'v':1,'status':'ok','custody_renewed':True,'dispatch_ready':dispatch_clear(state),
                    'pending_effect_preserved':bool(journal.get('pending') or journal.get('bootstrap_pending'))}
        if journal.get("adoption_pending"):
            replacement = journal["adoption_pending"]
            save(PROFILE, replacement)
            journal.update(owner=replacement["owner"], active=False, needs_successor=False,
                           bootstrap_receipts={}, bootstrap_pending=None, pending=None, adoption_pending=None)
            save(path, journal)
            return {"v": 1, "status": "ok", "native_profile_reconciled": True}
        owner = journal.get("owner", owner)
        if mode == "Reconcile":
            if journal.get("needs_successor"):
                receipt = request(profile, dict(owner, op="successor_status"))
                return adopt_successor(profile, journal, path, receipt["result"])
            pending = journal.get("pending") or (journal.get("bootstrap_pending") or {}).get("request")
            if pending is None:
                return request(profile, dict(owner, op="inspect"))
            # Reuse the exact serialized operation/key. Authority's durable
            # uncertain journal cannot execute it again or accept a new key.
            receipt = request(profile, pending)
            journal.update(pending=None, last_reconciled_receipt=receipt)
            if journal.get("bootstrap_pending"):
                phase = journal["bootstrap_pending"]["stage"]
                journal.setdefault("bootstrap_receipts", {})[phase] = receipt
                journal["bootstrap_pending"] = None
            save(path, journal)
            return receipt
        if journal.get("pending"):
            raise RuntimeError("uncertain prior operation; reconcile its existing key")
        if mode == "Recover" and journal.get("desired_stopped"):
            return {"v": 1, "status": "ok", "held": "intentional-stop"}
        if mode in ("Start", "Recover") and journal.get("active"):
            state = json.loads((directory / "root-runtime.json").read_text())
            backend_alive = bool(state.get("pid") and state.get("process_creation_filetime") and
                                 recorded_process_state(state["pid"], state["process_creation_filetime"]) == "alive")
            frontend_alive = bool(state.get("frontend_pid") and state.get("frontend_creation_filetime") and
                                  recorded_process_state(state["frontend_pid"], state["frontend_creation_filetime"]) == "alive")
            if profile.get('runtime_mode')=='api-root':frontend_alive=recorded_api_custody(profile,state,owner,recorded_process_state)
            if not backend_alive or not frontend_alive or state.get("model_launch_complete") is not True:
                journal.update(active=False, needs_successor=True)
                save(path, journal)
        if mode in ("Start", "Recover") and journal.get("needs_successor"):
            journal["pending"] = dict(owner, op="recovery_successor", payload={})
            save(path, journal)
            receipt = request(profile, journal["pending"])
            return adopt_successor(profile, journal, path, receipt["result"])
        if mode in ("Start", "Recover") and not journal.get("active"):
            return bootstrap(profile, journal, path)
        slot = scheduled_slot(mode, scheduled=scheduled)
        if slot and slot in journal.get("submitted_slots", []):
            return {"v": 1, "status": "ok", "already_submitted": True}
        # Renew is authority-validated and carries no self-asserted readiness.
        refresh_owned(profile,owner)
        if profile.get('runtime_mode')=='api-root' and mode in ('Check','Standup','Writeup','Stop','TestKill'):
            state=load_private_profile(directory/'root-runtime.json')
            if not dispatch_clear(state):raise RuntimeError('API provider/tool/history busy or unknown; no new effect')
        if mode == "Recover":
            state = json.loads((directory / "root-runtime.json").read_text())
            if not state.get("pid") or state.get("model_launch_complete") is not True:
                journal.update(active=False, needs_successor=True)
                save(path, journal)
                return {"v": 1, "status": "ok", "held": "replacement-native-custody-required"}
        operation = MODES[mode]
        payload = {}
        if mode in ("Stop", "TestKill"):
            state = json.loads((directory / "root-runtime.json").read_text())
            if state.get("launched_epoch") != owner["epoch"] or not state.get("pid"):
                raise RuntimeError("no exact newly owned kill target")
        counter = int(journal.get("counter", 0)) + 1
        key = hashlib.sha256(json.dumps([owner, mode, counter], sort_keys=True).encode()).hexdigest()
        body = dict(owner, op="execute", key=key, operation=operation, payload=payload)
        journal.update(counter=counter, pending=body)
        save(path, journal)
        result = request(profile, body)
        journal.update(pending=None, last_receipt=result, completed_at=time.time())
        if slot:
            # Model turn acceptance is scheduling evidence, not a principal
            # delivery or owner ACK. Keep those receipts separate.
            journal["submitted_slots"] = (journal.get("submitted_slots", []) + [slot])[-180:]
        if mode == "Stop":
            journal["desired_stopped"] = True
            journal.update(active=False, needs_successor=True)
        elif mode == "Start":
            journal["desired_stopped"] = False
        if mode == "TestKill":
            journal.update(active=False, needs_successor=True)
        save(path, journal)
        return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["Status", "Ack", "Deliver", "Reports", "Handled", "Reconcile"] + list(MODES))
    parser.add_argument("--scheduled", action="store_true", help="Task-owned invocation with Berlin daily catch-up")
    parser.add_argument("--message-id", help="Handled-only actual principal reply ID")
    args = parser.parse_args()
    try:
        if args.mode == "Ack":
            print(json.dumps(model_ack()))
            return
        if args.mode in ("Deliver", "Reports", "Handled"):
            print(json.dumps(model_proxy(args.mode, args.message_id)))
            return
        result = run(args.mode, scheduled=args.scheduled)
        # No profile/token/native IDs or raw authority result in public output.
        print(json.dumps(result if args.mode == "Status" else {"status": "ok", "mode": args.mode}))
    except Exception:
        print(json.dumps({"status": "held", "mode": args.mode, "reconciliation_required": True}))
        raise SystemExit(75)

if __name__ == "__main__":
    main()


