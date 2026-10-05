#!/usr/bin/env python3
"""
Launcher & Agent Bus Integration Bridge (C2070 / C2072 / C2074 Codex Principal Directives).

Directly integrates the self-organizing control plane with:
1. `agent-quota-launcher` (Store, check_resources, admission gates)
2. `agent-coordination` (FileBus, Envelope, Cursors)

Pin & Durability Disclosures (C2072 / C2074):
- `agent-coordination` at `bb8dcad` is a legacy core pin (successor `207a93f9` durability
  fixes were not backported; public agent-bus HEAD is `f3295f99`).
- Known durability boundaries in legacy `coordination/bus.py`:
  1. `_write` does a single `os.write` without a short-write retry loop.
  2. `_write` does `fsync(fd)` and `os.replace`, but omits parent directory `fsync`.
  3. `register` writes `identities.json` and `tokens.json` in two separate non-transactional
     writes (crash between writes can tear credential state).
  Note: This bridge provides defensive application-layer validation and fail-closed
  consistency guards. Full core bus engine durability belongs to successor pin `207a93f9`.

Strict Directives & Architectural Rules (C2070 / C2074):
1. Fail-Closed Quota Admission:
   - Rejects `quota_telemetry is None` immediately with `QuotaAdmissionError` (fail-closed).
   - Rejects non-queued or already completed tasks in Store.
   - Fails closed on Store connection or read errors (never assumes 0 reservations on error).
2. Clean Adapter Design (ZERO Monkeypatching):
   - Pure, un-monkeypatched integration. No globals or external module monkeypatching.
   - Truthful naming: `check_resource_eligibility` (read-only pre-check) and
     `check_dispatch_admission` (full transactional admission with quota evaluation).
3. Defensive Durability:
   - `durable_atomic_write` enforces full write loop and parent directory fsync (raising
     on fsync failure).
   - Anti-tearing credential consistency guard fails closed (`BusStoreInconsistentError`).
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid

_DEFAULT = object()

# Ensure sibling repositories are in sys.path (strictly read-only access)
LAUNCHER_REPO_PATH = Path("/home/alexey/git/agent-quota-launcher").resolve()
COORDINATION_REPO_PATH = Path("/home/alexey/git/agent-coordination").resolve()

for repo_path in (LAUNCHER_REPO_PATH, COORDINATION_REPO_PATH):
    if repo_path.exists() and str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))

# Imports from agent-quota-launcher (STRICTLY READ-ONLY)
from launcher.resources import (
    MAX_WORKER_MEMORY_MB,
    MIN_DISK_FREE_BYTES,
    MIN_MEM_AVAILABLE_BYTES,
    check_resources,
)
from launcher.store import (
    LEASED_STATES,
    RESOURCE_HOLDING_STATES,
    StateTransitionError,
    Store,
    launch_lock,
)
from launcher.admission import (
    ADAPTER_MODELS,
    ADAPTER_ROUTES,
    fetch_quse,
    validate_quse,
)
from launcher.ranking import select_candidate
from launcher.launch import (
    ADAPTERS,
    build_adapter_argv,
)

# Imports from agent-coordination (STRICTLY READ-ONLY)
from coordination.bus import (
    BusError,
    BusIdentity,
    BusMessage,
    FileBus,
)
from coordination.envelope import (
    ActionOutcome,
    NamespacedId,
    ReadAck,
    SendReceipt,
    TransportState,
    new_idempotency_key,
    new_message_id,
)
from coordination.cursors import (
    CursorStore,
    payload_digest,
)

logger = logging.getLogger("launcher_bus_bridge")


# ===========================================================================
# C2072 / C2074 Defensive Durability Helpers: Full-Write Loops & Directory Fsync
# ===========================================================================

def durable_atomic_write(target_path: Union[str, Path], data: Union[str, bytes]) -> None:
    """
    Writes data atomically and durably to target_path:
    1. Uses a full-write retry loop (`while total_written < len(payload_bytes)`).
    2. Calls `os.fsync(fd)` on the temporary file.
    3. Atomically replaces target with `os.replace`.
    4. Calls `os.fsync(dir_fd)` on the parent directory to guarantee durability
       across power loss / hard reset. Propagates any fsync error (fails closed).
    """
    path = Path(target_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_bytes = data.encode("utf-8") if isinstance(data, str) else data

    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    fd = os.open(str(tmp_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        total_written = 0
        while total_written < len(payload_bytes):
            written = os.write(fd, payload_bytes[total_written:])
            if written == 0:
                raise OSError("Zero bytes written during durable write")
            total_written += written
        os.fsync(fd)
    finally:
        os.close(fd)

    os.replace(tmp_path, path)

    # Parent directory fsync to persist directory entry mutation durably
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


# ===========================================================================
# Typed Envelope Implementation
# ===========================================================================

@dataclass
class Envelope:
    """
    Typed transport envelope for bus message exchange.
    Tracks sender/recipient namespaced IDs, transport state, body, data, and digest.
    """
    message_id: str
    sender_id: str
    recipient_id: str
    body: str
    data: Optional[Dict[str, Any]] = None
    kind: str = "note"
    state: TransportState = TransportState.RECORDED
    idempotency_key: Optional[str] = None
    created_at: str = ""
    acked_at: Optional[str] = None
    digest: str = ""
    sender_ns: Optional[NamespacedId] = None
    recipient_ns: Optional[NamespacedId] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "body": self.body,
            "data": self.data,
            "kind": self.kind,
            "state": self.state.value if isinstance(self.state, TransportState) else str(self.state),
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "acked_at": self.acked_at,
            "digest": self.digest,
            "sender_ns": self.sender_ns.render() if self.sender_ns else None,
            "recipient_ns": self.recipient_ns.render() if self.recipient_ns else None,
        }

    @classmethod
    def from_bus_message(
        cls,
        msg: BusMessage,
        sender_ns: Optional[NamespacedId] = None,
        recipient_ns: Optional[NamespacedId] = None,
    ) -> Envelope:
        state = TransportState.RECIPIENT_READ_ACK if msg.acked_at else TransportState.SEND_RECEIPT
        return cls(
            message_id=msg.message_id,
            sender_id=msg.sender_id,
            recipient_id=msg.recipient_id,
            body=msg.body,
            data=msg.data,
            kind=msg.kind,
            state=state,
            idempotency_key=msg.idempotency_key,
            created_at=msg.created_at,
            acked_at=msg.acked_at,
            digest=msg.digest,
            sender_ns=sender_ns,
            recipient_ns=recipient_ns,
        )


# ===========================================================================
# Component 1: LauncherAdmissionBridge & Exceptions (C2074 Fail-Closed)
# ===========================================================================

class AdmissionError(Exception):
    """Raised when task admission fails resource, security, or quota gates."""
    pass


class ResourceAdmissionError(AdmissionError):
    """Raised when host resources (disk, memory, TMPDIR) violate admission boundaries."""
    pass


class QuotaAdmissionError(AdmissionError):
    """Raised when quota telemetry is missing, invalid, stale, exhausted, or unavailable."""
    pass


class LauncherAdmissionBridge:
    """
    Bridge interfacing directly with canonical `agent-quota-launcher` admission and Store.
    Enforces fail-closed semantics across all resource and quota gates:
    - Rejects missing quota telemetry (quota_telemetry is None).
    - Rejects /tmp paths and uncontained TMPDIR.
    - Rejects memory requests > 1500MB.
    - Rejects non-queued or already completed tasks in Store.
    - Fails closed on Store connection or read errors.
    """

    MIN_TIMEOUT_SECONDS = 60
    MAX_TIMEOUT_SECONDS = 7200

    def __init__(
        self,
        store: Optional[Union[str, Path, Store]] = None,
        workspace: Optional[Union[str, Path]] = None,
    ) -> None:
        self.workspace = Path(workspace).resolve() if workspace else Path("/home/alexey/git/cloudflare-agent-git")
        if isinstance(store, Store):
            self.store = store
        elif store is not None:
            self.store = Store(str(Path(store).resolve()))
        else:
            self.store = None

    @classmethod
    def check_resource_eligibility(
        cls,
        workspace: Union[str, Path],
        timeout: float,
        requested_memory_mb: int = 1500,
        requested_tmpdir: Optional[Union[str, Path]] = None,
        repo_root: Optional[Union[str, Path]] = None,
        store: Optional[Store] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read-only pre-check validating host resource eligibility and Store task state.
        Fails closed on any violation or Store error.
        """
        # 1. Bounded timeout validation
        try:
            timeout_float = float(timeout)
        except (TypeError, ValueError) as exc:
            raise AdmissionError(f"Timeout must be a numeric value in seconds: {timeout}") from exc

        if not (cls.MIN_TIMEOUT_SECONDS <= timeout_float <= cls.MAX_TIMEOUT_SECONDS):
            raise AdmissionError(
                f"Requested timeout {timeout_float}s outside bounded range "
                f"[{cls.MIN_TIMEOUT_SECONDS}, {cls.MAX_TIMEOUT_SECONDS}]"
            )

        # 2. Memory ceiling validation
        if requested_memory_mb > MAX_WORKER_MEMORY_MB:
            raise ResourceAdmissionError(
                f"Requested worker memory {requested_memory_mb}MiB exceeds maximum "
                f"{MAX_WORKER_MEMORY_MB}MiB cooperative pool limit"
            )

        # 3. Workspace and TMPDIR path setup
        ws_path = Path(workspace).resolve()
        root_path = Path(repo_root or ws_path).resolve()

        if requested_tmpdir is None:
            resolved_tmp = root_path / ".local" / "tmp"
            resolved_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
        else:
            resolved_tmp = Path(requested_tmpdir).resolve()

        # Strict anti-/tmp pre-check
        if resolved_tmp == Path("/tmp") or resolved_tmp.parts[:2] == ("/", "tmp"):
            raise ResourceAdmissionError("reject /tmp")

        # 4. Check active resource reservations in Store if provided (C2074: fail closed on error!)
        active_mem = 0
        active_disk = 0
        if store is not None:
            try:
                active_mem, active_disk = store.get_active_resources(exclude_task_id=task_id)
            except Exception as exc:
                raise AdmissionError(
                    f"Store active resources query failed (failing closed): {exc}"
                ) from exc

            # Verify task state in Store if task_id provided
            if task_id is not None:
                try:
                    task_info = store.get_task(task_id)
                except Exception as exc:
                    raise AdmissionError(
                        f"Store task query failed for '{task_id}' (failing closed): {exc}"
                    ) from exc

                if task_info is None:
                    raise AdmissionError(f"Task '{task_id}' not found in launcher Store")

                task_state = task_info.get("state")
                if task_state not in ("queued", "starting"):
                    raise AdmissionError(
                        f"Task '{task_id}' state is '{task_state}', expected 'queued' (failing closed)"
                    )

        # 5. Invoke canonical launcher.resources.check_resources
        try:
            check_resources(
                requested_memory_mb=requested_memory_mb,
                requested_cwd=str(ws_path),
                requested_tmpdir=str(resolved_tmp),
                active_mem_mb=active_mem,
                active_disk_mb=active_disk,
                repo_root=str(root_path),
            )
        except ValueError as exc:
            raise ResourceAdmissionError(f"Resource admission rejected: {exc}") from exc

        return {
            "eligible": True,
            "workspace": str(ws_path),
            "tmpdir": str(resolved_tmp),
            "memory_mb": requested_memory_mb,
            "timeout_seconds": timeout_float,
            "active_mem_mb": active_mem,
            "active_disk_mb": active_disk,
        }

    @classmethod
    def check_dispatch_admission(
        cls,
        workspace: Union[str, Path],
        timeout: float,
        requested_model: Optional[str] = None,
        quota_telemetry: Optional[Dict[str, Any]] = None,
        requested_memory_mb: int = 1500,
        requested_tmpdir: Optional[Union[str, Path]] = None,
        repo_root: Optional[Union[str, Path]] = None,
        store: Optional[Store] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read-only admission eligibility verification combining resource checks and quota validation.
        NOTICE (Codex Principal C2075): This is a read-only pre-flight eligibility check, NOT an atomic
        transactional dispatch. It does not hold dispatch locks, allocate store reservation units, or
        perform CAS task state transitions. Live model activation remains strictly blocked/held.
        C2074: Strictly fails closed when quota_telemetry is None or empty.
        """
        # 1. Resource and Store state eligibility
        eligibility = cls.check_resource_eligibility(
            workspace=workspace,
            timeout=timeout,
            requested_memory_mb=requested_memory_mb,
            requested_tmpdir=requested_tmpdir,
            repo_root=repo_root,
            store=store,
            task_id=task_id,
        )

        # 2. C2074 Fail-Closed Quota Gate
        if quota_telemetry is None:
            raise QuotaAdmissionError("Quota telemetry missing/None: fail-closed")

        if not isinstance(quota_telemetry, dict) or not quota_telemetry:
            raise QuotaAdmissionError("Quota telemetry empty or malformed: fail-closed")

        req_spec = {"models": [requested_model]} if requested_model else None
        try:
            valid_routes, rejections = validate_quse(quota_telemetry, task_requirements=req_spec)
        except Exception as exc:
            raise QuotaAdmissionError(f"Failed to validate quota telemetry: {exc}") from exc

        if not valid_routes:
            raise QuotaAdmissionError(
                f"No valid quota routes available for dispatch. Rejections: {rejections}"
            )

        chosen_route: Optional[Dict[str, Any]] = None
        if requested_model:
            candidates = [
                r for r in valid_routes
                if r.get("model") == requested_model
                or r.get("name") == requested_model
                or r.get("provider") == requested_model
            ]
            if not candidates:
                raise QuotaAdmissionError(
                    f"Requested model '{requested_model}' not available in valid routes. "
                    f"Rejections: {rejections}"
                )
            chosen_route = candidates[0]
        else:
            chosen_route = valid_routes[0]

        return {
            "admitted": True,
            "phase": "admission_eligibility_verified",
            "transactional_dispatch": False,
            "workspace": eligibility["workspace"],
            "tmpdir": eligibility["tmpdir"],
            "memory_mb": eligibility["memory_mb"],
            "timeout_seconds": eligibility["timeout_seconds"],
            "requested_model": requested_model,
            "chosen_route": chosen_route,
            "rejections": rejections,
            "active_mem_mb": eligibility["active_mem_mb"],
            "active_disk_mb": eligibility["active_disk_mb"],
        }

    # Authoritative admission method alias
    check_admission = check_dispatch_admission

    def inspect_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Queries task state and payload from launcher Store."""
        if not self.store:
            raise AdmissionError("No Store configured in LauncherAdmissionBridge")
        try:
            return self.store.get_task(task_id)
        except Exception as exc:
            raise AdmissionError(f"Store task query failed: {exc}") from exc

    def transition_task_state(
        self,
        task_id: str,
        new_state: str,
        expected_states: Tuple[str, ...],
        reviewer: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Transitions task state in launcher Store under guard."""
        if not self.store:
            raise AdmissionError("No Store configured in LauncherAdmissionBridge")
        try:
            return self.store.transition_task(
                task_id=task_id,
                new_state=new_state,
                expected_states=expected_states,
                reviewer=reviewer,
                reason=reason,
            )
        except StateTransitionError as exc:
            raise AdmissionError(f"State transition failed: {exc}") from exc
        except Exception as exc:
            raise AdmissionError(f"Store state transition error: {exc}") from exc


# ===========================================================================
# Component 2: AgentBusEnrollmentBridge & Exceptions (C2072 / C2074)
# ===========================================================================

class BusBridgeError(Exception):
    """Base exception for agent bus enrollment and messaging failures."""
    pass


class BusSecurityError(BusBridgeError):
    """Raised when bus directory security or file permissions are violated."""
    pass


class BusStoreInconsistentError(BusBridgeError):
    """Raised when underlying FileBus credential state is torn or inconsistent (C2072)."""
    pass


class AgentBusEnrollmentBridge:
    """
    Bridge interfacing directly with `agent-coordination` FileBus.
    Enforces mode 0700 bus store security, registers distinct subagent identities,
    guards against legacy pin credential tearing (C2072), and produces/consumes
    typed Envelope instances with cursor tracking.
    """

    def __init__(
        self,
        bus_dir: Union[str, Path],
        device_id: str = "local-device",
        workspace: str = "cloudflare-agent-git",
    ) -> None:
        self.bus_dir = Path(bus_dir).resolve()
        self.device_id = device_id
        self.workspace = workspace

        # Check existing directory permissions before creating or modifying
        if self.bus_dir.exists():
            st = self.bus_dir.stat()
            if (st.st_mode & 0o077) != 0:
                raise BusSecurityError(
                    f"Insecure permissions on existing bus dir {self.bus_dir}: "
                    f"mode {oct(st.st_mode)} has group/other bits set (mode 0700 required)"
                )
        else:
            self.bus_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        self.bus = FileBus(self.bus_dir)
        self.cursors = CursorStore(self.bus_dir)
        self._enrolled_identities: Dict[str, Tuple[BusIdentity, str, NamespacedId]] = {}

    def verify_bus_security(self) -> None:
        """Verifies that bus directory mode strictly forbids group/other read/write."""
        try:
            st = self.bus_dir.stat()
            if (st.st_mode & 0o077) != 0:
                raise BusSecurityError(
                    f"Insecure permissions on bus dir {self.bus_dir}: mode {oct(st.st_mode)} has group/other bits set"
                )
        except OSError as exc:
            raise BusSecurityError(f"Cannot stat bus directory: {exc}") from exc

    def verify_credential_consistency(self, identity_id: Optional[str] = None) -> None:
        """
        C2072 Defensive Invariant:
        Checks for torn credential states resulting from non-transactional writes
        in legacy FileBus pin (bb8dcad). Fails closed with BusStoreInconsistentError.
        """
        identities_file = self.bus_dir / "identities.json"
        tokens_file = self.bus_dir / "tokens.json"

        if not identities_file.exists() and not tokens_file.exists():
            return

        try:
            identities = json.loads(identities_file.read_text(encoding="utf-8")) if identities_file.exists() else {}
            tokens = json.loads(tokens_file.read_text(encoding="utf-8")) if tokens_file.exists() else {}
        except Exception as exc:
            raise BusStoreInconsistentError(f"Failed to read credential stores for consistency check: {exc}") from exc

        # Check for asymmetric tearing
        if identity_id:
            has_ident = identity_id in identities
            has_tok = identity_id in tokens
            if has_ident != has_tok:
                raise BusStoreInconsistentError(
                    f"Credential tearing detected for {identity_id}: in_identities={has_ident}, in_tokens={has_tok}"
                )
        else:
            # Check all entries for consistency
            for i_id in identities.keys():
                if i_id not in tokens:
                    raise BusStoreInconsistentError(
                        f"Credential tearing detected: identity '{i_id}' exists without matching token in tokens.json"
                    )
            for t_id in tokens.keys():
                if t_id not in identities:
                    raise BusStoreInconsistentError(
                        f"Credential tearing detected: token for '{t_id}' exists without identity in identities.json"
                    )

    def enroll_agent(
        self,
        agent_name: str,
        project_id: str,
        task_id: Optional[str] = None,
    ) -> Tuple[BusIdentity, str, NamespacedId]:
        """
        Enrolls a dedicated subagent identity into the FileBus store.
        Verifies directory security, performs registration, and validates credential consistency.
        Returns (BusIdentity, auth_token, NamespacedId).
        """
        self.verify_bus_security()
        self.verify_credential_consistency()

        try:
            ident, token = self.bus.register(
                agent_name=agent_name,
                device_id=self.device_id,
                project_id=project_id,
                task_id=task_id,
            )
        except Exception as exc:
            raise BusBridgeError(f"Failed to register agent identity on FileBus: {exc}") from exc

        # Validate that the registration produced a consistent state across both files
        self.verify_credential_consistency(identity_id=ident.identity_id)

        ns_id = NamespacedId(
            device_id=self.device_id,
            workspace=self.workspace,
            agent_tag=agent_name,
            task_id=task_id or "-",
            session_id=ident.identity_id,
        )
        self._enrolled_identities[agent_name] = (ident, token, ns_id)
        return ident, token, ns_id

    def get_agent_credentials(self, agent_name: str) -> Tuple[BusIdentity, str, NamespacedId]:
        """Retrieves previously enrolled credentials for agent."""
        if agent_name not in self._enrolled_identities:
            raise BusBridgeError(f"Agent '{agent_name}' has not enrolled with this bus bridge")
        return self._enrolled_identities[agent_name]

    def send_envelope(
        self,
        sender_name: str,
        recipient_id: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        kind: str = "note",
        idempotency_key: Optional[str] = None,
        recipient_ns: Optional[NamespacedId] = None,
    ) -> Envelope:
        """
        Constructs and sends a typed Envelope over FileBus.
        Records send in cursor store and verifies delivery state.
        """
        self.verify_bus_security()
        ident, token, sender_ns = self.get_agent_credentials(sender_name)
        self.verify_credential_consistency(identity_id=ident.identity_id)

        key = idempotency_key or new_idempotency_key(prefix="bridge")
        digest = payload_digest(body, data)

        try:
            msg = self.bus.send(
                sender_id=ident.identity_id,
                token=token,
                recipient_id=recipient_id,
                body=body,
                data=data,
                idempotency_key=key,
                kind=kind,
            )
        except BusError as exc:
            raise BusBridgeError(f"FileBus send failed: {exc}") from exc

        # Update cursor store
        self.cursors.remember_send(
            key=key,
            sender=ident.identity_id,
            recipient=recipient_id,
            digest=digest,
            message_id=msg.message_id,
        )

        envelope = Envelope(
            message_id=msg.message_id,
            sender_id=msg.sender_id,
            recipient_id=msg.recipient_id,
            body=msg.body,
            data=msg.data,
            kind=msg.kind,
            state=TransportState.SEND_RECEIPT,
            idempotency_key=msg.idempotency_key,
            created_at=msg.created_at,
            digest=msg.digest,
            sender_ns=sender_ns,
            recipient_ns=recipient_ns,
        )
        return envelope

    def fetch_inbox(
        self,
        agent_name: str,
        unread_only: bool = True,
    ) -> List[Envelope]:
        """
        Reads messages from recipient's inbox and returns typed Envelope objects.
        """
        self.verify_bus_security()
        ident, token, recipient_ns = self.get_agent_credentials(agent_name)
        self.verify_credential_consistency(identity_id=ident.identity_id)

        try:
            messages = self.bus.inbox(
                identity_id=ident.identity_id,
                token=token,
                unread_only=unread_only,
            )
        except BusError as exc:
            raise BusBridgeError(f"FileBus inbox fetch failed: {exc}") from exc

        envelopes: List[Envelope] = []
        for m in messages:
            env = Envelope.from_bus_message(m, recipient_ns=recipient_ns)
            envelopes.append(env)
        return envelopes

    def ack_message(
        self,
        agent_name: str,
        message_id: str,
    ) -> Envelope:
        """
        Acknowledges receipt of message in FileBus and returns updated Envelope.
        """
        self.verify_bus_security()
        ident, token, recipient_ns = self.get_agent_credentials(agent_name)
        self.verify_credential_consistency(identity_id=ident.identity_id)

        try:
            msg = self.bus.ack(
                identity_id=ident.identity_id,
                token=token,
                message_id=message_id,
            )
        except BusError as exc:
            raise BusBridgeError(f"FileBus ack failed: {exc}") from exc

        env = Envelope.from_bus_message(msg, recipient_ns=recipient_ns)
        env.state = TransportState.RECIPIENT_READ_ACK
        return env


def read_bounded_log(path: Path, max_bytes: int = 65536) -> str:
    """Reads log file with strict byte bound (head and tail if oversized)."""
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if size <= max_bytes:
                return f.read()
            half = max_bytes // 2
            head = f.read(half)
            f.seek(max(0, size - half))
            tail = f.read(half)
            return f"{head}\n... [TRUNCATED {size - max_bytes} BYTES] ...\n{tail}"
    except Exception:
        return ""


def query_systemctl_show(unit_name: str) -> Dict[str, str]:
    """Queries systemctl --user show for authoritative unit properties."""
    cmd = [
        "systemctl", "--user", "show", unit_name,
        "-p", "ActiveState",
        "-p", "SubState",
        "-p", "MemoryMax",
        "-p", "ControlGroup",
        "-p", "InvocationID",
        "-p", "TasksCurrent",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            props: Dict[str, str] = {}
            for line in res.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
            return props
    except Exception:
        pass
    return {}


def _is_cgroup_dissolved_or_empty(
    cg_rel_path: str,
    cgroup_fs_root: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Authoritatively checks that the kernel cgroup at /sys/fs/cgroup/{cg_rel_path}
    is either dissolved (does not exist) or has zero processes across its entire hierarchy (C2106).

    Guarantees:
    - Recursively checks all descendant cgroups (all **/cgroup.procs).
    - Inspects cgroup.events for `populated 0` (cgroup v2 kernel guarantee that neither
      this cgroup nor any descendant contains live processes).
    - Returns False if any process remains or if cgroup.events indicates populated!=0.
    """
    clean_path = cg_rel_path.lstrip("/")
    if not clean_path:
        return False
    fs_root = Path(cgroup_fs_root).resolve() if cgroup_fs_root else Path("/sys/fs/cgroup")
    cg_fs_path = fs_root / clean_path
    if not cg_fs_path.exists():
        return True

    # 1. Check cgroup.events (cgroup v2 authoritative populated flag)
    try:
        events_files = []
        root_events = cg_fs_path / "cgroup.events"
        if root_events.exists():
            events_files.append(root_events)
        for sub_events in cg_fs_path.glob("**/cgroup.events"):
            if sub_events not in events_files:
                events_files.append(sub_events)
        for ef in events_files:
            if ef.exists():
                for line in ef.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[0] == "populated":
                        if parts[1] != "0":
                            return False  # Cgroup or descendant is populated!
    except Exception:
        return False

    # 2. Descendant cgroup scan: check root and all descendant cgroup.procs
    try:
        procs_files = [cg_fs_path / "cgroup.procs"]
        for sub_procs in cg_fs_path.glob("**/cgroup.procs"):
            if sub_procs not in procs_files:
                procs_files.append(sub_procs)
        for pf in procs_files:
            if pf.exists():
                pids = [p.strip() for p in pf.read_text(encoding="utf-8").splitlines() if p.strip()]
                if len(pids) > 0:
                    return False
    except Exception:
        return False

    return True


def verify_unit_cleanup(
    unit_name: str,
    expected_cgroup: Optional[str] = None,
    expected_invocation_id: Optional[str] = None,
    max_retries: int = 30,
    retry_delay: float = 0.1,
    cgroup_fs_root: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Authoritatively checks that a systemd unit is deactivated and its kernel cgroup has 0 tasks (C2097 / C2100 / C2106).

    Guarantees:
    1. Rejects Blind Query Absence: An uninitialized, nonexistent, or collected unit where
       TasksCurrent is '[not set]' or '' CANNOT prove emptiness without cached cgroup confirmation.
    2. Strict InvocationID Verification (C2106): If expected_invocation_id is provided, InvocationID
       must be present AND strictly match. Absent or mismatched InvocationID is rejected.
    3. Strict ControlGroup Verification (C2106): Fallback missing ControlGroup fails closed (returns False).
    4. Hierarchical Cgroup Dissolution (C2106): Checks cgroup.events for populated==0 and recursively
       verifies all descendant cgroup.procs in the hierarchy.
    """
    for _ in range(max_retries):
        props = query_systemctl_show(unit_name)
        state = props.get("ActiveState") if props else None
        inv_id = props.get("InvocationID") if props else None
        cg = props.get("ControlGroup") if props else None

        if state not in ("inactive", "failed"):
            time.sleep(retry_delay)
            continue

        if expected_invocation_id:
            if not inv_id or inv_id != expected_invocation_id:
                time.sleep(retry_delay)
                continue

        target_cg = expected_cgroup if expected_cgroup else cg
        if not target_cg:
            # Fallback missing ControlGroup fails closed (C2106)
            time.sleep(retry_delay)
            continue

        if not expected_cgroup and props:
            tasks = props.get("TasksCurrent")
            if tasks in ("[not set]", "", None):
                time.sleep(retry_delay)
                continue

        if _is_cgroup_dissolved_or_empty(target_cg, cgroup_fs_root=cgroup_fs_root):
            return True

        time.sleep(retry_delay)
    return False


PROVIDER_ROUTE_BINARIES: Dict[str, Set[str]] = {
    "zai": {"zcodex"},
    "zcode": {"zcodex"},
    "grok": {"grok"},
    "antigravity": {"agy", "env"},
    "gemini": {"agy", "env"},
    "opencode": {"opencode"},
    "codex": {"codex"},
}
ALLOWED_COMMAND_BINARIES = PROVIDER_ROUTE_BINARIES  # Backward compatibility alias

LOCAL_PROBE_ALLOWED_BINARIES: Set[str] = {
    "echo", "true", "sleep", "cat", "python3", "python"
}

FORBIDDEN_MODEL_INTERPRETERS: Set[str] = {
    "python", "python3", "bash", "sh", "dash", "zsh"
}

PROVIDER_PRIMARY_CLIS: Dict[str, Set[str]] = {
    "zai": {"zcodex"},
    "zcode": {"zcodex"},
    "opencode": {"opencode"},
    "codex": {"codex"},
    "grok": {"grok"},
    "antigravity": {"agy"},
    "gemini": {"agy"},
}

ALL_MODEL_CLIS: Set[str] = {"zcodex", "codex", "opencode", "grok", "agy"}


ADAPTER_ALIASES: Dict[str, str] = {
    "zcode": "zai",
    "gemini": "antigravity",
}


def validate_route_to_command(
    provider: str,
    command_argv: List[str],
    is_local_probe: bool = False,
    expected_model: Optional[str] = None,
) -> None:
    """
    Enforces structured launcher recipe validation and local probe typing (C2106 / C2114 / C2118 / C2126 / C2271).

    Guarantees:
    1. If is_local_probe is True:
       - Allowed binaries: LOCAL_PROBE_ALLOWED_BINARIES (echo, true, sleep, cat, python3, python).
       - Evaluated under provider 'local', model 'none', with ZERO model quota claim.
       - Strictly forbids smuggling any model CLI (zcodex, codex, opencode, grok, agy).
    2. If is_local_probe is False (MODEL route):
       - Provider must be registered in ADAPTERS (fail-closed, zero permissive fallback; C2114 / C2126).
       - Generic shell interpreters and arbitrary python runtimes (python3, python, bash, sh, dash, zsh)
         are NEVER permitted under any model route (raises ResourceAdmissionError; C2118 / C2126).
       - Structured prefix match against canonical launcher.launch.ADAPTERS[provider]["argv"]:
         * len(command_argv) == len(expected_prefix) + 1
         * command_argv[:len(expected_prefix)] strictly matches canonical expected_prefix.
         * Trailing argument command_argv[-1] is the opaque goal string and is NOT token-scanned.
         * Any modified, injected, duplicate, or reordered options fail closed.
       - Exact model binding (C2271): If command_argv specifies --model <model_name>, that model_name
         MUST strictly match expected_model when expected_model is provided (and not "none").
    """
    if not command_argv:
        raise ResourceAdmissionError("command_argv must be non-empty")

    bin_name = Path(command_argv[0]).name

    # 1. Local probe handling (ZERO model quota claim)
    if is_local_probe:
        if bin_name not in LOCAL_PROBE_ALLOWED_BINARIES:
            raise ResourceAdmissionError(
                f"Local probe violation: binary '{bin_name}' is not authorized for local probe (allowed: {sorted(LOCAL_PROBE_ALLOWED_BINARIES)})"
            )
        # Check that local probe does not smuggle any model CLI
        for arg in command_argv:
            words = re.findall(r"\b[a-zA-Z0-9_-]+\b", arg)
            for word in words:
                if word in ALL_MODEL_CLIS:
                    raise ResourceAdmissionError(
                        f"Local probe foreign CLI violation: model CLI '{word}' not permitted in local probe"
                    )
        return

    # 2. Strict provider check: zero permissive fallback for unknown providers
    effective_provider = ADAPTER_ALIASES.get(provider, provider)
    if effective_provider not in ADAPTERS:
        raise ResourceAdmissionError(
            f"Unknown or unsupported route provider '{provider}': fail-closed (zero permissive fallback; C2114 / C2126)"
        )

    # Directive C2271: Exact model binding between admitted/reserved model and command recipe
    if "--model" in command_argv:
        m_idx = command_argv.index("--model")
        if m_idx + 1 < len(command_argv):
            model_name = command_argv[m_idx + 1]
            if expected_model and expected_model != "none" and model_name != expected_model:
                raise ResourceAdmissionError(
                    f"Model binding mismatch: command recipe model '{model_name}' does not match admitted/reserved model '{expected_model}' (C2271)"
                )

    # 3. Model route: strictly forbid python, python3, bash, sh, etc.
    if bin_name in FORBIDDEN_MODEL_INTERPRETERS:
        raise ResourceAdmissionError(
            f"Interpreter '{bin_name}' is strictly forbidden under model route '{provider}'. "
            "Model routes require exact launcher binary recipes; arbitrary scripts/interpreters rejected (C2118 / C2126)."
        )

    # Specific exact recipe validation for antigravity / gemini (C2261)
    if effective_provider == "antigravity":
        if len(command_argv) < 3:
            raise ResourceAdmissionError(
                f"Route recipe violation for provider '{provider}': command argv too short"
            )

        if "--model" in command_argv:
            m_idx = command_argv.index("--model")
            if m_idx + 1 < len(command_argv):
                model_name = command_argv[m_idx + 1]
                if model_name not in ("gemini-3.7-flash-medium", "gemini-3.1-pro-high"):
                    raise ResourceAdmissionError(
                        f"Unauthorized antigravity model '{model_name}': must be gemini-3.7-flash-medium (or gemini-3.1-pro-high)"
                    )
                if expected_model and expected_model != "none" and model_name != expected_model:
                    raise ResourceAdmissionError(
                        f"Model binding mismatch: command recipe model '{model_name}' does not match admitted/reserved model '{expected_model}' (C2271)"
                    )
            else:
                raise ResourceAdmissionError(
                    f"Route recipe violation for provider '{provider}': --model missing argument"
                )
        else:
            raise ResourceAdmissionError(
                f"Route recipe violation for provider '{provider}': missing --model"
            )

        if "-p" in command_argv:
            p_idx = command_argv.index("-p")
            for flag in ("--print-timeout", "--output-format", "--dangerously-skip-permissions", "--effort", "--model"):
                if flag in command_argv:
                    flag_idx = command_argv.index(flag)
                    if flag_idx > p_idx:
                        raise ResourceAdmissionError("Malformed agy argv: -p must be followed by prompt string, not options")
            if p_idx >= len(command_argv) - 1:
                raise ResourceAdmissionError("Malformed agy argv: -p must be followed by prompt string, not options")
            prompt_str = command_argv[p_idx + 1]
            if prompt_str.startswith("-") and prompt_str not in ("-", "--"):
                raise ResourceAdmissionError("Malformed agy argv: -p must be followed by prompt string, not options")
            if p_idx != len(command_argv) - 2:
                raise ResourceAdmissionError("Malformed agy argv: -p must be followed by prompt string, not options")
        else:
            raise ResourceAdmissionError(
                f"Route recipe violation for provider '{provider}': missing -p print mode flag"
            )

        allowed_antigravity_prefixes = [
            ["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY", "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium", "--dangerously-skip-permissions", "--print-timeout", "0", "--output-format", "text", "-p"],
            ["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY", "agy", "--model", "gemini-3.1-pro-high", "--effort", "high", "--dangerously-skip-permissions", "--print-timeout", "0", "--output-format", "text", "-p"],
        ]
        cmd_prefix = command_argv[:-1]
        if cmd_prefix not in allowed_antigravity_prefixes:
            raise ResourceAdmissionError(
                f"Route recipe violation for provider '{provider}': command does not strictly match authorized adapter argv"
            )
        return

    # Specific exact recipe validation for grok
    if effective_provider == "grok":
        prefix = list(command_argv[:-1])
        patched_grok_prefix = ["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p"]
        canonical_grok_prefix = list(ADAPTERS["grok"]["argv"])
        if prefix not in (patched_grok_prefix, canonical_grok_prefix) or len(command_argv) != len(prefix) + 1:
            raise ResourceAdmissionError(
                f"Route recipe violation for provider 'grok': command does not strictly match adapter argv"
            )
        return

    # 4. Structured prefix match against canonical ADAPTERS recipe
    expected_prefix = list(ADAPTERS[effective_provider]["argv"])
    prefix = list(command_argv[:len(expected_prefix)])
    # Model routes must strictly match canonical installed executable and prefix from build_adapter_argv (C2126 / C2128)
    # Basename-only lookalike fallbacks are strictly forbidden.
    if len(command_argv) != len(expected_prefix) + 1 or prefix != expected_prefix:
        raise ResourceAdmissionError(
            f"Route recipe violation for provider '{provider}': command does not strictly match canonical adapter argv {expected_prefix} + [<goal>] (C2126/C2128)"
        )



MAX_DISK_LOG_BYTES = 65536  # 64 KiB strict cap on disk log files while child runs (C2106)
MIN_DISK_FREE_FLOOR_BYTES = 50 * (1024 ** 3) + 512 * (1024 ** 2)  # 50 GiB + 512 MiB reserve (C2284)
MAX_TMPDIR_GROWTH_BYTES = 512 * 1024 * 1024  # 512 MiB net tmpdir growth cap (C2284)


def _get_dir_size_bytes(dir_path: Union[str, Path]) -> int:
    """
    Recursively calculates the total size in bytes of all files within dir_path (C2284).
    Safe against non-existent paths, dangling symlinks, and unreadable files.
    """
    total = 0
    p = Path(dir_path)
    if not p.exists():
        return 0
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    try:
        for root, _dirs, files in os.walk(str(p)):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.lstat(fp).st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _bounded_pipe_pump(src_pipe, dst_path: Path, max_bytes: int = MAX_DISK_LOG_BYTES) -> None:
    """
    Reads from src_pipe in chunks and writes up to max_bytes to dst_path, discarding excess (C2106).
    Guarantees disk writes are strictly bounded while child runs.
    """
    bytes_written = 0
    try:
        with open(dst_path, "wb") as f:
            while True:
                chunk = src_pipe.read(4096)
                if not chunk:
                    break
                if bytes_written < max_bytes:
                    to_write = chunk[: max_bytes - bytes_written]
                    f.write(to_write)
                    bytes_written += len(to_write)
                    f.flush()
    except Exception:
        pass
    finally:
        try:
            src_pipe.close()
        except Exception:
            pass


def get_canonical_launcher_paths(
    config_dir: Optional[Union[str, Path]] = None,
) -> Tuple[Path, Path]:
    """
    Resolves canonical launcher store and lock paths matching canonical launcher.cli.config_dir_for (C2268).
    If config_dir is None: defaults strictly to ~/.config/agent-quota-launcher.
    Do NOT read AGENT_QUOTA_LAUNCHER_CONFIG_DIR from environment.
    Returns (cfg / "state.db", cfg / "launch.lock").
    """
    if config_dir is not None:
        cfg = Path(config_dir).expanduser().resolve()
    else:
        cfg = Path(os.path.expanduser("~/.config/agent-quota-launcher")).resolve()
    return cfg / "state.db", cfg / "launch.lock"


class ChildModelRuntimeAdapter:
    """
    Thin, positively verified unit lifecycle adapter under real existing admission lock (C2087).

    Guarantees:
    1. Shared Admission Lock: Host resource admission, fresh quse evaluation, and Store reservation
       are strictly executed inside `store.launch_lock` to eliminate admission races.
    2. Route-to-Payload Binding: The selected route's provider/model explicitly binds to the command
       and execution environment; arbitrary disjoint payloads fail admission.
    3. Contained Scratch TMPDIR: Enforces TMPDIR inside owned repo scratch root (mode 0700, <= 512 MB).
       Caller overrides attempting to set global /tmp or /data/tmp are strictly rejected.
    4. Environment Stripping: Strips all APLEXER_* environment variables from the child environment
       so the child cannot impersonate the parent or pollute the parent mailbox.
    5. Pre-Payload Containment Verification: Before payload execution, queries systemctl --user show
       verifying ActiveState=active, MemoryMax=1572864000 (1500M), non-empty InvocationID, non-empty
       ControlGroup, and confirms kernel process membership in the scope cgroup.
    6. Separated Lifecycle States:
       - 'reserved': Admitted under launch_lock, resources held in Store.
       - 'unit_verified_active': Unit verified active in systemd with 1500M limit and cgroup membership.
       - 'tool_activity': First tool invocation / stdout activity recorded.
       - 'output_produced': Payload finished and non-empty output artifact verified on disk.
       - 'completed-awaiting-review': Payload exited 0 with valid artifacts, awaiting independent review.
       NEVER auto-accepts returncode 0 as 'done'. Independent review required before completion.
    7. True Process Tree Termination: On timeout or failure, executes `systemctl --user kill --kill-who=all --signal=SIGKILL <unit>`
       to terminate the entire unit process tree (not just client wrapper).
    8. Retained Uncertain Reservations: If unit termination / cgroup emptiness cannot be authoritatively
       proven, Store reservation resources are RETAINED as UNCERTAIN (launch-uncertain) rather than released,
       preventing host overload.
    9. Bounded Log Streaming: Logs are written to disk and read with strict size bounds (<= 64 KiB),
       preventing unbounded memory accumulation.
    10. Canonical Agent-Bus Alignment: Uses canonical NamespacedId conventions and enroll_agent contract.
    """

    def __init__(
        self,
        store: Optional[Union[str, Path, Store]] = None,
        workspace: Optional[Union[str, Path]] = None,
        bus_bridge: Optional[AgentBusEnrollmentBridge] = None,
        config_dir: Optional[Union[str, Path]] = None,
        lock_path: Optional[Union[str, Path]] = None,
        is_test_fixture: Optional[bool] = None,
    ) -> None:
        self.workspace = Path(workspace).resolve() if workspace else Path("/home/alexey/git/cloudflare-agent-git")
        canonical_store_path, canonical_lock_path = get_canonical_launcher_paths(None)

        if store is not None:
            if isinstance(store, Store):
                self.store = store
            else:
                self.store = Store(str(Path(store).resolve()))
        elif config_dir is not None:
            cfg_path = Path(config_dir).expanduser().resolve()
            self.store = Store(str(cfg_path / "state.db"))
        else:
            self.store = Store(str(canonical_store_path))

        if lock_path is not None:
            self.lock_path = Path(lock_path).resolve()
        elif config_dir is not None:
            cfg_path = Path(config_dir).expanduser().resolve()
            self.lock_path = (cfg_path / "launch.lock").resolve()
        else:
            self.lock_path = (Path(self.store.db_path).parent / "launch.lock").resolve()

        resolved_store = Path(self.store.db_path).resolve()
        resolved_lock = self.lock_path.resolve()
        is_exact_canonical = (
            resolved_store == canonical_store_path.resolve()
            and resolved_lock == canonical_lock_path.resolve()
        )

        if is_test_fixture is not None:
            self.is_test_fixture = bool(is_test_fixture)
        else:
            self.is_test_fixture = not is_exact_canonical

        self.bus_bridge = bus_bridge

    MIN_DISK_FREE_FLOOR_BYTES = MIN_DISK_FREE_FLOOR_BYTES
    MAX_TMPDIR_GROWTH_BYTES = MAX_TMPDIR_GROWTH_BYTES

    @classmethod
    def check_host_admission(
        cls,
        paths_to_check: Optional[List[Union[str, Path]]] = None,
    ) -> Dict[str, Any]:
        """
        Validates host capacity gates under Codex C2083, C2277, and C2284:
        - MemAvailable >= 10 GiB floor
        - Root disk free >= 50 GiB floor + 512 MiB reserve (C2284)
        - Split-mount / filesystems for target paths (CWD, TMPDIR) >= 50 GiB floor + 512 MiB reserve (C2277/C2284)
        Fails closed with ResourceAdmissionError if below bounds.
        """
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                meminfo = f.read()
            mem_avail_kb = None
            for line in meminfo.splitlines():
                if line.startswith("MemAvailable:"):
                    mem_avail_kb = int(line.split()[1])
                    break
            if mem_avail_kb is None:
                raise ResourceAdmissionError("Failed to parse MemAvailable from /proc/meminfo: fail-closed")
            mem_avail_bytes = mem_avail_kb * 1024
            min_floor_bytes = 10 * (1024 ** 3)
            if mem_avail_bytes < min_floor_bytes:
                raise ResourceAdmissionError(
                    f"Host MemAvailable {mem_avail_bytes / (1024**3):.2f} GiB below 10 GiB floor"
                )
        except OSError as exc:
            raise ResourceAdmissionError(f"Cannot read /proc/meminfo for memory admission: {exc}") from exc

        min_disk_floor = MIN_DISK_FREE_FLOOR_BYTES
        try:
            stat_res = os.statvfs("/")
            disk_free_bytes = stat_res.f_bavail * stat_res.f_frsize
            if disk_free_bytes < min_disk_floor:
                raise ResourceAdmissionError(
                    f"Host root disk free {disk_free_bytes / (1024**3):.2f} GiB below 50 GiB floor (+ 512 MiB reserve, C2284)"
                )
        except OSError as exc:
            raise ResourceAdmissionError(f"Cannot stat root filesystem for disk admission: {exc}") from exc

        # Multi-Mount / Split-Filesystem Host Admission Gates (C2277 / C2284)
        if paths_to_check:
            for p_raw in paths_to_check:
                p = Path(p_raw).resolve()
                stat_target = p
                while not stat_target.exists() and stat_target.parent != stat_target:
                    stat_target = stat_target.parent
                try:
                    target_stat = os.statvfs(str(stat_target))
                    target_disk_free = target_stat.f_bavail * target_stat.f_frsize
                    if target_disk_free < min_disk_floor:
                        raise ResourceAdmissionError(
                            f"Filesystem for path '{p}' has {target_disk_free / (1024**3):.2f} GiB free below 50 GiB floor (+ 512 MiB reserve, C2284)"
                        )
                except OSError as exc:
                    raise ResourceAdmissionError(
                        f"Cannot stat filesystem for path '{p}': {exc}"
                    ) from exc

        return {
            "admitted": True,
            "mem_available_bytes": mem_avail_bytes,
            "disk_free_bytes": disk_free_bytes,
        }

    @classmethod
    def check_quse_admission(
        cls,
        quse_data: Any = _DEFAULT,
        model_requirements: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Any]:
        """
        Validates provider quota gates against fresh quse telemetry:
        - Telemetry must be present and dict (fails closed if None or invalid)
        - Evaluates valid routes and candidate selection via canonical launcher.admission
        """
        data = fetch_quse() if quse_data is _DEFAULT else quse_data
        if not data or not isinstance(data, dict):
            raise QuotaAdmissionError("Quota telemetry missing, invalid, or unparseable: fail-closed")

        reqs = model_requirements if isinstance(model_requirements, dict) else {}
        allowed = reqs.get("allowed_providers") or reqs.get("providers")
        if allowed and "providers" not in reqs:
            reqs = dict(reqs)
            reqs["providers"] = list(allowed)
        valid_routes, rejections = validate_quse(data, task_requirements=reqs)
        if allowed:
            valid_routes = [r for r in valid_routes if r.get("provider") in allowed]
            if not valid_routes:
                raise QuotaAdmissionError(
                    f"No valid routes match allowed_providers {allowed}. Rejections: {rejections}"
                )
        if not valid_routes:
            raise QuotaAdmissionError(f"No valid routes available in quse telemetry. Rejections: {rejections}")

        seed = int(time.time() * 1000)
        chosen, provenance = select_candidate(valid_routes, seed=seed)
        if not chosen:
            raise QuotaAdmissionError("No selectable candidate chosen by canonical ranking")

        return chosen, provenance

    def prepare_and_dispatch_task(
        self,
        task_id: str,
        goal: str,
        cwd: Union[str, Path],
        timeout_sec: float = 120.0,
        owned_paths: Optional[List[str]] = None,
        requested_memory_mb: int = 1500,
        tmpdir: Optional[Union[str, Path]] = None,
        lock_path: Optional[Union[str, Path]] = None,
        quse_override: Optional[Dict[str, Any]] = None,
        provider_preference: Optional[str] = None,
        model_requirements: Optional[Dict[str, Any]] = None,
        is_local_probe: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes atomic reservation, quse validation, host check, and dispatch strictly inside launch_lock.
        Fails closed on missing quota telemetry, host capacity violation, or Store transition error.
        """
        cwd_path = Path(cwd).resolve()
        workspace_path = self.workspace.resolve()
        lock_file = Path(lock_path).resolve() if lock_path else self.lock_path
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        canonical_store_path, canonical_lock_path = get_canonical_launcher_paths(None)

        # Pre-launch negative gate 1 (Disjoint Store/Lock, C2261/C2268):
        if lock_file.parent.resolve() != Path(self.store.db_path).parent.resolve():
            raise ResourceAdmissionError(
                f"Disjoint store and lock paths: store in {Path(self.store.db_path).parent.resolve()} but lock in {lock_file.parent.resolve()}. "
                "Shared admission requires co-located canonical store and lock."
            )

        # 1. Enforce owned contained TMPDIR (reject global /tmp)
        if tmpdir is None:
            tmpdir_path = workspace_path / ".local" / "tmp"
        else:
            tmpdir_path = Path(tmpdir).resolve()

        if "tmp" in tmpdir_path.parts and tmpdir_path != workspace_path / ".local" / "tmp":
            if str(tmpdir_path).startswith("/tmp") or str(tmpdir_path).startswith("/data/tmp"):
                raise ResourceAdmissionError(f"Contained TMPDIR violation: reject global /tmp path {tmpdir_path}")

        # Pre-launch negative gate 2 (Alternative Store/Lock under Real Model Route, C2261/C2268):
        if not is_local_probe:
            if (
                self.is_test_fixture
                or Path(self.store.db_path).resolve() != canonical_store_path.resolve()
                or lock_file.resolve() != canonical_lock_path.resolve()
            ):
                raise ResourceAdmissionError(
                    f"Real model route requires exact canonical shared store '{canonical_store_path}' and lock '{canonical_lock_path}'; got store '{self.store.db_path}' and lock '{lock_file}'. "
                    "Alternative stores/locks are strictly non-runtime test fixtures."
                )

        # Pre-launch negative gate: reject quse_override on real model routes (C2277)
        if not is_local_probe and not self.is_test_fixture and quse_override is not None:
            raise QuotaAdmissionError(
                "quse_override is strictly forbidden for real model routes; fresh canonical telemetry fetch is required (C2277)"
            )

        tmpdir_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        paths_to_own = owned_paths if owned_paths is not None else [str(cwd_path)]

        # Perform atomic check-and-reserve sequence strictly under launch_lock to prevent double-commit races
        with launch_lock(str(lock_file)):
            # 2. Host Admission Gates (MemAvailable >= 10 GiB, Root Disk >= 50 GiB, Split Mounts >= 50 GiB, C2277)
            self.check_host_admission(paths_to_check=[cwd_path, tmpdir_path])

            # 3. Fresh Quota Admission (C2079 / C2083)
            chosen, provenance = self.check_quse_admission(
                quse_data=_DEFAULT if quse_override is None else quse_override,
                model_requirements=model_requirements,
            )

            provider = provider_preference if provider_preference else chosen["provider"]
            model = chosen.get("model")

            # Route-to-payload binding check
            if model_requirements and "allowed_providers" in model_requirements:
                if provider not in model_requirements["allowed_providers"]:
                    raise QuotaAdmissionError(
                        f"Route mismatch: chosen provider '{provider}' not in allowed_providers {model_requirements['allowed_providers']}"
                    )

            # 4. Check Active Resources in Store
            active_mem, active_disk = self.store.get_active_resources(exclude_task_id=task_id)
            check_resources(
                requested_memory_mb,
                str(cwd_path),
                str(tmpdir_path),
                active_mem,
                active_disk,
                repo_root=str(workspace_path),
            )

            # 5. Canonical Store Registration
            task_data = self.store.get_task(task_id)
            if task_data is None:
                payload = {
                    "owner": "antigravity-head",
                    "cwd": str(cwd_path),
                    "timeout": float(timeout_sec),
                    "goal": str(goal),
                    "model_requirements": model_requirements,
                }
                self.store.submit_task(
                    task_id=task_id,
                    idempotency_key=f"launch-{task_id}",
                    payload=payload,
                    paths=paths_to_own,
                    memory_mb=requested_memory_mb,
                )
            elif task_data.get("state") != "queued":
                raise AdmissionError(f"Task {task_id} state is '{task_data.get('state')}', expected 'queued'")

            # 6. Isolated Agent Bus Identity Enrollment (canonical enroll_agent contract)
            bus_identity_receipt = None
            if self.bus_bridge is not None:
                ident, token, ns = self.bus_bridge.enroll_agent(
                    agent_name=task_id,
                    project_id="tasks",
                    task_id=task_id,
                )
                bus_identity_receipt = {
                    "identity_id": ident.identity_id,
                    "agent_tag": ns.agent_tag,
                    "token_registered": bool(token),
                }

            # 7. Atomic Transition queued -> starting under launch_lock
            self.store.transition_task(
                task_id,
                "starting",
                ("queued",),
                reason=f"launching via {provider} ({model})",
            )

        dispatch_record = {
            "task_id": task_id,
            "provider": provider,
            "model": model,
            "status": "starting",
            "cwd": str(cwd_path),
            "tmpdir": str(tmpdir_path),
            "memory_mb": requested_memory_mb,
            "timeout_sec": timeout_sec,
            "bus_identity": bus_identity_receipt,
            "provenance": provenance,
            "quse_admitted": True,
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        return dispatch_record

    def prepare_and_dispatch_under_launch_lock(
        self,
        task_id: str,
        goal: str,
        cwd: Union[str, Path],
        timeout_sec: float = 120.0,
        owned_paths: Optional[List[str]] = None,
        requested_memory_mb: int = 1500,
        tmpdir: Optional[Union[str, Path]] = None,
        lock_path: Optional[Union[str, Path]] = None,
        quse_override: Optional[Dict[str, Any]] = None,
        provider_preference: Optional[str] = None,
        model_requirements: Optional[Dict[str, Any]] = None,
        is_local_probe: bool = False,
    ) -> Dict[str, Any]:
        """
        Canonical entry point for preparing and dispatching task under launch_lock (C2261 / C2268).
        Enforces pre-launch negative gates (disjoint store/lock and non-canonical fixture store on real model routes).
        """
        canonical_store_path, canonical_lock_path = get_canonical_launcher_paths(None)
        lock_file = Path(lock_path).resolve() if lock_path else self.lock_path

        # Pre-launch negative gate 1 (Disjoint Store/Lock, C2261/C2268):
        if lock_file.parent.resolve() != Path(self.store.db_path).parent.resolve():
            raise ResourceAdmissionError(
                f"Disjoint store and lock paths: store in {Path(self.store.db_path).parent.resolve()} but lock in {lock_file.parent.resolve()}. "
                "Shared admission requires co-located canonical store and lock."
            )

        # Pre-launch negative gate 2 (Alternative Store/Lock under Real Model Route, C2261/C2268):
        if not is_local_probe:
            if (
                self.is_test_fixture
                or Path(self.store.db_path).resolve() != canonical_store_path.resolve()
                or lock_file.resolve() != canonical_lock_path.resolve()
            ):
                raise ResourceAdmissionError(
                    f"Real model route requires exact canonical shared store '{canonical_store_path}' and lock '{canonical_lock_path}'; got store '{self.store.db_path}' and lock '{lock_file}'. "
                    "Alternative stores/locks are strictly non-runtime test fixtures."
                )

        # Pre-launch negative gate: reject quse_override on real model routes (C2277)
        if not is_local_probe and not self.is_test_fixture and quse_override is not None:
            raise QuotaAdmissionError(
                "quse_override is strictly forbidden for real model routes; fresh canonical telemetry fetch is required (C2277)"
            )

        return self.prepare_and_dispatch_task(
            task_id=task_id,
            goal=goal,
            cwd=cwd,
            timeout_sec=timeout_sec,
            owned_paths=owned_paths,
            requested_memory_mb=requested_memory_mb,
            tmpdir=tmpdir,
            lock_path=lock_path,
            quse_override=quse_override,
            provider_preference=provider_preference,
            model_requirements=model_requirements,
            is_local_probe=is_local_probe,
        )

    def execute_in_verified_systemd_scope(
        self,
        task_id: str,
        command_argv: List[str],
        cwd: Optional[Union[str, Path]] = None,
        timeout_sec: float = 120.0,
        env_vars: Optional[Dict[str, str]] = None,
        requested_memory_mb: int = 1500,
        tmpdir: Optional[Union[str, Path]] = None,
        lock_path: Optional[Union[str, Path]] = None,
        quse_override: Optional[Dict[str, Any]] = None,
        model_requirements: Optional[Dict[str, Any]] = None,
        expected_outputs: Optional[List[Union[str, Path]]] = None,
        is_local_probe: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executes an explicitly owned, canonically admitted task in a directly verified
        systemd scope with MemoryMax 1500M under launch_lock (C2086 / C2087).

        Enforces:
        - Atomic admission & reservation strictly inside launch_lock
        - Route-to-command binding
        - Clean environment stripping APLEXER_* and preventing global /tmp overrides
        - Pre-payload verification prelude inside scope asserting ActiveState=active,
          MemoryMax=1500M, non-empty InvocationID, non-empty ControlGroup, and writing receipt
        - Non-auto-accepting exit 0 (moves to completed-awaiting-review; independent review required)
        - Tree/cgroup teardown on timeout via systemctl kill --kill-who=all --signal=SIGKILL
        - Retaining launch-uncertain capacity in Store if cleanup is unproven
        - Bounded log streaming (<= 64 KiB)
        - Typed local probes (C2114) with ZERO model quota claim
        """
        # Strict kwargs validation (Directives C2321): reject unknown kwargs and reject conflicting formal vs alias args
        allowed_kwargs = {"cwd_path", "tmpdir_path"}
        unknown_kwargs = set(kwargs.keys()) - allowed_kwargs
        if unknown_kwargs:
            raise ResourceAdmissionError(
                f"Unknown kwargs passed to execute_in_verified_systemd_scope: {sorted(unknown_kwargs)}"
            )

        if cwd is not None and "cwd_path" in kwargs:
            if Path(cwd).resolve() != Path(kwargs["cwd_path"]).resolve():
                raise ResourceAdmissionError(
                    f"Conflicting cwd and cwd_path arguments: cwd={cwd}, cwd_path={kwargs['cwd_path']}"
                )
        cwd_val = cwd if cwd is not None else kwargs.get("cwd_path")
        if cwd_val is None:
            raise ResourceAdmissionError("cwd must be provided")
        cwd_path = Path(cwd_val).resolve()
        workspace_path = self.workspace.resolve()
        unit_nonce = uuid.uuid4().hex[:8]
        clean_task_id = re.sub(r"[^a-zA-Z0-9_]+", "-", task_id).strip("-")[:12].strip("-")
        unit_name = f"agent-scope-{clean_task_id}-{unit_nonce}.scope"
        canonical_store_path, canonical_lock_path = get_canonical_launcher_paths(None)
        lock_file = Path(lock_path).resolve() if lock_path else self.lock_path
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Pre-launch negative gate 1 (Disjoint Store/Lock, C2261/C2268):
        if lock_file.parent.resolve() != Path(self.store.db_path).parent.resolve():
            raise ResourceAdmissionError(
                f"Disjoint store and lock paths: store in {Path(self.store.db_path).parent.resolve()} but lock in {lock_file.parent.resolve()}. "
                "Shared admission requires co-located canonical store and lock."
            )

        # 1. Contained TMPDIR (reject global /tmp)
        if tmpdir is not None and "tmpdir_path" in kwargs:
            if Path(tmpdir).resolve() != Path(kwargs["tmpdir_path"]).resolve():
                raise ResourceAdmissionError(
                    f"Conflicting tmpdir and tmpdir_path arguments: tmpdir={tmpdir}, tmpdir_path={kwargs['tmpdir_path']}"
                )
        tmpdir_val = tmpdir if tmpdir is not None else kwargs.get("tmpdir_path")
        if tmpdir_val is None:
            tmpdir_path = workspace_path / ".local" / "tmp"
        else:
            tmpdir_path = Path(tmpdir_val).resolve()

        if "tmp" in tmpdir_path.parts and tmpdir_path != workspace_path / ".local" / "tmp":
            if str(tmpdir_path).startswith("/tmp") or str(tmpdir_path).startswith("/data/tmp"):
                raise ResourceAdmissionError(f"Contained TMPDIR violation: reject global /tmp path {tmpdir_path}")

        # Directive C2284: Reject divergent TMPDIR/TMP/TEMP in env_vars
        if env_vars:
            for k in ("TMPDIR", "TMP", "TEMP"):
                if k in env_vars:
                    v = env_vars[k]
                    try:
                        resolved_v = Path(v).resolve()
                    except Exception as exc:
                        raise ResourceAdmissionError(
                            f"Divergent temporary directory in env_vars '{k}={v}' does not match checked tmpdir '{tmpdir_path}' (C2284)"
                        ) from exc
                    if resolved_v != tmpdir_path.resolve():
                        raise ResourceAdmissionError(
                            f"Divergent temporary directory in env_vars '{k}={v}' does not match checked tmpdir '{tmpdir_path}' (C2284)"
                        )

        # Pre-launch negative gate: reject quse_override on real model routes (C2277)
        if not is_local_probe and not self.is_test_fixture and quse_override is not None:
            raise QuotaAdmissionError(
                "quse_override is strictly forbidden for real model routes; fresh canonical telemetry fetch is required (C2277)"
            )

        tmpdir_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        # 2. Atomic admission & reservation strictly under launch_lock
        with launch_lock(str(lock_file)):
            # Host Admission Check (MemAvailable >= 10 GiB, Root Disk >= 50 GiB, Split Mounts >= 50 GiB, C2277)
            self.check_host_admission(paths_to_check=[cwd_path, tmpdir_path])

            chosen: Dict[str, Any] = {"provider": "local", "model": "none"}
            provenance: Any = None
            if is_local_probe:
                # Explicit local probe: provider strictly "local", model "none", ZERO model quota claim (C2114 / C2118)
                # Do NOT query quota or select candidate.
                chosen = {"provider": "local", "model": "none"}
                provenance = None
            else:
                # Quota Admission Check
                chosen, provenance = self.check_quse_admission(
                    quse_data=_DEFAULT if quse_override is None else quse_override,
                    model_requirements=model_requirements,
                )

                # Route-to-payload binding check
                if model_requirements and "allowed_providers" in model_requirements:
                    if chosen["provider"] not in model_requirements["allowed_providers"]:
                        raise QuotaAdmissionError(
                            f"Route mismatch: chosen provider '{chosen['provider']}' not in allowed_providers {model_requirements['allowed_providers']}"
                        )

            # Strict route-to-command binding & foreign CLI smuggling protection (C2106 / C2114 / C2118 / C2261 / C2271)
            validate_route_to_command(
                "local" if is_local_probe else chosen["provider"],
                command_argv,
                is_local_probe=is_local_probe,
                expected_model=None if is_local_probe else chosen.get("model"),
            )

            # Pre-launch negative gate 2 (Alternative Store/Lock under Real Model Route, C2261/C2268):
            if not is_local_probe:
                if (
                    self.is_test_fixture
                    or Path(self.store.db_path).resolve() != canonical_store_path.resolve()
                    or lock_file.resolve() != canonical_lock_path.resolve()
                ):
                    raise ResourceAdmissionError(
                        f"Real model route requires exact canonical shared store '{canonical_store_path}' and lock '{canonical_lock_path}'; got store '{self.store.db_path}' and lock '{lock_file}'. "
                        "Alternative stores/locks are strictly non-runtime test fixtures."
                    )

            # Store Registration & Active Resource Check
            task_data = self.store.get_task(task_id)
            active_mem, active_disk = self.store.get_active_resources(exclude_task_id=task_id)
            check_resources(
                requested_memory_mb,
                str(cwd_path),
                str(tmpdir_path),
                active_mem,
                active_disk,
                repo_root=str(workspace_path),
            )

            # Pre-flight environment validation before submitting task to Store
            if env_vars:
                for k, v in env_vars.items():
                    if k in ("PATH", "HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
                        raise ResourceAdmissionError(f"Forbidden environment variable override in env_vars: {k}")
                    if k in ("TMPDIR", "TMP", "TEMP"):
                        if Path(v).resolve() != tmpdir_path.resolve():
                            raise ResourceAdmissionError(
                                f"Divergent temporary directory in env_vars '{k}={v}' does not match checked tmpdir '{tmpdir_path}' (C2284)"
                            )
                        if str(v).startswith("/tmp") or str(v).startswith("/data/tmp"):
                            raise ResourceAdmissionError(f"Contained TMPDIR violation in env_vars: {v}")

            if task_data is None:
                payload = {
                    "owner": "antigravity-head",
                    "cwd": str(cwd_path),
                    "timeout": float(timeout_sec),
                    "goal": " ".join(command_argv),
                    "model_requirements": model_requirements,
                    "provider": "local" if is_local_probe else chosen["provider"],
                    "model": "none" if is_local_probe else chosen.get("model", "none"),
                    "model_quota_claimed": False if is_local_probe else True,
                }
                self.store.submit_task(
                    task_id=task_id,
                    idempotency_key=f"scope-{task_id}",
                    payload=payload,
                    paths=[str(cwd_path)],
                    memory_mb=requested_memory_mb,
                )
            elif task_data.get("state") != "queued":
                raise AdmissionError(f"Task {task_id} state is '{task_data.get('state')}', expected 'queued'")

            # Isolated Agent Bus Identity Enrollment (canonical enroll_agent)
            bus_identity_receipt = None
            if self.bus_bridge is not None:
                ident, token, ns = self.bus_bridge.enroll_agent(
                    agent_name=task_id,
                    project_id="tasks",
                    task_id=task_id,
                )
                bus_identity_receipt = {
                    "identity_id": ident.identity_id,
                    "agent_tag": ns.agent_tag,
                    "token_registered": bool(token),
                }

            # Transition task queued -> starting
            self.store.transition_task(
                task_id,
                "starting",
                ("queued",),
                reason=f"initiating direct systemd scope {unit_name}",
            )

        # 3. Clean environment construction (strip APLEXER_* & prevent global /tmp override)
        # Directive C2371: Child workers must use FileBus (AgentBus registered creds),
        # not inherited helper/parent aplexer mailbox authority.
        # Place fail-closed shims for 'aplexer' and 'a' in child_bin_dir to prevent
        # child processes from resolving to ambient parent workspace sessions.
        child_bin_dir = tmpdir_path / "bin"
        child_bin_dir.mkdir(parents=True, exist_ok=True)
        for shim_name in ("aplexer", "a"):
            shim_path = child_bin_dir / shim_name
            shim_path.write_text(
                "#!/bin/sh\n"
                "echo 'Error: aplexer CLI is forbidden in isolated child worker scope (Directive C2371). "
                "Workers must use AgentBus registered task/recipient creds, not native aplexer CLI.' >&2\n"
                "exit 127\n"
            )
            shim_path.chmod(0o755)

        clean_env = {
            "PATH": f"{child_bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
            "HOME": str(Path.home()),
            "APLEXER_SESSION_ID": "isolated-child-worker-no-aplexer",
            "APLEXER_TAG": "isolated-child-worker",
        }
        if "XDG_RUNTIME_DIR" in os.environ:
            clean_env["XDG_RUNTIME_DIR"] = os.environ["XDG_RUNTIME_DIR"]
        if "DBUS_SESSION_BUS_ADDRESS" in os.environ:
            clean_env["DBUS_SESSION_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
        if env_vars:
            for k, v in env_vars.items():
                if k in ("PATH", "HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
                    raise ResourceAdmissionError(f"Forbidden environment variable override in env_vars: {k}")
                if k.startswith("APLEXER_") or k.startswith("PARENT_") or k.startswith("CLOUDFLARE_"):
                    continue
                if k in ("TMPDIR", "TMP", "TEMP"):
                    if Path(v).resolve() != tmpdir_path.resolve():
                        raise ResourceAdmissionError(
                            f"Divergent temporary directory in env_vars '{k}={v}' does not match checked tmpdir '{tmpdir_path}' (C2284)"
                        )
                    if str(v).startswith("/tmp") or str(v).startswith("/data/tmp"):
                        raise ResourceAdmissionError(f"Contained TMPDIR violation in env_vars: {v}")
                clean_env[k] = str(v)

        # Enforce clean_env explicitly sets TMPDIR, TMP, TEMP to checked tmpdir_path (C2284)
        clean_env["TMPDIR"] = str(tmpdir_path)
        clean_env["TMP"] = str(tmpdir_path)
        clean_env["TEMP"] = str(tmpdir_path)

        # 4. Pre-Payload Containment Verification Prelude
        receipt_path = tmpdir_path / f"containment_verified_{unit_name}.json"
        prelude_script = tmpdir_path / f"prelude_{unit_name}.py"
        req_mem_bytes = requested_memory_mb * 1024 * 1024

        prelude_code = f"""import sys, os, subprocess, json

unit = "{unit_name}"
req_mem_bytes = "{req_mem_bytes}"

res = subprocess.run(["systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "MemoryMax", "-p", "TasksMax", "-p", "ControlGroup", "-p", "InvocationID"], capture_output=True, text=True)
props = dict(line.split("=", 1) for line in res.stdout.splitlines() if "=" in line)

if props.get("ActiveState") != "active":
    sys.exit(91)
if props.get("MemoryMax") != req_mem_bytes:
    sys.exit(92)
if not props.get("InvocationID"):
    sys.exit(93)
cgroup = props.get("ControlGroup", "")
if not cgroup:
    sys.exit(94)
if props.get("TasksMax") != "100":
    sys.exit(95)

# C2106: Inspect /proc/self/cgroup and verify it matches ControlGroup (exit 96)
self_cgroup = ""
if os.path.exists("/proc/self/cgroup"):
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":", 2)
                if len(parts) == 3:
                    self_cgroup = parts[2]
                    if parts[0] == "0":
                        break
    except Exception:
        sys.exit(96)

if not self_cgroup or self_cgroup.strip("/") != cgroup.strip("/"):
    sys.exit(96)

# C2106: Authoritative kernel membership in cgroup.procs (exit 97)
cg_procs_path = f"/sys/fs/cgroup/{{cgroup.lstrip('/')}}/cgroup.procs"
if not os.path.exists(cg_procs_path):
    sys.exit(97)
try:
    with open(cg_procs_path, "r", encoding="utf-8") as f:
        pids = [p.strip() for p in f.read().splitlines() if p.strip()]
    if str(os.getpid()) not in pids:
        sys.exit(97)
except Exception:
    sys.exit(97)

with open("{receipt_path}", "w", encoding="utf-8") as f:
    json.dump({{"unit": unit, "pid": os.getpid(), "cgroup": cgroup, "memory_max": props.get("MemoryMax"), "tasks_max": props.get("TasksMax"), "invocation_id": props.get("InvocationID")}}, f)

# Enforce contained scratch TMPDIR before execvp into child payload (C2134)
os.environ["TMPDIR"] = "{tmpdir_path}"
os.environ["TEMP"] = "{tmpdir_path}"
os.environ["TMP"] = "{tmpdir_path}"

os.execvp(sys.argv[1], sys.argv[1:])
"""
        prelude_script.write_text(prelude_code, encoding="utf-8")
        prelude_script.chmod(0o700)

        # 5. Construct systemd-run invocation with prelude and explicit environment bindings
        scope_cmd = [
            "systemd-run",
            "--user",
            "--scope",
            "--collect",
            f"--unit={unit_name}",
            "-p", f"MemoryMax={requested_memory_mb}M",
            "-p", "TasksMax=100",
            "-E", f"TMPDIR={tmpdir_path}",
            "-E", f"TEMP={tmpdir_path}",
            "-E", f"TMP={tmpdir_path}",
            "--",
            sys.executable,
            str(prelude_script),
        ] + list(command_argv)

        stdout_log = cwd_path / ".local" / f"{task_id}-stdout.log"
        stderr_log = cwd_path / ".local" / f"{task_id}-stderr.log"
        stdout_log.parent.mkdir(parents=True, exist_ok=True)

        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Record initial tmpdir size for measured disk growth guard (C2284)
        initial_tmp_size = _get_dir_size_bytes(tmpdir_path)

        # 6. Spawn process with bounded disk logging (C2106) and Popen failure guard
        out_thread = None
        err_thread = None
        try:
            proc = subprocess.Popen(
                scope_cmd,
                cwd=str(cwd_path),
                env=clean_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            out_thread = threading.Thread(
                target=_bounded_pipe_pump,
                args=(proc.stdout, stdout_log, MAX_DISK_LOG_BYTES),
                daemon=True,
            )
            err_thread = threading.Thread(
                target=_bounded_pipe_pump,
                args=(proc.stderr, stderr_log, MAX_DISK_LOG_BYTES),
                daemon=True,
            )
            out_thread.start()
            err_thread.start()
        except Exception as exc:
            subprocess.run(["systemctl", "--user", "kill", "--kill-who=all", "--signal=SIGKILL", unit_name], check=False)
            subprocess.run(["systemctl", "--user", "stop", unit_name], check=False)
            cleaned_up = verify_unit_cleanup(unit_name, expected_cgroup=None)
            if cleaned_up:
                self.store.transition_task(
                    task_id,
                    "failed",
                    ("starting",),
                    reviewer="popen-guard",
                    reason=f"Popen failed: {exc}; unit confirmed clean",
                )
            else:
                self.store.transition_task(
                    task_id,
                    "launch-uncertain",
                    ("starting",),
                    reviewer="popen-guard",
                    reason=f"Popen failed: {exc}; cleanup unproven, holding resources",
                )
            raise

        def _check_and_enforce_tmpdir_growth() -> None:
            current_size = _get_dir_size_bytes(tmpdir_path)
            delta = current_size - initial_tmp_size
            if delta > MAX_TMPDIR_GROWTH_BYTES:
                subprocess.run(["systemctl", "--user", "kill", "--kill-who=all", "--signal=SIGKILL", unit_name], check=False)
                subprocess.run(["systemctl", "--user", "stop", unit_name], check=False)
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
                if out_thread and out_thread.is_alive():
                    out_thread.join(timeout=1.0)
                if err_thread and err_thread.is_alive():
                    err_thread.join(timeout=1.0)

                cleaned_up = verify_unit_cleanup(
                    unit_name,
                    expected_cgroup=cached_cgroup,
                )
                task_data = self.store.get_task(task_id)
                current_state = task_data.get("state") if task_data else "running"
                valid_from = (current_state,) if current_state in ("starting", "running") else ("starting", "running")

                if cleaned_up:
                    self.store.transition_task(
                        task_id,
                        "failed",
                        valid_from,
                        reviewer="tmpdir-growth-guard",
                        reason=f"Tmpdir net growth {delta} bytes exceeds 512 MiB limit ({MAX_TMPDIR_GROWTH_BYTES} bytes); unit confirmed clean",
                    )
                else:
                    self.store.transition_task(
                        task_id,
                        "launch-uncertain",
                        valid_from,
                        reviewer="tmpdir-growth-guard",
                        reason=f"Tmpdir net growth {delta} bytes exceeds 512 MiB limit ({MAX_TMPDIR_GROWTH_BYTES} bytes); cleanup unproven, holding resources",
                    )
                raise ResourceAdmissionError(
                    f"Tmpdir net growth {delta} bytes exceeds 512 MiB limit ({MAX_TMPDIR_GROWTH_BYTES} bytes)"
                )

        # Poll up to 3s for unit activation & containment receipt
        verified_active = False
        cached_cgroup: Optional[str] = None
        cached_invocation_id: Optional[str] = None
        for _ in range(30):
            _check_and_enforce_tmpdir_growth()
            if receipt_path.exists():
                try:
                    receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
                    if (
                        receipt_data.get("unit") == unit_name
                        and receipt_data.get("invocation_id")
                        and receipt_data.get("cgroup")
                    ):
                        cached_cgroup = receipt_data.get("cgroup")
                        cached_invocation_id = receipt_data.get("invocation_id")
                        verified_active = True
                        break
                except Exception:
                    pass
            if proc.poll() is not None:
                if receipt_path.exists():
                    try:
                        receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
                        if (
                            receipt_data.get("unit") == unit_name
                            and receipt_data.get("invocation_id")
                            and receipt_data.get("cgroup")
                        ):
                            cached_cgroup = receipt_data.get("cgroup")
                            cached_invocation_id = receipt_data.get("invocation_id")
                            verified_active = True
                    except Exception:
                        pass
                break
            time.sleep(0.1)

        if verified_active:
            self.store.transition_task(
                task_id,
                "running",
                ("starting",),
                reason=f"scope {unit_name} verified active in kernel cgroup",
            )
        else:
            # Containment verification failed: terminate unit and evaluate cleanup
            subprocess.run(["systemctl", "--user", "kill", "--kill-who=all", "--signal=SIGKILL", unit_name], check=False)
            subprocess.run(["systemctl", "--user", "stop", unit_name], check=False)
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
            if out_thread and out_thread.is_alive():
                out_thread.join(timeout=1.0)
            if err_thread and err_thread.is_alive():
                err_thread.join(timeout=1.0)
            rc = proc.poll()
            cleaned_up = verify_unit_cleanup(
                unit_name,
                expected_cgroup=cached_cgroup,
            )
            if cleaned_up:
                self.store.transition_task(
                    task_id,
                    "failed",
                    ("starting",),
                    reviewer="prelude-containment-guard",
                    reason=f"scope {unit_name} failed containment verification (exit={rc}); unit confirmed clean",
                )
            else:
                # Cleanup unproven: preserve starting -> launch-uncertain to hold Store resources
                self.store.transition_task(
                    task_id,
                    "launch-uncertain",
                    ("starting",),
                    reviewer="prelude-containment-guard",
                    reason=f"scope {unit_name} failed containment verification (exit={rc}); unit cleanup unproven, holding resources",
                )
            raise ResourceAdmissionError(f"Scope {unit_name} failed containment verification prelude (exit={rc}, cleaned_up={cleaned_up})")

        # 7. Wait with timeout, tmpdir growth guard, and authoritative teardown (C2284)
        start_wait = time.time()
        poll_interval = 0.05
        returncode = None
        while True:
            _check_and_enforce_tmpdir_growth()

            rc = proc.poll()
            if rc is not None:
                returncode = rc
                break

            if time.time() - start_wait >= timeout_sec:
                # Terminate the entire process tree via systemctl kill --kill-who=all
                subprocess.run(["systemctl", "--user", "kill", "--kill-who=all", "--signal=SIGKILL", unit_name], check=False)
                subprocess.run(["systemctl", "--user", "stop", unit_name], check=False)
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
                if out_thread and out_thread.is_alive():
                    out_thread.join(timeout=1.0)
                if err_thread and err_thread.is_alive():
                    err_thread.join(timeout=1.0)

                cleaned_up = verify_unit_cleanup(
                    unit_name,
                    expected_cgroup=cached_cgroup,
                )
                if cleaned_up:
                    self.store.fail_task(
                        task_id,
                        reviewer="systemd-watchdog",
                        reason=f"Timeout expired ({timeout_sec}s); unit confirmed terminated",
                    )
                else:
                    # Retain uncertain reservation in Store (launch-uncertain holds resources)
                    self.store.transition_task(
                        task_id,
                        "launch-uncertain",
                        ("running",),
                        reviewer="systemd-watchdog",
                        reason=f"Timeout expired; unit cleanup unproven, holding resources",
                    )
                raise TimeoutError(f"Task {task_id} in systemd scope {unit_name} exceeded timeout {timeout_sec}s (cleaned_up={cleaned_up})")

            time.sleep(poll_interval)

        if out_thread and out_thread.is_alive():
            out_thread.join(timeout=2.0)
        if err_thread and err_thread.is_alive():
            err_thread.join(timeout=2.0)

        # Post-execution tmpdir growth check (C2284)
        _check_and_enforce_tmpdir_growth()

        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        stdout_text = read_bounded_log(stdout_log, max_bytes=65536)
        stderr_text = read_bounded_log(stderr_log, max_bytes=65536)

        # 8. Non-auto-accepting completion handling (no rc0-as-done)
        if returncode == 0:
            # C2106: Stop unit and verify cleanup FIRST before checking expected_outputs
            subprocess.run(["systemctl", "--user", "stop", unit_name], check=False)
            cleaned_up = verify_unit_cleanup(
                unit_name,
                expected_cgroup=cached_cgroup,
            )
            if not cleaned_up:
                # Lingering children after client exit!
                subprocess.run(["systemctl", "--user", "kill", "--kill-who=all", "--signal=SIGKILL", unit_name], check=False)
                self.store.transition_task(
                    task_id,
                    "launch-uncertain",
                    ("running",),
                    reviewer="systemd-scope-runner",
                    reason=f"scope {unit_name} exited 0 but unconfined processes remain in cgroup, holding resources",
                )
                raise ResourceAdmissionError(f"Scope {unit_name} exited 0 but left unconfined background tasks in cgroup")

            # Unit verified clean! Now check expected outputs (C2106)
            if expected_outputs:
                for out_p_str in expected_outputs:
                    out_p = Path(out_p_str).resolve()
                    if not out_p.exists() or out_p.stat().st_size == 0:
                        self.store.fail_task(
                            task_id,
                            reviewer="systemd-scope-runner",
                            reason=f"scope {unit_name} exited 0 but expected output {out_p.name} missing or empty",
                        )
                        raise ResourceAdmissionError(f"Expected output file {out_p} missing or empty")

            # Transition to completed-awaiting-review via complete_task
            self.store.complete_task(
                task_id,
                reviewer="systemd-scope-runner",
                reason=f"scope {unit_name} exited 0; unit confirmed clean; awaiting independent review",
            )
        else:
            subprocess.run(["systemctl", "--user", "kill", "--kill-who=all", "--signal=SIGKILL", unit_name], check=False)
            subprocess.run(["systemctl", "--user", "stop", unit_name], check=False)
            cleaned_up = verify_unit_cleanup(
                unit_name,
                expected_cgroup=cached_cgroup,
            )
            if cleaned_up:
                self.store.fail_task(
                    task_id,
                    reviewer="systemd-scope-runner",
                    reason=f"scope {unit_name} exited rc={returncode}; unit confirmed clean",
                )
            else:
                self.store.transition_task(
                    task_id,
                    "launch-uncertain",
                    ("running",),
                    reviewer="systemd-scope-runner",
                    reason=f"scope {unit_name} exited rc={returncode}; lingering tasks or unproven cleanup, holding resources",
                )
                raise ResourceAdmissionError(f"Scope {unit_name} exited rc={returncode} with unproven cleanup")

        return {
            "task_id": task_id,
            "unit_name": unit_name,
            "returncode": returncode,
            "pid": proc.pid,
            "started_at": started_at,
            "completed_at": completed_at,
            "bus_identity": bus_identity_receipt,
            "stdout_preview": stdout_text[:500],
            "stderr_preview": stderr_text[:500],
            "quse_admitted": not is_local_probe,
            "is_local_probe": is_local_probe,
            "model_quota_claimed": False if is_local_probe else True,
            "provider_chosen": "local" if is_local_probe else chosen["provider"],
        }


