#!/usr/bin/env python3
"""
Durable Task Ownership Lease & Fencing Manager.
Pure Python standard library implementation with atomic file-based locking (fcntl.flock).

Guarantees:
1. Mutual Exclusion: At most one worker holds an active, unexpired lease for a task.
2. Monotonic Fencing Tokens: Every lease reclaim or reassignment strictly increments
   the task's fencing token. Old workers with stale tokens cannot overwrite state.
3. Safe Peer Takeover: When a lease expires (worker crash, OOM, network freeze), any
   eligible peer worker or the supervisor can reclaim the task safely.
4. Stale Write Rejection: Prevents zombie / split-brain worker writes by validating
   fencing tokens before any state or artifact mutation.
5. Idempotent Renewal: Active lease holders can heartbeat and extend lease TTL.
"""

from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass, field
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LeaseError(Exception):
    """Base exception for lease operations."""


class LeaseAlreadyHeldError(LeaseError):
    """Raised when acquiring a lease that is actively held by another worker."""


class LeaseExpiredError(LeaseError):
    """Raised when attempting an operation on an expired lease."""


class LeaseNotFoundError(LeaseError):
    """Raised when a lease for the specified task does not exist."""


class HolderMismatchError(LeaseError):
    """Raised when caller identity does not match the active lease holder."""


class FencingTokenMismatchError(LeaseError):
    """Raised when fencing token does not match active lease (stale write / zombie worker)."""


class LeaseNotExpiredError(LeaseError):
    """Raised when attempting to reclaim a lease that has not expired yet."""


