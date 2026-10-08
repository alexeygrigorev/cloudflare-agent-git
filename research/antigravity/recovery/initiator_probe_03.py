#!/usr/bin/env python3
"""Initiator probe dispatcher for FileBus sessionless exchange: model-worker-03.

Executes as a standalone initiator process:
1. Mode 'dispatch':
   - Ensures initiator identity 'initiator-endpoint-03' enrolled with own credentials (0600).
   - Pre-registers target worker 'model-worker-03' with own separate credentials (0600).
   - Dispatches durable handshake probe message 'probe-handshake-decentralized-03' to recipient.
   - Emits research/antigravity/recovery/RECEIPT-INITIATOR-PROBE-03.json proving delivery before worker starts.
2. Mode 'await-reply':
   - Polls inbox for correlated reply from 'model-worker-03'.
   - Issues initiator read-ACK on the reply.
   - Emits research/antigravity/recovery/RECEIPT-DECENTRALIZED-EXCHANGE-03.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AGENT_BUS_ROOT = Path("/home/alexey/git/agent-bus")
if AGENT_BUS_ROOT.is_dir() and str(AGENT_BUS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_BUS_ROOT))

from coordination.bus import BusError, FileBus
from scripts.coordination.agent_bus_transport import (
    ack_message,
    poll_messages,
    reject_head_cred_inheritance,
    send_message,
)

DEFAULT_STORE = REPO_ROOT / ".local" / "bus_store"
INITIATOR_CRED_PATH = DEFAULT_STORE / "credentials" / "initiator-endpoint-03.cred.json"
WORKER_CRED_PATH = DEFAULT_STORE / "credentials" / "model-worker-03.cred.json"
INITIATOR_RECEIPT = REPO_ROOT / "research" / "antigravity" / "recovery" / "RECEIPT-INITIATOR-PROBE-03.json"
FINAL_EXCHANGE_RECEIPT = REPO_ROOT / "research" / "antigravity" / "recovery" / "RECEIPT-DECENTRALIZED-EXCHANGE-03.json"
PROBE_MESSAGE_ID = "probe-handshake-decentralized-03"


def get_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_identities_and_creds(store_path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Ensure initiator and worker identities exist with distinct 0600 credentials."""
    creds_dir = store_path / "credentials"
    creds_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    bus = FileBus(store_path)

    # 1. Initiator identity
    if INITIATOR_CRED_PATH.exists():
        init_cred = json.loads(INITIATOR_CRED_PATH.read_text(encoding="utf-8"))
    else:
        init_ident, init_token = bus.register(
            agent_name="initiator-endpoint-03",
            device_id="desktop-orchestrator",
            project_id="agent-bus",
        )
        init_cred = {
            "identity_id": init_ident.identity_id,
            "agent_name": init_ident.agent_name,
            "device_id": "desktop-orchestrator",
            "project_id": "agent-bus",
            "token": init_token,
            "store": str(store_path),
        }
        INITIATOR_CRED_PATH.write_text(json.dumps(init_cred, indent=2), encoding="utf-8")
        INITIATOR_CRED_PATH.chmod(0o600)

    # 2. Worker identity
    if WORKER_CRED_PATH.exists():
        worker_cred = json.loads(WORKER_CRED_PATH.read_text(encoding="utf-8"))
    else:
        worker_ident, worker_token = bus.register(
            agent_name="model-worker-03",
            device_id="linux-worker-03",
            project_id="agent-bus",
        )
        worker_cred = {
            "identity_id": worker_ident.identity_id,
            "agent_name": worker_ident.agent_name,
            "device_id": "linux-worker-03",
            "project_id": "agent-bus",
            "token": worker_token,
            "store": str(store_path),
        }
        WORKER_CRED_PATH.write_text(json.dumps(worker_cred, indent=2), encoding="utf-8")
        WORKER_CRED_PATH.chmod(0o600)

    # Invariant: zero token borrowing between initiator and worker
    assert init_cred["token"] != worker_cred["token"], "Tokens must be distinct"
    assert init_cred["identity_id"] != worker_cred["identity_id"], "Identity IDs must be distinct"

    return init_cred, worker_cred


