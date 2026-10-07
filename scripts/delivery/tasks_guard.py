#!/usr/bin/env python3
"""
scripts/delivery/tasks_guard.py

Anti-stale registry guard and atomic task writer for coordination/TASKS.json.
Directive C3069 / scale50-E (addressing regression incident C3067).

Key Capabilities:
1. Optimistic Concurrency Control (CAS): validates expected content hash and generation.
2. Anti-Stale Registry Guard: preserves all historical task IDs; rejects writes that
   silently drop task IDs unless an explicit, audited tombstone is provided.
3. Checkpoint & Status Preservation: prevents erasure or truncation of checkpoint_history,
   and prevents silent downgrade of 'done' or 'accepted' statuses without an audited reason.
4. Atomic, Locked Writes: acquires flock and writes via temporary file and atomic replace.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


# =====================================================================
# Exceptions
# =====================================================================

class TasksGuardError(Exception):
    """Base exception for all tasks guard errors."""
    pass


class ConcurrentModificationError(TasksGuardError):
    """Raised when expected generation or content hash does not match current state."""
    pass


class StaleOverwriteError(TasksGuardError):
    """Raised when an update would result in stale overwrite, dropped IDs, or unauthorized downgrades."""
    pass


class TombstoneRequiredError(StaleOverwriteError):
    """Raised when task IDs are dropped without an explicit, audited tombstone."""
    pass


class HistoryTruncationError(TasksGuardError):
    """Raised when checkpoint_history or audit trails are truncated or modified."""
    pass


# =====================================================================
# Hashing & Extraction Helpers
# =====================================================================

def _extract_task_records(data: Any) -> List[dict]:
    """Extract list of task record dictionaries from data structure."""
    if isinstance(data, dict):
        if "tasks" in data:
            raw_tasks = data["tasks"]
            if isinstance(raw_tasks, list):
                return [t for t in raw_tasks if isinstance(t, dict)]
            elif isinstance(raw_tasks, dict):
                return [t for t in raw_tasks.values() if isinstance(t, dict)]
        if all(isinstance(v, dict) for v in data.values()) and data:
            return list(data.values())
    elif isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    return []


def compute_tasks_hash(data: dict) -> str:
    """Canonical SHA-256 over task records (sorted keys, stable JSON)."""
    tasks = _extract_task_records(data)
    # Sort task list by ID (or string representation) for canonical stability
    sorted_tasks = sorted(
        tasks,
        key=lambda t: str(t.get("id", ""))
    )
    # Serialize with sorted keys, compact separators, UTF-8
    canonical_json = json.dumps(
        sorted_tasks,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_file_hash(path: Union[str, Path]) -> str:
    """SHA-256 over raw file bytes."""
    p = Path(path).resolve()
    return hashlib.sha256(p.read_bytes()).hexdigest()


# =====================================================================
# Validation Logic
# =====================================================================

def validate_task_update(
    current_data: dict,
    new_data: dict,
    expected_hash: Optional[str] = None,
    expected_gen: Optional[int] = None,
    tombstones: Optional[Dict[str, Dict[str, str]]] = None
) -> Tuple[bool, List[str]]:
    """
    Validate that candidate task update is safe and does not drop records or history.

    Parameters:
      current_data: Existing tasks state dictionary.
      new_data: Candidate tasks state dictionary.
      expected_hash: If provided, must match current content hash, stored content_sha256,
                     or raw file hash. Raises ConcurrentModificationError on mismatch.
      expected_gen: If provided, must match current generation (if present).
                    Raises ConcurrentModificationError on mismatch.
      tombstones: Dictionary mapping dropped task_id to required audit dictionary:
                  {'reason': str, 'author': str, 'timestamp': str, 'approved_by': str}.

    Returns:
      (True, warnings): Tuple of boolean status and non-fatal audit warnings.

    Raises:
      ConcurrentModificationError: if expected_hash or expected_gen mismatch.
      TombstoneRequiredError / StaleOverwriteError: if task IDs are dropped without valid tombstone.
      HistoryTruncationError: if checkpoint_history is truncated or erased.
      StaleOverwriteError: if accepted/done status is downgraded without audited reason.
    """
    # 1. Validate expected content hash (optimistic concurrency / CAS)
    if expected_hash is not None:
        valid_hashes: Set[str] = set()
        valid_hashes.add(compute_tasks_hash(current_data))
        if isinstance(current_data, dict):
            if current_data.get("content_sha256"):
                valid_hashes.add(current_data["content_sha256"])
            if current_data.get("_file_hash"):
                valid_hashes.add(current_data["_file_hash"])
        if expected_hash not in valid_hashes:
            raise ConcurrentModificationError(
                f"Content hash mismatch: expected '{expected_hash}', current valid hashes: {valid_hashes}"
            )

    # 2. Validate expected generation
    if expected_gen is not None:
        curr_gen = current_data.get("generation") if isinstance(current_data, dict) else None
        if curr_gen is not None and curr_gen != expected_gen:
            raise ConcurrentModificationError(
                f"Generation mismatch: expected {expected_gen}, found {curr_gen}"
            )
        elif curr_gen is None and expected_gen != 0:
            raise ConcurrentModificationError(
                f"Generation mismatch: expected {expected_gen}, but current generation is unset"
            )

    warnings: List[str] = []

    # 3. Extract existing task IDs and candidate task IDs
    curr_tasks = _extract_task_records(current_data)
    curr_by_id = {t["id"]: t for t in curr_tasks if "id" in t}
    curr_ids = set(curr_by_id.keys())

    new_tasks = _extract_task_records(new_data)
    new_by_id = {t["id"]: t for t in new_tasks if "id" in t}
    new_ids = set(new_by_id.keys())

    # 4. Check for dropped task IDs and enforce audited tombstones
    dropped_ids = curr_ids - new_ids
    if dropped_ids:
        active_tombstones = {}
        if isinstance(new_data, dict) and isinstance(new_data.get("tombstones"), dict):
            active_tombstones.update(new_data["tombstones"])
        if tombstones:
            active_tombstones.update(tombstones)

        required_fields = ("reason", "author", "timestamp", "approved_by")
        for dropped_id in sorted(dropped_ids):
            if dropped_id not in active_tombstones:
                raise TombstoneRequiredError(
                    f"Stale overwrite rejected: task ID '{dropped_id}' was dropped without "
                    f"an explicit audited tombstone (total dropped: {len(dropped_ids)} IDs: {sorted(dropped_ids)})"
                )
            tomb = active_tombstones[dropped_id]
            if not isinstance(tomb, dict):
                raise TombstoneRequiredError(
                    f"Tombstone for dropped task ID '{dropped_id}' must be a dictionary"
                )
            for rf in required_fields:
                val = tomb.get(rf)
                if not val or not isinstance(val, str) or not val.strip():
                    raise TombstoneRequiredError(
                        f"Tombstone for dropped task ID '{dropped_id}' missing or empty required field '{rf}'"
                    )
            warnings.append(
                f"Audited tombstone accepted for dropped task '{dropped_id}': "
                f"reason='{tomb['reason']}', author='{tomb['author']}', approved_by='{tomb['approved_by']}'"
            )

    # 5. Checkpoint History Preservation
    common_ids = curr_ids & new_ids
    for task_id in common_ids:
        curr_t = curr_by_id[task_id]
        new_t = new_by_id[task_id]

        curr_cp = curr_t.get("checkpoint_history")
        if curr_cp is not None and isinstance(curr_cp, list):
            new_cp = new_t.get("checkpoint_history")
            if new_cp is None or not isinstance(new_cp, list):
                raise HistoryTruncationError(
                    f"Task '{task_id}' has {len(curr_cp)} checkpoints in current state, "
                    f"but candidate state has no checkpoint_history"
                )
            if len(new_cp) < len(curr_cp):
                raise HistoryTruncationError(
                    f"Task '{task_id}' checkpoint_history was truncated: "
                    f"current has {len(curr_cp)} entries, candidate has {len(new_cp)}"
                )
            for idx, curr_entry in enumerate(curr_cp):
                new_entry = new_cp[idx]
                if curr_entry != new_entry:
                    raise HistoryTruncationError(
                        f"Task '{task_id}' historical checkpoint at index {idx} was modified or erased. "
                        f"Expected {curr_entry}, got {new_entry}"
                    )

    # 6. Status/ACK Preservation
    accepted_statuses = {"done", "accepted"}
    for task_id in common_ids:
        curr_t = curr_by_id[task_id]
        new_t = new_by_id[task_id]

        curr_status = curr_t.get("status")
        new_status = new_t.get("status")

        if curr_status in accepted_statuses and new_status not in accepted_statuses:
            audit_reason = None
            if tombstones and task_id in tombstones:
                audit_reason = tombstones[task_id].get("reason")
            if not audit_reason and isinstance(new_data, dict):
                audit_reason = (
                    new_t.get("status_downgrade_reason")
                    or new_t.get("downgrade_reason")
                    or new_t.get("status_change_reason")
                    or new_t.get("audit_reason")
                )
            if not audit_reason and isinstance(new_t.get("status_history"), list):
                sh = new_t["status_history"]
                if sh and isinstance(sh[-1], dict) and sh[-1].get("reason"):
                    audit_reason = sh[-1]["reason"]

            if not audit_reason:
                raise StaleOverwriteError(
                    f"Task '{task_id}' was marked '{curr_status}' and silently downgraded to "
                    f"'{new_status}' without an audited reason"
                )
            warnings.append(
                f"Task '{task_id}' status downgraded from '{curr_status}' to '{new_status}' "
                f"with audited reason: {audit_reason}"
            )

        if curr_t.get("accepted_at") and not new_t.get("accepted_at"):
            audit_reason = (
                new_t.get("status_downgrade_reason")
                or new_t.get("downgrade_reason")
                or (tombstones.get(task_id, {}).get("reason") if tombstones else None)
            )
            if not audit_reason:
                raise StaleOverwriteError(
                    f"Task '{task_id}' accepted_at timestamp was removed without an audited reason"
                )

    return True, warnings


# =====================================================================
# Atomic Locked Writer
# =====================================================================

def safe_update_tasks_file(
    path: Union[str, Path],
    update_fn_or_data: Union[dict, Callable[[dict], Optional[dict]]],
    expected_hash: Optional[str] = None,
    tombstones: Optional[Dict[str, Dict[str, str]]] = None,
    lock_path: Optional[Union[str, Path]] = None
) -> dict:
    """
    Perform atomic, locked update to tasks JSON file with optimistic concurrency validation.

    Parameters:
      path: Path to target tasks JSON file (e.g. coordination/TASKS.json).
      update_fn_or_data: Either a new dictionary or a function taking current_data and returning updated dict.
      expected_hash: Expected content SHA-256 (or raw file SHA-256) of current file state.
      tombstones: Audited tombstones dictionary for any intentionally deleted task IDs.
      lock_path: Path to flock lockfile (defaults to .local/tasks.lock or path.with_suffix('.lock')).

    Returns:
      Updated dictionary written to disk, including updated generation and content_sha256.
    """
    path = Path(path).resolve()

    if lock_path is None:
        # Canonical lockfile used across all teams per coordination/OPERATING-MODEL.md
        cwd_local = Path(".local")
        local_dir = path.parent / ".local"
        repo_local = path.parent.parent / ".local"
        if (cwd_local / "task-registry.lock").exists() or cwd_local.is_dir():
            lock_path = cwd_local / "task-registry.lock"
        elif (repo_local / "task-registry.lock").exists() or repo_local.is_dir():
            lock_path = repo_local / "task-registry.lock"
        elif (local_dir / "task-registry.lock").exists() or local_dir.is_dir():
            lock_path = local_dir / "task-registry.lock"
        else:
            lock_path = path.with_suffix(".lock")
    else:
        lock_path = Path(lock_path).resolve()

    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            # 1. Read current state
            if path.exists():
                raw_bytes = path.read_bytes()
                file_hash = hashlib.sha256(raw_bytes).hexdigest()
                current_data = json.loads(raw_bytes.decode("utf-8"))
                current_data["_file_hash"] = file_hash
            else:
                current_data = {
                    "schema_version": 1,
                    "updated_at": None,
                    "generation": 0,
                    "content_sha256": None,
                    "tasks": [],
                    "_file_hash": None,
                }

            # 2. Compute new candidate state
            if callable(update_fn_or_data):
                clean_input = copy.deepcopy(current_data)
                clean_input.pop("_file_hash", None)
                candidate_data = update_fn_or_data(clean_input)
                if candidate_data is None:
                    candidate_data = clean_input
            elif isinstance(update_fn_or_data, dict):
                candidate_data = copy.deepcopy(update_fn_or_data)
            else:
                raise TypeError(
                    f"update_fn_or_data must be callable or dict, got {type(update_fn_or_data).__name__}"
                )

            # 3. Increment generation counter and stamp timestamp + hash
            curr_gen = current_data.get("generation", 0) or 0
            candidate_data["generation"] = curr_gen + 1
            candidate_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            candidate_data["content_sha256"] = compute_tasks_hash(candidate_data)

            # 4. Perform validation
            validate_task_update(
                current_data=current_data,
                new_data=candidate_data,
                expected_hash=expected_hash,
                expected_gen=current_data.get("generation"),
                tombstones=tombstones
            )

            # 5. Prepare payload and write to temporary file in same parent directory
            output_data = {k: v for k, v in candidate_data.items() if not k.startswith("_")}
            payload = json.dumps(output_data, indent=2, ensure_ascii=False) + "\n"

            temp_file = path.parent / f"{path.name}.tmp.{os.getpid()}"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_file, path)
            finally:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

            return output_data
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


# =====================================================================
# CLI
# =====================================================================

def cli_main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for tasks guard."""
    parser = argparse.ArgumentParser(
        prog="tasks_guard",
        description="Anti-stale registry guard and atomic task writer (C3069 / scale50-E)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: hash --file <path>
    hash_parser = subparsers.add_parser("hash", help="Compute canonical tasks hash and file hash")
    hash_parser.add_argument("--file", "-f", required=True, type=Path, help="Path to tasks JSON file")

    # Subcommand: validate --current <path> --candidate <path>
    validate_parser = subparsers.add_parser("validate", help="Validate candidate update against current file")
    validate_parser.add_argument("--current", "-c", required=True, type=Path, help="Path to current tasks JSON")
    validate_parser.add_argument("--candidate", "-n", required=True, type=Path, help="Path to candidate tasks JSON")

    # Subcommand: check --file <path>
    check_parser = subparsers.add_parser("check", help="Check internal consistency of a tasks JSON file")
    check_parser.add_argument("--file", "-f", required=True, type=Path, help="Path to tasks JSON file")

    args = parser.parse_args(argv)

    if args.subcommand == "hash":
        if not args.file.exists():
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            return 1
        data = json.loads(args.file.read_text(encoding="utf-8"))
        th = compute_tasks_hash(data)
        fh = compute_file_hash(args.file)
        print(f"tasks_hash: {th}")
        print(f"file_hash:  {fh}")
        return 0

    elif args.subcommand == "validate":
        if not args.current.exists():
            print(f"ERROR: Current file not found: {args.current}", file=sys.stderr)
            return 1
        if not args.candidate.exists():
            print(f"ERROR: Candidate file not found: {args.candidate}", file=sys.stderr)
            return 1
        curr_data = json.loads(args.current.read_text(encoding="utf-8"))
        cand_data = json.loads(args.candidate.read_text(encoding="utf-8"))
        try:
            valid, warnings = validate_task_update(curr_data, cand_data)
            print("VALID: Candidate update passed all integrity checks")
            for w in warnings:
                print(f"WARNING: {w}")
            return 0
        except TasksGuardError as e:
            print(f"INVALID: {type(e).__name__}: {e}", file=sys.stderr)
            return 1

    elif args.subcommand == "check":
        if not args.file.exists():
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            return 1
        try:
            data = json.loads(args.file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
            return 1
        tasks = _extract_task_records(data)
        ids = [t["id"] for t in tasks if isinstance(t, dict) and "id" in t]
        if len(ids) != len(set(ids)):
            print("ERROR: Duplicate task IDs found in tasks list", file=sys.stderr)
            return 1
        computed_hash = compute_tasks_hash(data)
        stored_hash = data.get("content_sha256")
        if stored_hash and stored_hash != computed_hash:
            print(
                f"ERROR: Stored content_sha256 ({stored_hash}) does not match "
                f"computed hash ({computed_hash})",
                file=sys.stderr
            )
            return 1
        print(
            f"OK: {args.file} is consistent ({len(tasks)} tasks, "
            f"generation={data.get('generation', 'unset')}, hash={computed_hash})"
        )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
