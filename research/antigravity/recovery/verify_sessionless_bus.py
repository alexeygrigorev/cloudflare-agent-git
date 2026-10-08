#!/usr/bin/env python3
"""Verification of sessionless FileBus enrollment and negative foreign identity tests.

Validates:
1. Sessionless enrollment: identity created with session_id=None (rendered as '-').
2. Credential security: credential file written with mode 0600.
3. Negative foreign identity: foreign worker cannot ACK messages addressed to another agent (not_recipient).
4. Negative auth failure: invalid/forged token is rejected (auth_failed).
5. Head credential rejection: reject_head_cred_inheritance raises ValueError on head cred material.
6. Aplexer independence: APLEXER_* environment variables are ignored; no synthetic session created.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

# Ensure paths
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AGENT_BUS_ROOT = Path("/home/alexey/git/agent-bus")
if AGENT_BUS_ROOT.is_dir() and str(AGENT_BUS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_BUS_ROOT))

AGENT_COORD_ROOT = Path("/home/alexey/git/agent-coordination")
if AGENT_COORD_ROOT.is_dir() and str(AGENT_COORD_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_COORD_ROOT))

from coordination.bus import BusError, FileBus
from coordination.worker_bus import SessionlessWorkerBus
from scripts.coordination.agent_bus_transport import (
    enroll_agent,
    reject_head_cred_inheritance,
)


def run_verification() -> dict:
    results = {}
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bus_store = tmp_path / "bus"
        bus_store.mkdir(parents=True, mode=0o700)

        # 1. Sessionless enrollment
        os.environ["APLEXER_SESSION_ID"] = "forbidden-inherited-aplexer-session-id"
        os.environ["APLEXER_PORT"] = "9999"

        cred_data, cred_file_str = enroll_agent(
            store_path=bus_store,
            agent_name="sessionless-executor-01",
            device_id="linux-worker",
            project_id="cloudflare-agent-git",
            task_id="task-sessionless-verify",
        )
        cred_file = Path(cred_file_str)
        ident = cred_data["identity"]

        t1_pass = (
            ident.get("session_id") is None
            and ident.get("agent_name") == "sessionless-executor-01"
            and ident.get("identity_id") != "forbidden-inherited-aplexer-session-id"
        )
        results["test_sessionless_enrollment_no_aplexer"] = {
            "status": "PASS" if t1_pass else "FAIL",
            "identity_id": ident.get("identity_id"),
            "session_id": ident.get("session_id"),
            "agent_name": ident.get("agent_name"),
        }

        # 2. Mode 0600 credential
        file_mode = stat.S_IMODE(cred_file.stat().st_mode)
        t2_pass = file_mode == 0o600
        results["test_credential_file_mode_0600"] = {
            "status": "PASS" if t2_pass else "FAIL",
            "mode": oct(file_mode),
            "expected": "0o600",
            "path": str(cred_file),
        }

        # 3. SessionlessWorkerBus namespaced ID formatting
        worker_a = SessionlessWorkerBus.register(
            store=bus_store,
            agent_name="worker-alice",
            device_id="linux-worker",
            project_id="cloudflare-agent-git",
            task_id="task-alice",
        )
        nid = worker_a.namespaced_id
        t3_pass = (
            nid.session_id is None
            and nid.render() == "linux-worker/cloudflare-agent-git/worker-alice/-/task-alice"
        )
        results["test_namespaced_id_renders_dash_for_sessionless"] = {
            "status": "PASS" if t3_pass else "FAIL",
            "rendered": nid.render(),
            "session_id": nid.session_id,
        }

        # 4. Negative foreign worker rejection
        worker_b = SessionlessWorkerBus.register(
            store=bus_store,
            agent_name="worker-bob",
            device_id="linux-worker",
            project_id="cloudflare-agent-git",
        )
        worker_foreign = SessionlessWorkerBus.register(
            store=bus_store,
            agent_name="worker-foreign",
            device_id="linux-worker",
            project_id="cloudflare-agent-git",
        )
        msg, _ = worker_a.send(recipient_id=worker_b.identity_id, body="secret message for bob")

        foreign_rejected = False
        rejection_code = None
        try:
            worker_foreign.ack(msg.message_id)
        except BusError as err:
            foreign_rejected = True
            rejection_code = err.code

        results["test_negative_foreign_worker_ack_rejection"] = {
            "status": "PASS" if (foreign_rejected and rejection_code == "not_recipient") else "FAIL",
            "rejected": foreign_rejected,
            "error_code": rejection_code,
            "expected_error": "not_recipient",
        }

        # 5. Negative forged token rejection
        imposter = SessionlessWorkerBus(
            store=bus_store,
            identity=worker_b.identity,
            token="forged-imposter-token",
        )
        imposter_rejected = False
        imposter_code = None
        try:
            imposter.receive()
        except BusError as err:
            imposter_rejected = True
            imposter_code = err.code

        results["test_negative_forged_token_rejection"] = {
            "status": "PASS" if (imposter_rejected and imposter_code == "auth_failed") else "FAIL",
            "rejected": imposter_rejected,
            "error_code": imposter_code,
            "expected_error": "auth_failed",
        }

        # 6. Rejection of head credential inheritance
        head_cred_payloads = [
            {"head.cred": "sensitive-data"},
            {"head_token": "secret-token"},
            {"head": {"token": "sub-secret"}},
            "string with head.cred inside",
        ]
        head_cred_rejected_all = True
        for p in head_cred_payloads:
            try:
                reject_head_cred_inheritance(p, reject=True)
                head_cred_rejected_all = False
            except ValueError:
                pass

        results["test_reject_head_cred_inheritance"] = {
            "status": "PASS" if head_cred_rejected_all else "FAIL",
            "payloads_tested": len(head_cred_payloads),
            "all_rejected": head_cred_rejected_all,
        }

    all_passed = all(v.get("status") == "PASS" for v in results.values())
    return {
        "status": "PASS" if all_passed else "FAIL",
        "tests_run": len(results),
        "all_passed": all_passed,
        "details": results,
    }


if __name__ == "__main__":
    report = run_verification()
    output_path = REPO_ROOT / "research/antigravity/recovery/RECEIPT-SESSIONLESS-BUS-ENROLLMENT.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["all_passed"] else 1)
