"""Terminal receipt and review consumer for autonomous supervision.

Ingests task-unit completion receipts and independent review receipts,
enforces distinct reviewer validation (anti-self-review), gates dependent
task transitions on review acceptance, and filters supervision notifications
to only emit substantive actionable transitions.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import pathlib
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

MAX_RECEIPT_SIZE = 1024 * 1024  # 1 MiB limit


class ReceiptValidationError(ValueError):
    """Raised when a terminal or review receipt violates schema or safety gates."""
    pass


class SelfReviewProhibitedError(ReceiptValidationError):
    """Raised when an executor attempts to review their own output."""
    pass


def canonical_json_hash(data: Dict[str, Any]) -> str:
    """Return deterministic SHA-256 hex digest of dictionary payload."""
    raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def validate_terminal_receipt(receipt: Dict[str, Any]) -> Tuple[bool, Optional[str], str]:
    """Validate task execution terminal receipt.

    Returns: (is_valid, error_message, receipt_sha256).
    """
    if not isinstance(receipt, dict):
        return False, "Receipt must be a JSON object", ""

    task_id = receipt.get("task_id")
    if not task_id or not isinstance(task_id, str):
        return False, "Missing or non-string 'task_id'", ""

    project_id = receipt.get("project_id")
    if not project_id or not isinstance(project_id, str):
        return False, "Missing or non-string 'project_id'", ""

    executor = receipt.get("executor")
    if not isinstance(executor, dict):
        return False, "Missing or invalid 'executor' block", ""
    for field in ("session_id", "tag", "engine"):
        val = executor.get(field)
        if not val or not isinstance(val, str):
            return False, f"Missing or invalid executor field '{field}'", ""

    phase = receipt.get("phase")
    if phase != "execution":
        return False, f"Expected phase 'execution', got {phase!r}", ""

    status = receipt.get("status")
    if status not in ("completed-awaiting-review", "completed", "done"):
        return False, f"Invalid terminal status: {status!r}", ""

    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list):
        return False, "Field 'artifacts' must be a list", ""
    for art in artifacts:
        if not isinstance(art, dict) or not art.get("path") or not art.get("sha256"):
            return False, "Each artifact must contain 'path' and 'sha256'", ""

    first_tool = receipt.get("first_tool_evidence")
    if not isinstance(first_tool, dict) or not first_tool.get("tool_name"):
        return False, "Missing or invalid 'first_tool_evidence' with 'tool_name'", ""

    completed_at = receipt.get("completed_at")
    if not completed_at or not isinstance(completed_at, str):
        return False, "Missing or non-string 'completed_at'", ""

    receipt_sha = canonical_json_hash(receipt)
    return True, None, receipt_sha


def validate_review_receipt(
    review: Dict[str, Any],
    terminal_receipt: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], str]:
    """Validate independent review receipt.

    Enforces distinct reviewer requirement against the target terminal receipt.
    Returns: (is_valid, error_message, review_sha256).
    """
    if not isinstance(review, dict):
        return False, "Review must be a JSON object", ""

    task_id = review.get("task_id")
    if not task_id or not isinstance(task_id, str):
        return False, "Missing or non-string 'task_id'", ""

    review_task_id = review.get("review_task_id")
    if not review_task_id or not isinstance(review_task_id, str):
        return False, "Missing or non-string 'review_task_id'", ""

    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        return False, "Missing or invalid 'reviewer' block", ""
    for field in ("session_id", "tag", "engine"):
        val = reviewer.get(field)
        if not val or not isinstance(val, str):
            return False, f"Missing or invalid reviewer field '{field}'", ""

    verdict = review.get("verdict")
    if verdict not in ("ACCEPTED", "REJECTED"):
        return False, f"Verdict must be 'ACCEPTED' or 'REJECTED', got {verdict!r}", ""

    review_evidence = review.get("review_evidence")
    if not isinstance(review_evidence, dict):
        return False, "Missing or invalid 'review_evidence' block", ""
    if "exit_code" not in review_evidence or review_evidence.get("exit_code") != 0 and verdict == "ACCEPTED":
        return False, "Accepted review requires exit_code == 0", ""

    target_sha = review.get("target_receipt_sha256")
    if not target_sha or not isinstance(target_sha, str):
        return False, "Missing or invalid 'target_receipt_sha256'", ""

    # Anti-self-review check if terminal receipt is supplied
    if terminal_receipt is not None:
        exec_info = terminal_receipt.get("executor", {})
        if reviewer.get("session_id") == exec_info.get("session_id"):
            return False, "Self-review prohibited: reviewer session_id equals executor session_id", ""
        if reviewer.get("tag") == exec_info.get("tag"):
            return False, "Self-review prohibited: reviewer tag equals executor tag", ""
        expected_target_sha = canonical_json_hash(terminal_receipt)
        if target_sha != expected_target_sha:
            return False, f"target_receipt_sha256 mismatch: expected {expected_target_sha}, got {target_sha}", ""

    review_sha = canonical_json_hash(review)
    return True, None, review_sha


class TerminalConsumer:
    """Manages ingestion of terminal and review receipts and computes state transitions."""

    def __init__(self, spool_dir: pathlib.Path):
        self.spool_dir = pathlib.Path(spool_dir)
        self.receipts_dir = self.spool_dir / "receipts"
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        self.terminal_receipts: Dict[str, Dict[str, Any]] = {}
        self.review_receipts: Dict[str, Dict[str, Any]] = {}
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.processed_receipt_shas: Set[str] = set()

    def ingest_terminal_receipt(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest and validate execution terminal receipt."""
        ok, err, r_sha = validate_terminal_receipt(receipt)
        if not ok:
            raise ReceiptValidationError(f"Invalid terminal receipt: {err}")

        task_id = receipt["task_id"]
        self.terminal_receipts[task_id] = receipt
        self.processed_receipt_shas.add(r_sha)

        self.task_states[task_id] = {
            "task_id": task_id,
            "project_id": receipt["project_id"],
            "status": "completed-awaiting-review",
            "executor": receipt["executor"],
            "terminal_receipt_sha256": r_sha,
            "terminal_completed_at": receipt["completed_at"],
            "artifacts": receipt["artifacts"],
            "first_tool_evidence": receipt["first_tool_evidence"],
            "reviewer": None,
            "verdict": None,
            "reviewed_at": None,
        }

        # Persist receipt
        rec_path = self.receipts_dir / f"terminal-{task_id}.json"
        rec_path.write_text(json.dumps(receipt, indent=2))

        return {
            "status": "ingested",
            "task_id": task_id,
            "sha256": r_sha,
            "action_required": "REVIEW_REQUIRED",
        }

    def ingest_review_receipt(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest, validate, and apply an independent review receipt."""
        task_id = review.get("task_id")
        term_receipt = self.terminal_receipts.get(task_id)

        ok, err, r_sha = validate_review_receipt(review, term_receipt)
        if not ok:
            if "Self-review prohibited" in err:
                raise SelfReviewProhibitedError(err)
            raise ReceiptValidationError(f"Invalid review receipt: {err}")

        self.review_receipts[task_id] = review
        self.processed_receipt_shas.add(r_sha)

        verdict = review["verdict"]
        new_status = "accepted" if verdict == "ACCEPTED" else "rejected-needs-repair"

        if task_id in self.task_states:
            self.task_states[task_id]["status"] = new_status
            self.task_states[task_id]["reviewer"] = review["reviewer"]
            self.task_states[task_id]["verdict"] = verdict
            self.task_states[task_id]["review_receipt_sha256"] = r_sha
            self.task_states[task_id]["reviewed_at"] = review.get("reviewed_at")

        # Persist review
        rev_path = self.receipts_dir / f"review-{task_id}.json"
        rev_path.write_text(json.dumps(review, indent=2))

        return {
            "status": "ingested",
            "task_id": task_id,
            "verdict": verdict,
            "new_task_status": new_status,
            "sha256": r_sha,
        }

    def reconcile_and_unblock_tasks(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """Check all blocked tasks against accepted dependencies and unblock them.

        Returns list of newly unblocked task IDs.
        """
        accepted_ids = {
            t_id for t_id, st in self.task_states.items()
            if st.get("status") == "accepted"
        }

        newly_unblocked = []
        for t in tasks:
            if t.get("status") not in ("blocked", "queued", "pending"):
                continue
            blocked_on = t.get("blocked_on", [])
            if not blocked_on:
                continue

            # Check if all blockers are satisfied in accepted_ids
            if all(blocker in accepted_ids for blocker in blocked_on):
                t["status"] = "ready"
                t["unblocked_at"] = datetime.now(timezone.utc).isoformat()
                newly_unblocked.append(t["id"])

        return newly_unblocked

    def compute_actionable_events(
        self,
        tasks: List[Dict[str, Any]],
        previous_emitted_digest: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Compute substantive actionable events for supervision broadcast.

        Returns: (events_list, new_digest).
        If new_digest equals previous_emitted_digest, caller should suppress emission.
        """
        events = []

        # 1. Unblocked / Ready tasks requiring worker dispatch
        ready_tasks = [t for t in tasks if t.get("status") == "ready"]
        for t in ready_tasks:
            events.append({
                "type": "TASK_READY",
                "task_id": t["id"],
                "project_id": t.get("project_id") or t.get("team_id"),
                "summary": f"Task {t['id']} ready for model execution dispatch",
            })

        # 2. Completed execution tasks awaiting independent review
        for t_id, st in self.task_states.items():
            if st.get("status") == "completed-awaiting-review":
                events.append({
                    "type": "REVIEW_REQUIRED",
                    "task_id": t_id,
                    "project_id": st.get("project_id"),
                    "executor_tag": st.get("executor", {}).get("tag"),
                    "summary": f"Task {t_id} completed execution; distinct review required",
                })
            elif st.get("status") == "rejected-needs-repair":
                events.append({
                    "type": "TASK_REJECTED",
                    "task_id": t_id,
                    "project_id": st.get("project_id"),
                    "reviewer_tag": st.get("reviewer", {}).get("tag"),
                    "summary": f"Task {t_id} rejected by reviewer; repair required",
                })

        # Compute deterministic digest over meaningful actionable events
        events_payload = sorted(
            [{"type": e["type"], "task_id": e["task_id"]} for e in events],
            key=lambda x: (x["type"], x["task_id"]),
        )
        new_digest = canonical_json_hash({"actionable_events": events_payload})[:20]

        return events, new_digest

    def format_actionable_notification(
        self,
        events: List[Dict[str, Any]],
        active_heads: List[str],
    ) -> Optional[str]:
        """Format a concise notification string containing ONLY actionable events.

        Returns None if events list is empty.
        """
        if not events:
            return None

        heads_str = ", ".join(active_heads) if active_heads else "all heads"
        parts = [f"SUPERVISION-ACTIONABLE (heads: {heads_str}):"]

        ready_count = sum(1 for e in events if e["type"] == "TASK_READY")
        review_count = sum(1 for e in events if e["type"] == "REVIEW_REQUIRED")
        rejected_count = sum(1 for e in events if e["type"] == "TASK_REJECTED")

        summary_counts = []
        if ready_count:
            summary_counts.append(f"{ready_count} ready")
        if review_count:
            summary_counts.append(f"{review_count} need review")
        if rejected_count:
            summary_counts.append(f"{rejected_count} rejected")

        parts.append(f"State transitions: {', '.join(summary_counts)}.")

        items = []
        for e in events:
            items.append(f"[{e['type']}] {e['task_id']} ({e.get('project_id', 'unknown')})")
        parts.append("Details: " + "; ".join(items))

        return " ".join(parts)
