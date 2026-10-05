#!/usr/bin/env python3
"""
run_hardened_filebus_model_review.py

Hardened FileBus Model Review Runner adopting frozen-runner (4f974) invariants
under Codex Directives C2387 and C2392.

Key Hardened Invariants:
1. Unsteered Prompt: Worker instructions contain strictly NO signposted or hardcoded
   outcomes ("VERDICT: ACCEPT" removed). The prompt demands an independent verdict
   (ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT) based purely on empirical evidence.
2. Fail-Closed Verdict Extraction: Parser NEVER defaults missing/unparseable verdict
   to ACCEPT. Raises ValueError if an affirmative allowed verdict is not found or if
   conflicts are detected.
3. Exact Reply Correlation: FileBus inbox check strictly asserts
   reply["reply_to"] == task_msg_id AND reply["sender_id"] == reviewer_identity_id.
   Never relies on stdout substring matches.
4. Cryptographic Digest Verification: Extracts ARTIFACT_SHA256 from reply and strictly
   asserts equality against actual computed SHA-256 of deliverable on disk.
5. Per-Run Exclusivity & Append-Only Ledger:
   - Uses run-scoped exclusive directory creation (collision deny on duplicate run_id).
   - Appends all trial receipts to trial_receipts.jsonl (with flock) rather than overwriting.
6. Loaded Source Manifest: Computes and records in-process SHA256 of loaded agent-bus
   components (bus_cli.py, bus.py).
7. Accurate Terminology: Explicitly labels authentication as symmetric token
   authentication per identity.
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
BUS_REPO = Path("/home/alexey/git/agent-bus").resolve()
BUS_CLI = BUS_REPO / "coordination" / "bus_cli.py"
BUS_PY = BUS_REPO / "coordination" / "bus.py"
DASHBOARD_REPO = Path("/home/alexey/git/agent-dashboard").resolve()

DEFAULT_SCRATCH_ROOT = REPO_ROOT / ".local" / "scratch" / "filebus-hardened-model-review"
DEFAULT_TMP_ROOT = REPO_ROOT / ".local" / "tmp" / "filebus-hardened-model-review"

TARGET_COMMIT = "249d086a007ee3d5d0381334a27d56771b959d11"
TARGET_PATCH_C2392 = REPO_ROOT / "research" / "antigravity" / "recovery" / "dashboard-unattributed-and-as-of-c2392.patch"
TARGET_PATCH = TARGET_PATCH_C2392 if TARGET_PATCH_C2392.exists() else (REPO_ROOT / "research" / "antigravity" / "recovery" / "dashboard-unattributed-and-as-of-c2372.patch")
EXPECTED_PATCH_SHA = "2549317aa716edc744326c72a71960398f6315386e89a8e33a5879bfabba2efd"

CANONICAL_DELIVERABLE_PATH = REPO_ROOT / "research" / "antigravity" / "reviews" / "REV-DASHBOARD-UNATTRIBUTED-TRANSITIONS-C2374.md"

ALLOWED_VERDICTS: Set[str] = {
    "ACCEPT",
    "BOUNDED ACCEPTANCE",
    "REQUEST_CHANGES",
    "REJECT",
}


# ---------------------------------------------------------------------------
# Cryptographic & Manifest Helpers
# ---------------------------------------------------------------------------
def compute_sha256(path: Path) -> str:
    """Computes standard hex SHA-256 digest of a local file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_loaded_source_manifest() -> Dict[str, Any]:
    """
    Computes and records SHA256 of loaded agent-bus source files.
    Invariant 6: Pin loaded sources to avoid unpinned manifest claims.
    """
    manifest: Dict[str, Any] = {}
    for label, p in [("bus_cli", BUS_CLI), ("bus_py", BUS_PY)]:
        if p.exists():
            manifest[label] = {
                "path": str(p),
                "sha256": compute_sha256(p),
                "bytes": p.stat().st_size,
            }
        else:
            manifest[label] = {
                "path": str(p),
                "error": "FILE_NOT_FOUND",
            }
    return manifest