class LeaseStorageCorruptedError(LeaseError):
    """Raised when lease storage file exists but contains corrupted or invalid JSON (fails closed)."""


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class Lease:
    task_id: str
    lease_holder: str
    fence_token: int
    lease_expires_at: float
    acquired_at: float
    updated_at: float
    status: str = "active"  # "active", "released", "revoked"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        ts = now if now is not None else time.time()
        return ts >= self.lease_expires_at

    def time_remaining(self, now: Optional[float] = None) -> float:
        ts = now if now is not None else time.time()
        return max(0.0, self.lease_expires_at - ts)

    def is_valid(
        self,
        holder: str,
        fence_token: int,
        now: Optional[float] = None,
    ) -> bool:
        if self.status != "active":
            return False
        if self.lease_holder != holder:
            return False
        if self.fence_token != fence_token:
            return False
        return not self.is_expired(now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Lease:
        return cls(
            task_id=data["task_id"],
            lease_holder=data["lease_holder"],
            fence_token=int(data["fence_token"]),
            lease_expires_at=float(data["lease_expires_at"]),
            acquired_at=float(data["acquired_at"]),
            updated_at=float(data["updated_at"]),
            status=data.get("status", "active"),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# LeaseManager
# ---------------------------------------------------------------------------

class LeaseManager:
    """
    Atomic file-based task lease and fencing manager.
    Serialized across concurrent processes using fcntl.flock on a dedicated lock file.
    """

    def __init__(
        self,
        lease_file: Optional[Union[str, Path]] = None,
        lock_file: Optional[Union[str, Path]] = None,
        default_ttl: float = 60.0,
    ) -> None:
        if lease_file is None:
            self.lease_file = Path("/home/alexey/git/cloudflare-agent-git/.local/self_org/leases.json")
        else:
            self.lease_file = Path(lease_file)

        if lock_file is None:
            self.lock_file = self.lease_file.with_name(self.lease_file.name + ".lock")
        else:
            self.lock_file = Path(lock_file)

        self.default_ttl = float(default_ttl)

        # Ensure parent directory exists
        self.lease_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def _transaction(self):
        """
        Context manager providing exclusive flock protection for atomic
        read-modify-write cycles across concurrent processes/subagents.
        """
        lock_fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            state = self._read_unlocked()
            yield state
            self._write_unlocked(state)
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)

    def _read_unlocked(self) -> Dict[str, Any]:
        """
        Reads lease state without locking (must be called inside _transaction).
        If the file does not exist, returns a fresh empty schema.
        If the file exists but is corrupted, FAILS CLOSED by raising LeaseStorageCorruptedError
        to prevent sequence reset and duplicate owner hazards.
        """
        if not self.lease_file.exists():
            return {
                "schema_version": 1,
                "leases": {},
                "fence_sequences": {},
                "updated_at": time.time(),
            }
        try:
            with open(self.lease_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    raise LeaseStorageCorruptedError(f"Lease storage file '{self.lease_file}' is empty / corrupted")
                data = json.loads(content)
                if not isinstance(data, dict):
                    raise LeaseStorageCorruptedError(f"Lease storage file '{self.lease_file}' root is not a dict: {type(data)}")
                data.setdefault("schema_version", 1)
                data.setdefault("leases", {})
                data.setdefault("fence_sequences", {})
                return data
        except json.JSONDecodeError as exc:
            raise LeaseStorageCorruptedError(
                f"Lease storage file '{self.lease_file}' contains invalid JSON: {exc}"
            ) from exc
        except OSError as exc:
            raise LeaseStorageCorruptedError(
                f"Failed to read lease storage file '{self.lease_file}': {exc}"
            ) from exc

    def _write_unlocked(self, state: Dict[str, Any]) -> None:
        """Writes lease state atomically via tmpfile replace (must be called inside _transaction)."""
        state["updated_at"] = time.time()
        dir_path = self.lease_file.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=str(dir_path), delete=False, encoding="utf-8"
        ) as tf:
            json.dump(state, tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            temp_path = tf.name
        os.replace(temp_path, str(self.lease_file))

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def acquire_lease(
        self,
        task_id: str,
        holder: str,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> Lease:
        """
        Acquire a lease on a task.
        - If task has no active lease: acquires new lease with monotonic fence token.
        - If task is held by same holder: acts as idempotent renewal, extending TTL.
        - If task lease has expired: reclaims lease, monotonically incrementing fence token.
        - If task is actively held by someone else: raises LeaseAlreadyHeldError.
        """
        ts = now if now is not None else time.time()
        ttl = float(ttl_seconds if ttl_seconds is not None else self.default_ttl)
        meta = dict(metadata or {})

        with self._transaction() as state:
            leases = state["leases"]
            sequences = state["fence_sequences"]
            highest_seq = int(sequences.get(task_id, 0))

            existing_dict = leases.get(task_id)
            if existing_dict:
                existing_lease = Lease.from_dict(existing_dict)
                if existing_lease.status == "active" and not existing_lease.is_expired(ts):
                    if existing_lease.lease_holder == holder:
                        # Idempotent re-acquire / renewal by same holder
                        existing_lease.lease_expires_at = ts + ttl
                        existing_lease.updated_at = ts
                        if meta:
                            existing_lease.metadata.update(meta)
                        leases[task_id] = existing_lease.to_dict()
                        return existing_lease
                    else:
                        raise LeaseAlreadyHeldError(
                            f"Task '{task_id}' is already held by '{existing_lease.lease_holder}' "
                            f"until {existing_lease.lease_expires_at:.1f} "
                            f"({existing_lease.time_remaining(ts):.1f}s remaining)"
                        )

            # Either no existing lease, released/revoked, or expired.
            # Next fence token must be strictly greater than any previous sequence for this task!
            if existing_dict:
                prev_token = int(existing_dict.get("fence_token", 0))
                next_token = max(highest_seq + 1, prev_token + 1)
            else:
                next_token = max(highest_seq + 1, 1)

            new_lease = Lease(
                task_id=task_id,
                lease_holder=holder,
                fence_token=next_token,
                lease_expires_at=ts + ttl,
                acquired_at=ts,
                updated_at=ts,
                status="active",
                metadata=meta,
            )
            leases[task_id] = new_lease.to_dict()
            sequences[task_id] = next_token
            return new_lease

    def heartbeat(
        self,
        task_id: str,
        holder: str,
        fence_token: int,
        ttl_seconds: Optional[float] = None,
        now: Optional[float] = None,
    ) -> Lease:
        """
        Renew an active lease.
        Requires exact match of task_id, holder, and fence_token.
        Raises FencingTokenMismatchError if token is stale (e.g. lease was reclaimed).
        Raises LeaseExpiredError if lease already expired.
        """
        ts = now if now is not None else time.time()
        ttl = float(ttl_seconds if ttl_seconds is not None else self.default_ttl)

        with self._transaction() as state:
            leases = state["leases"]
            raw_lease = leases.get(task_id)
            if not raw_lease:
                raise LeaseNotFoundError(f"No lease found for task '{task_id}'")

            lease = Lease.from_dict(raw_lease)
            if lease.status != "active":
                raise LeaseNotFoundError(f"Lease for task '{task_id}' is inactive ({lease.status})")

            if lease.fence_token != fence_token:
                raise FencingTokenMismatchError(
                    f"Fencing token mismatch for task '{task_id}': active={lease.fence_token}, caller={fence_token}"
                )

            if lease.lease_holder != holder:
                raise HolderMismatchError(
                    f"Holder mismatch for task '{task_id}': active='{lease.lease_holder}', caller='{holder}'"
                )

            if lease.is_expired(ts):
                raise LeaseExpiredError(
                    f"Lease for task '{task_id}' expired at {lease.lease_expires_at:.1f} (current: {ts:.1f})"
                )

            lease.lease_expires_at = ts + ttl
            lease.updated_at = ts
            leases[task_id] = lease.to_dict()
            return lease

    def reclaim_expired_lease(
        self,
        task_id: str,
        new_holder: str,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> Lease:
        """
        Reclaim an expired or abandoned lease for peer takeover or supervisor reassignment.
        Monotonically increments fence_token, rendering any stale holder writes invalid.
        Raises LeaseNotExpiredError if the lease is still actively unexpired.
        """
        ts = now if now is not None else time.time()
        ttl = float(ttl_seconds if ttl_seconds is not None else self.default_ttl)
        meta = dict(metadata or {})

        with self._transaction() as state:
            leases = state["leases"]
            sequences = state["fence_sequences"]
            highest_seq = int(sequences.get(task_id, 0))

            raw_lease = leases.get(task_id)
            if raw_lease:
                lease = Lease.from_dict(raw_lease)
                if lease.status == "active" and not lease.is_expired(ts):
                    raise LeaseNotExpiredError(
                        f"Cannot reclaim lease for '{task_id}': still held by '{lease.lease_holder}' "
                        f"until {lease.lease_expires_at:.1f} ({lease.time_remaining(ts):.1f}s remaining)"
                    )
                prev_token = lease.fence_token
                next_token = max(highest_seq + 1, prev_token + 1)
            else:
                next_token = max(highest_seq + 1, 1)

            reclaimed = Lease(
                task_id=task_id,
                lease_holder=new_holder,
                fence_token=next_token,
                lease_expires_at=ts + ttl,
                acquired_at=ts,
                updated_at=ts,
                status="active",
                metadata=meta,
            )
            leases[task_id] = reclaimed.to_dict()
            sequences[task_id] = next_token
            return reclaimed

    def release_lease(
        self,
        task_id: str,
        holder: str,
        fence_token: int,
    ) -> bool:
        """
        Explicitly release a lease upon task completion or graceful exit.
        Requires exact match on holder and fence_token.
        """
        with self._transaction() as state:
            leases = state["leases"]
            raw_lease = leases.get(task_id)
            if not raw_lease:
                return False

            lease = Lease.from_dict(raw_lease)
            if lease.status != "active":
                return False

            if lease.fence_token != fence_token:
                raise FencingTokenMismatchError(
                    f"Cannot release lease for '{task_id}': fencing token mismatch (active={lease.fence_token}, caller={fence_token})"
                )

            if lease.lease_holder != holder:
                raise HolderMismatchError(
                    f"Cannot release lease for '{task_id}': holder mismatch (active='{lease.lease_holder}', caller='{holder}')"
                )

            lease.status = "released"
            lease.updated_at = time.time()
            leases[task_id] = lease.to_dict()
            return True

    def revoke_lease(
        self,
        task_id: str,
        reason: str = "supervisor_revoke",
    ) -> bool:
        """
        Administrative revocation of an active lease (by supervisor).
        """
        with self._transaction() as state:
            leases = state["leases"]
            raw_lease = leases.get(task_id)
            if not raw_lease:
                return False

            lease = Lease.from_dict(raw_lease)
            if lease.status != "active":
                return False

            lease.status = "revoked"
            lease.updated_at = time.time()
            lease.metadata["revoke_reason"] = reason
            leases[task_id] = lease.to_dict()
            return True

    def validate_fence(
        self,
        task_id: str,
        fence_token: int,
        check_expiry: bool = True,
        now: Optional[float] = None,
    ) -> bool:
        """
        Fast non-raising fence check. Returns True if fence_token matches active unexpired lease.
        """
        ts = now if now is not None else time.time()
        with self._transaction() as state:
            leases = state["leases"]
            raw_lease = leases.get(task_id)
            if not raw_lease:
                return False
            lease = Lease.from_dict(raw_lease)
            if lease.status != "active":
                return False
            if lease.fence_token != fence_token:
                return False
            if check_expiry and lease.is_expired(ts):
                return False
            return True

    def check_fence_or_raise(
        self,
        task_id: str,
        fence_token: int,
        check_expiry: bool = True,
        now: Optional[float] = None,
    ) -> Lease:
        """
        Strict fence check for workers before writing deliverables or updating state.
        Raises FencingTokenMismatchError, LeaseExpiredError, or LeaseNotFoundError.
        """
        ts = now if now is not None else time.time()
        with self._transaction() as state:
            leases = state["leases"]
            raw_lease = leases.get(task_id)
            if not raw_lease:
                raise LeaseNotFoundError(f"No lease found for task '{task_id}'")

            lease = Lease.from_dict(raw_lease)
            if lease.status != "active":
                raise LeaseNotFoundError(f"Lease for task '{task_id}' is inactive ({lease.status})")

            if lease.fence_token != fence_token:
                raise FencingTokenMismatchError(
                    f"Fencing token mismatch on write for task '{task_id}': active={lease.fence_token}, caller={fence_token}"
                )

            if check_expiry and lease.is_expired(ts):
                raise LeaseExpiredError(
                    f"Cannot write deliverable: lease for task '{task_id}' expired at {lease.lease_expires_at:.1f}"
                )

            return lease

    def get_lease(self, task_id: str) -> Optional[Lease]:
        """Fetch current lease for task_id, or None if none exists."""
        with self._transaction() as state:
            raw = state["leases"].get(task_id)
            return Lease.from_dict(raw) if raw else None

    def list_active_leases(self, now: Optional[float] = None) -> List[Lease]:
        """List all active, unexpired leases."""
        ts = now if now is not None else time.time()
        with self._transaction() as state:
            results = []
            for raw in state["leases"].values():
                lease = Lease.from_dict(raw)
                if lease.status == "active" and not lease.is_expired(ts):
                    results.append(lease)
            return results

    def list_expired_leases(self, now: Optional[float] = None) -> List[Lease]:
        """List all active leases whose lease_expires_at <= now."""
        ts = now if now is not None else time.time()
        with self._transaction() as state:
            results = []
            for raw in state["leases"].values():
                lease = Lease.from_dict(raw)
                if lease.status == "active" and lease.is_expired(ts):
                    results.append(lease)
            return results

    def get_fence_token(self, task_id: str) -> int:
        """Fetch latest monotonic fence token sequence for task_id."""
        with self._transaction() as state:
            return int(state["fence_sequences"].get(task_id, 0))

    def atomic_fence_execute(
        self,
        task_id: str,
        fence_token: int,
        action: Any,
        check_expiry: bool = True,
        now: Optional[float] = None,
    ) -> Any:
        """
        Atomically verifies the fencing token under fcntl.flock and executes the
        provided callable, eliminating race conditions between fence verification
        and state mutation.
        """
        ts = now if now is not None else time.time()
        with self._transaction() as state:
            raw_lease = state["leases"].get(task_id)
            if not raw_lease:
                raise LeaseNotFoundError(f"No lease found for task '{task_id}'")

            lease = Lease.from_dict(raw_lease)
            if lease.status != "active":
                raise LeaseNotFoundError(f"Lease for task '{task_id}' is inactive ({lease.status})")

            if lease.fence_token != fence_token:
                raise FencingTokenMismatchError(
                    f"Atomic fence verification failed for task '{task_id}': active={lease.fence_token}, caller={fence_token}"
                )

            if check_expiry and lease.is_expired(ts):
                raise LeaseExpiredError(
                    f"Cannot execute mutation: lease for task '{task_id}' expired at {lease.lease_expires_at:.1f}"
                )

            result = action(lease)
            state["leases"][task_id] = lease.to_dict()
            return result

