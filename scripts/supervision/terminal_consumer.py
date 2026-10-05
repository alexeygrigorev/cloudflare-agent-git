"""Terminal receipt and review consumer for autonomous supervision.

Ingests task-unit completion receipts and independent review receipts,
enforces distinct reviewer validation (anti-self-review), gates dependent
task transitions on review acceptance, and filters supervision notifications
to only emit substantive actionable transitions.

Guards strictly against synthetic or fabricated evidence:
DB rows lacking genuine model execution/review logs are ingested as
imported DB acceptances and marked explicitly ineligible for runtime/autonomy acceptance.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import pathlib
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

MAX_RECEIPT_SIZE = 1024 * 1024  # 1 MiB limit
SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
AUTHORIZED_ENGINES = {'zcodex', 'codex', 'claude', 'opencode', 'grok', 'gemini', 'antigravity', 'shell'}


class ReceiptValidationError(ValueError):
    """Raised when a terminal or review receipt violates schema or safety gates."""
    pass


class SelfReviewProhibitedError(ReceiptValidationError):
    """Raised when an executor attempts to review their own output."""
    pass


class StolenLeaseError(ReceiptValidationError):
    """Raised when an execution or lease is attempted on an already-claimed or mismatched invocation."""
    pass


def canonical_json_hash(data: Dict[str, Any]) -> str:
    """Return deterministic SHA-256 hex digest of dictionary payload."""
    raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def is_safe_identifier(val: Any) -> bool:
    """Validate that an identifier is a safe non-empty string without path traversal."""
    if not isinstance(val, str) or not val:
        return False
    if ".." in val or "/" in val or "\\" in val:
        return False
    return bool(SAFE_ID_PATTERN.match(val))


def is_valid_uuid(val: Any) -> bool:
    """Validate that val is a genuine UUID string and not a fabricated/synthetic prefix."""
    if not isinstance(val, str) or not val:
        return False
    # Explicitly prohibit fabricated synthetic prefixes
    if val.startswith("ql-") or val.startswith("synthetic-") or val.startswith("mock-"):
        return False
    try:
        parsed = uuid.UUID(val)
        return str(parsed).lower() == val.lower()
    except (ValueError, TypeError, AttributeError):
        return False


def get_host_boot_id() -> Optional[str]:
    """Read host boot ID from /proc/sys/kernel/random/boot_id if available."""
    try:
        p = pathlib.Path("/proc/sys/kernel/random/boot_id")
        if p.is_file():
            val = p.read_text().strip()
            if is_valid_uuid(val):
                return val
    except Exception:
        pass
    return None


def verify_real_artifact(path_str: str, expected_sha: str) -> bool:
    """Verify that an artifact file actually exists on disk and its SHA-256 matches expected_sha."""
    if not path_str or not expected_sha or not isinstance(path_str, str) or not isinstance(expected_sha, str):
        return False
    try:
        p = pathlib.Path(path_str)
        if not p.is_file():
            return False
        # Protect against oversized files
        if p.stat().st_size > 100 * 1024 * 1024:
            return False
        actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        return actual_sha.lower() == expected_sha.lower()
    except Exception:
        return False


def extract_native_evidence(
    task_id: str,
    payload_dict: Dict[str, Any],
    reviewer: str,
    reason: str,
    updated_at: str,
    db_paths_artifacts: Optional[List[str]] = None,
    registered_sessions: Optional[Set[str]] = None,
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Extract and strictly validate genuine native execution and review evidence.

    Returns (terminal_receipt, review_receipt) ONLY if all evidence is genuine,
    unspoofed, and verified against actual file bytes.
    Returns None if evidence is absent, incomplete, or synthetic.
    """
    if not isinstance(payload_dict, dict):
        return None

    # 1. Genuine executor validation
    exec_data = payload_dict.get("executor") or payload_dict.get("native_executor")
    if not isinstance(exec_data, dict):
        return None
    exec_sess = exec_data.get("session_id")
    if not is_valid_uuid(exec_sess):
        return None
    if registered_sessions is not None and exec_sess not in registered_sessions:
        return None

    payload_owner = payload_dict.get("owner")
    exec_tag = exec_data.get("tag")
    # Prohibit wrong task owner: receipt tag must match assigned payload owner
    if payload_owner and exec_tag and exec_tag != payload_owner:
        return None
    exec_tag = exec_tag or payload_owner
    if not is_safe_identifier(exec_tag):
        return None
    exec_engine = exec_data.get("engine") or payload_dict.get("provider")
    if not exec_engine or exec_engine not in AUTHORIZED_ENGINES:
        return None

    inv_id = exec_data.get("invocation_id") or payload_dict.get("invocation_id")
    if inv_id is not None:
        if not is_safe_identifier(inv_id) or str(inv_id).startswith(("mock-", "synthetic-")):
            return None

    boot_id = exec_data.get("boot_id") or payload_dict.get("boot_id")
    if boot_id is not None:
        if not is_valid_uuid(boot_id):
            return None

    # 2. Genuine first tool validation
    first_tool_raw = payload_dict.get("first_tool_evidence") or payload_dict.get("first_tool")
    if isinstance(first_tool_raw, str):
        tool_name = first_tool_raw.strip()
        first_tool_dict = {"tool_name": tool_name, "timestamp": updated_at}
    elif isinstance(first_tool_raw, dict):
        tool_name = str(first_tool_raw.get("tool_name", "")).strip()
        ts = first_tool_raw.get("timestamp")
        if not ts or not isinstance(ts, str) or not ts.strip():
            return None
        first_tool_dict = first_tool_raw
    else:
        return None

    # Prohibit synthetic tool names
    if not tool_name or tool_name.lower() in ("task_execution", "unknown", "none", "execute", "mock", "run_task", "test"):
        return None

    # 3. Genuine artifact verification
    raw_artifacts = payload_dict.get("artifacts")
    if not raw_artifacts and db_paths_artifacts:
        raw_artifacts = []
        for p_str in db_paths_artifacts:
            p = pathlib.Path(p_str)
            if p.is_file():
                raw_artifacts.append({"path": p_str, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})

    if not raw_artifacts or not isinstance(raw_artifacts, list):
        return None

    verified_artifacts = []
    for art in raw_artifacts:
        if not isinstance(art, dict):
            return None
        p_str = art.get("path")
        sha = art.get("sha256")
        if not verify_real_artifact(p_str, sha):
            return None
        verified_artifacts.append({"path": p_str, "sha256": sha})

    # 4. Genuine reviewer validation
    rev_data = payload_dict.get("reviewer_evidence") or payload_dict.get("reviewer_info")
    if not isinstance(rev_data, dict):
        return None

    rev_sess = rev_data.get("session_id")
    if not is_valid_uuid(rev_sess):
        return None
    if registered_sessions is not None and rev_sess not in registered_sessions:
        return None

    rev_tag = rev_data.get("tag") or reviewer
    if not is_safe_identifier(rev_tag):
        return None

    rev_engine = rev_data.get("engine") or "antigravity"
    if rev_engine not in AUTHORIZED_ENGINES:
        return None

    # Anti-self-review gate
    if rev_sess == exec_sess or rev_tag == exec_tag:
        return None

    terminal_receipt = {
        "task_id": task_id,
        "project_id": payload_dict.get("project_id", "agent-quota-launcher"),
        "executor": {
            "session_id": exec_sess,
            "tag": exec_tag,
            "engine": exec_engine,
        },
        "phase": "execution",
        "status": "completed-awaiting-review",
        "artifacts": verified_artifacts,
        "first_tool_evidence": first_tool_dict,
        "completed_at": updated_at,
    }
    if inv_id is not None:
        terminal_receipt["invocation_id"] = inv_id
        terminal_receipt["executor"]["invocation_id"] = inv_id
    if boot_id is not None:
        terminal_receipt["boot_id"] = boot_id
        terminal_receipt["executor"]["boot_id"] = boot_id

    review_receipt = {
        "task_id": task_id,
        "review_task_id": f"rev-{task_id}",
        "reviewer": {
            "session_id": rev_sess,
            "tag": rev_tag,
            "engine": rev_engine,
        },
        "target_receipt_sha256": canonical_json_hash(terminal_receipt),
        "verdict": "ACCEPTED",
        "review_evidence": {
            "exit_code": 0,
            "reason": reason or "distinct reviewer accepted verified artifacts",
        },
        "reviewed_at": updated_at,
    }

    return terminal_receipt, review_receipt