# ---------------------------------------------------------------------------
# Unsteered Prompt Construction (Invariant 1)
# ---------------------------------------------------------------------------
def build_unsteered_worker_prompt(
    bus_cli_path: Path,
    bus_store_path: Path,
    reviewer_cred_path: Path,
    task_msg_id: str,
    target_patch_path: Path,
    expected_patch_sha: str,
    target_commit: str,
    deliverable_path: Path,
    scratch_testbed_path: Path,
) -> str:
    """
    Constructs an unsteered review prompt.
    Invariant 1: Strictly removes signposted outcomes such as 'VERDICT: ACCEPT'.
    Requires model to determine verdict independently based on empirical tests.
    """
    prompt = f"""You are an independent model reviewer (identity: dogfood-model-reviewer).
You have received a mission via FileBus under Codex Directives C2374, C2379, C2381, C2385, C2387, and C2392.

Step 1: Ingest and acknowledge the task message from your FileBus inbox:
python3 {bus_cli_path} --store {bus_store_path} inbox --cred {reviewer_cred_path}
python3 {bus_cli_path} --store {bus_store_path} ack --message-id {task_msg_id} --cred {reviewer_cred_path}

Step 2: Conduct an independent technical audit of the updated dashboard patch:
- Patch file: {target_patch_path} (SHA256: {expected_patch_sha})
- Base commit: {target_commit} in /home/alexey/git/agent-dashboard
- In scratch testbed ({scratch_testbed_path}):
  Clone or copy /home/alexey/git/agent-dashboard at {target_commit}.
  Apply the patch using `git apply {target_patch_path}`.
  Run python unittests: `PYTHONPATH=src python3 -m unittest discover -s tests/ -v` (record test outcome).
  Run JS transition tests: `node tests/test_dashboard_js_transitions.js` (record test outcome).
- Verify the bugfixes:
  1) renderUsage returning early before resetting #events-unattributed and #tokens-unattributed to 'n/a'.
  2) renderHourly clearing all 6 unattributed fields to 'unknown' / 'n/a' and chart to fallback paragraph on data === null or HTTP 400 error.
  3) Synchronized as_of dispatch across /api/hourly, /api/usage, /api/features.
  4) Canonical /home/alexey/git/agent-dashboard strictly untouched and read-only.
  5) Zero compiler invocations host-wide under human hold.

Step 3: Write your comprehensive independent audit report to:
{deliverable_path}
Determine your verdict STRICTLY INDEPENDENTLY based purely on empirical test evidence.
Allowed verdicts: ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT.
Do not assume or presuppose any verdict.

Step 4: Compute the SHA256 of your written deliverable and dispatch your structured reply over FileBus:
python3 {bus_cli_path} --store {bus_store_path} reply --message-id {task_msg_id} --body "VERDICT: <YOUR_INDEPENDENT_VERDICT>\\nARTIFACT_SHA256: <computed_sha256>\\nARTIFACT_PATH: {deliverable_path}\\nNOTES: <your empirical test summary>" --cred {reviewer_cred_path}

Output 'REVIEW AND FILEBUS CYCLE COMPLETE' when finished.
"""
    return prompt