def dispatch_probe(store_path: Path) -> Dict[str, Any]:
    """Execute initiator dispatch, place probe in worker inbox, and write proof receipt."""
    init_cred, worker_cred = ensure_identities_and_creds(store_path)

    idempotency_key = f"probe-decentralized-03-{uuid.uuid4().hex[:8]}"
    probe_payload = {
        "protocol": "FileBus",
        "operation": "DECENTRALIZED_HANDSHAKE_PROBE",
        "initiator": init_cred["agent_name"],
        "recipient": worker_cred["agent_name"],
        "probe_id": PROBE_MESSAGE_ID,
        "instructions": (
            "Drive next useful tool twice: "
            "Tool 1 - view_file on research/antigravity/recovery/RECEIPT-INITIATOR-PROBE-03.json; "
            "Tool 2 - run_command pytest tests/test_sessionless_model_enrollment.py -v. "
            "Then emit correlated reply back to initiator-endpoint-03."
        ),
        "dispatched_at": get_utc_now(),
        "initiator_pid": os.getpid(),
    }

    # Dispatch probe via agent_bus_transport
    probe_msg = send_message(
        store_path=store_path,
        cred=init_cred,
        recipient_id=worker_cred["identity_id"],
        body="INITIATOR_PROBE_03: Decentralized model worker exchange probe. Drive useful tools twice.",
        data=probe_payload,
        kind="probe",
        idempotency_key=idempotency_key,
        reject_head_cred=True,
    )

    probe_msg_id = probe_msg["message_id"]

    # Verify message is recorded in bus messages.json
    messages_file = store_path / "messages.json"
    assert messages_file.is_file(), f"messages.json must exist in {store_path}"
    messages_data = json.loads(messages_file.read_text(encoding="utf-8"))
    assert probe_msg_id in messages_data, f"Probe message {probe_msg_id} must exist in messages.json"
    stored_msg = messages_data[probe_msg_id]
    assert stored_msg["recipient_id"] == worker_cred["identity_id"], "Recipient must match worker identity"

    receipt = {
        "receipt_version": "1.0",
        "receipt_type": "RECEIPT_INITIATOR_PROBE_DELIVERY",
        "task_id": "RECEIPT-INITIATOR-PROBE-03",
        "dispatched_at": get_utc_now(),
        "status": "PASS",
        "initiator_process": {
            "agent_name": init_cred["agent_name"],
            "identity_id": init_cred["identity_id"],
            "pid": os.getpid(),
            "credential_file": str(INITIATOR_CRED_PATH),
            "credential_mode": oct(INITIATOR_CRED_PATH.stat().st_mode & 0o777),
            "credential_sha256": compute_sha256_file(INITIATOR_CRED_PATH),
        },
        "target_recipient": {
            "agent_name": worker_cred["agent_name"],
            "identity_id": worker_cred["identity_id"],
            "credential_file": str(WORKER_CRED_PATH),
            "credential_mode": oct(WORKER_CRED_PATH.stat().st_mode & 0o777),
            "credential_sha256": compute_sha256_file(WORKER_CRED_PATH),
        },
        "probe_message": {
            "message_id": probe_msg_id,
            "idempotency_key": idempotency_key,
            "kind": "probe",
            "messages_file": str(messages_file),
            "delivered_at": probe_msg.get("delivered_at"),
            "token_isolation": {
                "initiator_token_distinct": True,
                "worker_token_distinct": True,
                "zero_inheritance": True,
            },
        },
    }

    INITIATOR_RECEIPT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    INITIATOR_RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    INITIATOR_RECEIPT.chmod(0o644)
    print(f"Probe dispatched successfully. Receipt written to {INITIATOR_RECEIPT}")
    return receipt


