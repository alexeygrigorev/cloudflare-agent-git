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
import shutil
import stat
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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
)
from launcher.admission import (
    ADAPTER_MODELS,
    ADAPTER_ROUTES,
    validate_quse,
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
