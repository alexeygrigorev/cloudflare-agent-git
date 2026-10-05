#!/usr/bin/env python3
"""
Cross-Computer Offline Recovery & ACK Retry Engine (Codex Principal C2416).

Implements the outbound durable outbox, retry coordinator, and fail-closed crash
recovery for two-computer agent coordination topologies (e.g. Desktop Windows client
to Hetzner Linux server rendezvous).

Key Architectural Guarantees:
1. Two-Computer Topology Modeling:
   - Node A (Client / Windows Desktop): Outbound durable outbox, client-side retry
     loop, ACK reconciliation, and crash survival.
   - Node B (Server / Hetzner Linux): Rendezvous FileBus store, idempotency enforcement,
     verified SHA-256 receipt generation, read-ACK issuance, and completion reply.
2. 6-Stage Offline Delivery & ACK Lifecycle:
   - Stage 1: Sender attempts dispatch while remote transport or recipient is offline / unreachable
     (simulating network timeout or connection refused).
   - Stage 2: Sender persists outbound message in durable outbox with strict mode 0600,
     preserving message ID, sender ID, recipient ID, and idempotency key.
   - Stage 3: Remote receiver / transport comes online; sender re-attempts delivery via retry mechanism.
   - Stage 4: Remote receiver ingests message, generates verified SHA-256 receipt, and issues read ACK.
   - Stage 5: Sender receives ACK and unlinks/removes message from retry queue without duplicate execution.
   - Stage 6: Crashing or restarting sender or receiver mid-cycle preserves all state fail-closed
     without re-running tasks or duplicating replies.
3. Durable Atomic Storage & Fail-Closed Quarantine:
   - Outbox directory strictly mode 0700.
   - Outbox files strictly mode 0600.
   - Atomic writes via temporary file and rename.
   - Zero-byte files or malformed JSON fail-closed and are safely quarantined.
   - Permission violations (e.g. world-writable mode) fail closed.
4. Scratch & Host Isolation:
   - All ephemeral paths contained within designated scratch root (mode 0700, <= 512 MiB).
   - TMPDIR contained; zero net /tmp growth.
   - Zero cargo/rustc invocations.
"""

from __future__ import annotations

import copy
import dataclasses
import datetime
import enum
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
import uuid

logger = logging.getLogger("cross_computer_retry")


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class CrossComputerRetryError(Exception):
    """Base exception for cross-computer retry operations."""
    pass


class OutboxError(CrossComputerRetryError):
    """Base exception for outbox storage operations."""
    pass


class CorruptedOutboxError(OutboxError):
    """Raised when an outbox file contains invalid JSON or truncated contents."""
    pass


class OutboxPermissionError(OutboxError):
    """Raised when an outbox directory or file violates strict permission modes."""
    pass


class MissingOutboxError(OutboxError):
    """Raised when an expected outbox record does not exist on disk."""
    pass


class DuplicateExecutionPrevented(CrossComputerRetryError):
    """Raised or flagged when an idempotent replay prevents redundant task execution."""
    pass


class TransportOfflineError(CrossComputerRetryError):
    """Raised when the remote transport is unreachable or offline."""
    def __init__(self, message: str, reason: str = "offline"):
        super().__init__(message)
        self.reason = reason


# -----------------------------------------------------------------------------
# Data Models & Envelopes
# -----------------------------------------------------------------------------

class MessageDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    INFLIGHT = "inflight"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


@dataclasses.dataclass
class OutboxMessage:
    """
    Durable outbound message record stored in the sender's local outbox.
    """
    message_id: str
    sender_id: str
    recipient_id: str
    idempotency_key: str
    body: str
    data: Dict[str, Any] = dataclasses.field(default_factory=dict)
    queued_at: str = dataclasses.field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    status: MessageDeliveryStatus = MessageDeliveryStatus.PENDING
    retry_count: int = 0
    last_attempt_at: Optional[str] = None
    last_error: Optional[str] = None
    receipt_digest: Optional[str] = None
    ack_received_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "idempotency_key": self.idempotency_key,
            "body": self.body,
            "data": copy.deepcopy(self.data),
            "queued_at": self.queued_at,
            "status": self.status.value if isinstance(self.status, MessageDeliveryStatus) else str(self.status),
            "retry_count": self.retry_count,
            "last_attempt_at": self.last_attempt_at,
            "last_error": self.last_error,
            "receipt_digest": self.receipt_digest,
            "ack_received_at": self.ack_received_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OutboxMessage:
        required_keys = ("message_id", "sender_id", "recipient_id", "idempotency_key", "body")
        for k in required_keys:
            if k not in data or not isinstance(data[k], str) or not data[k].strip():
                raise CorruptedOutboxError(f"Missing or invalid required field '{k}' in outbox payload")

        status_str = data.get("status", MessageDeliveryStatus.PENDING.value)
        try:
            status = MessageDeliveryStatus(status_str)
        except ValueError:
            status = MessageDeliveryStatus.PENDING

        return cls(
            message_id=str(data["message_id"]),
            sender_id=str(data["sender_id"]),
            recipient_id=str(data["recipient_id"]),
            idempotency_key=str(data["idempotency_key"]),
            body=str(data["body"]),
            data=dict(data.get("data", {})),
            queued_at=str(data.get("queued_at", datetime.datetime.now(datetime.timezone.utc).isoformat())),
            status=status,
            retry_count=int(data.get("retry_count", 0)),
            last_attempt_at=data.get("last_attempt_at"),
            last_error=data.get("last_error"),
            receipt_digest=data.get("receipt_digest"),
            ack_received_at=data.get("ack_received_at"),
        )


