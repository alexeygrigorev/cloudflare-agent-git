#!/usr/bin/env python3
"""Execution engine for sessionless FileBus enrollment and message exchange.

Enrolls model-worker-01 on FileBus with:
1. session_id=None (bus-native, zero aplexer interactive session dependency).
2. Mode 0600 credentials file written atomically.
3. Zero inherited head or aplexer tokens (verified via reject_head_cred_inheritance and token isolation).
4. Handshake message dispatch, inbox polling, and read ACK on FileBus store.
5. Bidirectional correlated reply and ACK exchange.
6. Emits verified execution receipt at research/antigravity/recovery/RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01.json.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Workspace and Path configuration
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AGENT_BUS_ROOT = Path("/home/alexey/git/agent-bus")
if AGENT_BUS_ROOT.is_dir() and str(AGENT_BUS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_BUS_ROOT))

from coordination.bus import BusError, BusIdentity, FileBus
from coordination.worker_bus import SessionlessWorkerBus
from scripts.coordination.agent_bus_transport import (
    ack_message,
    enroll_agent,
    poll_messages,
    reject_head_cred_inheritance,
    reply_message,
    send_message,
)

DEFAULT_STORE = REPO_ROOT / ".local" / "bus_store"
DEFAULT_HEAD_CRED = REPO_ROOT / ".local" / "bus_client_creds.json"
RECEIPT_FILE = REPO_ROOT / "research" / "antigravity" / "recovery" / "RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01.json"
SCRATCH_DIR = REPO_ROOT / ".local" / "scratch" / "sessionless-model-enrollment"


def get_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_sessionless_model_enrollment(
    store_path: Path = DEFAULT_STORE,
    head_cred_path: Path = DEFAULT_HEAD_CRED,
    receipt_output_path: Path = RECEIPT_FILE,
    scratch_root: Path = SCRATCH_DIR,
) -> Dict[str, Any]:
    """Execute sessionless enrollment, handshake message exchange, and verification."""
    # Ensure scratch and isolate TMPDIR (zero net /tmp growth)
    scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    scratch_root.chmod(0o700)
    tmp_scratch = scratch_root / "tmp"
    tmp_scratch.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp_scratch.chmod(0o700)

    os.environ["TMPDIR"] = str(tmp_scratch)
    os.environ["TMP"] = str(tmp_scratch)
    os.environ["TEMP"] = str(tmp_scratch)

    store_path = store_path.resolve()
    store_path.mkdir(parents=True, exist_ok=True, mode=0o700)

    verification_checks: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 1. Head Credential Audit & Aplexer Token Injection Resistance
    # -------------------------------------------------------------------------
    # Load head credentials for initiator
    if head_cred_path.exists():
        head_cred_raw = json.loads(head_cred_path.read_text(encoding="utf-8"))
        head_id = head_cred_raw["identity_id"]
        head_token = head_cred_raw["token"]
        head_agent = head_cred_raw["agent_name"]
        head_project = head_cred_raw.get("project_id", "agent-bus")
    else:
        # Self-bootstrap coordinator if head cred file not present
        head_bus = FileBus(store_path)
        head_ident, head_token = head_bus.register(
            agent_name="ant-head-initiator",
            device_id="desktop-orchestrator",
            project_id="agent-bus",
        )
        head_id = head_ident.identity_id
        head_agent = head_ident.agent_name
        head_project = head_ident.project_id
        head_cred_raw = {
            "identity_id": head_id,
            "agent_name": head_agent,
            "device_id": "desktop-orchestrator",
            "project_id": head_project,
            "token": head_token,
        }

    head_token_sha256 = compute_sha256_bytes(head_token.encode("utf-8"))

    # Deliberately pollute environment with APLEXER tokens to verify immunity
    os.environ["APLEXER_SESSION_ID"] = "forbidden-ambient-aplexer-session-token-9999"
    os.environ["APLEXER_PORT"] = "8888"

    # -------------------------------------------------------------------------
    # 2. Sessionless FileBus Enrollment: model-worker-01
    # -------------------------------------------------------------------------
    target_cred_path = store_path / "credentials" / "model-worker-01.cred.json"
    cred_data, saved_cred_str = enroll_agent(
        store_path=store_path,
        agent_name="model-worker-01",
        device_id="linux-worker-01",
        project_id=head_project,
        task_id="task-model-worker-handshake-01",
        cred_path=target_cred_path,
    )
    saved_cred_file = Path(saved_cred_str)

    # Ensure credential has both flat and nested keys for compatibility with both
    # agent_bus_transport and SessionlessWorkerBus.from_credentials
    ident = cred_data["identity"]
    worker_id = ident["identity_id"]
    worker_token = cred_data["token"]
    worker_token_sha256 = compute_sha256_bytes(worker_token.encode("utf-8"))

    flat_compatible_cred = {
        "identity_id": worker_id,
        "agent_name": ident["agent_name"],
        "device_id": ident["device_id"],
        "project_id": ident["project_id"],
        "task_id": ident.get("task_id"),
        "parent_id": ident.get("parent_id"),
        "kind": ident.get("kind", "bus-agent"),
        "created_at": ident.get("created_at"),
        "session_id": None,
        "identity": ident,
        "token": worker_token,
        "store": str(store_path),
    }

    # Write back atomically with mode 0600
    tmp_path = saved_cred_file.with_name(f"{saved_cred_file.name}.tmp.{uuid.uuid4().hex}")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(flat_compatible_cred, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(str(tmp_path), 0o600)
        os.replace(str(tmp_path), str(saved_cred_file))
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    cred_data = flat_compatible_cred

    # Check 2.1: Credential file mode 0600
    cred_mode = stat.S_IMODE(saved_cred_file.stat().st_mode)
    check_mode_pass = cred_mode == 0o600
    verification_checks["credential_file_mode_0600"] = {
        "status": "PASS" if check_mode_pass else "FAIL",
        "path": str(saved_cred_file),
        "actual_mode": oct(cred_mode),
        "expected_mode": "0o600",
    }
    assert check_mode_pass, f"Credential file mode {oct(cred_mode)} != 0o600"

    # Check 2.2: session_id is None
    ident = cred_data["identity"]
    worker_id = ident["identity_id"]
    worker_token = cred_data["token"]
    worker_token_sha256 = compute_sha256_bytes(worker_token.encode("utf-8"))

    check_sessionless_pass = (
        ident.get("session_id") is None
        and ident.get("agent_name") == "model-worker-01"
        and ident.get("project_id") == head_project
        and ident.get("identity_id") != os.environ.get("APLEXER_SESSION_ID")
    )
    verification_checks["sessionless_identity_null_session_id"] = {
        "status": "PASS" if check_sessionless_pass else "FAIL",
        "agent_name": ident.get("agent_name"),
        "identity_id": worker_id,
        "session_id": ident.get("session_id"),
        "expected_session_id": None,
        "aplexer_session_ignored": True,
    }
    assert check_sessionless_pass, f"Identity session_id is not None: {ident.get('session_id')}"

    # Check 2.3: Zero inherited head or aplexer tokens
    check_no_head_token = (
        worker_token != head_token
        and worker_token_sha256 != head_token_sha256
        and "forbidden-ambient-aplexer" not in worker_token
    )
    verification_checks["distinct_token_no_head_inheritance"] = {
        "status": "PASS" if check_no_head_token else "FAIL",
        "worker_token_sha256": worker_token_sha256,
        "head_token_sha256": head_token_sha256,
        "tokens_distinct": check_no_head_token,
        "zero_head_tokens_inherited": True,
    }
    assert check_no_head_token, "Worker token matched head token or aplexer token!"

    # Check 2.4: reject_head_cred_inheritance validation
    # Verify worker cred data passes clean inspection
    head_cred_leak = False
    try:
        reject_head_cred_inheritance(cred_data, reject=True)
    except ValueError:
        head_cred_leak = True

    # Test negative injection: verify reject_head_cred_inheritance blocks leaks
    negative_sample = copy.deepcopy(cred_data)
    negative_sample["head_token"] = head_token
    neg_caught = False
    try:
        reject_head_cred_inheritance(negative_sample, reject=True)
    except ValueError:
        neg_caught = True

    check_guard_pass = (not head_cred_leak) and neg_caught
    verification_checks["head_cred_inheritance_guard"] = {
        "status": "PASS" if check_guard_pass else "FAIL",
        "worker_cred_clean": not head_cred_leak,
        "negative_synthetic_leak_caught": neg_caught,
    }
    assert check_guard_pass, "Head cred inheritance guard failed validation"

    # Check 2.5: NamespacedId renders dash '-' for sessionless
    worker_bus_client = SessionlessWorkerBus.from_credentials(store=store_path, cred=saved_cred_file)
    nid = worker_bus_client.namespaced_id
    rendered_nid = nid.render()
    check_nid_pass = nid.session_id is None and "/-/" in rendered_nid
    verification_checks["namespaced_id_renders_dash"] = {
        "status": "PASS" if check_nid_pass else "FAIL",
        "rendered": rendered_nid,
        "session_id": nid.session_id,
        "expected_session_delimiter": "/-/",
    }
    assert check_nid_pass, f"NamespacedId does not render '-' for sessionless: {rendered_nid}"

    # -------------------------------------------------------------------------
    # 3. Message Exchange: Handshake Send
    # -------------------------------------------------------------------------
    handshake_idempotency_key = f"handshake-probe-{uuid.uuid4().hex[:12]}"
    handshake_payload = {
        "protocol": "FileBus",
        "operation": "HANDSHAKE_PROBE",
        "sender": head_agent,
        "recipient": "model-worker-01",
        "sessionless": True,
        "timestamp": get_utc_now(),
    }

    handshake_msg = send_message(
        store_path=store_path,
        cred=head_cred_raw,
        recipient_id=worker_id,
        body="HANDSHAKE_INIT: model-worker-01 sessionless activation probe",
        data=handshake_payload,
        kind="handshake",
        idempotency_key=handshake_idempotency_key,
        reject_head_cred=True,
    )
    handshake_msg_id = handshake_msg["message_id"]

    check_send_pass = (
        handshake_msg["sender_id"] == head_id
        and handshake_msg["recipient_id"] == worker_id
        and handshake_msg["delivered_at"] is not None
        and handshake_msg["acked_at"] is None
    )
    verification_checks["handshake_dispatch"] = {
        "status": "PASS" if check_send_pass else "FAIL",
        "message_id": handshake_msg_id,
        "sender_id": head_id,
        "recipient_id": worker_id,
        "delivered_at": handshake_msg["delivered_at"],
    }
    assert check_send_pass, "Handshake dispatch validation failed"

    # -------------------------------------------------------------------------
    # 4. Message Exchange: Poll & ACK
    # -------------------------------------------------------------------------
    # Poll unread inbox as model-worker-01
    unread_before = poll_messages(store_path=store_path, cred=saved_cred_file, unread_only=True)
    check_poll_pass = any(m["message_id"] == handshake_msg_id for m in unread_before)
    verification_checks["worker_inbox_poll"] = {
        "status": "PASS" if check_poll_pass else "FAIL",
        "messages_found": len(unread_before),
        "target_message_found": check_poll_pass,
    }
    assert check_poll_pass, f"Message {handshake_msg_id} not found in model-worker-01 inbox"

    # Execute read ACK
    ack_result = ack_message(store_path=store_path, cred=saved_cred_file, message_id=handshake_msg_id)
    check_ack_call_pass = ack_result is True

    # Verify unread inbox is now 0 for this message (durable cursor progression)
    unread_after = poll_messages(store_path=store_path, cred=saved_cred_file, unread_only=True)
    check_cursor_pass = not any(m["message_id"] == handshake_msg_id for m in unread_after)

    # Verify store messages.json contains acked_at
    all_worker_msgs = poll_messages(store_path=store_path, cred=saved_cred_file, unread_only=False)
    matched_acked_msg = next((m for m in all_worker_msgs if m["message_id"] == handshake_msg_id), None)
    check_acked_stored = (
        matched_acked_msg is not None
        and matched_acked_msg.get("acked_at") is not None
    )

    check_ack_pass = check_ack_call_pass and check_cursor_pass and check_acked_stored
    verification_checks["worker_read_ack_and_cursor_advancement"] = {
        "status": "PASS" if check_ack_pass else "FAIL",
        "message_id": handshake_msg_id,
        "ack_call_result": ack_result,
        "unread_cleared": check_cursor_pass,
        "acked_at": matched_acked_msg.get("acked_at") if matched_acked_msg else None,
    }
    assert check_ack_pass, "Worker read ACK or cursor advancement validation failed"

    # -------------------------------------------------------------------------
    # 5. Message Exchange: Correlated Reply and Head Ingest/ACK
    # -------------------------------------------------------------------------
    reply_idempotency_key = f"handshake-reply-{uuid.uuid4().hex[:12]}"
    reply_payload = {
        "protocol": "FileBus",
        "operation": "HANDSHAKE_RESPONSE",
        "worker": "model-worker-01",
        "sessionless": True,
        "status": "active_and_enrolled",
        "zero_head_tokens": True,
        "timestamp": get_utc_now(),
    }

    reply_msg = reply_message(
        store_path=store_path,
        cred=saved_cred_file,
        message_id=handshake_msg_id,
        body="HANDSHAKE_ACK: sessionless model-worker-01 active with zero head tokens",
        data=reply_payload,
        idempotency_key=reply_idempotency_key,
        reject_head_cred=True,
    )
    reply_msg_id = reply_msg["message_id"]

    check_reply_pass = (
        reply_msg["sender_id"] == worker_id
        and reply_msg["recipient_id"] == head_id
        and reply_msg["reply_to"] == handshake_msg_id
        and reply_msg["kind"] == "reply"
    )
    verification_checks["worker_correlated_reply"] = {
        "status": "PASS" if check_reply_pass else "FAIL",
        "reply_message_id": reply_msg_id,
        "correlated_reply_to": reply_msg.get("reply_to"),
        "sender_id": worker_id,
        "recipient_id": head_id,
    }
    assert check_reply_pass, "Worker reply validation failed"

    # Head polls and ACKs the reply
    head_inbox = poll_messages(store_path=store_path, cred=head_cred_raw, unread_only=True)
    check_head_poll = any(m["message_id"] == reply_msg_id for m in head_inbox)
    head_ack_result = ack_message(store_path=store_path, cred=head_cred_raw, message_id=reply_msg_id)

    check_head_ack_pass = check_head_poll and (head_ack_result is True)
    verification_checks["head_reply_ingest_and_ack"] = {
        "status": "PASS" if check_head_ack_pass else "FAIL",
        "reply_message_id": reply_msg_id,
        "head_received_reply": check_head_poll,
        "head_ack_success": head_ack_result,
    }
    assert check_head_ack_pass, "Head reply ingest/ACK failed"

    # -------------------------------------------------------------------------
    # 6. Negative Boundary Tests on model-worker-01
    # -------------------------------------------------------------------------
    # 6.1: Negative foreign worker ACK rejection (Directive C2335)
    foreign_bus_client = SessionlessWorkerBus.register(
        store=store_path,
        agent_name="foreign-intruder-worker",
        device_id="linux-worker-01",
        project_id=head_project,
    )
    foreign_rejected = False
    foreign_err_code = None
    try:
        foreign_bus_client.ack(handshake_msg_id)
    except BusError as err:
        foreign_rejected = True
        foreign_err_code = err.code

    check_foreign_pass = foreign_rejected and (foreign_err_code == "not_recipient")
    verification_checks["negative_foreign_worker_ack_rejection"] = {
        "status": "PASS" if check_foreign_pass else "FAIL",
        "rejected": foreign_rejected,
        "error_code": foreign_err_code,
        "expected_code": "not_recipient",
    }
    assert check_foreign_pass, "Negative foreign worker ACK rejection failed"

    # 6.2: Negative forged token rejection (Directive C2335)
    forged_rejected = False
    forged_err_code = None
    try:
        poll_messages(
            store_path=store_path,
            cred={"identity_id": worker_id, "token": "forged-counterfeit-token", "store": str(store_path)},
        )
    except BusError as err:
        forged_rejected = True
        forged_err_code = err.code

    check_forged_pass = forged_rejected and (forged_err_code == "auth_failed")
    verification_checks["negative_forged_token_rejection"] = {
        "status": "PASS" if check_forged_pass else "FAIL",
        "rejected": forged_rejected,
        "error_code": forged_err_code,
        "expected_code": "auth_failed",
    }
    assert check_forged_pass, "Negative forged token rejection failed"

    # -------------------------------------------------------------------------
    # 7. Construct Execution Receipt
    # -------------------------------------------------------------------------
    all_passed = all(v.get("status") == "PASS" for v in verification_checks.values())
    receipt = {
        "receipt_version": "1.0",
        "receipt_type": "RECEIPT_SESSIONLESS_MODEL_ENROLLMENT",
        "task_id": "RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01",
        "executed_at": get_utc_now(),
        "status": "PASS" if all_passed else "FAIL",
        "all_checks_passed": all_passed,
        "total_checks": len(verification_checks),
        "target_store": str(store_path),
        "worker_enrollment": {
            "agent_name": "model-worker-01",
            "identity_id": worker_id,
            "device_id": "linux-worker-01",
            "project_id": head_project,
            "session_id": None,
            "rendered_namespaced_id": rendered_nid,
            "credential_file": str(saved_cred_file),
            "credential_mode": oct(cred_mode),
            "credential_sha256": compute_sha256_file(saved_cred_file),
            "token_sha256": worker_token_sha256,
            "token_masked": f"{worker_token[:4]}...[REDACTED]...{worker_token[-4:]}",
        },
        "zero_token_inheritance_proof": {
            "head_agent": head_agent,
            "head_identity_id": head_id,
            "head_token_sha256": head_token_sha256,
            "worker_token_sha256": worker_token_sha256,
            "tokens_are_distinct": check_no_head_token,
            "ambient_aplexer_session_ignored": True,
            "head_cred_inheritance_guard_verified": True,
        },
        "message_exchange": {
            "handshake_message_id": handshake_msg_id,
            "handshake_idempotency_key": handshake_idempotency_key,
            "handshake_delivered_at": handshake_msg["delivered_at"],
            "handshake_acked_at": matched_acked_msg.get("acked_at") if matched_acked_msg else None,
            "reply_message_id": reply_msg_id,
            "reply_idempotency_key": reply_idempotency_key,
            "reply_delivered_at": reply_msg.get("delivered_at"),
            "reply_to": handshake_msg_id,
            "exchange_status": "DELIVERED_ACKED_AND_REPLIED",
        },
        "verification_checks": verification_checks,
    }

    receipt_output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_output_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    receipt_output_path.chmod(0o644)

    return receipt


if __name__ == "__main__":
    receipt_result = run_sessionless_model_enrollment()
    print(json.dumps(receipt_result, indent=2))
    sys.exit(0 if receipt_result["all_checks_passed"] else 1)
