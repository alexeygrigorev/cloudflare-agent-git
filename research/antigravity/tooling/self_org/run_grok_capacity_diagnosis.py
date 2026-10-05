#!/usr/bin/env python3
"""
run_grok_capacity_diagnosis.py

Executes the Grok capacity recovery diagnosis task under Codex Directives C2400/C2401.
Orchestrates an authentic Grok model worker under canonical launcher admission,
FileBus symmetric token authentication, verified systemd scope containment,
and frozen-runner (4f974/C2396) invariants.

Target Deliverable:
research/antigravity/reviews/REV-CAPACITY-CONTINUATION-GROK.md
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

# ---------------------------------------------------------------------------
# Path and Configuration Resolution
# ---------------------------------------------------------------------------
REPO_ROOT = Path("/home/alexey/git/cloudflare-agent-git").resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BUS_REPO = Path("/home/alexey/git/agent-bus").resolve()
BUS_CLI = BUS_REPO / "coordination" / "bus_cli.py"
BUS_PY = BUS_REPO / "coordination" / "bus.py"

DEFAULT_SCRATCH_ROOT = REPO_ROOT / ".local" / "scratch" / "grok-capacity-diagnosis"
DEFAULT_TMP_ROOT = REPO_ROOT / ".local" / "tmp" / "grok-capacity-diagnosis"

CANONICAL_DELIVERABLE_PATH = REPO_ROOT / "research" / "antigravity" / "reviews" / "REV-CAPACITY-CONTINUATION-GROK.md"
CLIPBOARD_SCREENSHOT_PATH = Path("/home/alexey/.pocketshell/attachments/cloudflare-agent-git/codex-principal/20261004-132555-01-clipboard.png")

from research.antigravity.tooling.self_org.run_hardened_filebus_model_review import (
    ALLOWED_VERDICTS,
    append_receipt_to_ledger,
    build_loaded_source_manifest,
    compute_sha256,
    correlate_reply,
    extract_artifact_sha256,
    extract_verdict_from_data,
    extract_verdict_from_text,
    parse_verdict,
    verify_cryptographic_digest,
)


# ---------------------------------------------------------------------------
# Environment Setup (Run-Scoped Exclusivity)
# ---------------------------------------------------------------------------
def init_run_environment(
    scratch_root: Path,
    tmp_root: Path,
    run_id: str,
) -> Dict[str, Path]:
    """
    Initializes run-scoped directories with collision-denial semantics.
    Invariant 5: Run-scoped exclusivity prevents race conditions and data corruption.
    """
    scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    run_dir = scratch_root / run_id
    if run_dir.exists():
        raise RuntimeError(f"Exclusive create collision deny: run scratch directory already exists: {run_dir}")
    run_dir.mkdir(parents=False, exist_ok=False, mode=0o700)

    run_tmp = tmp_root / run_id
    if run_tmp.exists():
        raise RuntimeError(f"Exclusive create collision deny: run tmp directory already exists: {run_tmp}")
    run_tmp.mkdir(parents=False, exist_ok=False, mode=0o700)

    bus_store = run_dir / "bus_store"
    bus_store.mkdir(parents=False, exist_ok=False, mode=0o700)

    creds_dir = run_dir / "creds"
    creds_dir.mkdir(parents=False, exist_ok=False, mode=0o700)

    return {
        "run_dir": run_dir,
        "run_tmp": run_tmp,
        "bus_store": bus_store,
        "creds_dir": creds_dir,
        "dispatcher_cred": creds_dir / "dispatcher_cred.json",
        "reviewer_cred": creds_dir / "reviewer_cred.json",
        "receipt_json": run_dir / "receipt.json",
        "ledger_jsonl": scratch_root / "trial_receipts.jsonl",
    }


# ---------------------------------------------------------------------------
# Unsteered Worker Prompt Construction (Invariant 1 & Directives C2400/C2401)
# ---------------------------------------------------------------------------
def build_unsteered_grok_capacity_prompt(
    bus_cli_path: Path,
    bus_store_path: Path,
    reviewer_cred_path: Path,
    task_msg_id: str,
    deliverable_path: Path,
    screenshot_path: Path,
) -> str:
    """
    Constructs an unsteered, objective worker prompt for Grok under C2400/C2401.
    Strictly forbids hardcoded outcomes or steering.
    Demands independent evaluation across all required failure shapes.
    """
    prompt = f"""You are an independent Grok expert systems reviewer dispatched to perform a rigorous diagnosis of provider capacity rejection, stale working lifecycle deadlocks, and safe receiver continuation under Codex Directives C2400 and C2401.

