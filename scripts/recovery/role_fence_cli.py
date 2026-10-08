"""Bounded stdin adapter for the existing authenticated role authority.

No listener, scheduler, enrollment, local election fallback, or database creation.
The owner provisions an existing DB/bus, native bindings and reviewed fixed sink
commands. A transport failure is a hold, never permission to retry a new key.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from role_fence import CoordinatorFence, Owner

CANONICAL_CONFIG = Path(__file__).resolve().parents[2] / ".local" / "win35-root-authority" / "authority.json"


class ModelCustodyPending(PermissionError):
    """Native backend/fence exists but genuine model custody is not proven."""


def durable_sink(journal, key, message, effect):
    """Reserve before external mutation; ambiguous effects stay held on retry.

    This is at-most-once dispatch, not exactly-once completion. The existing
    owner reconciles an uncertain native receipt before any replacement intent.
    """
    body = json.dumps(message, sort_keys=True)
    with sqlite3.connect(journal, timeout=5) as db:
        db.execute("CREATE TABLE IF NOT EXISTS sink_receipts "
                   "(key TEXT PRIMARY KEY,body TEXT NOT NULL,result TEXT)")
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT body,result FROM sink_receipts WHERE key=?", (key,)).fetchone()
        if old:
            if old[0] != body:
                raise PermissionError("sink key intent conflict")
            return json.loads(old[1]) if old[1] else {"key": key, "state": "uncertain"}
        db.execute("INSERT INTO sink_receipts VALUES(?,?,NULL)", (key, body))
        db.commit()  # A process crash from here never replays the external call.
    result = effect()
    with sqlite3.connect(journal, timeout=5) as db:
        db.execute("UPDATE sink_receipts SET result=? WHERE key=?",
                   (json.dumps(result, sort_keys=True), key))
    return result


def private_json(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise PermissionError("regular private configuration required")
    st = p.stat()
    if os.name != "posix" or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600:
        raise PermissionError("server configuration must be owner-only POSIX 0600")
    return json.loads(p.read_text(encoding="utf-8"))


def pinned_file(path, digest):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("absolute regular pinned source required")
    if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        raise PermissionError("installed source pin mismatch")
    return p


def active_model(config, owner):
    """Read immutable accepted evidence; caller must already hold a role guard."""
    with sqlite3.connect(Path(config["authority_db"]).as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT first_action FROM activation_receipts WHERE project=? AND role=? AND epoch=?", (owner.project, owner.role, owner.epoch)).fetchone()
    if not row:
        raise PermissionError("actual model custody required")
    with sqlite3.connect(config["sink_journal"]) as db:
        receipt = db.execute("SELECT body,result FROM sink_receipts WHERE key=?", (row[0],)).fetchone()
    if not receipt or not receipt[1]:
        raise PermissionError("actual model receipt unavailable")
    intent, result = json.loads(receipt[0]), json.loads(receipt[1])
    expected_owner = dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args()))
    model = result.get("evidence", {}).get("model", {})
    if (intent.get("owner") != expected_owner or intent.get("operation") != owner.role + "-model-evidence"
            or result.get("state") not in ("ok", "completed") or model.get("native_actor") != owner.actor
            or not isinstance(model.get("thread_id"), str) or not 1 <= len(model["thread_id"]) <= 128):
        raise PermissionError("exact accepted model CID required")
    return model["thread_id"]


def build(config, channel_dispatch=None, proxy=None):
    source = pinned_file(config["authority_source"], config["authority_sha256"])
    source_root = source.parents[1]
    sys.path.insert(0, str(source_root))
    from coordination.role_failover import RoleAuthority
    from coordination.bus import FileBus
    import coordination.role_failover as installed
    if Path(installed.__file__).resolve() != source.resolve():
        raise PermissionError("authority module resolved outside pinned source")
    import coordination.bus as installed_bus
    bus_source = pinned_file(config["bus_source"], config["bus_sha256"])
    if Path(installed_bus.__file__).resolve() != bus_source.resolve():
        raise PermissionError("Bus module resolved outside pinned source")
    database = Path(config["authority_db"])
    if not database.is_absolute() or database.is_symlink() or not database.is_file():
        raise PermissionError("existing authoritative DB required; no creation allowed")
    # Read-only schema probe before RoleAuthority's boot/clock transaction.
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.execute("SELECT holder,epoch FROM roles LIMIT 1").fetchall()
    bus_root = Path(config["bus_store"])
    if not bus_root.is_absolute() or not all((bus_root / n).is_file()
                                             for n in ("identities.json", "tokens.json")):
        raise PermissionError("existing enrolled bus required; no creation allowed")
    bus = FileBus(bus_root)
    authority = RoleAuthority(database)

    def authenticate(credential, owner):
        binding = config["bindings"].get(owner.actor)
        if not binding or (owner.project, owner.role, owner.generation) != (
                binding["project"], binding["role"], binding["generation"]):
            return False
        if credential.get("identity_id") != binding["bus_identity"]:
            return False
        ident = bus._auth(credential["identity_id"], credential.get("token"))
        if (ident["device_id"], ident["project_id"]) != (binding["host"], owner.project):
            return False
        # Host/session/incarnation comes from owner-installed binding and the
        # trusted runtime observation, never from request booleans or PID alone.
        with authority._tx() as db:
            row = db.execute("SELECT host,generation FROM agents WHERE id=?",
                             (owner.actor,)).fetchone()
            return row is not None and (row["host"], row["generation"]) == (
                binding["host"], binding["generation"])

    operations = {}
    journal = Path(config["sink_journal"])
    if not journal.is_absolute() or journal.is_symlink() or not journal.is_file():
        raise PermissionError("owner-provisioned private sink journal required")
    for entry in config.get("operations", []):
        role, name = entry["role"], entry["name"]
        if entry.get("transport") == "managed-proxy":
            if role != "root" or name not in ("root-principal-send", "root-principal-report-ack") or type(entry["timeout"]) is not int or not 1 <= entry["timeout"] <= 30:
                raise PermissionError("fixed managed proxy operation required")
            timeout = entry["timeout"]
            if name == "root-principal-send":
                def validate(p):
                    return (isinstance(p, dict) and set(p) == {"model_thread_id", "ping_kind", "body"}
                        and p["ping_kind"] in ("root-check", "root-standup-ping", "root-writeup-ping")
                        and isinstance(p["body"], str) and 1 <= len(p["body"]) <= 2048)
            else:
                def validate(p):
                    return isinstance(p, dict) and set(p) == {"message_id"} and isinstance(p["message_id"], str) and 1 <= len(p["message_id"]) <= 128
            def effect(key, payload, owner, name=name, timeout=timeout):
                if proxy is None:
                    raise ConnectionError("managed native proxy unavailable")
                native_owner = dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args()))
                message = {"v": 1, "key": key, "operation": name, "owner": native_owner, "payload": payload}
                if name == "root-principal-send":
                    if payload["model_thread_id"] != active_model(config, owner):
                        raise PermissionError("actual active model CID mismatch")
                    return durable_sink(journal, key, message, lambda: proxy.dispatch(native_owner, key,
                        payload["model_thread_id"], payload["ping_kind"], payload["body"], timeout=timeout))
                return durable_sink(journal, key, message, lambda: proxy.dispatch_ack(native_owner, key, payload["message_id"], timeout=timeout))
            operations[(role, name)] = (validate, effect)
            continue
        if entry.get("transport") == "native-channel":
            if role not in ("root", "principal") or not 1 <= entry["timeout"] <= 60:
                raise ValueError("fixed bounded native channel operation required")
            expected, timeout = entry["payload"], entry["timeout"]
            def effect(key, payload, owner, name=name, timeout=timeout):
                if channel_dispatch is None:
                    raise ConnectionError("native channel unavailable; no fallback")
                message = {"v": 1, "key": key, "operation": name,
                    "owner": {"project": owner.project, "role": owner.role, "actor": owner.actor,
                              "generation": owner.generation, "epoch": owner.epoch}, "payload": payload}
                return durable_sink(journal, key, message,
                                    lambda: channel_dispatch(owner, message, timeout))
            operations[(role, name)] = (lambda p, expected=expected: p == expected, effect)
            continue
        argv = entry["argv"]
        if role not in ("root", "principal") or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError("fixed role operation argv required")
        pinned_file(argv[0], entry["executable_sha256"])
        if entry.get("idempotency_contract") != "key-durable-v1":
            raise PermissionError("reviewed durable sink idempotency required")
        timeout = entry["timeout"]
        if type(timeout) is not int or not 1 <= timeout <= 60:
            raise ValueError("bounded sink timeout required")
        expected = entry["payload"]
        pins = dict(entry.get("file_pins", {}))
        pins[argv[0]] = entry["executable_sha256"]
        for path, digest in pins.items():
            pinned_file(path, digest)

        def effect(key, payload, owner, argv=tuple(argv), timeout=timeout, pins=pins, name=name):
            message = {"v": 1, "key": key, "operation": name, "owner": {
                "project": owner.project, "role": owner.role, "actor": owner.actor,
                "generation": owner.generation, "epoch": owner.epoch}, "payload": payload}
            def run():
                for path, digest in pins.items():
                    pinned_file(path, digest)
                completed = subprocess.run(argv, input=json.dumps(message), text=True,
                                           capture_output=True, timeout=timeout, check=False)
                if completed.returncode:
                    raise RuntimeError("fixed sink failed; reconcile original key before retry")
                result = json.loads(completed.stdout)
                if result.get("key") != key:
                    raise RuntimeError("sink receipt key mismatch; reconcile before retry")
                return result
            return durable_sink(journal, key, message, run)
        operations[(role, name)] = (lambda p, expected=expected: p == expected, effect)
    def semantic_message(message_id, owner, action, model_thread=None):
        binding = config["bindings"].get(owner.actor)
        if not binding:
            return False
        # The pinned Bus writes messages keyed by native message_id after its
        # sender-token authentication. Caller-provided message bodies are ignored.
        message = bus._read(bus._messages, {}).get(message_id)
        data = message.get("data", {}) if message else {}
        expected = {"action": action, "project": owner.project, "role": owner.role,
                    "actor": owner.actor, "generation": owner.generation, "epoch": owner.epoch}
        if model_thread is not None:
            expected["model_thread_id"] = model_thread
        if not message:
            return False
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(message["created_at"].replace("Z", "+00:00"))).total_seconds()
        return bool(message.get("body") and message["sender_id"] == binding["bus_identity"]
                    and message["recipient_id"] == config["control_bus_identity"]
                    and message["kind"] == "role-control" and 0 <= age <= 300 and data == expected)

    def handover(old, new, evidence):
        return bool(isinstance(evidence, dict)
                    and semantic_message(evidence.get("checkpoint"), old, "handover-checkpoint")
                    and semantic_message(evidence.get("ack"), new, "handover-ack"))

    fence = CoordinatorFence(authority, authenticate, operations, handover)
    fence.semantic_message = semantic_message
    return authority, fence


def handle(config, request, channel_dispatch=None, *, private_delivery=False, proxy=None):
    if request.get("v") != 1:
        raise ValueError("request version required")
    authority, fence = build(config, channel_dispatch, proxy)
    owner = Owner(*(request[k] for k in ("project", "role", "actor", "generation", "epoch")))
    credential = request["credential"]
    fence._identity(credential, owner)
    op = request["op"]
    if config["bindings"][owner.actor].get("retired") and op not in ("inspect", "bus_inbox", "successor_status"):
        raise PermissionError("retired native actor is read-only")
    if op == "inspect":
        result = authority.role_state(owner.project, owner.role)
    elif op in ("recovery_successor", "successor_status"):
        from role_fence_enrollment import enroll_successor, successor_key
        if not private_delivery:
            raise PermissionError("successor credentials require the scoped private mTLS transport")
        if owner.role != "root":
            raise PermissionError("only managed new root succession is installed")
        key = successor_key(owner)
        if op == "successor_status":
            record = config.get("successors", {}).get(key)
            if not record or record.get("predecessor_owner") != dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args())):
                raise PermissionError("exact recorded successor unavailable")
            with authority._tx() as db:
                row = db.execute("SELECT host,generation FROM agents WHERE id=?", (record["actor"],)).fetchone()
            if row is None:
                result = {"state": "uncertain", "reason": "owner_server_startup_reconciliation_required"}
            elif (row["host"], row["generation"]) != (config["bindings"][record["actor"]]["host"], record["generation"]):
                raise PermissionError("recorded successor authority conflict")
            else:
                result = record
            return {"v": 1, "status": "pending" if result.get("state") == "uncertain" else "ok", "result": result}
        if op == "recovery_successor":
            fence.execute(credential, owner, key, "root-native-successor", {})
        with sqlite3.connect(config["sink_journal"]) as db:
            row = db.execute("SELECT body,result FROM sink_receipts WHERE key=?", (key,)).fetchone()
        if not row or not row[1]:
            raise PermissionError("original successor operation remains uncertain")
        intent, receipt = json.loads(row[0]), json.loads(row[1])
        if intent != {"v": 1, "key": key, "operation": "root-native-successor",
                "owner": dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args())), "payload": {}}:
            raise PermissionError("exact durable native successor intent required")
        result = enroll_successor(CANONICAL_CONFIG, authority, owner, receipt)
    elif op == "admission_refresh":
        # Eligibility comes only from the reviewed authenticated host consumer.
        # This read-only probe must also work before a candidate owns a lease.
        operation = owner.role + "-admission"
        entry = next((e for e in config["operations"] if (e["role"], e["name"]) == (owner.role, operation)), None)
        binding = config["bindings"][owner.actor]
        if entry is None or entry.get("read_only") is not True or entry.get("transport") != "native-channel":
            raise PermissionError("reviewed read-only native admission operation required")
        validate, effect = fence.operations[(owner.role, operation)]
        if validate({}) is not True:
            raise PermissionError("fixed empty admission payload required")
        with authority._tx() as db:
            priority = db.execute("SELECT priority FROM agents WHERE id=?", (owner.actor,)).fetchone()[0]
        try:
            observed = effect("admission:" + str(uuid.uuid4()), {}, owner)
            admission = observed["evidence"]["admission"]
            if observed.get("state") not in ("ok", "completed") or any(type(admission.get(k)) is not bool for k in ("ready", "draft", "quota_ok")):
                raise PermissionError("unknown native admission remains held")
            if (admission.get("actor"), admission.get("host"), admission.get("generation")) != (owner.actor, binding["host"], owner.generation):
                raise PermissionError("native admission binding mismatch")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(admission["observed_at"].replace("Z", "+00:00"))).total_seconds()
            # Observed Win35/authority clock skew is subsecond. Admit at most
            # one future second; retain the 30-second age and live callback bounds.
            if not -1 <= age <= 30:
                raise PermissionError("fresh native admission evidence required")
            authority.observe(owner.actor, binding["host"], owner.generation,
                ready=admission["ready"], draft=admission["draft"], quota_ok=admission["quota_ok"], priority=priority)
            result = {"admission": "eligible" if admission["ready"] and not admission["draft"] and admission["quota_ok"] else "held"}
        except Exception:
            authority.observe(owner.actor, binding["host"], owner.generation, ready=False, draft=True, quota_ok=False, priority=priority)
            raise
    elif op == "acquire":
        result = authority.tick(owner.project, owner.role)
        result["read_only"] = (result.get("holder"), result.get("generation")) != (
            owner.actor, owner.generation)
    elif op == "renew":
        result = fence.renew(credential, owner)
    elif op == "execute":
        result = fence.execute(credential, owner, request["key"], request["operation"], request["payload"])
    elif op == "first_action":
        operation = request["operation"]
        entry = next((e for e in config["operations"]
                      if (e["role"], e["name"]) == (owner.role, operation)), None)
        if (entry is None or entry.get("first_action") is not True
                or operation != owner.role + "-fence-activate"):
            raise PermissionError("fixed first-action operation required")
        validate, effect = fence.operations[(owner.role, operation)]
        if validate(request["payload"]) is not True:
            raise ValueError("invalid first action payload")
        key = "first-action:" + ":".join(map(str, owner.args()))
        body = {"operation": operation, "payload": request["payload"], "kind": "first_action"}
        result = authority.guarded_effect(*owner.args(), key, body,
            lambda k, p: effect(k, p["payload"], owner))
        result = {**result, "first_action_key": key}
    elif op == "activate":
        model_key = request["model_evidence_key"]
        with sqlite3.connect(config["sink_journal"]) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sink_receipts'").fetchone():
                raise ModelCustodyPending("actual model-thread first-tool receipt required")
            row = db.execute("SELECT body,result FROM sink_receipts WHERE key=?", (model_key,)).fetchone()
            expected_owner = dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args()))
            if not row or not row[1]:
                raise ModelCustodyPending("actual model-thread first-tool receipt required")
            intent, observed = json.loads(row[0]), json.loads(row[1])
            model = observed.get("evidence", {}).get("model", {})
            tool = model.get("first_tool", {})
            if (intent.get("owner") != expected_owner or intent.get("operation") != owner.role + "-model-evidence"
                    or model.get("native_actor") != owner.actor or not model.get("thread_id")
                    or not tool.get("event_id") or tool.get("exit_code") != 0
                    or tool.get("ack_message_id") != request["ack_message"]):
                raise ModelCustodyPending("model CID/tool/native actor/ACK linkage missing")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(tool["completed_at"].replace("Z", "+00:00"))).total_seconds()
            if not 0 <= age <= 300:
                raise ModelCustodyPending("fresh completed model tool required")
        if not fence.semantic_message(request["ack_message"], owner, "role-ack", model["thread_id"]):
            raise PermissionError("genuine semantic model-thread custody ACK required")
        expected_key = "first-action:" + ":".join(map(str, owner.args()))
        if request["first_action_key"] != expected_key:
            raise PermissionError("exact actual first-action receipt required")
        with authority._tx() as db:
            receipt = db.execute("SELECT * FROM actions WHERE key=?", (expected_key,)).fetchone()
            if (receipt is None or receipt["epoch"] != owner.epoch
                    or json.loads(receipt["payload"]).get("kind") != "first_action"):
                raise PermissionError("completed guarded first action missing")
        with sqlite3.connect(config["sink_journal"]) as db:
            receipt = db.execute("SELECT result FROM sink_receipts WHERE key=?", (expected_key,)).fetchone()
            if receipt is None or receipt[0] is None or json.loads(receipt[0]).get("state") not in ("ok", "completed"):
                raise PermissionError("first action remains uncertain")
            activation = json.loads(receipt[0]).get("evidence", {}).get("fence_activation")
            if activation != dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args())):
                raise PermissionError("native action-lock/highest-epoch activation receipt required")
        result = authority.activation(*owner.args(), role_ack=request["ack_message"], first_action=model_key)
    elif op == "model_evidence":
        operation = owner.role + "-model-evidence"
        validate, effect = fence.operations[(owner.role, operation)]
        if validate(request["payload"]) is not True:
            raise PermissionError("fixed read-only model evidence operation required")
        key = request["key"]
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise ValueError("bounded evidence attempt key required")
        body = {"operation": operation, "payload": request["payload"]}
        result = authority.guarded_effect(*owner.args(), key, body,
            lambda k, p: effect(k, p["payload"], owner))
    elif op == "bootstrap_start":
        if owner.role != "root" or request.get("operation") != "root-start":
            raise PermissionError("only fixed new root bootstrap may precede model custody")
        key = "first-action:" + ":".join(map(str, owner.args()))
        with sqlite3.connect(config["sink_journal"]) as db:
            row = db.execute("SELECT result FROM sink_receipts WHERE key=?", (key,)).fetchone()
            if not row or not row[0] or json.loads(row[0]).get("evidence", {}).get("fence_activation") != dict(zip(
                    ("project", "role", "actor", "generation", "epoch"), owner.args())):
                raise PermissionError("native fencing activation required before bootstrap")
        validate, effect = fence.operations[("root", "root-start")]
        if validate(request["payload"]) is not True:
            raise PermissionError("fixed native root bootstrap payload required")
        key = "bootstrap-root-start:" + ":".join(map(str, owner.args()))
        body = {"operation": "root-start", "payload": request["payload"]}
        result = authority.guarded_effect(*owner.args(), key, body,
            lambda k, p: effect(k, p["payload"], owner))
    elif op == "handback":
        successor = Owner(*(request["successor"][k] for k in (
            "project", "role", "actor", "generation", "epoch")))
        result = fence.handback(credential, owner, successor, request["evidence"])
    elif op == "bus_inbox":
        from coordination.bus import FileBus
        bus = FileBus(config["bus_store"])
        result = {"messages": [m.public() if hasattr(m, "public") else m.__dict__ for m in
            bus.inbox(credential["identity_id"], credential["token"], unread_only=True)][:20]}
        if proxy is not None and owner.role == "root" and not config["bindings"][owner.actor].get("retired"):
            activation = authority.activation(*owner.args())
            if not activation.get("role_ack") or not activation.get("first_action"):
                raise PermissionError("active root custody required for managed reports")
            result["proxy_reports"] = proxy.read_reports(dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args())))
    elif op == "bus_ack":
        if request.get("action") != "principal-report" or owner.role != "root":
            raise PermissionError("only managed principal reports may be handled")
        result = fence.execute(credential, owner, request["key"], "root-principal-report-ack", {"message_id": request["message_id"]})
    elif op == "bus_send":
        from coordination.bus import FileBus
        action = request["action"]
        if action == "principal-ping":
            if owner.role != "root":
                raise PermissionError("only managed root principal pings are installed")
            result = fence.execute(credential, owner, request["key"], "root-principal-send", {
                "model_thread_id": request["model_thread_id"], "ping_kind": request["ping_kind"], "body": request["body"]})
            return {"v": 1, "status": "pending" if result.get("state") == "uncertain" else "ok", "result": result}
        if action not in ("role-ack", "handover-checkpoint", "handover-ack"):
            raise PermissionError("only own semantic role signals allowed")
        if action == "role-ack":
            authority.authorize(*owner.args())
        data = {"action": action, **dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args()))}
        if action == "role-ack":
            data["model_thread_id"] = request["model_thread_id"]
        body = request["body"]
        if not isinstance(body, str) or not 1 <= len(body) <= 1024:
            raise ValueError("bounded own semantic ACK required")
        message = FileBus(config["bus_store"]).send(sender_id=credential["identity_id"], token=credential["token"],
            recipient_id=config["control_bus_identity"], body=body, data=data, kind="role-control",
            idempotency_key=request["key"])
        result = {"message_id": message.message_id}
    else:
        raise PermissionError("unsupported operation; native custody adapter required")
    return {"v": 1, "status": "pending" if result.get("state") == "uncertain" else "ok",
            "role": owner.role, "result": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()  # No client-selected server profile or command route.
    try:
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            raise ValueError("bounded request required")
        response = handle(private_json(CANONICAL_CONFIG), json.loads(raw))
    except ModelCustodyPending:
        print(json.dumps({"v": 1, "status": "pending", "reason": "model_thread_ack_and_first_tool_pending"}))
        return 1
    except Exception:
        # Unknown authority, clock hold, partition, stale epoch and auth failure
        # all stop mutations. Details stay in owner-controlled local diagnostics.
        print(json.dumps({"v": 1, "status": "fenced", "reason": "authority_or_sink_hold"}))
        return 1
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    sys.exit(main())
