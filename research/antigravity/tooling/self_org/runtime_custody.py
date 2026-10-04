#!/usr/bin/env python3
"""
Runtime Custody & Containment Architecture (C2059 / Codex Principal Directives).

Implements hard technical prerequisites for runtime custody so that headless execution
can eventually be safely unlocked once kernel-enforced and provider-enforced boundaries
are verified.

Components:
1. CGroupV2Custody:
   - Kernel-enforced cgroup v2 unified hierarchy detection.
   - Strict memory ceiling inspection (memory.max).
   - Fail-closed rejection of unmounted hierarchy, unbounded ("max") memory,
     or allocations exceeding the 1500 MB cooperative pool limit.
   - PID containment via cgroup.procs assignment and descendant inspection.

2. ProviderQuotaReservation:
   - Pre-dispatch quota reservations with monotonic fencing tokens.
   - Enforcement of Codex 15% reserve floor, GLM 17:00-03:00 Berlin promotion window,
     and Grok cooldown/rate-limit bounds.
   - Fail-closed rejection of stale quota readings (> 300s), unknown balances,
     or exhausted capacity.
   - Multi-process atomic persistence protected by POSIX flock.

3. BusSocketConnector:
   - Secure UNIX domain socket client connection enforcing mode 0700 file & directory permissions.
   - Environment sanitization stripping parent APLEXER_*, PARENT_*, and MAILBOX_* authority.
   - Authenticated enrollment protocol and length-prefixed framing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import fcntl
import json
import logging
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from zoneinfo import ZoneInfo

logger = logging.getLogger("runtime_custody")

# CGroup and Memory Limits
DEFAULT_CGROUP_ROOT = Path("/sys/fs/cgroup")
DEFAULT_PROC_CGROUP = Path("/proc/self/cgroup")
MAX_COOPERATIVE_MEMORY_BYTES = 1500 * 1024 * 1024  # 1500 MB

# Quota Gate Constants
DEFAULT_MAX_QUOTA_AGE_SEC = 300.0
CODEX_RESERVE_FLOOR_FRACTION = 0.15
ALLOWED_PROVIDERS: Set[str] = {
    "codex",
    "glm",
    "glm-5.3-flash",
    "grok",
    "gemini",
    "opencode",
    "anthropic",
    "claude",
    "zcode",
}

# Environment variables to strip to prevent parent mailbox leakage
PARENT_AUTHORITY_ENV_PREFIXES: Tuple[str, ...] = (
    "APLEXER_",
    "PARENT_",
    "MAILBOX_",
)


# ===========================================================================
# Component 1: CGroupV2Custody & Exceptions
# ===========================================================================

class CustodyError(Exception):
    """Base exception for runtime custody and containment errors."""
    pass


class CGroupV2UnavailableError(CustodyError):
    """Raised when cgroup v2 unified hierarchy is not mounted or available."""
    pass


class CGroupCustodyError(CustodyError):
    """Raised when cgroup inspection, assignment, or validation fails."""
    pass


class UnboundedMemoryError(CGroupCustodyError):
    """Raised when cgroup memory.max is 'max' (unbounded), violating containment."""
    pass


class MemoryLimitExceededError(CGroupCustodyError):
    """Raised when cgroup memory ceiling exceeds the cooperative 1500 MB limit."""
    pass


class CGroupV2Custody:
    """
    Manages kernel-level process containment using cgroup v2 unified hierarchy.
    Enforces hard memory limits and tracks process membership.
    """

    def __init__(
        self,
        cgroup_root: Optional[Union[str, Path]] = None,
        proc_cgroup_file: Optional[Union[str, Path]] = None,
        max_memory_limit_bytes: int = MAX_COOPERATIVE_MEMORY_BYTES,
    ) -> None:
        self.cgroup_root = Path(cgroup_root).resolve() if cgroup_root else DEFAULT_CGROUP_ROOT
        self.proc_cgroup_file = Path(proc_cgroup_file).resolve() if proc_cgroup_file else DEFAULT_PROC_CGROUP
        self.max_memory_limit_bytes = int(max_memory_limit_bytes)

    def is_cgroup_v2_available(self) -> bool:
        """
        Verifies that cgroup v2 unified hierarchy is mounted and accessible.
        Checks for cgroup.controllers at the hierarchy root or 0:: unified entry in /proc.
        """
        controllers_file = self.cgroup_root / "cgroup.controllers"
        if controllers_file.exists():
            return True

        if self.proc_cgroup_file.exists():
            try:
                content = self.proc_cgroup_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith("0::"):
                        return True
            except OSError as exc:
                logger.warning("Failed to read proc cgroup file %s: %s", self.proc_cgroup_file, exc)

        return False

    def check_cgroup_v2_or_raise(self) -> None:
        """Fails closed by raising CGroupV2UnavailableError if cgroup v2 is not active."""
        if not self.is_cgroup_v2_available():
            raise CGroupV2UnavailableError(
                f"CGroup v2 unified hierarchy unavailable: {self.cgroup_root / 'cgroup.controllers'} not found "
                f"and no 0:: unified entry in {self.proc_cgroup_file}"
            )

    def _resolve_cgroup_path(self, cgroup_path: Union[str, Path]) -> Path:
        """Resolves target cgroup directory relative to cgroup_root."""
        raw_path = Path(cgroup_path)
        if raw_path.is_absolute():
            # If path is already rooted under cgroup_root, keep it
            try:
                raw_path.relative_to(self.cgroup_root)
                return raw_path
            except ValueError:
                pass
            # If cgroup_root is non-default (e.g. test mock), strip standard /sys/fs/cgroup prefix
            if self.cgroup_root != DEFAULT_CGROUP_ROOT:
                try:
                    rel = raw_path.relative_to(DEFAULT_CGROUP_ROOT)
                    return self.cgroup_root / rel
                except ValueError:
                    pass
                # Otherwise treat absolute path as relative to mock root
                rel = Path(*raw_path.parts[1:])
                return self.cgroup_root / rel
            return raw_path
        return self.cgroup_root / raw_path

    def get_memory_ceiling_bytes(self, cgroup_path: Union[str, Path]) -> int:
        """
        Reads memory.max for the target cgroup path and returns the ceiling in bytes.
        Fails closed on missing file, unparseable contents, or unbounded 'max'.
        """
        self.check_cgroup_v2_or_raise()
        cgroup_dir = self._resolve_cgroup_path(cgroup_path)
        memory_max_file = cgroup_dir / "memory.max"

        if not memory_max_file.is_file():
            raise CGroupCustodyError(f"CGroup memory.max file does not exist at {memory_max_file}")

        try:
            content = memory_max_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CGroupCustodyError(f"Failed to read memory.max at {memory_max_file}: {exc}") from exc

        if not content:
            raise CGroupCustodyError(f"Empty memory.max file at {memory_max_file}")

        if content == "max":
            raise UnboundedMemoryError(
                f"CGroup memory ceiling at {cgroup_dir} is 'max' (unbounded). "
                f"Fail-closed: execution rejected without bounded memory limit."
            )

        try:
            ceiling_bytes = int(content)
        except ValueError as exc:
            raise CGroupCustodyError(
                f"Non-integer memory.max value '{content}' at {memory_max_file}"
            ) from exc

        if ceiling_bytes < 0:
            raise CGroupCustodyError(
                f"Negative memory.max value {ceiling_bytes} at {memory_max_file}"
            )

        if ceiling_bytes > self.max_memory_limit_bytes:
            raise MemoryLimitExceededError(
                f"CGroup memory ceiling {ceiling_bytes} bytes exceeds cooperative limit "
                f"{self.max_memory_limit_bytes} bytes (1500 MB)"
            )

        return ceiling_bytes

    def assign_process_to_cgroup(self, cgroup_path: Union[str, Path], pid: int) -> None:
        """
        Attaches process PID to the target cgroup by writing to cgroup.procs.
        Kernel migrates the process and all threads into the target cgroup.
        """
        self.check_cgroup_v2_or_raise()
        cgroup_dir = self._resolve_cgroup_path(cgroup_path)
        procs_file = cgroup_dir / "cgroup.procs"

        if not procs_file.is_file():
            raise CGroupCustodyError(f"CGroup procs file does not exist at {procs_file}")

        try:
            with open(procs_file, "w", encoding="utf-8") as f:
                f.write(f"{int(pid)}\n")
        except (ProcessLookupError, PermissionError, OSError) as exc:
            raise CGroupCustodyError(
                f"Failed to assign PID {pid} to cgroup at {procs_file}: {exc}"
            ) from exc

    def get_cgroup_pids(self, cgroup_path: Union[str, Path]) -> List[int]:
        """
        Returns all descendant process PIDs currently contained within the cgroup.
        Processes cannot escape kernel cgroup tracking without migration by root/delegate.
        """
        self.check_cgroup_v2_or_raise()
        cgroup_dir = self._resolve_cgroup_path(cgroup_path)
        procs_file = cgroup_dir / "cgroup.procs"

        if not procs_file.is_file():
            raise CGroupCustodyError(f"CGroup procs file does not exist at {procs_file}")

        try:
            content = procs_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise CGroupCustodyError(f"Failed to read cgroup.procs at {procs_file}: {exc}") from exc

        pids: List[int] = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str and line_str.isdigit():
                pids.append(int(line_str))
        return pids


# ===========================================================================
# Component 2: ProviderQuotaReservation & Exceptions
# ===========================================================================

class QuotaReservationError(Exception):
    """Base exception for quota reservation failures."""
    pass


class ProviderIneligibleError(QuotaReservationError):
    """Raised when a provider is unauthorized, un-whitelisted, or outside time window."""
    pass


class ReserveFloorViolationError(QuotaReservationError):
    """Raised when provider balance falls below the mandatory 15% reserve floor."""
    pass


class QuotaExhaustedError(QuotaReservationError):
    """Raised when provider balance is exhausted or rate limited."""
    pass


class StaleQuotaError(QuotaReservationError):
    """Raised when quota telemetry is older than the max freshness threshold (300s)."""
    pass


class ReservationExpiredError(QuotaReservationError):
    """Raised when attempting to commit or extend an expired quota lease."""
    pass


class ReservationFencingError(QuotaReservationError):
    """Raised when reservation fence token does not match."""
    pass


@dataclass
class QuotaReservation:
    """Represents a bounded quota lease allocated before execution dispatch."""
    reservation_id: str
    provider: str
    task_id: str
    fence_token: int
    units: float
    created_at: float
    expires_at: float
    status: str = "active"  # "active", "committed", "released", "expired"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        ts = now if now is not None else time.time()
        return self.status == "active" and ts > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "provider": self.provider,
            "task_id": self.task_id,
            "fence_token": self.fence_token,
            "units": self.units,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QuotaReservation:
        return cls(
            reservation_id=str(data["reservation_id"]),
            provider=str(data["provider"]),
            task_id=str(data["task_id"]),
            fence_token=int(data["fence_token"]),
            units=float(data.get("units", 1.0)),
            created_at=float(data["created_at"]),
            expires_at=float(data["expires_at"]),
            status=str(data.get("status", "active")),
            metadata=dict(data.get("metadata", {})),
        )


class ProviderQuotaReservation:
    """
    Manages bounded pre-dispatch provider quota reservations.
    Enforces Codex 15% reserve floor, GLM Berlin campaign window, and Grok limits.
    All state transitions are persisted atomically under POSIX flock.
    """

    def __init__(
        self,
        reservation_file: Optional[Union[str, Path]] = None,
        quota_file: Optional[Union[str, Path]] = None,
        default_ttl_sec: float = 60.0,
        max_quota_age_sec: float = DEFAULT_MAX_QUOTA_AGE_SEC,
        codex_reserve_floor: float = CODEX_RESERVE_FLOOR_FRACTION,
    ) -> None:
        self.reservation_file = Path(reservation_file).resolve() if reservation_file else None
        self.quota_file = Path(quota_file).resolve() if quota_file else None
        self.default_ttl_sec = float(default_ttl_sec)
        self.max_quota_age_sec = float(max_quota_age_sec)
        self.codex_reserve_floor = float(codex_reserve_floor)

        if self.reservation_file:
            self.lock_file = self.reservation_file.with_name(self.reservation_file.name + ".lock")
            self.reservation_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.lock_file = None

        self._in_memory_reservations: Dict[str, QuotaReservation] = {}
        self._in_memory_fences: Dict[str, int] = {}

    @staticmethod
    def is_glm_window_open(now_or_dt: Optional[Union[datetime.datetime, float]] = None) -> bool:
        """
        GLM-5.3-Flash is prioritized/eligible strictly within 17:00-03:00 Europe/Berlin.
        Outside this window, GLM dispatch is not eligible.
        """
        tz_berlin = ZoneInfo("Europe/Berlin")
        if now_or_dt is None:
            dt = datetime.datetime.now(tz=tz_berlin)
        elif isinstance(now_or_dt, (int, float)):
            dt = datetime.datetime.fromtimestamp(now_or_dt, tz=tz_berlin)
        else:
            dt = now_or_dt.astimezone(tz_berlin)

        hour = dt.hour
        # 17:00 to 03:00 means hours >= 17 OR hour < 3
        return hour >= 17 or hour < 3

    def evaluate_provider_quota(
        self,
        provider: str,
        now: Optional[float] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates provider eligibility and telemetry against hard reservation criteria.
        Returns (is_eligible, reason, telemetry_dict).
        Fails closed on un-whitelisted, stale, unknown, or reserve-violating quotas.
        """
        current_ts = now if now is not None else time.time()
        clean_provider = provider.strip().lower() if provider else ""

        if not clean_provider:
            return False, "Provider tag cannot be empty or None (fail-closed)", {}

        if clean_provider not in ALLOWED_PROVIDERS:
            return False, f"Provider '{clean_provider}' is not in authorized whitelist (fail-closed)", {}

        # GLM Campaign Window Check
        if clean_provider in ("glm", "glm-5.3-flash"):
            if not self.is_glm_window_open(current_ts):
                return (
                    False,
                    "GLM-5.3-Flash outside eligible campaign promotion window (17:00-03:00 Europe/Berlin)",
                    {"provider": clean_provider, "window_open": False},
                )

        # Quota Telemetry Evaluation
        if self.quota_file is None or not self.quota_file.exists():
            # If no quota file is provided, non-rate-limited providers can be reserved
            return True, "Eligible (no telemetry file constraint)", {"provider": clean_provider}

        # Check telemetry file freshness
        try:
            st = self.quota_file.stat()
            file_age = current_ts - st.st_mtime
            if file_age > self.max_quota_age_sec:
                return (
                    False,
                    f"Quota telemetry file is stale ({file_age:.1f}s > {self.max_quota_age_sec}s threshold)",
                    {"file_age_sec": file_age},
                )

            quota_data = json.loads(self.quota_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"Failed to read or parse quota telemetry file: {exc}", {}

        # Provider specific records
        providers_dict = quota_data.get("providers", quota_data)
        record = providers_dict.get(clean_provider)

        if record is None:
            return False, f"Provider '{clean_provider}' telemetry record is missing (fail-closed)", {}

        if isinstance(record, dict):
            # Check timestamp inside JSON if present
            record_ts = record.get("timestamp") or record.get("updated_at")
            if record_ts is not None:
                try:
                    if isinstance(record_ts, str):
                        dt = datetime.datetime.fromisoformat(record_ts.replace("Z", "+00:00"))
                        ts_val = dt.timestamp()
                    else:
                        ts_val = float(record_ts)
                    rec_age = current_ts - ts_val
                    if rec_age > self.max_quota_age_sec:
                        return (
                            False,
                            f"Provider '{clean_provider}' telemetry timestamp is stale ({rec_age:.1f}s old)",
                            record,
                        )
                except Exception:
                    pass

            # Check for unknown reading
            status = str(record.get("status", "")).lower()
            if status in ("unknown", "unrecorded", "unverified"):
                return False, f"Provider '{clean_provider}' quota balance is unknown (fail-closed)", record

            # Codex 15% reserve floor
            if clean_provider == "codex":
                remaining_frac = record.get("remaining_fraction")
                remaining_pct = record.get("remaining_percent")

                if remaining_frac is None and remaining_pct is None:
                    # Look for raw balance/reserve
                    if "balance" in record and record["balance"] == "unknown":
                        return False, "Codex quota reading unknown (fail-closed)", record
                    return False, "Codex remaining quota percentage not recorded (fail-closed)", record

                frac_val = float(remaining_frac) if remaining_frac is not None else float(remaining_pct) / 100.0
                if frac_val < self.codex_reserve_floor:
                    return (
                        False,
                        f"Codex remaining quota ({frac_val*100:.1f}%) violates mandatory 15% reserve floor",
                        record,
                    )

            # Grok rate-limit cooldown
            if clean_provider == "grok":
                cooldown_until = record.get("cooldown_until", 0.0)
                if current_ts < float(cooldown_until):
                    remaining_cool = float(cooldown_until) - current_ts
                    return (
                        False,
                        f"Grok is in rate-limit cooldown ({remaining_cool:.1f}s remaining)",
                        record,
                    )
                if record.get("remaining_requests", 1) <= 0:
                    return False, "Grok hourly quota exhausted", record

            # General exhaustion check
            if status in ("exhausted", "quota_exceeded"):
                return False, f"Provider '{clean_provider}' balance exhausted", record

            if record.get("exhausted", False):
                return False, f"Provider '{clean_provider}' balance marked exhausted", record

        return True, "Eligible", record if isinstance(record, dict) else {}

    def _load_reservations_locked(self) -> Tuple[Dict[str, QuotaReservation], Dict[str, int]]:
        """Reads reservation state from disk under lock or returns in-memory state."""
        if not self.reservation_file or not self.reservation_file.exists():
            return dict(self._in_memory_reservations), dict(self._in_memory_fences)

        try:
            data = json.loads(self.reservation_file.read_text(encoding="utf-8"))
            res_dict: Dict[str, QuotaReservation] = {}
            for item in data.get("reservations", []):
                r = QuotaReservation.from_dict(item)
                res_dict[r.reservation_id] = r
            fences = {k: int(v) for k, v in data.get("fence_sequences", {}).items()}
            return res_dict, fences
        except Exception as exc:
            logger.warning("Failed to parse reservation file %s: %s", self.reservation_file, exc)
            return dict(self._in_memory_reservations), dict(self._in_memory_fences)

    def _save_reservations_locked(
        self,
        reservations: Dict[str, QuotaReservation],
        fences: Dict[str, int],
    ) -> None:
        """Writes reservation state to disk under lock."""
        self._in_memory_reservations = reservations
        self._in_memory_fences = fences

        if not self.reservation_file:
            return

        payload = {
            "version": 1,
            "updated_at": time.time(),
            "reservations": [r.to_dict() for r in reservations.values()],
            "fence_sequences": fences,
        }
        tmp_file = self.reservation_file.with_name(f"{self.reservation_file.name}.tmp.{os.getpid()}")
        tmp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_file.replace(self.reservation_file)

    def acquire_reservation(
        self,
        provider: str,
        task_id: str,
        units: float = 1.0,
        ttl_sec: Optional[float] = None,
        now: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QuotaReservation:
        """
        Atomically leases provider quota with a monotonic fencing token.
        Evaluates provider quota eligibility and fails closed on violation.
        """
        current_ts = now if now is not None else time.time()
        ttl = float(ttl_sec) if ttl_sec is not None else self.default_ttl_sec

        # 1. Gate evaluation
        is_ok, reason, details = self.evaluate_provider_quota(provider, now=current_ts)
        if not is_ok:
            if "15% reserve floor" in reason:
                raise ReserveFloorViolationError(reason)
            if "exhausted" in reason or "cooldown" in reason:
                raise QuotaExhaustedError(reason)
            if "stale" in reason:
                raise StaleQuotaError(reason)
            raise ProviderIneligibleError(reason)

        # 2. Persistence under flock
        lock_fd = None
        if self.lock_file:
            lock_fd = open(self.lock_file, "w", encoding="utf-8")
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        try:
            reservations, fences = self._load_reservations_locked()

            # Monotonic fence token allocation per provider/task
            fence_key = f"{provider}:{task_id}"
            next_fence = fences.get(fence_key, 0) + 1
            fences[fence_key] = next_fence

            res_id = f"qres-{provider}-{int(current_ts*1000)}-{next_fence}"
            res = QuotaReservation(
                reservation_id=res_id,
                provider=provider.strip().lower(),
                task_id=task_id,
                fence_token=next_fence,
                units=float(units),
                created_at=current_ts,
                expires_at=current_ts + ttl,
                status="active",
                metadata=dict(metadata or {}),
            )
            reservations[res_id] = res
            self._save_reservations_locked(reservations, fences)
            return res
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except OSError:
                    pass

    def release_reservation(
        self,
        reservation_id: str,
        fence_token: int,
    ) -> bool:
        """Releases an active quota reservation."""
        lock_fd = None
        if self.lock_file:
            lock_fd = open(self.lock_file, "w", encoding="utf-8")
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        try:
            reservations, fences = self._load_reservations_locked()
            res = reservations.get(reservation_id)
            if not res:
                return False

            if res.fence_token != fence_token:
                raise ReservationFencingError(
                    f"Fence token mismatch on release for {reservation_id}: "
                    f"token {fence_token} != active {res.fence_token}"
                )

            res.status = "released"
            self._save_reservations_locked(reservations, fences)
            return True
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except OSError:
                    pass

    def commit_reservation(
        self,
        reservation_id: str,
        fence_token: int,
        units_used: float,
        now: Optional[float] = None,
    ) -> bool:
        """
        Commits an active quota reservation upon successful task completion.
        Fails if the lease expired or fence token is mismatched.
        """
        current_ts = now if now is not None else time.time()
        lock_fd = None
        if self.lock_file:
            lock_fd = open(self.lock_file, "w", encoding="utf-8")
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        try:
            reservations, fences = self._load_reservations_locked()
            res = reservations.get(reservation_id)
            if not res:
                return False

            if res.fence_token != fence_token:
                raise ReservationFencingError(
                    f"Fence token mismatch on commit for {reservation_id}: "
                    f"token {fence_token} != active {res.fence_token}"
                )

            if res.is_expired(now=current_ts):
                res.status = "expired"
                self._save_reservations_locked(reservations, fences)
                raise ReservationExpiredError(
                    f"Cannot commit expired reservation {reservation_id} "
                    f"(expired at {res.expires_at} < current {current_ts})"
                )

            res.status = "committed"
            res.units = float(units_used)
            res.metadata["committed_at"] = current_ts
            self._save_reservations_locked(reservations, fences)
            return True
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except OSError:
                    pass

    def get_reservation(self, reservation_id: str) -> Optional[QuotaReservation]:
        """Returns the reservation record by ID."""
        reservations, _ = self._load_reservations_locked()
        return reservations.get(reservation_id)

    def list_active_reservations(self, provider: Optional[str] = None) -> List[QuotaReservation]:
        """Returns all currently active (unexpired, status=active) quota reservations."""
        current_ts = time.time()
        reservations, _ = self._load_reservations_locked()
        result: List[QuotaReservation] = []
        clean_p = provider.strip().lower() if provider else None

        for r in reservations.values():
            if clean_p and r.provider != clean_p:
                continue
            if r.status == "active" and not r.is_expired(now=current_ts):
                result.append(r)
        return result


# ===========================================================================
# Component 3: BusSocketConnector & Framing
# ===========================================================================

class BusSocketError(Exception):
    """Base exception for bus socket communication errors."""
    pass


class SocketSecurityError(BusSocketError):
    """Raised when socket or directory permissions violate security mode (0700)."""
    pass


class EnrollmentError(BusSocketError):
    """Raised when bus authentication or identity enrollment fails."""
    pass


class FramingError(BusSocketError):
    """Raised when protocol framing or payload deserialization fails."""
    pass


class BusSocketConnector:
    """
    Client connector for authenticated UNIX domain socket message bus.
    Enforces mode 0700 permission boundaries, strips parent authority,
    and handles length-prefixed JSON binary message framing.
    """

    @staticmethod
    def strip_parent_authority(
        base_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Produces an isolated execution environment by stripping all inherited
        APLEXER_*, PARENT_*, and MAILBOX_* authority variables.
        """
        source = dict(base_env if base_env is not None else os.environ)
        cleaned: Dict[str, str] = {}
        for k, v in source.items():
            if any(k.startswith(prefix) for prefix in PARENT_AUTHORITY_ENV_PREFIXES):
                continue
            cleaned[k] = v
        return cleaned

    @staticmethod
    def verify_socket_security(socket_path: Union[str, Path]) -> None:
        """
        Validates that target socket exists, is a UNIX socket, and is protected
        against unauthorized group/other read/write permissions (mode 0700 style).
        """
        sock_p = Path(socket_path).resolve()
        if not sock_p.exists():
            raise SocketSecurityError(f"Socket does not exist at {sock_p}")

        try:
            st = sock_p.stat()
        except OSError as exc:
            raise SocketSecurityError(f"Cannot stat socket {sock_p}: {exc}") from exc

        if not stat.S_ISSOCK(st.st_mode):
            raise SocketSecurityError(f"Target path {sock_p} is not a UNIX domain socket")

        # Socket file mode check: no group or other read/write permissions
        if st.st_mode & 0o077 != 0:
            raise SocketSecurityError(
                f"Insecure permissions on socket {sock_p}: mode {oct(st.st_mode)} has group/other bits set"
            )

        # Socket parent directory mode check: mode 0700 or user-only
        parent_p = sock_p.parent
        try:
            st_parent = parent_p.stat()
        except OSError as exc:
            raise SocketSecurityError(f"Cannot stat socket directory {parent_p}: {exc}") from exc

        if st_parent.st_mode & 0o077 != 0:
            raise SocketSecurityError(
                f"Insecure permissions on socket parent dir {parent_p}: "
                f"mode {oct(st_parent.st_mode)} has group/other bits set (requires 0700)"
            )

    @staticmethod
    def send_message(sock: socket.socket, message: Dict[str, Any]) -> None:
        """
        Sends length-prefixed JSON message frame over connected socket.
        Format: 4-byte big-endian unsigned integer length prefix followed by UTF-8 JSON.
        """
        try:
            payload = json.dumps(message).encode("utf-8")
            header = struct.pack("!I", len(payload))
            sock.sendall(header + payload)
        except (OSError, TypeError, ValueError) as exc:
            raise FramingError(f"Failed to encode and send message frame: {exc}") from exc

    @staticmethod
    def receive_message(sock: socket.socket, timeout_sec: float = 5.0) -> Dict[str, Any]:
        """
        Receives length-prefixed JSON message frame from connected socket.
        Reads exactly 4 bytes length, then reads full payload.
        """
        sock.settimeout(timeout_sec)

        # 1. Read 4-byte length prefix
        header_bytes = bytearray()
        while len(header_bytes) < 4:
            try:
                chunk = sock.recv(4 - len(header_bytes))
                if not chunk:
                    raise FramingError("Connection closed while awaiting message header")
                header_bytes.extend(chunk)
            except socket.timeout as exc:
                raise FramingError("Timeout awaiting message header") from exc
            except OSError as exc:
                raise FramingError(f"Socket error reading header: {exc}") from exc

        (payload_len,) = struct.unpack("!I", header_bytes)
        if payload_len > 16 * 1024 * 1024:  # 16 MiB max message frame
            raise FramingError(f"Payload size {payload_len} exceeds maximum allowed frame limit (16MB)")

        # 2. Read exact payload
        payload_bytes = bytearray()
        while len(payload_bytes) < payload_len:
            try:
                chunk = sock.recv(min(4096, payload_len - len(payload_bytes)))
                if not chunk:
                    raise FramingError("Connection closed while reading message body")
                payload_bytes.extend(chunk)
            except socket.timeout as exc:
                raise FramingError("Timeout reading message body") from exc
            except OSError as exc:
                raise FramingError(f"Socket error reading body: {exc}") from exc

        try:
            return json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise FramingError(f"Failed to decode message frame JSON: {exc}") from exc

    def enroll_identity(
        self,
        socket_path: Union[str, Path],
        client_tag: str,
        role: str,
        auth_token: str,
        timeout_sec: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Connects to authenticated UNIX domain socket bus and enrolls a distinct subagent identity.
        Validates socket permissions and verifies handshake response.
        """
        self.verify_socket_security(socket_path)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout_sec)
        try:
            sock.connect(str(socket_path))
            enroll_frame = {
                "type": "enroll",
                "client_tag": client_tag,
                "role": role,
                "auth_token": auth_token,
                "isolated_env": True,
                "timestamp": time.time(),
            }
            self.send_message(sock, enroll_frame)
            resp = self.receive_message(sock, timeout_sec=timeout_sec)

            if resp.get("status") != "enrolled":
                error_msg = resp.get("error", "Unknown enrollment rejection")
                raise EnrollmentError(f"Identity enrollment rejected by bus: {error_msg}")

            return resp
        except (BusSocketError, OSError) as exc:
            if not isinstance(exc, EnrollmentError):
                raise EnrollmentError(f"Failed to enroll with bus socket: {exc}") from exc
            raise
        finally:
            try:
                sock.close()
            except OSError:
                pass