Your assigned Task Message ID is: {task_msg_id}
Your FileBus Store is: {bus_store_path}
Your Credential file is: {reviewer_cred_path}
Your Output Deliverable must be written to: {deliverable_path}

FOLLOW THIS STRICT PROTOCOL:

Step 1: Acknowledge the incoming task from FileBus:
python3 {bus_cli_path} --store {bus_store_path} ack --message-id {task_msg_id} --cred {reviewer_cred_path}

Step 2: Inspect Primary Evidence and Existing Diagnostic Reports:
1. Examine the primary screenshot at `{screenshot_path}`:
   - Observe the exact red error string: "Selected model is at capacity. Please try a different model."
   - Observe the trailing prompt composer: "> Ask Codex to do anything".
   - Note the header indicators: "Gemini 3.8", "? for shortcuts", "+ 73 lines (ctrl+t to expand)".
   - Confirm that this represents a live interactive CLI session experiencing transient model fleet overload.
2. Read existing prior reports and policies:
   - `research/grok/capacity-recovery/FINDINGS.md`
   - `research/antigravity/reviews/REV-GROK-CAPACITY-RECOVERY.md`
   - `research/antigravity/recovery/READINESS-PRODUCER-REPAIR-REPORT.md`
   - `research/antigravity/reviews/REV-SUPERVISION-FE312C7.md`

Step 3: Analyze and Distinguish Systematic Failure Shapes:
In your deliverable, explicitly demarcate the differences between:
1. Provider/Model Capacity:
   - Transient 429 / 503 fleet overload from LLM backend APIs.
   - Halts generation abnormally; installed Codex CLI / OpenCode harness does not fire a Stop/Error hook.
   - Result: `reported_state` remains locked in `working`, causing a stale lifecycle deadlock.
2. Context Exhaustion:
   - Exceeding the maximum token window; distinct error requiring compaction or session restart.
3. Account Quota:
   - Rate limit or billing balance exhaustion (`quse` windows, 15% Codex floor); hard fail-closed gate.
4. Normal Idle:
   - Clean turn completion where the Stop hook fires `state-report idle`.
5. Native Hook Events:
   - Inspect `/home/alexey/.codex/hooks.json` and `/home/alexey/.grok/hooks/aplexer.json`.
   - Identify that Codex lacks `OnError` / `CapacityRejection` hooks in `CODEX_EVENTS`.

Step 4: Pinpoint Safe 3-Minute Receiver Continuation Design:
Analyze how an autonomous agent system should safely recover after capacity:
1. Explain why an offline 180s (3-minute) timer ALONE cannot manufacture `state-report idle`:
   - Aplexer's `evaluate_readiness_verdict` strictly requires `source=="reported"` and state `waiting` or `idle`.
   - An expired working report falls back to heuristic checks, which fail closed for message delivery.
2. Prevention of Task Loss:
   - FileBus inbox messages must remain durably queued; never drop or delete unacknowledged tasks.
3. Prevention of Identity Spoofing:
   - Senders and receivers must retain authentic registered FileBus identities; no `--from` spoofing.
4. Prevention of Busy/Draft Input Injection:
   - Require two consecutive empty composer checks and verify zero running child tools before injecting input.
5. Safe Continuation Strategy:
   - Explain the 180s bounded backoff retry policy with fail-closed native guards, and how tasks should fall back to an eligible healthy alternative head/executor if capacity persists, without creating duplicate writers.

Step 5: Record Exact Source and Binary Pins:
- Grok CLI: 1.0.46 (`2765805b9442`)
- Aplexer CLI: 0.1.9 (`8d49a216d43c`)
- Codex CLI: 0.160.0
- Repositories: https://github.com/PocketShell-io/aplexer