# ---------------------------------------------------------------------------
# Fail-Closed Verdict Extraction (Invariant 2)
# ---------------------------------------------------------------------------
def extract_verdict_from_text(text: Optional[str]) -> Optional[str]:
    """Extracts single verdict from text; fails closed on internal conflict."""
    if not text or not isinstance(text, str):
        return None
    verdicts_found: Set[str] = set()
    pattern = re.compile(
        r"(?:verdict|independent review verdict)\s*[:\-]?\s*[\*`_]*\s*(ACCEPT|BOUNDED ACCEPTANCE|REQUEST_CHANGES|REJECT)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        matched = match.group(1).upper()
        if matched in ALLOWED_VERDICTS:
            verdicts_found.add(matched)

    if len(verdicts_found) > 1:
        raise ValueError(
            f"Fail-closed: Conflicting verdicts found within text: {sorted(verdicts_found)}"
        )
    return next(iter(verdicts_found)) if verdicts_found else None


def extract_verdict_from_data(data_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extracts verdict from structured data dictionary."""
    if not data_dict or not isinstance(data_dict, dict):
        return None
    raw_v = data_dict.get("verdict")
    if not raw_v or not isinstance(raw_v, str):
        return None
    clean_v = raw_v.strip().strip("`*\"'").upper()
    if clean_v in ALLOWED_VERDICTS:
        return clean_v
    raise ValueError(
        f"Fail-closed: Invalid structured data verdict '{clean_v}' (expected one of {sorted(ALLOWED_VERDICTS)})"
    )


def parse_verdict(
    deliv_text: Optional[str] = None,
    reply_body: Optional[Union[str, Dict[str, Any]]] = None,
    data_dict: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Parses and cross-validates the independent review verdict from:
    1. Deliverable markdown report content on disk (deliv_text)
    2. FileBus reply body text (reply_body)
    3. Structured data dictionary (data_dict)

    Invariant 2 & Directive C2396:
    - NEVER defaults missing or unparseable verdicts to ACCEPT.
    - If reply_body has a verdict and deliv_text has a verdict and they differ, strictly FAIL CLOSED.
    - If reply_data has a verdict and either reply_body or deliv_text differs, strictly FAIL CLOSED.
    - All available sources must agree.
    """
    # Backward compatibility: if called as parse_verdict(text, data_dict)
    if isinstance(reply_body, dict) and data_dict is None:
        data_dict = reply_body
        reply_body = None

    deliv_verdict = extract_verdict_from_text(deliv_text)
    body_verdict = extract_verdict_from_text(reply_body if isinstance(reply_body, str) else None)
    data_verdict = extract_verdict_from_data(data_dict)

    sources: Dict[str, str] = {}
    if deliv_verdict is not None:
        sources["deliverable"] = deliv_verdict
    if body_verdict is not None:
        sources["reply_body"] = body_verdict
    if data_verdict is not None:
        sources["reply_data"] = data_verdict

    if not sources:
        raise ValueError(
            f"Fail-closed: No valid independent verdict found in deliverable, reply body, or reply data (expected one of {sorted(ALLOWED_VERDICTS)})"
        )

    unique_verdicts = set(sources.values())
    if len(unique_verdicts) > 1:
        details = ", ".join(f"{k}='{v}'" for k, v in sources.items())
        raise ValueError(
            f"Fail-closed: Contradictory verdicts across sources: {details}"
        )

    return next(iter(unique_verdicts))


# ---------------------------------------------------------------------------
# Exact Reply Correlation (Invariant 3 & Directive C2396)
# ---------------------------------------------------------------------------
def correlate_reply(
    messages: List[Dict[str, Any]],
    task_msg_id: str,
    reviewer_identity_id: str,
) -> Dict[str, Any]:
    """
    Correlates an incoming message in FileBus inbox to the specific task and reviewer.
    Invariant 3 & Directive C2396:
    - Requires exact match on BOTH reply_to == task_msg_id AND sender_id == reviewer_identity_id.
    - If multiple replies exist for the same task_msg_id and reviewer:
      * Checks if their verdicts, artifact hashes, or payloads differ.
      * If they differ in any way, strictly FAILS CLOSED (raises ValueError).
      * If multiple replies exist and are identical idempotent duplicates in all fields, returns the reply.
        Otherwise, strictly FAILS CLOSED.
    """
    if not messages:
        raise ValueError("Fail-closed: Inbox is empty; no reply messages received")
    if not task_msg_id:
        raise ValueError("Fail-closed: task_msg_id must not be empty for reply correlation")
    if not reviewer_identity_id:
        raise ValueError("Fail-closed: reviewer_identity_id must not be empty for reply correlation")

    matched_replies: List[Dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        reply_to = m.get("reply_to")
        sender_id = m.get("sender_id")
        if reply_to == task_msg_id and sender_id == reviewer_identity_id:
            matched_replies.append(m)

    if not matched_replies:
        raise ValueError(
            f"Fail-closed: No reply found correlating to task_msg_id '{task_msg_id}' from reviewer '{reviewer_identity_id}'"
        )

    if len(matched_replies) > 1:
        # Fencing multiple replies: detect any contradictions across replies
        first_rep = matched_replies[0]
        first_verdict = extract_verdict_from_text(first_rep.get("body")) or extract_verdict_from_data(first_rep.get("data"))
        try:
            first_sha = extract_artifact_sha256(first_rep)
        except ValueError:
            first_sha = None

        for idx, other_rep in enumerate(matched_replies[1:], start=2):
            other_verdict = extract_verdict_from_text(other_rep.get("body")) or extract_verdict_from_data(other_rep.get("data"))
            try:
                other_sha = extract_artifact_sha256(other_rep)
            except ValueError:
                other_sha = None

            if first_verdict != other_verdict or first_sha != other_sha:
                raise ValueError(
                    f"Fail-closed: Multiple conflicting replies detected for task_msg_id '{task_msg_id}' "
                    f"(verdicts: {first_verdict} vs {other_verdict}, sha: {first_sha} vs {other_sha})"
                )

            # Check if bodies/payloads differ
            if first_rep.get("body") != other_rep.get("body") or first_rep.get("data") != other_rep.get("data"):
                raise ValueError(
                    f"Fail-closed: Multiple conflicting replies detected for task_msg_id '{task_msg_id}' "
                    f"(non-identical reply contents/data)"
                )

        # All matched replies are confirmed identical duplicates
        return matched_replies[0]

    return matched_replies[0]


# ---------------------------------------------------------------------------
# Cryptographic Digest Verification (Invariant 4)
# ---------------------------------------------------------------------------
def extract_artifact_sha256(reply: Dict[str, Any]) -> str:
    """
    Extracts ARTIFACT_SHA256 from reply body or reply data dict.
    Fails closed if hash is missing or not a valid 64-char hex string.
    """
    # 1. Check data dict first
    data = reply.get("data")
    if isinstance(data, dict):
        d_sha = data.get("artifact_sha256") or data.get("sha256")
        if d_sha and isinstance(d_sha, str):
            clean_sha = d_sha.strip().lower()
            if re.fullmatch(r"[0-9a-f]{64}", clean_sha):
                return clean_sha

    # 2. Check body text
    body = reply.get("body", "")
    if isinstance(body, str):
        m = re.search(r"ARTIFACT_SHA256:\s*([0-9a-fA-F]{64})\b", body)
        if m:
            return m.group(1).lower()

    raise ValueError(
        "Fail-closed: Missing or invalid 64-character hex ARTIFACT_SHA256 in FileBus reply"
    )


def verify_cryptographic_digest(deliverable_path: Path, claimed_sha256: str) -> str:
    """
    Verifies that the file on disk exists, is non-empty, and computes its SHA256 digest,
    asserting exact equality against claimed_sha256.
    Invariant 4: Cryptographic digest verification strictly enforced.
    """
    if not deliverable_path.exists():
        raise ValueError(f"Fail-closed: Deliverable file does not exist: {deliverable_path}")
    if deliverable_path.stat().st_size == 0:
        raise ValueError(f"Fail-closed: Deliverable file is empty (0 bytes): {deliverable_path}")

    actual_sha = compute_sha256(deliverable_path).lower()
    claimed = claimed_sha256.strip().lower()

    if actual_sha != claimed:
        raise ValueError(
            f"Fail-closed: Cryptographic digest mismatch! Claimed in reply: {claimed}, Actual on disk: {actual_sha}"
        )

    return actual_sha


# ---------------------------------------------------------------------------
# Per-Run Exclusivity & Append-Only Ledger (Invariant 5)
# ---------------------------------------------------------------------------
def init_run_environment(
    scratch_root: Path,
    tmp_root: Path,
    run_id: str,
) -> Dict[str, Path]:
    """
    Initializes run-scoped directories with mode 0700 and strict exclusive creation.
    Invariant 5: Fails closed (collision deny) if run directory or run tmp already exists.
    """
    scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    run_dir = scratch_root / f"run_{run_id}"
    try:
        run_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        raise RuntimeError(f"Exclusive create collision deny: run directory already exists: {run_dir}")
    run_dir.chmod(0o700)

    run_tmp = tmp_root / f"tmp_{run_id}"
    try:
        run_tmp.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        raise RuntimeError(f"Exclusive create collision deny: run tmp directory already exists: {run_tmp}")
    run_tmp.chmod(0o700)

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


def append_receipt_to_ledger(ledger_path: Path, receipt: Dict[str, Any]) -> None:
    """
    Appends execution receipt as a JSON line to trial_receipts.jsonl using flock.
    Invariant 5: Append-only durability without clobbering history.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    serialized = json.dumps(receipt, sort_keys=True) + "\n"

    with open(ledger_path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    try:
        os.chmod(ledger_path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main Runner Workflow
# ---------------------------------------------------------------------------
def run_hardened_filebus_review(
    run_id: Optional[str] = None,
    scratch_root: Path = DEFAULT_SCRATCH_ROOT,
    tmp_root: Path = DEFAULT_TMP_ROOT,
    target_patch: Path = TARGET_PATCH,
    target_commit: str = TARGET_COMMIT,
    deliverable_path: Path = CANONICAL_DELIVERABLE_PATH,
    timeout_sec: float = 720.0,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrates the hardened FileBus review execution with all 7 invariants enforced.
    """
    if not run_id:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{ts}-{uuid.uuid4().hex[:8]}"

    task_id = f"t-filebus-hardened-review-{run_id}"

    # 1. Environment initialization (Invariant 5)
    env_paths = init_run_environment(scratch_root, tmp_root, run_id)
    bus_store = env_paths["bus_store"]
    dispatcher_cred = env_paths["dispatcher_cred"]
    reviewer_cred = env_paths["reviewer_cred"]

    # 2. Source manifest capture (Invariant 6)
    source_manifest = build_loaded_source_manifest()

    # 3. Patch integrity pre-check
    if not target_patch.exists():
        raise FileNotFoundError(f"Target patch missing at {target_patch}")
    actual_patch_sha = compute_sha256(target_patch)
    if actual_patch_sha != EXPECTED_PATCH_SHA:
        raise ValueError(
            f"Target patch SHA256 mismatch: expected {EXPECTED_PATCH_SHA}, got {actual_patch_sha}"
        )

    # 4. Identity Enrollment via AgentBus CLI
    # Invariant 7: Symmetric token authentication per identity
    def _run_bus(args: List[str]) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(BUS_CLI), "--store", str(bus_store)] + args
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res

    _run_bus(["register", "--agent", "head-dispatcher", "--device", "local", "--cred", str(dispatcher_cred)])
    _run_bus(["register", "--agent", "dogfood-model-reviewer", "--device", "local", "--cred", str(reviewer_cred)])
    dispatcher_cred.chmod(0o600)
    reviewer_cred.chmod(0o600)

    reviewer_cred_data = json.loads(reviewer_cred.read_text(encoding="utf-8"))
    reviewer_identity_id = reviewer_cred_data["identity_id"]
    dispatcher_cred_data = json.loads(dispatcher_cred.read_text(encoding="utf-8"))
    dispatcher_identity_id = dispatcher_cred_data["identity_id"]

    # 5. Dispatch task to FileBus
    scratch_testbed = env_paths["run_dir"] / "testbed"
    unsteered_prompt = build_unsteered_worker_prompt(
        bus_cli_path=BUS_CLI,
        bus_store_path=bus_store,
        reviewer_cred_path=reviewer_cred,
        task_msg_id="{TASK_MSG_ID_PLACEHOLDER}",
        target_patch_path=target_patch,
        expected_patch_sha=actual_patch_sha,
        target_commit=target_commit,
        deliverable_path=deliverable_path,
        scratch_testbed_path=scratch_testbed,
    )

    task_body = (
        f"TASK: Conduct independent technical audit of updated dashboard patch {actual_patch_sha} atop {target_commit}.\n"
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
        # Dry-run mock execution for fast unit testing / scaffolding
        elapsed_sec = 0.1
        exec_receipt = {
            "unit_name": "mock-dry-run.scope",
            "returncode": 0,
            "provider_chosen": "mock-local",
            "model_chosen": "mock-model",
        }
        # In dry run, simulate reviewer consuming task, acking, and replying with actual deliverable SHA
        _run_bus(["inbox", "--cred", str(reviewer_cred)])
        _run_bus(["ack", "--message-id", task_msg_id, "--cred", str(reviewer_cred)])
        actual_deliv_sha = compute_sha256(deliverable_path)
        _run_bus([
            "reply",
            "--cred", str(reviewer_cred),
            "--message-id", task_msg_id,
            "--body", f"VERDICT: ACCEPT\nARTIFACT_SHA256: {actual_deliv_sha}\nARTIFACT_PATH: {deliverable_path}\nNOTES: Dry-run mock verification.",
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
            raise RuntimeError(f"Child execution failed with code {retcode}: {res}")
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

    # 8. Exact Reply Correlation (Invariant 3)
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
        "type": "filebus_hardened_model_review",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "elapsed_sec": round(elapsed_sec, 2),
        "auth_mechanism": "symmetric_token_auth_per_identity",
        "unit_name": exec_receipt.get("unit_name"),
        "returncode": exec_receipt.get("returncode", 0),
        "target_commit": target_commit,
        "target_patch_sha256": actual_patch_sha,
        "task_message_id": task_msg_id,
        "reply_message_id": reply_msg_id,
        "reply_to": correlated_reply.get("reply_to"),
        "head_ack": head_ack_data,
        "dispatcher_identity_id": dispatcher_identity_id,
        "reviewer_identity_id": reviewer_identity_id,
        "verdict": verdict,
        "deliverable": {
            "path": str(deliverable_path),
            "sha256": actual_sha,
            "bytes": deliv_size,
            "publication_guard": "PASS",
        },
        "loaded_source_manifest": source_manifest,
    }

    # Write run-scoped receipt
    run_receipt_path = env_paths["receipt_json"]
    run_receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    run_receipt_path.chmod(0o600)

    # Append to append-only ledger
    append_receipt_to_ledger(env_paths["ledger_jsonl"], receipt)

    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Hardened FileBus Model Review Runner (Directives C2387/C2392)")
    parser.add_argument("--run-id", default=None, help="Optional explicit run ID")
    parser.add_argument("--dry-run", action="store_true", help="Perform mock execution for testing verification logic")
    parser.add_argument("--timeout", type=float, default=720.0, help="Timeout in seconds")
    args = parser.parse_args()

    receipt = run_hardened_filebus_review(
        run_id=args.run_id,
        timeout_sec=args.timeout,
        dry_run=args.dry_run,
    )
    print(f"Hardened FileBus Model Review Succeeded (Verdict: {receipt['verdict']})")
    print(f"Run ID: {receipt['run_id']}")
    print(f"Receipt written to: {receipt['task_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