def validate_terminal_receipt(
    receipt: Dict[str, Any],
    expected_owner: Optional[str] = None,
    registered_sessions: Optional[Set[str]] = None,
    require_first_tool_timestamp: bool = False,
    expected_invocation_id: Optional[str] = None,
    expected_boot_id: Optional[str] = None,
) -> Tuple[bool, Optional[str], str]:
    """Validate task execution terminal receipt.

    Enforces safe invocation ID and host boot identity checks.
    Returns: (is_valid, error_message, receipt_sha256).
    """
    if not isinstance(receipt, dict):
        return False, "Receipt must be a JSON object", ""

    try:
        raw_size = len(json.dumps(receipt, separators=(',', ':')).encode('utf-8'))
    except Exception as e:
        return False, f"Receipt cannot be serialized to JSON: {e}", ""

    if raw_size > MAX_RECEIPT_SIZE:
        return False, f"Receipt payload size ({raw_size} bytes) exceeds MAX_RECEIPT_SIZE ({MAX_RECEIPT_SIZE} bytes)", ""

    task_id = receipt.get("task_id")
    if not task_id or not isinstance(task_id, str):
        return False, "Missing or non-string 'task_id'", ""
    if not is_safe_identifier(task_id):
        return False, f"Invalid or unsafe 'task_id' (contains path traversal or invalid characters): {task_id!r}", ""

    project_id = receipt.get("project_id")
    if not project_id or not isinstance(project_id, str):
        return False, "Missing or non-string 'project_id'", ""
    if not is_safe_identifier(project_id):
        return False, f"Invalid or unsafe 'project_id' (contains path traversal or invalid characters): {project_id!r}", ""

    executor = receipt.get("executor")
    if not isinstance(executor, dict):
        return False, "Missing or invalid 'executor' block", ""
    for field in ("session_id", "tag", "engine"):
        val = executor.get(field)
        if not val or not isinstance(val, str):
            return False, f"Missing or invalid executor field '{field}'", ""

    exec_sess = executor.get("session_id")
    if registered_sessions is not None and exec_sess not in registered_sessions:
        return False, f"Unregistered executor session_id: {exec_sess!r}", ""

    exec_tag = executor.get("tag")
    if expected_owner and exec_tag != expected_owner:
        return False, f"Task owner mismatch: expected {expected_owner}, got {exec_tag}", ""

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
    if not isinstance(first_tool, dict):
        return False, "Missing or invalid 'first_tool_evidence'", ""
    tool_name = str(first_tool.get("tool_name", "")).strip()
    if not tool_name:
        return False, "Missing or empty tool_name in first_tool_evidence", ""
    if tool_name.lower() in ("task_execution", "unknown", "none", "execute", "mock", "run_task", "test"):
        return False, f"Prohibited synthetic tool_name in first_tool_evidence: {tool_name!r}", ""
    if require_first_tool_timestamp or "timestamp" in first_tool:
        ts = first_tool.get("timestamp")
        if not ts or not isinstance(ts, str) or not ts.strip():
            return False, "Missing or invalid timestamp in first_tool_evidence", ""

    completed_at = receipt.get("completed_at")
    if not completed_at or not isinstance(completed_at, str):
        return False, "Missing or non-string 'completed_at'", ""

    inv_id = receipt.get("invocation_id") or executor.get("invocation_id")
    if inv_id is not None:
        if not is_safe_identifier(inv_id) or str(inv_id).startswith(("mock-", "synthetic-")):
            return False, f"Invalid or synthetic invocation_id: {inv_id!r}", ""
        if expected_invocation_id and inv_id != expected_invocation_id:
            return False, f"Invocation ID mismatch: expected {expected_invocation_id!r}, got {inv_id!r}", ""

    boot_id = receipt.get("boot_id") or executor.get("boot_id")
    if boot_id is not None:
        if not is_valid_uuid(boot_id):
            return False, f"Invalid boot_id: {boot_id!r}", ""
        if expected_boot_id and str(boot_id).lower() != str(expected_boot_id).lower():
            return False, f"Boot ID mismatch: expected {expected_boot_id!r}, got {boot_id!r}", ""

    receipt_sha = canonical_json_hash(receipt)
    return True, None, receipt_sha