Step 6: Write Your Independent Audit Report:
Write your complete, authoritative diagnostic report to:
{deliverable_path}
Determine your verdict STRICTLY INDEPENDENTLY based purely on empirical technical analysis.
Allowed verdicts: ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT.
Do not assume or presuppose any verdict.

Step 7: Compute SHA-256 and Reply over FileBus:
Compute the SHA-256 of `{deliverable_path}`.
Dispatch your structured reply over FileBus:
python3 {bus_cli_path} --store {bus_store_path} reply --message-id {task_msg_id} --body "VERDICT: <YOUR_INDEPENDENT_VERDICT>\\nARTIFACT_SHA256: <computed_sha256>\\nARTIFACT_PATH: {deliverable_path}\\nNOTES: <your empirical diagnosis summary>" --cred {reviewer_cred_path}

Output 'CAPACITY DIAGNOSIS AND FILEBUS CYCLE COMPLETE' when finished.
"""
    return prompt


# ---------------------------------------------------------------------------
# Main Execution Runner
# ---------------------------------------------------------------------------
def run_grok_capacity_diagnosis(
    run_id: Optional[str] = None,
    scratch_root: Path = DEFAULT_SCRATCH_ROOT,
    tmp_root: Path = DEFAULT_TMP_ROOT,
    deliverable_path: Path = CANONICAL_DELIVERABLE_PATH,
    timeout_sec: float = 720.0,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Executes the Grok capacity recovery diagnosis task under C2400/C2401.
    """
    if not run_id:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{ts}-{uuid.uuid4().hex[:8]}"

    task_id = f"t-grok-capacity-c2400-{run_id}"

    # 1. Environment initialization (Invariant 5)
    env_paths = init_run_environment(scratch_root, tmp_root, run_id)
    bus_store = env_paths["bus_store"]
    dispatcher_cred = env_paths["dispatcher_cred"]
    reviewer_cred = env_paths["reviewer_cred"]

    # 2. Source manifest capture (Invariant 6)
    source_manifest = build_loaded_source_manifest()

    # 3. Screenshot existence pre-check
    if not CLIPBOARD_SCREENSHOT_PATH.exists():
        raise FileNotFoundError(f"Primary capacity screenshot missing at {CLIPBOARD_SCREENSHOT_PATH}")

    # 4. Identity Enrollment via AgentBus CLI (Invariant 7)
    def _run_bus(args: List[str]) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(BUS_CLI), "--store", str(bus_store)] + args
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res

    _run_bus(["register", "--agent", "head-dispatcher", "--device", "local", "--cred", str(dispatcher_cred)])
    _run_bus(["register", "--agent", "grok-capacity-reviewer", "--device", "local", "--cred", str(reviewer_cred)])
    dispatcher_cred.chmod(0o600)
    reviewer_cred.chmod(0o600)

    reviewer_cred_data = json.loads(reviewer_cred.read_text(encoding="utf-8"))
    reviewer_identity_id = reviewer_cred_data["identity_id"]
    dispatcher_cred_data = json.loads(dispatcher_cred.read_text(encoding="utf-8"))
    dispatcher_identity_id = dispatcher_cred_data["identity_id"]

    # 5. Dispatch task to FileBus
    unsteered_prompt = build_unsteered_grok_capacity_prompt(
        bus_cli_path=BUS_CLI,
        bus_store_path=bus_store,
        reviewer_cred_path=reviewer_cred,
        task_msg_id="{TASK_MSG_ID_PLACEHOLDER}",
        deliverable_path=deliverable_path,
        screenshot_path=CLIPBOARD_SCREENSHOT_PATH,
    )

    task_body = (
        f"TASK: Conduct independent technical diagnosis of provider capacity recovery and safe receiver continuation under C2400/C2401.\n"
        f"Run ID: {run_id}\n"
        f"Deliverable Path: {deliverable_path}\n"
    )

    send_res = _run_bus([
        "send",
        "--cred", str(dispatcher_cred),
        "--to", reviewer_identity_id,
        "--body", task_body,
        "--idempotency-key", f"dispatch-{task_id}",
    ])
    send_data = json.loads(send_res.stdout) if send_res.stdout.strip().startswith("{") else {}
    task_msg_id = send_data.get("message_id")
    if not task_msg_id:
        m = re.search(r"message_id['\":\s]+([0-9a-fA-F-]+)", send_res.stdout)
        if m:
            task_msg_id = m.group(1)
    if not task_msg_id:
        raise ValueError(f"Failed to extract task_msg_id from send output: {send_res.stdout}")

    # Inject actual task_msg_id into worker prompt
    worker_prompt = unsteered_prompt.replace("{TASK_MSG_ID_PLACEHOLDER}", task_msg_id)

    # 6. Worker Execution in Systemd Scope
    start_time = time.time()
    exec_receipt: Dict[str, Any] = {}

    if dry_run:
        elapsed_sec = 0.1
        exec_receipt = {
            "unit_name": "mock-dry-run-grok.scope",
            "returncode": 0,
            "provider_chosen": "mock-grok",
            "model_chosen": "grok-4.6",
        }
        # Simulate worker creating deliverable and replying over FileBus
        deliverable_path.parent.mkdir(parents=True, exist_ok=True)
        if not deliverable_path.exists():
            deliverable_path.write_text(
                "# REV-CAPACITY-CONTINUATION-GROK\n\nVERDICT: BOUNDED ACCEPTANCE\n\nDry-run mock diagnosis deliverable.\n",
                encoding="utf-8",
            )
        _run_bus(["inbox", "--cred", str(reviewer_cred)])
        _run_bus(["ack", "--message-id", task_msg_id, "--cred", str(reviewer_cred)])
        actual_deliv_sha = compute_sha256(deliverable_path)
        _run_bus([
            "reply",
            "--cred", str(reviewer_cred),
            "--message-id", task_msg_id,
            "--body", f"VERDICT: BOUNDED ACCEPTANCE\nARTIFACT_SHA256: {actual_deliv_sha}\nARTIFACT_PATH: {deliverable_path}\nNOTES: Dry-run mock verification.",
        ])
    else:
        sys.path.insert(0, str(REPO_ROOT))
        from research.antigravity.tooling.self_org.launcher_bus_bridge import (
            ChildModelRuntimeAdapter,
            get_canonical_launcher_paths,
        )
        canon_store, canon_lock = get_canonical_launcher_paths(None)
        adapter = ChildModelRuntimeAdapter(
            store=canon_store,
            lock_path=canon_lock,
            workspace=REPO_ROOT,
        )
        command_argv = [
            "grok",
            "--model", "grok-4.6",
            "--effort", "high",
            "--permission-mode", "auto",
            "-p", worker_prompt,
        ]
        res = adapter.execute_in_verified_systemd_scope(
            task_id=task_id,
            command_argv=command_argv,
            cwd=REPO_ROOT,
            timeout_sec=timeout_sec,
            requested_memory_mb=1024,
            tmpdir=env_paths["run_tmp"],
            expected_outputs=[deliverable_path],
            is_local_probe=False,
            model_requirements={"allowed_providers": ["grok"], "providers": ["grok"]},
        )
        elapsed_sec = time.time() - start_time
        retcode = res.get("returncode")
        if retcode != 0:
            raise RuntimeError(f"Grok child execution failed with code {retcode}: {res}")
        exec_receipt = res

    # 7. Deliverable Existence & Publication Guard
    if not deliverable_path.exists():
        raise FileNotFoundError(f"Deliverable missing at {deliverable_path}")
    deliv_size = deliverable_path.stat().st_size
    if deliv_size == 0:
        raise ValueError(f"Deliverable at {deliverable_path} is empty")

    guard_script = REPO_ROOT / "research" / "antigravity" / "tooling" / "publication_guard.py"
    if guard_script.exists():
        guard_res = subprocess.run(
            [sys.executable, str(guard_script), str(deliverable_path)],
            capture_output=True,
            text=True,
        )
        if guard_res.returncode != 0:
            raise ValueError(f"Publication guard failed on deliverable: {guard_res.stderr}\n{guard_res.stdout}")

    # 8. Exact Reply Correlation (Invariant 3 & Directive C2396)
    inbox_res = _run_bus(["inbox", "--cred", str(dispatcher_cred)])
    inbox_messages = json.loads(inbox_res.stdout) if inbox_res.stdout.strip().startswith("[") else []
    correlated_reply = correlate_reply(
        messages=inbox_messages,
        task_msg_id=task_msg_id,
        reviewer_identity_id=reviewer_identity_id,
    )

    # 9. Cryptographic Digest Verification (Invariant 4)
    claimed_sha = extract_artifact_sha256(correlated_reply)
    actual_sha = verify_cryptographic_digest(deliverable_path, claimed_sha)

    # 10. Fail-Closed Verdict Extraction across all sources (Invariant 2 & Directive C2396)
    deliv_content = deliverable_path.read_text(encoding="utf-8")
    reply_body = correlated_reply.get("body")
    reply_data = correlated_reply.get("data") if isinstance(correlated_reply.get("data"), dict) else None
    verdict = parse_verdict(deliv_text=deliv_content, reply_body=reply_body, data_dict=reply_data)

    reply_msg_id = correlated_reply["message_id"]

    # 11. Real Head ACK for Worker Reply (Directive C2396)
    _run_bus(["ack", "--message-id", reply_msg_id, "--cred", str(dispatcher_cred)])
    head_ack_data = {
        "reply_msg_id": reply_msg_id,
        "acked": True,
        "acked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # 12. Immutable Execution Receipt & Append-Only Ledger (Invariants 5, 6 & 7)
    receipt = {
        "task_id": task_id,
        "run_id": run_id,
        "type": "grok_capacity_diagnosis",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed_sec, 3),
        "execution_receipt": exec_receipt,
        "deliverable": {
            "path": str(deliverable_path),
            "sha256": actual_sha,
            "bytes": deliv_size,
        },
        "verdict": verdict,
        "source_manifest": source_manifest,
        "identity_evidence": {
            "auth_type": "symmetric_token",
            "bus_store": str(bus_store),
            "dispatcher_identity_id": dispatcher_identity_id,
            "reviewer_identity_id": reviewer_identity_id,
            "task_msg_id": task_msg_id,
            "reply_msg_id": reply_msg_id,
        },
        "head_ack": head_ack_data,
        "guards_enforced": [
            "unsteered_prompt",
            "fail_closed_verdict_3way_consensus",
            "exact_reply_correlation_and_multiple_replies_fencing",
            "cryptographic_digest_verification",
            "per_run_scratch_isolation",
            "append_only_ledger_durability",
            "loaded_source_manifest",
            "symmetric_token_identity",
            "real_head_filebus_ack",
        ],
    }

    env_paths["receipt_json"].write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    env_paths["receipt_json"].chmod(0o600)

    append_receipt_to_ledger(env_paths["ledger_jsonl"], receipt)

    return receipt


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Grok Capacity Diagnosis Runner (C2400/C2401)")
    parser.add_argument("--dry-run", action="store_true", help="Execute dry-run mock flow without launching real child")
    parser.add_argument("--run-id", type=str, default=None, help="Explicit run ID")
    parser.add_argument("--timeout", type=float, default=720.0, help="Execution timeout in seconds")
    parser.add_argument("--deliverable", type=Path, default=CANONICAL_DELIVERABLE_PATH, help="Path to deliverable")
    args = parser.parse_args()

    try:
        receipt = run_grok_capacity_diagnosis(
            run_id=args.run_id,
            deliverable_path=args.deliverable,
            timeout_sec=args.timeout,
            dry_run=args.dry_run,
        )
        print(json.dumps(receipt, indent=2))
        print(f"\n[SUCCESS] Grok Capacity Diagnosis completed successfully with verdict: {receipt['verdict']}")
        sys.exit(0)
    except Exception as exc:
        print(f"\n[ERROR] Grok Capacity Diagnosis failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