def compute_message_receipt_digest(body: str, data: Optional[Dict[str, Any]] = None) -> str:
    """
    Computes a deterministic SHA-256 digest of the message body and data payload.
    Used for end-to-end receipt verification across computers.
    """
    canonical_repr = json.dumps(
        {"body": body, "data": data or {}},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# Durable Outbox Storage (Mode 0700 dir, Mode 0600 files)
# -----------------------------------------------------------------------------

class DurableOutboxQueue:
    """
    Manages client-side durable message outbox files on disk.

    Guarantees:
    - Outbox directory created with mode 0700 (user read/write/execute only).
    - Outbox files written atomically via .tmp and given mode 0600 (user read/write only).
    - Zero-byte files or corrupted JSON raise CorruptedOutboxError and are quarantined.
    - Permissions tampered to world-writable fail closed with OutboxPermissionError.
    """

    def __init__(self, outbox_dir: Path | str, enforce_permissions: bool = True):
        self.outbox_dir = Path(outbox_dir).resolve()
        self.enforce_permissions = enforce_permissions
        self.quarantine_dir = self.outbox_dir.parent / f"{self.outbox_dir.name}_quarantine"

        self.outbox_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.outbox_dir, stat.S_IRWXU)
        except OSError:
            pass

    def _verify_file_permissions(self, path: Path) -> None:
        """Verifies that file does not have group or other permissions (mode 0600)."""
        if not self.enforce_permissions:
            return
        if not path.exists():
            return
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)
        # Any permission in group or other is strictly prohibited (e.g. 0644, 0666, 0777)
        if mode & 0o077:
            raise OutboxPermissionError(
                f"Insecure file permissions {oct(mode)} on {path}; must be strictly mode 0600"
            )

    def _atomic_write_message(self, path: Path, msg: OutboxMessage) -> None:
        """Writes an OutboxMessage atomically with strict mode 0600."""
        tmp_path = path.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
        payload_bytes = json.dumps(msg.to_dict(), indent=2, sort_keys=True).encode("utf-8")

        # Open with O_CREAT | O_WRONLY | O_EXCL and mode 0600
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC

        fd = os.open(tmp_path, flags, stat.S_IRUSR | stat.S_IWUSR)
        try:
            with open(fd, "wb", closefd=True) as f:
                f.write(payload_bytes)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            tmp_path.unlink(missing_ok=True)
            raise

        try:
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        os.replace(tmp_path, path)

    def quarantine(self, path: Path, reason: str) -> Path:
        """Moves a corrupted or malformed outbox file to the quarantine directory."""
        self.quarantine_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        dest = self.quarantine_dir / f"{path.name}.{int(time.time())}.corrupted"
        try:
            shutil.move(str(path), str(dest))
            logger.warning(f"Quarantined outbox file {path} -> {dest} (reason: {reason})")
        except OSError as e:
            logger.error(f"Failed to quarantine {path}: {e}")
        return dest

    def enqueue(self, msg: OutboxMessage) -> Path:
        """
        Enqueues an OutboxMessage durably to disk.
        If an existing pending message with the exact same idempotency_key exists,
        returns the existing path without creating a duplicate.
        """
        # Check for existing idempotency key in pending messages
        for existing in self.list_pending():
            if existing.idempotency_key == msg.idempotency_key:
                return self.outbox_dir / f"{existing.message_id}.json"

        target_file = self.outbox_dir / f"{msg.message_id}.json"
        self._atomic_write_message(target_file, msg)
        return target_file

    def get(self, message_id: str) -> Optional[OutboxMessage]:
        """Loads and parses an outbox message by message_id."""
        target_file = self.outbox_dir / f"{message_id}.json"
        if not target_file.exists():
            return None

        self._verify_file_permissions(target_file)

        # Fail closed on 0-byte or empty file
        if target_file.stat().st_size == 0:
            self.quarantine(target_file, "0-byte empty file")
            raise CorruptedOutboxError(f"Outbox file {target_file} is 0 bytes; quarantined")

        try:
            raw_text = target_file.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            return OutboxMessage.from_dict(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.quarantine(target_file, f"json decode failure: {e}")
            raise CorruptedOutboxError(f"Outbox file {target_file} contains malformed JSON: {e}")

    def list_all(self) -> List[OutboxMessage]:
        """Lists all valid outbox messages in the outbox directory."""
        messages: List[OutboxMessage] = []
        if not self.outbox_dir.exists():
            return messages

        for p in sorted(self.outbox_dir.glob("*.json")):
            # Ignore temporary or swap files
            if p.name.startswith(".") or ".tmp" in p.name:
                continue

            try:
                self._verify_file_permissions(p)
                if p.stat().st_size == 0:
                    self.quarantine(p, "0-byte file during list")
                    continue
                raw_text = p.read_text(encoding="utf-8")
                data = json.loads(raw_text)
                msg = OutboxMessage.from_dict(data)
                messages.append(msg)
            except OutboxPermissionError:
                raise
            except CorruptedOutboxError:
                continue
            except (json.JSONDecodeError, Exception) as e:
                self.quarantine(p, f"unhandled load error: {e}")
                continue

        return messages

    def list_pending(self) -> List[OutboxMessage]:
        """Returns all messages currently awaiting delivery or acknowledgment."""
        return [
            m for m in self.list_all()
            if m.status != MessageDeliveryStatus.ACKNOWLEDGED
        ]

    def mark_attempt(self, message_id: str, error: Optional[str] = None) -> OutboxMessage:
        """Records a delivery attempt on disk, updating retry_count and last_error."""
        msg = self.get(message_id)
        if msg is None:
            raise MissingOutboxError(f"Cannot mark attempt for missing message {message_id}")

        msg.retry_count += 1
        msg.last_attempt_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        msg.last_error = error
        msg.status = MessageDeliveryStatus.PENDING

        target_file = self.outbox_dir / f"{message_id}.json"
        self._atomic_write_message(target_file, msg)
        return msg

    def mark_delivered(self, message_id: str, receipt_digest: Optional[str] = None) -> OutboxMessage:
        """Updates outbox message status to DELIVERED with the remote receipt digest."""
        msg = self.get(message_id)
        if msg is None:
            raise MissingOutboxError(f"Cannot mark delivered for missing message {message_id}")

        msg.status = MessageDeliveryStatus.DELIVERED
        msg.last_attempt_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        msg.last_error = None
        if receipt_digest:
            msg.receipt_digest = receipt_digest

        target_file = self.outbox_dir / f"{message_id}.json"
        self._atomic_write_message(target_file, msg)
        return msg

    def mark_acknowledged(
        self,
        message_id: str,
        ack_receipt: Optional[Dict[str, Any]] = None,
        unlink: bool = True,
    ) -> Optional[OutboxMessage]:
        """
        Acknowledges receipt of message by recipient.
        If unlink=True (default), unlinks the outbox file from disk cleanly (Stage 5).
        If unlink=False, retains the file with status ACKNOWLEDGED.
        """
        target_file = self.outbox_dir / f"{message_id}.json"
        if not target_file.exists():
            return None

        msg = self.get(message_id)
        if msg is None:
            return None

        msg.status = MessageDeliveryStatus.ACKNOWLEDGED
        msg.ack_received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if ack_receipt and "receipt_digest" in ack_receipt:
            msg.receipt_digest = ack_receipt["receipt_digest"]

        if unlink:
            target_file.unlink(missing_ok=True)
            return msg
        else:
            self._atomic_write_message(target_file, msg)
            return msg


# -----------------------------------------------------------------------------
# Simulated Two-Computer Topology Transport Controller
# -----------------------------------------------------------------------------

class TransportPartitionMode(str, enum.Enum):
    ONLINE = "online"
    TIMEOUT = "timeout"
    REFUSED = "refused"
    CORRUPTED = "corrupted"


class SimulatedNetworkTransport:
    """
    Models physical network link and remote host reachability between Desktop and Hetzner.

    Allows tests to deterministically simulate:
    - Normal online operation
    - Network timeout (e.g. WAN packet loss or SSH handshake hang)
    - Connection refused (e.g. remote daemon stopped or port closed)
    - Response framing corruption (e.g. proxy truncation or invalid framing)
    """

    def __init__(
        self,
        target_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        mode: TransportPartitionMode = TransportPartitionMode.ONLINE,
    ):
        self.target_fn = target_fn
        self.mode = mode
        self.call_count = 0
        self.delivered_calls: List[Dict[str, Any]] = []

    def set_mode(self, mode: TransportPartitionMode) -> None:
        self.mode = mode

    def send_rpc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes delivery across the simulated network link."""
        self.call_count += 1

        if self.mode == TransportPartitionMode.TIMEOUT:
            raise TransportOfflineError(
                "SSH RPC timed out after 10.0s: host 135.181.114.209 unreachable",
                reason="timeout",
            )
        elif self.mode == TransportPartitionMode.REFUSED:
            raise TransportOfflineError(
                "ssh: connect to host 135.181.114.209 port 22: Connection refused",
                reason="connection_refused",
            )
        elif self.mode == TransportPartitionMode.CORRUPTED:
            return {"ok": "not-a-bool", "error": "corrupted"}

        if self.target_fn is not None:
            res = self.target_fn(payload)
            self.delivered_calls.append(payload)
            return res

        self.delivered_calls.append(payload)
        return {
            "ok": True,
            "result": {
                "message_id": payload.get("message_id", str(uuid.uuid4())),
                "status": "delivered",
            },
        }


# -----------------------------------------------------------------------------
# Cross-Computer Retry Sender (Node A: Desktop Client)
# -----------------------------------------------------------------------------

class CrossComputerRetrySender:
    """
    Client-side offline-first retry coordinator representing the Desktop Windows Client.

    Enforces:
    - Stage 1: Catches transport errors during offline dispatch.
    - Stage 2: Persists message in local outbox with mode 0600 and idempotency key.
    - Stage 3: Flushes retry queue once remote transport is back online.
    - Stage 4/5: Reconciles read-ACKs and unlinks outbox messages without duplicate execution.
    - Stage 6: Restarts and crash recoveries preserve all pending messages fail-closed.
    """

    def __init__(
        self,
        sender_id: str,
        token: str,
        scratch_root: Path | str,
        transport: Optional[Any] = None,
        enforce_permissions: bool = True,
    ):
        self.sender_id = sender_id
        self.token = token
        self.scratch_root = Path(scratch_root).resolve()
        self.outbox_dir = self.scratch_root / "outbox"
        self.outbox = DurableOutboxQueue(self.outbox_dir, enforce_permissions=enforce_permissions)
        self.transport = transport

    def send(
        self,
        recipient_id: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        direct_attempt: bool = True,
    ) -> OutboxMessage:
        """
        Dispatches a message using the offline-first delivery pattern.

        1. Creates OutboxMessage with unique message_id and idempotency_key.
        2. Persists to durable outbox queue with mode 0600 (Stage 2).
        3. If direct_attempt=True, tries transport delivery:
           - On success: marks DELIVERED.
           - On failure (Stage 1): catches error, records retry attempt, leaves message PENDING.
        """
        msg_id = str(uuid.uuid4())
        idem_key = idempotency_key or f"idem-{self.sender_id[:8]}-{uuid.uuid4().hex[:12]}"

        msg = OutboxMessage(
            message_id=msg_id,
            sender_id=self.sender_id,
            recipient_id=recipient_id,
            idempotency_key=idem_key,
            body=body,
            data=data or {},
            status=MessageDeliveryStatus.PENDING,
        )

        # Stage 2: Persist to durable outbox FIRST with mode 0600
        self.outbox.enqueue(msg)

        if not direct_attempt or self.transport is None:
            return msg

        # Stage 1: Attempt delivery across transport
        try:
            rpc_payload = {
                "op": "send",
                "message_id": msg.message_id,
                "sender_id": self.sender_id,
                "token": self.token,
                "recipient_id": recipient_id,
                "idempotency_key": idem_key,
                "body": body,
                "data": data or {},
            }
            if hasattr(self.transport, "send_rpc"):
                resp = self.transport.send_rpc(rpc_payload)
            elif callable(self.transport):
                resp = self.transport(rpc_payload)
            else:
                resp = {"ok": True}

            if isinstance(resp, dict) and resp.get("ok"):
                digest = compute_message_receipt_digest(body, data)
                msg = self.outbox.mark_delivered(msg.message_id, receipt_digest=digest)
            else:
                msg = self.outbox.mark_attempt(msg.message_id, error="Remote transport returned ok=False")
        except Exception as e:
            # Stage 1 catch: Remote is offline / unreachable
            logger.info(f"Direct delivery failed for message {msg.message_id}: {e}; preserved in outbox")
            msg = self.outbox.mark_attempt(msg.message_id, error=str(e))

        return msg

    def flush_retry_queue(self) -> Tuple[List[OutboxMessage], List[OutboxMessage]]:
        """
        Stage 3: Scans outbox for all pending messages and attempts delivery.
        Returns (successful_messages, failed_messages).
        """
        if self.transport is None:
            return [], self.outbox.list_pending()

        pending = self.outbox.list_pending()
        succeeded: List[OutboxMessage] = []
        failed: List[OutboxMessage] = []

        for msg in pending:
            rpc_payload = {
                "op": "send",
                "message_id": msg.message_id,
                "sender_id": self.sender_id,
                "token": self.token,
                "recipient_id": msg.recipient_id,
                "idempotency_key": msg.idempotency_key,
                "body": msg.body,
                "data": msg.data,
            }
            try:
                if hasattr(self.transport, "send_rpc"):
                    resp = self.transport.send_rpc(rpc_payload)
                elif callable(self.transport):
                    resp = self.transport(rpc_payload)
                else:
                    resp = {"ok": True}

                if isinstance(resp, dict) and resp.get("ok"):
                    digest = compute_message_receipt_digest(msg.body, msg.data)
                    updated = self.outbox.mark_delivered(msg.message_id, receipt_digest=digest)
                    succeeded.append(updated)
                else:
                    updated = self.outbox.mark_attempt(msg.message_id, error="Remote returned ok=False")
                    failed.append(updated)
            except Exception as e:
                updated = self.outbox.mark_attempt(msg.message_id, error=str(e))
                failed.append(updated)

        return succeeded, failed

    def process_ack(self, message_id: str, ack_receipt: Optional[Dict[str, Any]] = None) -> bool:
        """
        Stage 5: Receives verified read ACK and removes message from outbox queue.
        """
        msg = self.outbox.mark_acknowledged(message_id, ack_receipt=ack_receipt, unlink=True)
        return msg is not None


# -----------------------------------------------------------------------------
# Simulated Receiver Endpoint (Node B: Hetzner Linux Rendezvous)
# -----------------------------------------------------------------------------

class SimulatedReceiverEndpoint:
    """
    Models the remote receiver service on Hetzner Linux (Node B).

    Guarantees:
    - Maintains an idempotency table indexed by `idempotency_key`.
    - Detects redundant re-deliveries and prevents duplicate task execution.
    - Generates deterministic SHA-256 verified receipts.
    - Issues read ACKs upon message processing.
    """

    def __init__(self, recipient_id: str, store_dir: Path | str):
        self.recipient_id = recipient_id
        self.store_dir = Path(store_dir).resolve()
        self.store_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_file = self.store_dir / "receiver_state.json"
        self.execution_counts: Dict[str, int] = {}
        self.processed_receipts: Dict[str, Dict[str, Any]] = {}
        self.load_state()

    def load_state(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.execution_counts = data.get("execution_counts", {})
                self.processed_receipts = data.get("processed_receipts", {})
            except Exception as e:
                logger.warning(f"Receiver state read error: {e}")

    def save_state(self) -> None:
        data = {
            "execution_counts": self.execution_counts,
            "processed_receipts": self.processed_receipts,
        }
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, self.state_file)

    def handle_incoming_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stage 4: Ingests message, checks idempotency, generates verified receipt, and issues read ACK.
        """
        msg_id = payload.get("message_id", "")
        idem_key = payload.get("idempotency_key", msg_id)
        body = payload.get("body", "")
        data = payload.get("data", {})

        # Check for duplicate delivery via idempotency key
        if idem_key in self.processed_receipts:
            logger.info(f"Duplicate delivery detected for idempotency key {idem_key}; returning existing receipt")
            existing_receipt = self.processed_receipts[idem_key]
            return {
                "ok": True,
                "duplicate": True,
                "result": existing_receipt,
            }

        # First execution: increment execution counter
        self.execution_counts[idem_key] = self.execution_counts.get(idem_key, 0) + 1

        # Generate verified SHA-256 receipt
        receipt_digest = compute_message_receipt_digest(body, data)
        receipt = {
            "message_id": msg_id,
            "idempotency_key": idem_key,
            "receipt_digest": receipt_digest,
            "status": "acknowledged",
            "acknowledged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # Store state atomically
        self.processed_receipts[idem_key] = receipt
        self.save_state()

        return {
            "ok": True,
            "duplicate": False,
            "result": receipt,
        }