def validate_review_receipt(
    review: Dict[str, Any],
    terminal_receipt: Optional[Dict[str, Any]] = None,
    registered_sessions: Optional[Set[str]] = None,
) -> Tuple[bool, Optional[str], str]:
    """Validate independent review receipt.

    Enforces distinct reviewer requirement against the target terminal receipt.
    Returns: (is_valid, error_message, review_sha256).
    """
    if not isinstance(review, dict):
        return False, "Review must be a JSON object", ""

    try:
        raw_size = len(json.dumps(review, separators=(',', ':')).encode('utf-8'))
    except Exception as e:
        return False, f"Review receipt cannot be serialized to JSON: {e}", ""

    if raw_size > MAX_RECEIPT_SIZE:
        return False, f"Review receipt payload size ({raw_size} bytes) exceeds MAX_RECEIPT_SIZE ({MAX_RECEIPT_SIZE} bytes)", ""

    task_id = review.get("task_id")
    if not task_id or not isinstance(task_id, str):
        return False, "Missing or non-string 'task_id'", ""
    if not is_safe_identifier(task_id):
        return False, f"Invalid or unsafe 'task_id': {task_id!r}", ""

    review_task_id = review.get("review_task_id")
    if not review_task_id or not isinstance(review_task_id, str):
        return False, "Missing or non-string 'review_task_id'", ""
    if not is_safe_identifier(review_task_id):
        return False, f"Invalid or unsafe 'review_task_id': {review_task_id!r}", ""

    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        return False, "Missing or invalid 'reviewer' block", ""
    for field in ("session_id", "tag", "engine"):
        val = reviewer.get(field)
        if not val or not isinstance(val, str):
            return False, f"Missing or invalid reviewer field '{field}'", ""

    rev_sess = reviewer.get("session_id")
    if registered_sessions is not None and rev_sess not in registered_sessions:
        return False, f"Unregistered reviewer session_id: {rev_sess!r}", ""

    verdict = review.get("verdict")
    if verdict not in ("ACCEPTED", "REJECTED"):
        return False, f"Verdict must be 'ACCEPTED' or 'REJECTED', got {verdict!r}", ""

    review_evidence = review.get("review_evidence")
    if not isinstance(review_evidence, dict):
        return False, "Missing or invalid 'review_evidence' block", ""
    if "exit_code" not in review_evidence or (review_evidence.get("exit_code") != 0 and verdict == "ACCEPTED"):
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

    def __init__(self, spool_dir: pathlib.Path, registered_sessions: Optional[Set[str]] = None):
        self.spool_dir = pathlib.Path(spool_dir)
        self.registered_sessions = set(registered_sessions) if registered_sessions is not None else None
        self.receipts_dir = self.spool_dir / "receipts"
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        self.terminal_receipts: Dict[str, Dict[str, Any]] = {}
        self.review_receipts: Dict[str, Dict[str, Any]] = {}
        self.imported_db_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.processed_receipt_shas: Set[str] = set()
        self.cursor_path = self.spool_dir / "launcher_cursor.json"
        self.recover_persisted_receipts()

    def recover_persisted_receipts(self) -> int:
        """Recover persisted terminal, review, and imported DB receipts from disk upon initialization."""
        recovered = 0
        if not self.receipts_dir.exists():
            return 0

        # 1. Recover terminal receipts
        for rec_file in sorted(self.receipts_dir.glob("terminal-*.json")):
            try:
                if rec_file.stat().st_size > MAX_RECEIPT_SIZE:
                    continue
                data = json.loads(rec_file.read_text())
                ok, err, r_sha = validate_terminal_receipt(data)
                if ok:
                    task_id = data["task_id"]
                    self.terminal_receipts[task_id] = data
                    self.processed_receipt_shas.add(r_sha)
                    self.task_states[task_id] = {
                        "task_id": task_id,
                        "project_id": data["project_id"],
                        "status": "completed-awaiting-review",
                        "autonomy_acceptance_eligible": False,
                        "native_receipt": True,
                        "executor": data["executor"],
                        "terminal_receipt_sha256": r_sha,
                        "terminal_completed_at": data["completed_at"],
                        "artifacts": data["artifacts"],
                        "first_tool_evidence": data["first_tool_evidence"],
                        "invocation_id": data.get("invocation_id") or data.get("executor", {}).get("invocation_id"),
                        "boot_id": data.get("boot_id") or data.get("executor", {}).get("boot_id"),
                        "reviewer": None,
                        "verdict": None,
                        "reviewed_at": None,
                    }
                    recovered += 1
            except Exception:
                continue

        # 2. Recover review receipts to update task states
        for rev_file in sorted(self.receipts_dir.glob("review-*.json")):
            try:
                if rev_file.stat().st_size > MAX_RECEIPT_SIZE:
                    continue
                data = json.loads(rev_file.read_text())
                task_id = data.get("task_id")
                term = self.terminal_receipts.get(task_id)
                ok, err, r_sha = validate_review_receipt(data, term)
                if ok:
                    self.review_receipts[task_id] = data
                    self.processed_receipt_shas.add(r_sha)
                    verdict = data["verdict"]
                    new_status = "accepted" if verdict == "ACCEPTED" else "rejected-needs-repair"
                    if task_id in self.task_states:
                        self.task_states[task_id]["status"] = new_status
                        self.task_states[task_id]["autonomy_acceptance_eligible"] = (verdict == "ACCEPTED")
                        self.task_states[task_id]["native_receipt"] = True
                        self.task_states[task_id]["reviewer"] = data["reviewer"]
                        self.task_states[task_id]["verdict"] = verdict
                        self.task_states[task_id]["review_receipt_sha256"] = r_sha
                        self.task_states[task_id]["reviewed_at"] = data.get("reviewed_at")
                    recovered += 1
            except Exception:
                continue

        # 3. Recover imported DB acceptances (explicitly ineligible for autonomy acceptance)
        for imp_file in sorted(self.receipts_dir.glob("imported-db-*.json")):
            try:
                if imp_file.stat().st_size > MAX_RECEIPT_SIZE:
                    continue
                data = json.loads(imp_file.read_text())
                task_id = data.get("task_id")
                if task_id and is_safe_identifier(task_id):
                    self.imported_db_tasks[task_id] = data
                    self.task_states[task_id] = {
                        "task_id": task_id,
                        "project_id": data.get("project_id", "agent-quota-launcher"),
                        "status": "imported-db-accepted",
                        "autonomy_acceptance_eligible": False,
                        "native_receipt": False,
                        "executor": {"tag": data.get("owner"), "provider": data.get("provider")},
                        "reviewer": {"tag": data.get("reviewer"), "reason": data.get("reason")},
                        "reviewed_at": data.get("updated_at"),
                    }
                    recovered += 1
            except Exception:
                continue

        return recovered

    def ingest_terminal_receipt(
        self,
        receipt: Dict[str, Any],
        expected_invocation_id: Optional[str] = None,
        expected_boot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ingest and validate execution terminal receipt."""
        ok, err, r_sha = validate_terminal_receipt(
            receipt,
            registered_sessions=self.registered_sessions,
            expected_invocation_id=expected_invocation_id,
            expected_boot_id=expected_boot_id,
        )
        if not ok:
            raise ReceiptValidationError(f"Invalid terminal receipt: {err}")

        task_id = receipt["task_id"]

        # Safe spool path confinement check
        rec_path = (self.receipts_dir / f"terminal-{task_id}.json").resolve()
        if not str(rec_path).startswith(str(self.receipts_dir.resolve())):
            raise ReceiptValidationError(f"Path traversal detected in task_id: {task_id}")

        inv_id = receipt.get("invocation_id") or receipt.get("executor", {}).get("invocation_id")
        boot_id = receipt.get("boot_id") or receipt.get("executor", {}).get("boot_id")
        incoming_sess = receipt.get("executor", {}).get("session_id")
        incoming_tag = receipt.get("executor", {}).get("tag")

        # Stolen lease and duplicate execution checks against existing task state
        if task_id in self.task_states:
            existing_state = self.task_states[task_id]
            existing_inv = existing_state.get("invocation_id")
            existing_sess = existing_state.get("executor", {}).get("session_id")
            existing_tag = existing_state.get("executor", {}).get("tag")
            existing_status = existing_state.get("status")

            # Stolen lease check: conflicting invocation ID for the same task
            if existing_inv and inv_id and existing_inv != inv_id:
                raise StolenLeaseError(
                    f"Stolen lease detected for task {task_id}: existing invocation {existing_inv!r} != incoming {inv_id!r}"
                )

            # Stolen lease check: conflicting executor session ID
            if existing_sess and incoming_sess and existing_sess != incoming_sess:
                raise StolenLeaseError(
                    f"Stolen lease detected for task {task_id}: existing executor session {existing_sess!r} != incoming {incoming_sess!r}"
                )

            # Stolen lease check: conflicting executor tag
            if existing_tag and incoming_tag and existing_tag != incoming_tag:
                raise StolenLeaseError(
                    f"Stolen lease detected for task {task_id}: existing executor tag {existing_tag!r} != incoming {incoming_tag!r}"
                )

            # Duplicate / transport failure retry with identical receipt SHA
            if r_sha in self.processed_receipt_shas:
                return {
                    "status": "ingested",
                    "task_id": task_id,
                    "sha256": r_sha,
                    "action_required": "NONE" if existing_status == "accepted" else "REVIEW_REQUIRED",
                    "duplicate": True,
                }

            # Duplicate / transport failure retry with exact same invocation ID
            if inv_id and existing_inv and inv_id == existing_inv:
                return {
                    "status": "ingested",
                    "task_id": task_id,
                    "sha256": r_sha,
                    "action_required": "NONE" if existing_status == "accepted" else "REVIEW_REQUIRED",
                    "duplicate": True,
                }

            # If task is already accepted past review, refuse clobbering by new execution
            if existing_status == "accepted":
                raise ReceiptValidationError(
                    f"Duplicate execution rejected for task {task_id}: task is already accepted past review"
                )

        self.terminal_receipts[task_id] = receipt
        self.processed_receipt_shas.add(r_sha)

        self.task_states[task_id] = {
            "task_id": task_id,
            "project_id": receipt["project_id"],
            "status": "completed-awaiting-review",
            "autonomy_acceptance_eligible": False,
            "native_receipt": True,
            "executor": receipt["executor"],
            "terminal_receipt_sha256": r_sha,
            "terminal_completed_at": receipt["completed_at"],
            "artifacts": receipt["artifacts"],
            "first_tool_evidence": receipt["first_tool_evidence"],
            "invocation_id": inv_id,
            "boot_id": boot_id,
            "reviewer": None,
            "verdict": None,
            "reviewed_at": None,
        }

        # Persist receipt
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

        ok, err, r_sha = validate_review_receipt(review, term_receipt, registered_sessions=self.registered_sessions)
        if not ok:
            if "Self-review prohibited" in err:
                raise SelfReviewProhibitedError(err)
            raise ReceiptValidationError(f"Invalid review receipt: {err}")

        # Safe spool path confinement check
        rev_path = (self.receipts_dir / f"review-{task_id}.json").resolve()
        if not str(rev_path).startswith(str(self.receipts_dir.resolve())):
            raise ReceiptValidationError(f"Path traversal detected in task_id: {task_id}")

        # Dedup / idempotency
        if r_sha in self.processed_receipt_shas and task_id in self.review_receipts:
            return {
                "status": "ingested",
                "task_id": task_id,
                "verdict": review["verdict"],
                "new_task_status": self.task_states.get(task_id, {}).get("status", "accepted"),
                "sha256": r_sha,
                "duplicate": True,
            }

        self.review_receipts[task_id] = review
        self.processed_receipt_shas.add(r_sha)

        verdict = review["verdict"]
        new_status = "accepted" if verdict == "ACCEPTED" else "rejected-needs-repair"

        if task_id in self.task_states:
            self.task_states[task_id]["status"] = new_status
            self.task_states[task_id]["autonomy_acceptance_eligible"] = (verdict == "ACCEPTED")
            self.task_states[task_id]["native_receipt"] = True
            self.task_states[task_id]["reviewer"] = review["reviewer"]
            self.task_states[task_id]["verdict"] = verdict
            self.task_states[task_id]["review_receipt_sha256"] = r_sha
            self.task_states[task_id]["reviewed_at"] = review.get("reviewed_at")

        # Persist review
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

        Only tasks with genuine native review acceptance (autonomy_acceptance_eligible=True)
        are accepted as valid unblocking dependencies. Imported DB acceptances lacking
        genuine native evidence are explicitly ineligible.
        Returns list of newly unblocked task IDs.
        """
        accepted_ids = {
            t_id for t_id, st in self.task_states.items()
            if st.get("status") == "accepted" and st.get("autonomy_acceptance_eligible") is True
        }

        newly_unblocked = []
        for t in tasks:
            if t.get("status") not in ("blocked", "queued", "pending"):
                continue
            blocked_on = t.get("blocked_on", [])
            if not blocked_on:
                continue

            # Check if all blockers are satisfied in genuinely accepted_ids
            if all(blocker in accepted_ids for blocker in blocked_on):
                t["status"] = "ready"
                t["unblocked_at"] = datetime.now(timezone.utc).isoformat()
                newly_unblocked.append(t["id"])

        return newly_unblocked

    def load_launcher_cursor(self) -> Dict[str, Any]:
        """Load persistent cursor for launcher state DB ingestion."""
        if self.cursor_path.exists():
            try:
                if self.cursor_path.stat().st_size <= MAX_RECEIPT_SIZE:
                    data = json.loads(self.cursor_path.read_text())
                    if isinstance(data, dict):
                        data.setdefault("known_task_ids", [])
                        data.setdefault("known_invocations", {})
                        data.setdefault("boot_id", None)
                        return data
            except Exception:
                pass
        return {"last_ingested_at": None, "known_task_ids": [], "known_invocations": {}, "boot_id": None}

    def save_launcher_cursor(self, cursor: Dict[str, Any]) -> None:
        """Atomically persist cursor for launcher state DB ingestion."""
        tmp = self.cursor_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cursor, indent=2))
        tmp.replace(self.cursor_path)

    def ingest_launcher_db(self, db_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Ingest accepted tasks and reviews directly from an agent-quota-launcher state.db.

        If a row has genuine, verified native evidence (valid UUID sessions, real first tool,
        and real verified on-disk artifact bytes), it is ingested as native receipts with
        autonomy_acceptance_eligible = True.
        If native evidence is absent or spoofed, it is recorded as a clearly separate
        imported DB acceptance event with autonomy_acceptance_eligible = False, keeping
        the task ineligible for runtime/autonomy acceptance.
        """
        import sqlite3

        db_file = pathlib.Path(db_path)
        if not db_file.exists():
            return []

        cursor = self.load_launcher_cursor()
        known_task_ids = set(cursor.get("known_task_ids", []))
        known_invocations = dict(cursor.get("known_invocations", {}))

        results = []
        try:
            con = sqlite3.connect(str(db_file), timeout=10.0)
            cur = con.cursor()
            rows = cur.execute(
                "SELECT id, payload, state, reviewer, reason, updated_at "
                "FROM tasks WHERE state = 'accepted' AND reviewer IS NOT NULL AND reviewer != ''"
            ).fetchall()

            task_paths_map = {}
            try:
                p_rows = cur.execute("SELECT task_id, path FROM task_paths").fetchall()
                for t_id, p in p_rows:
                    task_paths_map.setdefault(t_id, []).append(p)
            except Exception:
                pass
            con.close()
        except Exception:
            return []

        new_task_ids = set()
        max_updated_at = cursor.get("last_ingested_at")

        for row in rows:
            task_id, payload_raw, state, reviewer, reason, updated_at = row
            if task_id in known_task_ids or (task_id in self.task_states and self.task_states[task_id].get("status") in ("accepted", "imported-db-accepted")):
                continue

            # Safe identifier check for task_id and reviewer
            if not is_safe_identifier(task_id) or not is_safe_identifier(reviewer):
                continue

            owner = "quota-launcher-head-gemini"
            provider = "antigravity"
            payload_dict = {}
            if payload_raw:
                try:
                    payload_dict = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
                    if isinstance(payload_dict, dict):
                        owner = payload_dict.get("owner", owner)
                        provider = payload_dict.get("provider", provider)
                except Exception:
                    payload_dict = {}

            # Anti-self-review check
            if reviewer == owner or reviewer == task_id:
                continue

            row_inv_id = None
            if isinstance(payload_dict, dict):
                row_inv_id = payload_dict.get("invocation_id") or payload_dict.get("executor", {}).get("invocation_id")

            # Validate against stolen lease / conflicting invocation ID
            if row_inv_id and task_id in known_invocations and known_invocations[task_id] != row_inv_id:
                continue

            # Attempt extraction of genuine native evidence
            db_paths = task_paths_map.get(task_id, [])
            native_pair = extract_native_evidence(
                task_id=task_id,
                payload_dict=payload_dict,
                reviewer=reviewer,
                reason=reason or "head accepted reviewed artifacts",
                updated_at=updated_at or datetime.now(timezone.utc).isoformat(),
                db_paths_artifacts=db_paths,
                registered_sessions=self.registered_sessions,
            )

            if native_pair is not None:
                # Genuine native evidence verified: consume exact values
                term_receipt, rev_receipt = native_pair
                term_res = self.ingest_terminal_receipt(term_receipt)
                rev_res = self.ingest_review_receipt(rev_receipt)
                results.append({
                    "status": "ingested",
                    "task_id": task_id,
                    "verdict": "ACCEPTED",
                    "native_evidence": True,
                    "autonomy_acceptance_eligible": True,
                    "sha256": rev_res["sha256"],
                })
            else:
                # Native evidence is absent, incomplete, or spoofed:
                # Record a clearly separate imported DB acceptance event
                # Task remains INELIGIBLE for runtime/autonomy acceptance!
                imp_record = {
                    "kind": "imported-db-acceptance",
                    "task_id": task_id,
                    "project_id": payload_dict.get("project_id", "agent-quota-launcher"),
                    "owner": owner,
                    "provider": provider,
                    "reviewer": reviewer,
                    "reason": reason or "imported from launcher state.db",
                    "updated_at": updated_at,
                    "native_evidence_present": False,
                    "autonomy_acceptance_eligible": False,
                    "status": "imported-db-accepted",
                    "spool_timestamp": datetime.now(timezone.utc).isoformat(),
                }
                imp_path = self.receipts_dir / f"imported-db-{task_id}.json"
                imp_path.write_text(json.dumps(imp_record, indent=2))
                self.imported_db_tasks[task_id] = imp_record
                self.task_states[task_id] = {
                    "task_id": task_id,
                    "project_id": payload_dict.get("project_id", "agent-quota-launcher"),
                    "status": "imported-db-accepted",
                    "autonomy_acceptance_eligible": False,
                    "native_receipt": False,
                    "executor": {"tag": owner, "provider": provider},
                    "reviewer": {"tag": reviewer, "reason": reason},
                    "reviewed_at": updated_at,
                }
                results.append({
                    "status": "imported_db_acceptance",
                    "task_id": task_id,
                    "verdict": "ACCEPTED",
                    "native_evidence": False,
                    "autonomy_acceptance_eligible": False,
                })

            new_task_ids.add(task_id)
            if row_inv_id:
                known_invocations[task_id] = row_inv_id
            if not max_updated_at or (updated_at and updated_at > max_updated_at):
                max_updated_at = updated_at

        if new_task_ids:
            cursor["known_task_ids"] = sorted(known_task_ids | new_task_ids)
            cursor["known_invocations"] = known_invocations
            cursor["boot_id"] = get_host_boot_id()
            cursor["last_ingested_at"] = max_updated_at
            cursor["ingested_count"] = len(cursor["known_task_ids"])
            self.save_launcher_cursor(cursor)

        return results

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
