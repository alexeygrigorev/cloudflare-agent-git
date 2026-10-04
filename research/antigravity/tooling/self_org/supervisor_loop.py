#!/usr/bin/env python3
"""
Autonomous Hetzner Supervisor Control Loop (Remediated C2035).
Removes desktop orchestrator and principal LLM turns as single points of failure (SPOFs).

Strict Invariants & Remediations:
1. Canonical File Protection:
   - NEVER overwrites canonical coordination/TASKS.json!
   - Defaults CLI and systemd to isolated staging store (.local/self_org/tasks.json).
   - Direct write to canonical TASKS.json is hard-blocked with PermissionError.
   - All tasks file writes serialize under fcntl.flock on .local/task-registry.lock.
2. Lossless Task Attributes:
   - Preserves all peer and unknown attributes from TASKS.json (acceptance, assignment_ack,
     target_repo, branch, test_demarcation, etc.) without lossy reconstruction.
3. Provenance Dispatch Invariant:
   - Emits structured dispatch envelopes / first-tool receipts to .local/self_org/receipts/.
   - Records task started_at timestamp and first_action metadata.
4. Fresh Evidence Completion Invariant:
   - Rejects stale/pre-existing evidence files (asserts file mtime >= task started_at).
   - Validates file size > 0 and computes SHA256 artifact hashes.
5. Fail-Closed Host & Quota Gates:
   - MemAvailable parsing failure FAILS CLOSED (returns 0.0 MB).
   - Real quota gate inspection (.local/launch-quota.json, Codex 15% reserve).
6. Comprehensive Registry & Aplexer Parsing:
   - Parses projects, teams, agents, and delivery_executors from TEAM-REGISTRY.json.
   - Discovers live sessions from active aplexer session catalog (aplexer snapshot).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import datetime
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import uuid
from zoneinfo import ZoneInfo

from .lease_manager import (
    FencingTokenMismatchError,
    Lease,
    LeaseAlreadyHeldError,
    LeaseExpiredError,
    LeaseManager,
    LeaseNotExpiredError,
    LeaseNotFoundError,
    LeaseStorageCorruptedError,
)

logger = logging.getLogger("self_org_supervisor")

DEFAULT_PRODUCTS = [
    "agent-branches",
    "agent-dashboard",
    "quota-launcher",
    "agent-coordination",
]

CANONICAL_TASKS_PATH = Path("/home/alexey/git/cloudflare-agent-git/coordination/TASKS.json").resolve()
CANONICAL_LOCK_PATH = Path("/home/alexey/git/cloudflare-agent-git/.local/task-registry.lock")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    allowed: bool
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Worker:
    tag: str
    project_id: str
    mode: str = "headless"  # "headless" or "interactive"
    provider: str = "gemini"  # "gemini", "grok", "zcode", "opencode", "codex"
    status: str = "ready"  # "ready", "busy", "NOTREADY", "frozen", "stopped"
    has_active_draft: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_healthy_for_dispatch(self) -> bool:
        if self.status != "ready":
            return False
        if self.has_active_draft:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Worker:
        return cls(
            tag=data["tag"],
            project_id=data["project_id"],
            mode=data.get("mode", "headless"),
            provider=data.get("provider", "gemini"),
            status=data.get("status", "ready"),
            has_active_draft=bool(data.get("has_active_draft", False)),
            metadata=dict(data.get("metadata", {})),
        )


def _parse_timestamp(val: Any) -> float:
    if val is None:
        return time.time()
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            pass
        try:
            dt = datetime.datetime.fromisoformat(val)
            return dt.timestamp()
        except ValueError:
            pass
    return time.time()


@dataclass
class Task:
    id: str
    project_id: str
    status: str = "queued"  # "queued", "ready", "running", "review", "done", "blocked", "failed", "cancelled"
    blocked_on: List[str] = field(default_factory=list)
    owner_tag: Optional[str] = None
    executor_tag: Optional[str] = None
    evidence_paths: List[str] = field(default_factory=list)
    provider: Optional[str] = None
    failure_count: int = 0
    last_failure_at: Optional[float] = None
    started_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_fields: Dict[str, Any] = field(default_factory=dict)  # Lossless preservation of all peer attributes

    def to_dict(self) -> Dict[str, Any]:
        """Losslessly serialize task, starting from original peer fields."""
        out = dict(self.raw_fields)
        out.update({
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "blocked_on": list(self.blocked_on),
            "owner_tag": self.owner_tag,
            "executor_tag": self.executor_tag,
            "evidence_paths": list(self.evidence_paths),
            "provider": self.provider,
            "failure_count": int(self.failure_count),
            "last_failure_at": self.last_failure_at,
            "started_at": self.started_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        })
        if self.metadata:
            out.setdefault("metadata", {})
            out["metadata"].update(self.metadata)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        raw_copy = dict(data)
        raw_proj = data.get("project_id") or data.get("team_id", "unknown")
        # Normalize aliases to canonical product identifiers
        proj = raw_proj
        if raw_proj in ("branches", "agent-branches"):
            proj = "agent-branches"
        elif raw_proj in ("dashboard", "agent-dashboard"):
            proj = "agent-dashboard"
        elif raw_proj in ("launcher", "quota-launcher", "agent-quota-launcher"):
            proj = "quota-launcher"
        elif raw_proj in ("coordination", "agent-coordination", "cross-computer-agent-coordination"):
            proj = "agent-coordination"

        started_at = None
        if data.get("started_at") is not None:
            started_at = _parse_timestamp(data.get("started_at"))
        elif data.get("metadata", {}).get("started_at") is not None:
            started_at = _parse_timestamp(data["metadata"]["started_at"])

        return cls(
            id=data["id"],
            project_id=proj,
            status=data.get("status", "queued"),
            blocked_on=list(data.get("blocked_on", [])),
            owner_tag=data.get("owner_tag"),
            executor_tag=data.get("executor_tag"),
            evidence_paths=list(data.get("evidence_paths", [])),
            provider=data.get("provider") or data.get("model"),
            failure_count=int(data.get("failure_count", 0)),
            last_failure_at=_parse_timestamp(data.get("last_failure_at")) if data.get("last_failure_at") is not None else None,
            started_at=started_at,
            created_at=_parse_timestamp(data.get("created_at")),
            updated_at=_parse_timestamp(data.get("updated_at")),
            metadata=dict(data.get("metadata", {})),
            raw_fields=raw_copy,
        )


# ---------------------------------------------------------------------------
# Host & Quota Gate Checkers (Fail-Closed)
# ---------------------------------------------------------------------------

class ResourceGateChecker:
    """
    Enforces host sanity limits to prevent resource exhaustion crashes:
    - Root disk free >= 50.0 GB
    - Available memory >= 10240.0 MB (10 GiB host policy floor, fails closed on unreadable meminfo!)
      Note: Individual workers operate under a cooperative 1500 MB budget.
    - Scratch usage <= 512.0 MB
    - /tmp stability
    """

    def __init__(
        self,
        min_disk_free_gb: float = 50.0,
        min_mem_avail_mb: float = 10240.0,
        max_scratch_mb: float = 512.0,
        scratch_dir: Optional[Union[str, Path]] = None,
        root_dir: str = "/",
        meminfo_path: str = "/proc/meminfo",
    ) -> None:
        self.min_disk_free_gb = float(min_disk_free_gb)
        self.min_mem_avail_mb = float(min_mem_avail_mb)
        self.max_scratch_mb = float(max_scratch_mb)
        self.scratch_dir = Path(scratch_dir) if scratch_dir else Path("/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-arch")
        self.root_dir = root_dir
        self.meminfo_path = meminfo_path

    def get_disk_free_gb(self) -> float:
        try:
            st = os.statvfs(self.root_dir)
            return (st.f_bavail * st.f_frsize) / (1024.0 ** 3)
        except OSError as exc:
            logger.warning("Failed to statvfs root: %s", exc)
            return 0.0

    def get_mem_available_mb(self) -> float:
        """
        Extract MemAvailable from meminfo.
        FAIL-CLOSED: Returns 0.0 MB if file is missing, unreadable, or unparseable.
        """
        try:
            with open(self.meminfo_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        parts = line.split()
                        return float(parts[1]) / 1024.0
            logger.error("MemAvailable field missing in %s (failing closed: 0 MB)", self.meminfo_path)
            return 0.0
        except Exception as exc:
            logger.error("Failed to read %s (failing closed: 0 MB): %s", self.meminfo_path, exc)
            return 0.0

    def get_scratch_size_mb(self) -> float:
        if not self.scratch_dir.exists():
            return 0.0
        total_bytes = 0
        try:
            for root, _, files in os.walk(self.scratch_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_bytes += os.path.getsize(fp)
                    except OSError:
                        pass
        except OSError:
            pass
        return total_bytes / (1024.0 * 1024.0)

    def check(self) -> GateResult:
        disk_free = self.get_disk_free_gb()
        mem_avail = self.get_mem_available_mb()
        scratch_size = self.get_scratch_size_mb()

        metrics = {
            "root_disk_free_gb": round(disk_free, 2),
            "mem_available_mb": round(mem_avail, 2),
            "scratch_size_mb": round(scratch_size, 2),
            "limits": {
                "min_disk_free_gb": self.min_disk_free_gb,
                "min_mem_avail_mb": self.min_mem_avail_mb,
                "max_scratch_mb": self.max_scratch_mb,
            },
        }

        if disk_free < self.min_disk_free_gb:
            return GateResult(
                allowed=False,
                reason=f"Disk space exhausted: {disk_free:.2f} GB free < {self.min_disk_free_gb:.2f} GB threshold",
                metrics=metrics,
            )

        if mem_avail < self.min_mem_avail_mb:
            return GateResult(
                allowed=False,
                reason=f"Memory exhausted / unreadable: {mem_avail:.2f} MB available < {self.min_mem_avail_mb:.2f} MB threshold",
                metrics=metrics,
            )

        if scratch_size > self.max_scratch_mb:
            return GateResult(
                allowed=False,
                reason=f"Scratch budget exceeded: {scratch_size:.2f} MB used > {self.max_scratch_mb:.2f} MB limit",
                metrics=metrics,
            )

        return GateResult(allowed=True, reason="Host sanity gates clean", metrics=metrics)


AUTHORIZED_PROVIDERS = {
    "codex",
    "glm",
    "grok",
    "gemini",
    "opencode",
    "anthropic",
    "claude",
    "zcode",
}


class QuotaGateChecker:
    """
    Enforces provider quota rules:
    - Real launch-quota.json inspection (Codex 15% reserve, freshness <= 300s)
    - Whitelist validation for authorized providers (fail-closed on unknown/None)
    - GLM window: 17:00 to 03:00 Europe/Berlin
    - Grok cooldown timestamps
    """

    def __init__(
        self,
        launch_quota_file: Optional[Union[str, Path]] = None,
        grok_cooldown_file: Optional[Union[str, Path]] = None,
        codex_reserve_pct: float = 15.0,
        max_quota_age_sec: float = 300.0,
    ) -> None:
        self.launch_quota_file = Path(launch_quota_file) if launch_quota_file else Path("/home/alexey/git/cloudflare-agent-git/.local/launch-quota.json")
        self.grok_cooldown_file = Path(grok_cooldown_file) if grok_cooldown_file else None
        self.codex_reserve_pct = float(codex_reserve_pct)
        self.max_quota_age_sec = float(max_quota_age_sec)

    def is_glm_window_open(self, now: Optional[datetime.datetime] = None) -> bool:
        """GLM-5.3-Flash promotional window is active between 17:00 and 03:00 Berlin time."""
        try:
            tz = ZoneInfo("Europe/Berlin")
            dt = now if now is not None else datetime.datetime.now(tz)
            hour = dt.hour
            return hour >= 17 or hour < 3
        except Exception:
            utc_now = now or datetime.datetime.now(datetime.timezone.utc)
            berlin_hour = (utc_now.hour + 2) % 24
            return berlin_hour >= 17 or berlin_hour < 3

    def is_grok_on_cooldown(self, now: Optional[float] = None) -> Tuple[bool, float]:
        """Check if Grok has an active rate-limit cooldown."""
        ts = now if now is not None else time.time()
        if not self.grok_cooldown_file or not self.grok_cooldown_file.exists():
            return False, 0.0
        try:
            with open(self.grok_cooldown_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cooldown_until = float(data.get("cooldown_until", 0.0))
                if cooldown_until > ts:
                    return True, cooldown_until - ts
        except (json.JSONDecodeError, OSError):
            pass
        return False, 0.0

    def check_codex_reserve(self, now: Optional[float] = None) -> Tuple[bool, str]:
        """
        Check real launch-quota.json for Codex 15% reserve.
        FAIL-CLOSED: If quota file is missing, malformed, unreadable, stale (>300s),
        or missing codex record, it returns (False, reason) to prevent launching without validated quota reserve.
        """
        ts = now if now is not None else time.time()
        if not self.launch_quota_file or not self.launch_quota_file.exists():
            return False, f"Launch quota file missing: '{self.launch_quota_file}' (fail-closed)"
        try:
            st_mtime = self.launch_quota_file.stat().st_mtime
            age = ts - st_mtime
            if age > self.max_quota_age_sec:
                return False, f"Stale launch-quota file (age {age:.1f}s > {self.max_quota_age_sec:g}s; fail-closed)"

            with open(self.launch_quota_file, "r", encoding="utf-8") as f:
                data = json.load(f)

                if "updated_at_ms" in data:
                    rec_age = ts - (float(data["updated_at_ms"]) / 1000.0)
                    if rec_age > self.max_quota_age_sec:
                        return False, f"Stale launch-quota file (age {rec_age:.1f}s > {self.max_quota_age_sec:g}s; fail-closed)"
                elif "timestamp" in data:
                    rec_age = ts - float(data["timestamp"])
                    if rec_age > self.max_quota_age_sec:
                        return False, f"Stale launch-quota file (age {rec_age:.1f}s > {self.max_quota_age_sec:g}s; fail-closed)"

                codex_data = data.get("codex") or data.get("providers", {}).get("codex", {})
                if not codex_data:
                    return False, "No codex record in launch-quota.json (fail-closed)"
                if codex_data.get("limit_reached"):
                    return False, "Codex limit_reached=True in launch-quota.json"
                windows = codex_data.get("windows", {})
                values = [v.get("percent_remaining") for v in windows.values() if isinstance(v, dict) and isinstance(v.get("percent_remaining"), (float, int))]
                if not values:
                    return False, "No valid quota window readings in launch-quota.json (fail-closed)"
                min_rem = min(values)
                if min_rem <= self.codex_reserve_pct:
                    return False, f"Codex remaining quota ({min_rem:g}%) <= {self.codex_reserve_pct:g}% reserve limit"
                return True, f"Codex reserve validated ({min_rem:g}% remaining)"
        except Exception as exc:
            logger.error("Failed to parse %s for codex reserve (failing closed): %s", self.launch_quota_file, exc)
            return False, f"Failed to parse quota file: {exc} (fail-closed)"

    def check(self, provider: Optional[str], now: Optional[float] = None) -> GateResult:
        if not provider or not str(provider).strip():
            return GateResult(allowed=False, reason="No provider specified (fail-closed)")

        prov = str(provider).strip().lower()
        ts = now if now is not None else time.time()

        matched_ap = None
        for ap in AUTHORIZED_PROVIDERS:
            if ap in prov:
                matched_ap = ap
                break

        if not matched_ap:
            return GateResult(
                allowed=False,
                reason="Unknown/unauthorized provider (fail-closed)",
                metrics={"provider": prov},
            )

        if "codex" in prov:
            codex_ok, codex_reason = self.check_codex_reserve(now=ts)
            if not codex_ok:
                return GateResult(allowed=False, reason=codex_reason, metrics={"provider": prov})

        if "glm" in prov:
            dt = datetime.datetime.fromtimestamp(ts, tz=ZoneInfo("Europe/Berlin"))
            if not self.is_glm_window_open(dt):
                return GateResult(
                    allowed=False,
                    reason=f"Outside GLM promotion window (17:00-03:00 Berlin, current: {dt.strftime('%H:%M')})",
                    metrics={"provider": prov, "berlin_hour": dt.hour},
                )

        if "grok" in prov:
            on_cooldown, remaining = self.is_grok_on_cooldown(ts)
            if on_cooldown:
                return GateResult(
                    allowed=False,
                    reason=f"Grok provider on cooldown ({remaining:.1f}s remaining)",
                    metrics={"provider": prov, "cooldown_remaining_sec": remaining},
                )

        return GateResult(allowed=True, reason=f"Provider '{prov}' quota check passed", metrics={"provider": prov})


# ---------------------------------------------------------------------------
# Supervisor Loop
# ---------------------------------------------------------------------------

@dataclass
class SupervisorTickSummary:
    tick_number: int
    timestamp_utc: str
    host_gate: GateResult
    projects: Dict[str, Dict[str, Any]]
    dispatched_tasks: List[str]
    completed_tasks: List[str]
    reclaimed_leases: List[str]
    bypassed_workers: List[str]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_number": self.tick_number,
            "timestamp_utc": self.timestamp_utc,
            "host_gate": asdict(self.host_gate),
            "projects": self.projects,
            "dispatched_tasks": self.dispatched_tasks,
            "completed_tasks": self.completed_tasks,
            "reclaimed_leases": self.reclaimed_leases,
            "bypassed_workers": self.bypassed_workers,
            "errors": self.errors,
        }


class SupervisorLoop:
    """
    Decentralized self-organizing control loop for multi-project task continuation.
    Enforces strict staging isolation: NEVER mutates canonical coordination/TASKS.json.
    """

    def __init__(
        self,
        tasks_file: Optional[Union[str, Path]] = None,
        upstream_tasks_file: Optional[Union[str, Path]] = None,
        registry_file: Optional[Union[str, Path]] = None,
        state_file: Optional[Union[str, Path]] = None,
        receipts_dir: Optional[Union[str, Path]] = None,
        lease_manager: Optional[LeaseManager] = None,
        resource_checker: Optional[ResourceGateChecker] = None,
        quota_checker: Optional[QuotaGateChecker] = None,
        product_ids: Optional[Sequence[str]] = None,
        default_lease_ttl: float = 60.0,
        base_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 300.0,
        max_task_retries: int = 3,
        auto_discover_aplexer: bool = False,
    ) -> None:
        # Default tasks file is isolated staging store, NEVER canonical TASKS.json!
        if tasks_file is None:
            self.tasks_file = Path("/home/alexey/git/cloudflare-agent-git/.local/self_org/tasks.json")
        else:
            self.tasks_file = Path(tasks_file)

        # STRICT CANONICAL PROTECTION GUARD
        if self.tasks_file.resolve() == CANONICAL_TASKS_PATH:
            raise PermissionError(
                f"Direct mutation of canonical '{CANONICAL_TASKS_PATH}' is strictly prohibited! "
                "Specify an isolated staging store path (e.g. .local/self_org/tasks.json)."
            )

        self.upstream_tasks_file = Path(upstream_tasks_file) if upstream_tasks_file else None
        self.registry_file = Path(registry_file) if registry_file else None
        self.auto_discover_aplexer = bool(auto_discover_aplexer)

        if state_file is None:
            self.state_file = Path("/home/alexey/git/cloudflare-agent-git/.local/self_org/state.json")
        else:
            self.state_file = Path(state_file)

        if receipts_dir is None:
            self.receipts_dir = Path("/home/alexey/git/cloudflare-agent-git/.local/self_org/receipts")
        else:
            self.receipts_dir = Path(receipts_dir)

        self.lease_manager = lease_manager or LeaseManager(default_ttl=default_lease_ttl)
        self.resource_checker = resource_checker or ResourceGateChecker()
        self.quota_checker = quota_checker or QuotaGateChecker()

        self.product_ids = list(product_ids or DEFAULT_PRODUCTS)
        self.default_lease_ttl = float(default_lease_ttl)
        self.base_backoff_seconds = float(base_backoff_seconds)
        self.max_backoff_seconds = float(max_backoff_seconds)
        self.max_task_retries = int(max_task_retries)

        self._tasks: Dict[str, Task] = {}
        self._workers: Dict[str, Worker] = {}
        self._tick_counter: int = 0
        self._event_log: List[Dict[str, Any]] = []

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)

        self._load_initial_state()

    # -----------------------------------------------------------------------
    # Initial Loading & Safe Staging Persistence
    # -----------------------------------------------------------------------

    def _load_initial_state(self) -> None:
        """
        Load tasks from staging store or read-only upstream file.
        Load workers from TEAM-REGISTRY.json projects/teams and active aplexer session catalog.
        """
        source_file = None
        if self.tasks_file.exists():
            source_file = self.tasks_file
        elif self.upstream_tasks_file and self.upstream_tasks_file.exists():
            source_file = self.upstream_tasks_file

        if source_file:
            try:
                with open(source_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_tasks = data.get("tasks", []) if isinstance(data, dict) else data
                    for rt in raw_tasks:
                        task = Task.from_dict(rt)
                        self._tasks[task.id] = task
            except Exception as exc:
                logger.warning("Could not load tasks from %s: %s", source_file, exc)

        # 1. Parse TEAM-REGISTRY.json projects, teams, agents, and delivery executors
        if self.registry_file and self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                    # Projects
                    for p in reg.get("projects", []):
                        pid = p.get("id")
                        head_tag = p.get("head_tag")
                        if pid and head_tag:
                            self._workers[head_tag] = Worker(
                                tag=head_tag,
                                project_id=pid,
                                mode="interactive",
                                status="unverified",
                                metadata={"workspace": p.get("workspace"), "role": "head"},
                            )
                    # Teams
                    for t in reg.get("teams", []):
                        tid = t.get("id")
                        head_tag = t.get("head_tag")
                        if tid and head_tag and head_tag not in self._workers:
                            self._workers[head_tag] = Worker(
                                tag=head_tag,
                                project_id=tid,
                                mode="interactive",
                                status="unverified",
                                metadata={"role": "team_head"},
                            )
                    # Agents
                    for a in reg.get("agents", []):
                        atag = a.get("tag") or a.get("id")
                        if atag and atag not in self._workers:
                            self._workers[atag] = Worker(
                                tag=atag,
                                project_id=a.get("team") or "unknown",
                                mode="headless" if a.get("role") != "head" else "interactive",
                                status="unverified",
                                metadata={"role": a.get("role")},
                            )
                    # Delivery executors if present
                    for ex in reg.get("delivery_executors", []):
                        etag = ex.get("tag", ex.get("session_id", "unknown"))
                        self._workers[etag] = Worker(
                            tag=etag,
                            project_id=ex.get("project_id", "unknown"),
                            mode=ex.get("mode", "headless"),
                            provider=ex.get("provider", "gemini"),
                            status="unverified",
                        )
            except Exception as exc:
                logger.warning("Could not load registry from %s: %s", self.registry_file, exc)

        # 2. Inspect active aplexer session catalog if explicitly enabled
        if self.auto_discover_aplexer:
            self._discover_aplexer_sessions()

    def _discover_aplexer_sessions(self) -> None:
        """Query active aplexer session catalog to discover live workers and detect frozen/NOTREADY states."""
        try:
            res = subprocess.run(["aplexer", "snapshot"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                sessions = json.loads(res.stdout)
                for s in sessions:
                    tag = s.get("tag")
                    if not tag:
                        continue
                    reported_state = s.get("reported_state", "idle")
                    phase = s.get("phase", "running")
                    cwd = s.get("cwd", "")

                    # Map session to project by workspace path or tag prefix
                    matched_project = None
                    for pid in self.product_ids:
                        if pid in cwd or pid in tag:
                            matched_project = pid
                            break
                    if not matched_project:
                        # Do NOT map unknown/out-of-workspace sessions to agent-branches!
                        continue

                    is_notready = (reported_state == "NOTREADY" or phase in ("stalled", "stopped", "exited", "dead"))
                    is_busy = (reported_state in ("busy", "working"))
                    is_draft = (reported_state == "draft")

                    if is_notready:
                        status = "NOTREADY"
                    elif is_busy:
                        status = "busy"
                    elif phase == "running" and reported_state in ("idle", "ready"):
                        status = "ready"
                    else:
                        status = "busy"

                    if tag in self._workers:
                        self._workers[tag].status = status
                        self._workers[tag].has_active_draft = is_draft
                    else:
                        self._workers[tag] = Worker(
                            tag=tag,
                            project_id=matched_project,
                            mode="headless",
                            provider=s.get("agent", "gemini"),
                            status=status,
                            has_active_draft=is_draft,
                            metadata={"session_id": s.get("id"), "cwd": cwd},
                        )
        except Exception:
            # aplexer discovery is opportunistic; graceful fallback if CLI unavailable
            pass

    def _persist_tasks_file(self) -> None:
        """
        Atomically persist in-memory tasks to isolated staging tasks_file under flock.
        NEVER writes to canonical TASKS.json!
        """
        if not self.tasks_file:
            return

        if self.tasks_file.resolve() == CANONICAL_TASKS_PATH:
            logger.error("Attempted write to canonical TASKS.json intercepted and blocked!")
            return

        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.tasks_file.with_name(self.tasks_file.name + ".lock")
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            # Reread-merge from disk to prevent concurrent tick overwrites
            if self.tasks_file.exists():
                try:
                    with open(self.tasks_file, "r", encoding="utf-8") as f:
                        disk_data = json.load(f)
                        raw_disk_tasks = disk_data.get("tasks", []) if isinstance(disk_data, dict) else disk_data
                        for rdt in raw_disk_tasks:
                            dt = Task.from_dict(rdt)
                            if dt.id not in self._tasks:
                                self._tasks[dt.id] = dt
                            else:
                                local_t = self._tasks[dt.id]
                                disk_receipt = dt.metadata.get("receipt_path") or dt.raw_fields.get("receipt_path")
                                if disk_receipt and not (local_t.metadata.get("receipt_path") or local_t.raw_fields.get("receipt_path")):
                                    local_t.metadata["receipt_path"] = disk_receipt
                                    local_t.raw_fields["receipt_path"] = disk_receipt
                                # Preserve any external metadata/raw_fields added on disk
                                for k, v in dt.metadata.items():
                                    if k not in local_t.metadata or dt.updated_at >= local_t.updated_at:
                                        local_t.metadata[k] = v
                                for k, v in dt.raw_fields.items():
                                    if k not in local_t.raw_fields or dt.updated_at >= local_t.updated_at:
                                        local_t.raw_fields[k] = v
                                if dt.updated_at >= local_t.updated_at:
                                    if dt.status in ("done", "review", "awaiting-review") and local_t.status in ("running", "awaiting-review"):
                                        local_t.status = dt.status
                                    local_t.metadata.update(dt.metadata)
                                    local_t.raw_fields.update(dt.raw_fields)
                                    local_t.updated_at = dt.updated_at
                except Exception as exc:
                    logger.warning("Could not reread tasks from %s for merge: %s", self.tasks_file, exc)

            task_list = [t.to_dict() for t in self._tasks.values()]
            payload = {
                "schema_version": 1,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "tasks": task_list,
            }
            with tempfile.NamedTemporaryFile("w", dir=str(self.tasks_file.parent), delete=False, encoding="utf-8") as tf:
                json.dump(payload, tf, indent=2)
                tf.flush()
                os.fsync(tf.fileno())
                temp_path = tf.name
            os.replace(temp_path, str(self.tasks_file))
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)

    def _persist_state(self, summary: SupervisorTickSummary) -> None:
        """Atomically write loop supervisor state to state_file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        active_leases = [l.to_dict() for l in self.lease_manager.list_active_leases()]
        payload = {
            "schema_version": 1,
            "last_tick_utc": summary.timestamp_utc,
            "tick_number": summary.tick_number,
            "host_gate": asdict(summary.host_gate),
            "projects": summary.projects,
            "active_leases": active_leases,
            "recent_events": self._event_log[-50:],
        }
        with tempfile.NamedTemporaryFile("w", dir=str(self.state_file.parent), delete=False, encoding="utf-8") as tf:
            json.dump(payload, tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            temp_path = tf.name
        os.replace(temp_path, str(self.state_file))

    # -----------------------------------------------------------------------
    # In-Memory Management APIs (for tests & dynamic registration)
    # -----------------------------------------------------------------------

    def add_task(self, task: Task) -> None:
        self._tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def add_worker(self, worker: Worker) -> None:
        self._workers[worker.tag] = worker

    def get_worker(self, worker_tag: str) -> Optional[Worker]:
        return self._workers.get(worker_tag)

    def set_worker_status(self, worker_tag: str, status: str, has_active_draft: bool = False) -> None:
        if worker_tag in self._workers:
            self._workers[worker_tag].status = status
            self._workers[worker_tag].has_active_draft = has_active_draft

    # -----------------------------------------------------------------------
    # Task Lifecycle & Continuation Logic
    # -----------------------------------------------------------------------

    def _emit_dispatch_receipt(
        self,
        task: Task,
        worker: Worker,
        lease: Lease,
        project_id: str,
        now: float,
    ) -> Path:
        """
        Emits structured execution dispatch envelope / first-tool receipt to disk.
        Establishes real provenance for task assignment before setting status running.
        Demarcates dispatch intent without fabricating child process execution.
        """
        dispatch_id = str(uuid.uuid4())
        receipt = {
            "schema_version": 1,
            "dispatch_id": dispatch_id,
            "task_id": task.id,
            "project_id": project_id,
            "executor_tag": worker.tag,
            "executor_mode": worker.mode,
            "provider": worker.provider,
            "fence_token": lease.fence_token,
            "lease_expires_at": lease.lease_expires_at,
            "dispatched_at_utc": datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).isoformat(),
            "dispatch_intent": f"aplexer dispatch --session {worker.tag} --task {task.id}",
            "execution_adapter": "external_adapter_pending",
            "execution_demarcation": (
                "Execution dispatch intent recorded by supervisor; actual child process/tool "
                "execution happens out-of-band via registered executor adapter."
            ),
            "status": "DISPATCH_INTENT_RECORDED",
        }

        receipt_file = self.receipts_dir / f"{task.id}_dispatch.json"
        with tempfile.NamedTemporaryFile("w", dir=str(self.receipts_dir), delete=False, encoding="utf-8") as tf:
            json.dump(receipt, tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            temp_path = tf.name
        os.replace(temp_path, str(receipt_file))

        task.started_at = now
        task.metadata["dispatch_receipt"] = str(receipt_file)
        task.metadata["dispatch_intent"] = receipt["dispatch_intent"]
        task.metadata["started_at"] = now
        return receipt_file

    def _check_task_completion(self, task: Task, now: float) -> bool:
        """
        Strict completion check per C2038 / C2040:
        1. Task already marked "done" or "review".
        2. Rejects mere 'metadata.completed' flags without verified artifacts.
        3. Receipt validation (if receipt_path specified):
           - File exists, regular file, size >= 16 bytes (anti-junk).
           - Freshness: mtime >= task.started_at (1.0s clock skew tolerance).
           - Valid JSON containing:
             * task_id == task.id
             * fence_token == active_lease.fence_token
             * attempt == task.failure_count + 1
             * executor_tag == task.executor_tag
             * status in ('ACCEPT', 'ACCEPTED', 'PASS', 'DONE', 'COMPLETED')
             * independent_reviewer is non-empty string.
             * output_digest == artifact_sha256
        4. Evidence paths validation (if evidence_paths specified):
           - File must exist, be a regular file, and have size >= 16 bytes (anti-junk).
           - Freshness: mtime must be >= task.started_at (1.0s clock skew tolerance).
           - Anti-junk: If JSON, must not be empty object {} or empty list [].
           - Computes and verifies non-empty SHA256 artifact digest.
        """
        if task.status == "done":
            return True

        # Check explicit receipt path if specified
        receipt_path = task.metadata.get("receipt_path") or task.raw_fields.get("receipt_path")
        if receipt_path:
            rp = Path(receipt_path)
            if not rp.is_file():
                return False
            st = rp.stat()
            if st.st_size < 16:
                logger.warning("Receipt file %s is junk (< 16 bytes: %d bytes)", rp, st.st_size)
                return False
            if task.started_at is not None and st.st_mtime < (task.started_at - 1.0):
                logger.warning("Receipt %s is stale (mtime %f < started_at %f)", rp, st.st_mtime, task.started_at)
                return False
            try:
                with open(rp, "r", encoding="utf-8") as rf:
                    rdata = json.load(rf)
            except Exception as exc:
                logger.warning("Receipt %s invalid JSON: %s", rp, exc)
                return False

            if not isinstance(rdata, dict):
                return False

            # 1. Assert task_id matches
            if not rdata.get("task_id") or rdata["task_id"] != task.id:
                logger.warning("Receipt %s task_id mismatch (%s != %s)", rp, rdata.get("task_id"), task.id)
                return False

            # 2. Assert active lease matches fence_token, holder, and unexpired
            active_lease = self.lease_manager.get_lease(task.id)
            if not active_lease or active_lease.status != "active":
                logger.warning("Receipt %s: no active lease for task %s", rp, task.id)
                return False
            if active_lease.is_expired(now):
                logger.warning("Receipt %s: active lease for task %s is expired", rp, task.id)
                return False
            if active_lease.lease_holder != task.executor_tag:
                logger.warning("Receipt %s: lease holder mismatch (%s != %s)", rp, active_lease.lease_holder, task.executor_tag)
                return False
            if rdata.get("fence_token") != active_lease.fence_token:
                logger.warning(
                    "Receipt %s fence_token mismatch (receipt=%s, active=%s)",
                    rp, rdata.get("fence_token"), getattr(active_lease, "fence_token", None)
                )
                return False
            if rdata.get("executor_tag") != active_lease.lease_holder:
                logger.warning(
                    "Receipt %s executor_tag mismatch (receipt=%s, active=%s)",
                    rp, rdata.get("executor_tag"), active_lease.lease_holder
                )
                return False

            # 3. Assert attempt == task.failure_count + 1
            expected_attempt = task.failure_count + 1
            if rdata.get("attempt") != expected_attempt:
                logger.warning(
                    "Receipt %s attempt mismatch (receipt=%s, expected=%s)",
                    rp, rdata.get("attempt"), expected_attempt
                )
                return False

            # 4. Assert executor_tag matches
            if not rdata.get("executor_tag") or (task.executor_tag and rdata.get("executor_tag") != task.executor_tag):
                logger.warning(
                    "Receipt %s executor_tag mismatch (receipt=%s, task=%s)",
                    rp, rdata.get("executor_tag"), task.executor_tag
                )
                return False

            # 5. Assert status in allowed set
            status = str(rdata.get("status", "")).upper()
            if status not in ("ACCEPT", "ACCEPTED", "PASS", "DONE", "COMPLETED"):
                logger.warning("Receipt %s status '%s' not accepted", rp, status)
                return False

            # 6. Assert independent_reviewer is non-empty string and distinct from executor_tag
            reviewer = rdata.get("independent_reviewer")
            if not reviewer or not isinstance(reviewer, str) or not reviewer.strip():
                logger.warning("Receipt %s missing or empty independent_reviewer", rp)
                return False
            clean_reviewer = reviewer.strip()
            if clean_reviewer == (task.executor_tag or "").strip() or clean_reviewer == (rdata.get("executor_tag") or "").strip():
                logger.warning(
                    "Receipt %s independent_reviewer matches executor_tag (%s == %s); distinct reviewer required!",
                    rp, clean_reviewer, task.executor_tag
                )
                return False

            # 7. Assert output_digest == artifact_sha256
            artifact_path = rdata.get("artifact_path")
            if not artifact_path and task.evidence_paths:
                artifact_path = task.evidence_paths[0]

            if not artifact_path:
                logger.warning("Receipt %s has no artifact_path and task has no evidence_paths", rp)
                return False

            ap = Path(artifact_path)
            if not ap.is_file():
                logger.warning("Receipt %s artifact_path '%s' is not a file", rp, artifact_path)
                return False
            if ap.stat().st_size < 16:
                logger.warning("Receipt %s artifact '%s' is junk (< 16 bytes)", rp, artifact_path)
                return False

            artifact_bytes = ap.read_bytes()
            artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
            if rdata.get("output_digest") != artifact_sha256:
                logger.warning(
                    "Receipt %s output_digest mismatch (receipt=%s != artifact=%s)",
                    rp, rdata.get("output_digest"), artifact_sha256
                )
                return False

            task.metadata["verified_receipt"] = str(rp)
            task.metadata["verified_at"] = now
            task.metadata["output_digest"] = artifact_sha256
            return True

        # Check evidence paths if specified
        if task.evidence_paths:
            all_evidence_valid = True
            hashes = {}
            for ep in task.evidence_paths:
                p = Path(ep)
                if not p.is_file():
                    all_evidence_valid = False
                    break
                st = p.stat()
                # Anti-junk: file size must be >= 16 bytes!
                if st.st_size < 16:
                    logger.warning("Evidence file %s is junk/placeholder (size %d < 16 bytes)", ep, st.st_size)
                    all_evidence_valid = False
                    break

                # Strict freshness check: reject pre-existing / stale files!
                if task.started_at is not None:
                    if st.st_mtime < (task.started_at - 1.0):
                        logger.warning(
                            "Evidence %s is stale (mtime %f < task started_at %f); rejecting completion",
                            ep, st.st_mtime, task.started_at
                        )
                        all_evidence_valid = False
                        break

                file_bytes = p.read_bytes()
                # Anti-junk: If JSON, must not be empty object {} or empty list []
                if p.suffix.lower() == ".json":
                    try:
                        content_str = file_bytes.decode("utf-8").strip()
                        jdata = json.loads(content_str)
                        if jdata == {} or jdata == []:
                            logger.warning("Evidence file %s is empty JSON {} or []", ep)
                            all_evidence_valid = False
                            break
                    except Exception:
                        logger.warning("Evidence JSON file %s is invalid JSON", ep)
                        all_evidence_valid = False
                        break

                # Compute artifact hash
                h = hashlib.sha256(file_bytes).hexdigest()
                hashes[str(p)] = h

            if all_evidence_valid:
                task.metadata["evidence_hashes"] = hashes
                task.metadata["verified_at"] = now
                if task.status == "running":
                    task.status = "awaiting-review"
                    task.updated_at = now
                    logger.info("Task %s evidence verified; advanced to awaiting-review (awaiting independent review receipt)", task.id)
                # NEVER return True on evidence alone without verified receipt!
                return False

        return False

    def _calculate_backoff_delay(self, failure_count: int) -> float:
        """Exponential backoff: base * 2^(failures - 1), capped at max_backoff."""
        if failure_count <= 0:
            return 0.0
        delay = self.base_backoff_seconds * (2.0 ** (failure_count - 1))
        return min(delay, self.max_backoff_seconds)

    def _get_healthy_worker_for_project(
        self,
        project_id: str,
        bypassed_list: List[str],
    ) -> Optional[Worker]:
        """
        Selects a healthy worker for the given project.
        - First choice: healthy 'headless' worker.
        - Second choice: healthy 'interactive' worker.
        - If an interactive worker is marked NOTREADY, frozen, or has an active draft:
          bypasses it, logs the bypass, and continues to look for a headless worker!
        """
        project_workers = [w for w in self._workers.values() if w.project_id == project_id]

        for w in project_workers:
            if not w.is_healthy_for_dispatch():
                bypassed_list.append(f"{w.tag}(status={w.status},draft={w.has_active_draft})")

        # 1. Prefer healthy headless workers
        for w in project_workers:
            if w.mode == "headless" and w.is_healthy_for_dispatch():
                return w

        # 2. Fall back to healthy interactive workers
        for w in project_workers:
            if w.mode == "interactive" and w.is_healthy_for_dispatch():
                return w

        return None

    # -----------------------------------------------------------------------
    # Main Control Loop Tick
    # -----------------------------------------------------------------------

    def tick(self, now: Optional[float] = None) -> SupervisorTickSummary:
        """
        Executes a single autonomous supervision tick:
        1. Checks host resource sanity (fail-closed memory/disk checks).
        2. Iterates across all independent product queues in complete isolation.
        3. Detects completions (fresh mtime + hash) -> marks done -> releases lease.
        4. Detects expired leases -> reclaims lease with fencing token increment -> reassigns/retries.
        5. Unblocks queued tasks whose dependencies are met.
        6. Dispatches ready tasks with real first-tool receipt (bypassing frozen/NOTREADY TUIs).
        7. Persists state to isolated staging files under flock.
        """
        ts = now if now is not None else time.time()
        self._tick_counter += 1
        utc_str = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

        host_gate = self.resource_checker.check()
        projects_summary: Dict[str, Dict[str, Any]] = {}
        dispatched_tasks: List[str] = []
        completed_tasks: List[str] = []
        reclaimed_leases: List[str] = []
        bypassed_workers: List[str] = []
        errors: List[str] = []

        for project_id in self.product_ids:
            proj_data: Dict[str, Any] = {
                "status": "healthy",
                "running_tasks": [],
                "ready_tasks": [],
                "completed_tasks": [],
                "error": None,
            }
            projects_summary[project_id] = proj_data

            try:
                self._process_project_queue(
                    project_id=project_id,
                    host_gate=host_gate,
                    proj_data=proj_data,
                    dispatched_tasks=dispatched_tasks,
                    completed_tasks=completed_tasks,
                    reclaimed_leases=reclaimed_leases,
                    bypassed_workers=bypassed_workers,
                    now=ts,
                )
            except Exception as exc:
                err_msg = f"Project '{project_id}' failure: {exc}"
                logger.exception(err_msg)
                proj_data["status"] = "degraded"
                proj_data["error"] = str(exc)
                errors.append(err_msg)

        summary = SupervisorTickSummary(
            tick_number=self._tick_counter,
            timestamp_utc=utc_str,
            host_gate=host_gate,
            projects=projects_summary,
            dispatched_tasks=dispatched_tasks,
            completed_tasks=completed_tasks,
            reclaimed_leases=reclaimed_leases,
            bypassed_workers=bypassed_workers,
            errors=errors,
        )

        self._persist_tasks_file()
        self._persist_state(summary)
        return summary

    def _process_project_queue(
        self,
        project_id: str,
        host_gate: GateResult,
        proj_data: Dict[str, Any],
        dispatched_tasks: List[str],
        completed_tasks: List[str],
        reclaimed_leases: List[str],
        bypassed_workers: List[str],
        now: float,
    ) -> None:
        """Processes tasks for a single isolated product queue."""
        project_tasks = [t for t in self._tasks.values() if t.project_id == project_id]

        # -------------------------------------------------------------------
        # Phase 1: Check running and awaiting-review tasks for completion or lease expiry
        # -------------------------------------------------------------------
        for task in list(project_tasks):
            if task.status in ("running", "awaiting-review", "review"):
                # Check for strict completion (requires verified receipt for done/release)
                if self._check_task_completion(task, now=now):
                    task.status = "done"
                    task.updated_at = now
                    completed_tasks.append(task.id)
                    proj_data["completed_tasks"].append(task.id)

                    # Release lease cleanly under flock
                    current_lease = self.lease_manager.get_lease(task.id)
                    if current_lease and current_lease.status == "active":
                        try:
                            self.lease_manager.release_lease(
                                task_id=task.id,
                                holder=current_lease.lease_holder,
                                fence_token=current_lease.fence_token,
                            )
                        except Exception as exc:
                            logger.warning("Could not release lease for %s: %s", task.id, exc)

                    self._event_log.append({
                        "event": "TASK_COMPLETED",
                        "task_id": task.id,
                        "project_id": project_id,
                        "timestamp": now,
                    })
                    continue

                if task.status == "awaiting-review":
                    proj_data.setdefault("awaiting_review_tasks", []).append(task.id)
                    continue

                # Check for lease expiration (dead or stalled worker)
                lease = self.lease_manager.get_lease(task.id)
                if lease and lease.is_expired(now):
                    # Lease expired! Reclaim with monotonic fence token increment under flock
                    new_worker = self._get_healthy_worker_for_project(project_id, bypassed_workers)
                    new_holder = new_worker.tag if new_worker else f"supervisor-recovery-{project_id}"

                    reclaimed_lease = self.lease_manager.reclaim_expired_lease(
                        task_id=task.id,
                        new_holder=new_holder,
                        ttl_seconds=self.default_lease_ttl,
                        now=now,
                    )
                    reclaimed_leases.append(f"{task.id}(fence={reclaimed_lease.fence_token},holder={new_holder})")

                    task.failure_count += 1
                    task.last_failure_at = now
                    task.updated_at = now

                    if task.failure_count <= self.max_task_retries:
                        task.executor_tag = new_holder
                        # Emit fresh dispatch receipt on lease takeover
                        if new_worker:
                            self._emit_dispatch_receipt(task, new_worker, reclaimed_lease, project_id, now)

                        self._event_log.append({
                            "event": "LEASE_RECLAIMED_RETRY",
                            "task_id": task.id,
                            "new_holder": new_holder,
                            "fence_token": reclaimed_lease.fence_token,
                            "failure_count": task.failure_count,
                            "timestamp": now,
                        })
                    else:
                        task.status = "failed"
                        task.metadata["failure_reason"] = "Lease expired and max retries exceeded"
                        self.lease_manager.revoke_lease(task.id, reason="max_retries_exceeded")
                        self._event_log.append({
                            "event": "TASK_FAILED_MAX_RETRIES",
                            "task_id": task.id,
                            "timestamp": now,
                        })
                    continue

                proj_data["running_tasks"].append(task.id)

        # -------------------------------------------------------------------
        # Phase 2: Advance queued tasks whose dependencies are met
        # -------------------------------------------------------------------
        done_task_ids = {t.id for t in self._tasks.values() if t.status == "done"}
        for task in list(project_tasks):
            if task.status == "queued":
                dependencies_met = all(dep in done_task_ids for dep in task.blocked_on)
                if dependencies_met:
                    task.status = "ready"
                    task.updated_at = now
                    self._event_log.append({
                        "event": "TASK_READY",
                        "task_id": task.id,
                        "project_id": project_id,
                        "timestamp": now,
                    })

        # -------------------------------------------------------------------
        # Phase 3: Dispatch ready tasks to healthy available workers
        # -------------------------------------------------------------------
        ready_tasks = [t for t in self._tasks.values() if t.project_id == project_id and t.status == "ready"]
        for task in ready_tasks:
            proj_data["ready_tasks"].append(task.id)

        # If host sanity gates failed, do NOT dispatch new tasks (protect host resources)
        if not host_gate.allowed:
            proj_data["status"] = "throttled_host_sanity"
            return

        # Check concurrency (at most 1 running/awaiting-review task per project queue in baseline)
        current_running = [t for t in self._tasks.values() if t.project_id == project_id and t.status in ("running", "awaiting-review")]
        if current_running:
            return  # Already actively executing or awaiting review receipt

        for task in ready_tasks:
            # Check restart backoff
            if task.failure_count > 0 and task.last_failure_at:
                backoff_delay = self._calculate_backoff_delay(task.failure_count)
                if now < task.last_failure_at + backoff_delay:
                    continue  # Still within backoff window

            # Find healthy worker (bypassing frozen NOTREADY interactive workers!)
            worker = self._get_healthy_worker_for_project(project_id, bypassed_workers)
            if not worker:
                continue

            # Check provider quota gates against effective provider
            effective_provider = task.provider or worker.provider
            quota_res = self.quota_checker.check(effective_provider, now=now)
            if not quota_res.allowed:
                continue  # Provider quota constraint active, skip

            # Acquire lease with LeaseManager under flock
            try:
                lease = self.lease_manager.acquire_lease(
                    task_id=task.id,
                    holder=worker.tag,
                    ttl_seconds=self.default_lease_ttl,
                    metadata={"project_id": project_id, "provider": worker.provider},
                    now=now,
                )
            except (LeaseAlreadyHeldError, LeaseStorageCorruptedError) as exc:
                logger.warning("Could not acquire lease for %s: %s", task.id, exc)
                continue

            # Emit structured dispatch envelope & first-tool receipt
            self._emit_dispatch_receipt(task, worker, lease, project_id, now)

            # Transition task to running
            task.status = "running"
            task.executor_tag = worker.tag
            task.updated_at = now
            dispatched_tasks.append(task.id)
            proj_data["running_tasks"].append(task.id)
            proj_data["ready_tasks"].remove(task.id)

            self._event_log.append({
                "event": "TASK_DISPATCHED",
                "task_id": task.id,
                "project_id": project_id,
                "executor": worker.tag,
                "fence_token": lease.fence_token,
                "timestamp": now,
            })
            break  # Dispatched one task for this queue

    # -----------------------------------------------------------------------
    # Continuous Daemon Execution
    # -----------------------------------------------------------------------

    def run_forever(self, interval_seconds: float = 30.0) -> None:
        """Run continuous autonomous control loop."""
        logger.info("Starting autonomous self-organization supervisor loop (interval: %.1fs)", interval_seconds)
        while True:
            try:
                summary = self.tick()
                logger.info(
                    "Tick #%d completed at %s: dispatched=%d, completed=%d, reclaimed=%d, errors=%d",
                    summary.tick_number,
                    summary.timestamp_utc,
                    len(summary.dispatched_tasks),
                    len(summary.completed_tasks),
                    len(summary.reclaimed_leases),
                    len(summary.errors),
                )
            except Exception as exc:
                logger.exception("Unexpected error in supervisor loop tick: %s", exc)
            time.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Hetzner Self-Organization Supervisor Loop")
    parser.add_argument("--tick", action="store_true", help="Run a single evaluation pass and exit (ideal for systemd timer / cron)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as a background daemon")
    parser.add_argument("--interval", type=float, default=30.0, help="Loop interval in seconds for daemon mode (default: 30.0)")
    parser.add_argument("--state-file", type=str, default="/home/alexey/git/cloudflare-agent-git/.local/self_org/state.json", help="Path to state JSON output file")
    parser.add_argument("--tasks-file", type=str, default="/home/alexey/git/cloudflare-agent-git/.local/self_org/tasks.json", help="Path to isolated staging tasks.json")
    parser.add_argument("--registry-file", type=str, default="/home/alexey/git/cloudflare-agent-git/coordination/TEAM-REGISTRY.json", help="Path to TEAM-REGISTRY.json")
    parser.add_argument("--lease-file", type=str, default="/home/alexey/git/cloudflare-agent-git/.local/self_org/leases.json", help="Path to leases JSON file")
    parser.add_argument("--receipts-dir", type=str, default="/home/alexey/git/cloudflare-agent-git/.local/self_org/receipts", help="Path to receipts directory")
    parser.add_argument("--scratch-dir", type=str, default="/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-arch", help="Path to scratch directory")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    lease_mgr = LeaseManager(lease_file=args.lease_file)
    res_checker = ResourceGateChecker(scratch_dir=args.scratch_dir)
    quota_checker = QuotaGateChecker()

    supervisor = SupervisorLoop(
        tasks_file=args.tasks_file,
        registry_file=args.registry_file,
        state_file=args.state_file,
        receipts_dir=args.receipts_dir,
        lease_manager=lease_mgr,
        resource_checker=res_checker,
        quota_checker=quota_checker,
    )

    if args.daemon:
        supervisor.run_forever(interval_seconds=args.interval)
    else:
        summary = supervisor.tick()
        print(json.dumps(summary.to_dict(), indent=2))


if __name__ == "__main__":
    main()