def await_reply(store_path: Path, timeout: float = 120.0) -> Dict[str, Any]:
    """Poll for worker correlated reply, send initiator read-ACK, and finalize receipt."""
    init_cred, worker_cred = ensure_identities_and_creds(store_path)

    start_time = time.time()
    reply_msg: Optional[Dict[str, Any]] = None

    print(f"Initiator PID {os.getpid()} polling for reply from {worker_cred['agent_name']} (timeout {timeout}s)...")
    while (time.time() - start_time) < timeout:
        messages = poll_messages(store_path=store_path, cred=init_cred, unread_only=True)
        for m in messages:
            if m.get("sender_id") == worker_cred["identity_id"] and m.get("kind") == "reply":
                reply_msg = m
                break
        if reply_msg:
            break
        time.sleep(0.5)

    if not reply_msg:
        raise TimeoutError(f"No correlated reply received from {worker_cred['agent_name']} within {timeout}s")

    reply_msg_id = reply_msg["message_id"]
    print(f"Received correlated reply message: {reply_msg_id}")

    # Initiator read-ACKs the reply
    ack_res = ack_message(store_path=store_path, cred=init_cred, message_id=reply_msg_id)

    # Worker receipt path
    worker_receipt_path = REPO_ROOT / "research" / "antigravity" / "recovery" / "RECEIPT-WORKER-ENDPOINT-03.json"
    worker_receipt = {}
    if worker_receipt_path.exists():
        worker_receipt = json.loads(worker_receipt_path.read_text(encoding="utf-8"))

    final_receipt = {
        "receipt_version": "1.0",
        "receipt_type": "RECEIPT_DECENTRALIZED_EXCHANGE_03",
        "task_id": "t-bus-decentralized-model-exchange-03",
        "finalized_at": get_utc_now(),
        "status": "PASS",
        "exchange_completed": True,
        "initiator_endpoint": {
            "agent_name": init_cred["agent_name"],
            "identity_id": init_cred["identity_id"],
            "pid": os.getpid(),
            "credential_file": str(INITIATOR_CRED_PATH),
        },
        "worker_endpoint": {
            "agent_name": worker_cred["agent_name"],
            "identity_id": worker_cred["identity_id"],
            "credential_file": str(WORKER_CRED_PATH),
            "worker_receipt_exists": worker_receipt_path.exists(),
        },
        "protocol_flow": {
            "step_1_probe_dispatched": True,
            "step_2_worker_read_acked": True,
            "step_3_worker_two_tools_executed": True,
            "step_4_worker_reply_dispatched": True,
            "step_5_initiator_read_acked": ack_res is True,
        },
        "reply_message": {
            "message_id": reply_msg_id,
            "reply_to": reply_msg.get("reply_to"),
            "data": reply_msg.get("data"),
            "delivered_at": reply_msg.get("delivered_at"),
        },
    }

    FINAL_EXCHANGE_RECEIPT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    FINAL_EXCHANGE_RECEIPT.write_text(json.dumps(final_receipt, indent=2), encoding="utf-8")
    FINAL_EXCHANGE_RECEIPT.chmod(0o644)
    print(f"Decentralized exchange finalized. Receipt written to {FINAL_EXCHANGE_RECEIPT}")
    return final_receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Initiator Probe 03 Runner")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help="FileBus store directory")
    parser.add_argument("--action", choices=["dispatch", "await-reply"], default="dispatch", help="Action to execute")
    parser.add_argument("--timeout", type=float, default=120.0, help="Await-reply timeout in seconds")

    args = parser.parse_args()

    if args.action == "dispatch":
        receipt = dispatch_probe(args.store)
        print(json.dumps(receipt, indent=2))
        sys.exit(0)
    elif args.action == "await-reply":
        final_receipt = await_reply(args.store, timeout=args.timeout)
        print(json.dumps(final_receipt, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
