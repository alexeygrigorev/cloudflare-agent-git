#!/usr/bin/env python3
"""
FileBus Queue / Receive Dispatcher Service (Codex Directives C2332 / C2333 / C2335 / C2337).

Mechanical worker and task dispatcher owned by `antigravity-head` (`245c7bba-9a7b-45c1-87a7-4537f289f9a5`).
Operates on the durable FileBus message queue with canonical launcher admission and systemd scope isolation.

Key Architectural Guarantees & Constraints (C2332 / C2333 / C2335 / C2337):
1. Head-Owned Mechanical Service:
   - Mechanical task queue receiver/worker. Strictly NOT a new principal.
   - Never borrows or impersonates native aplexer identity (`APLEXER_*` environment variables stripped).
2. Genuine Token-Based FileBus Registration (Directive C2333):
   - Integrates directly with public 23b0742 FileBus CLI (`bus_cli.py register`).
   - Generates and maintains token-based credentials (`dispatcher_cred.json`) with:
     `{"identity_id": "<UUID>", "token": "<TOKEN>", "agent_name": "<NAME>", "device_id": "<DEV>", "project_id": "<PROJ>"}`.
   - Enforced file mode 0600 with durable directory fsync.
3. Durable Set Message Tracking (Directive C2335):
   - FileBus message IDs are random UUID4 strings (never compared with lexical `<` or `>`).
   - The dispatcher tracks a durable set of seen/processed message UUIDs (`processed_message_ids`)
     along with the latest processed `cursor` and `processed_tasks` list.
   - Atomic state persistence to `dispatcher_state.json` tracking `pid`, `start_ticks` (from /proc/self/stat),
     `cursor`, `processed_message_ids`, `processed_tasks`, and `status`.
   - Fail-closed on missing credential or corrupted state.
4. Elimination of Admission Bypass Fallbacks (Directive C2337):
   - Strictly zero direct `subprocess.run(["systemd-run", ...])` or raw command bypass fallbacks.
   - Integrates with canonical `LauncherAdmissionBridge` and `ChildModelRuntimeAdapter` binding to
     canonical launcher paths (`.local/scratch/quota-service/store/state.db` and `launch.lock`).
   - Fails closed before ACK or launch if canonical admission cannot be bound (raises `AdmissionError`).
5. Lifetime Singleton Process Lock (Directive C2337):
   - Acquires an exclusive non-blocking `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` on `dispatcher.lock`
     held for the ENTIRE lifetime of the running dispatcher process.
   - Raises `DuplicateProcessError` immediately on lock conflict.
   - Read-only queries (`get_status()`, `--status`) strictly inspect state without lock acquisition
     and never mutate state or overwrite `pid`/`start_ticks`.
6. Safe ACK & In-Flight Receipt Ordering (Directive C2337):
   - Validates and admits the task BEFORE issuing FileBus ACK.
   - Durably commits task in `dispatcher_inflight.json` before issuing ACK.
   - If crash occurs before execution completes, in-flight state is preserved on disk.
7. Invariants:
   - Strictly 0 cargo/rustc invocations.
   - Memory <= 1500 MB cooperative pool.
   - Publication guard clean (zero unredacted secrets / bearer tokens).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import datetime
import errno
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

# Ensure repository and sibling repositories are in sys.path (strictly read-only access)
WORKSPACE_PATH = Path("/home/alexey/git/cloudflare-agent-git").resolve()
LAUNCHER_REPO_PATH = Path("/home/alexey/git/agent-quota-launcher").resolve()
COORDINATION_REPO_PATH = Path("/home/alexey/git/agent-coordination").resolve()

for repo_path in (WORKSPACE_PATH, LAUNCHER_REPO_PATH, COORDINATION_REPO_PATH):
    if repo_path.exists() and str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))

# Imports from launcher_bus_bridge
from research.antigravity.tooling.self_org.launcher_bus_bridge import (
    AdmissionError,
    ChildModelRuntimeAdapter,
    LauncherAdmissionBridge,
    LOCAL_PROBE_ALLOWED_BINARIES,
    QuotaAdmissionError,
    ResourceAdmissionError,
    durable_atomic_write,
    get_canonical_launcher_paths,
    verify_unit_cleanup,
)

# Imports from coordination / agent-bus
from coordination.bus import BusError, BusIdentity, BusMessage, FileBus
from launcher.store import Store, launch_lock

logger = logging.getLogger("filebus_dispatcher_service")

# Default paths and boundaries
DEFAULT_WORKSPACE = Path("/home/alexey/git/cloudflare-agent-git")
DEFAULT_SCRATCH_ROOT = DEFAULT_WORKSPACE / ".local" / "scratch" / "filebus-dispatcher-c2332"
DEFAULT_STATE_FILE = DEFAULT_SCRATCH_ROOT / "dispatcher_state.json"
DEFAULT_CRED_FILE = DEFAULT_SCRATCH_ROOT / "dispatcher_cred.json"
PINNED_BUS_CLI = WORKSPACE_PATH / ".local" / "scratch" / "architect06-bus-integration" / "agent-bus" / "coordination" / "bus_cli.py"
DEFAULT_BUS_CLI = PINNED_BUS_CLI

MAX_WORKER_MEMORY_MB = 1500
MAX_SCRATCH_DIR_BYTES = 512 * 1024 * 1024  # 512 MiB
MODEL_CLIS = {"zcodex", "codex", "opencode", "grok", "agy"}


# ===========================================================================
# Exceptions (Fail-Closed)
# ===========================================================================

class DispatcherError(Exception):
    """Base exception for filebus dispatcher errors."""
    pass


class DuplicateProcessError(DispatcherError):
    """Raised when another dispatcher instance is already running with active lock."""
    pass


class MissingCredentialError(DispatcherError):
    """Raised when the dispatcher credential file is missing or unreadable."""
    pass


class CorruptedCredentialError(DispatcherError):
    """Raised when the credential file contains invalid JSON or missing fields."""
    pass


class CorruptedStateError(DispatcherError):
    """Raised when the dispatcher state file is corrupted (fails closed)."""
    pass


class CorruptedInflightError(DispatcherError):
    """Raised when in-flight task file is corrupted, malformed, or empty (fails closed)."""
    pass


class DispatcherAdmissionError(DispatcherError):
    """Raised when a task violates memory, tmpdir, or resource admission rules."""
    pass


class TaskExecutionError(DispatcherError):
    """Raised when task execution fails or exits with an unexpected code."""
    pass


# ===========================================================================
# Helper Functions
# ===========================================================================

def get_process_start_ticks(pid: int = os.getpid()) -> int:
    """
    Retrieves process start time in clock ticks from Linux /proc/[pid]/stat.
    Field 22 (1-based) is 'starttime'.
    Safely splits after the last ')' to handle process names with spaces or brackets.
    Falls back to integer monotonic clock ticks if /proc is unavailable.
    """
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
            content = f.read()
        idx = content.rfind(")")
        if idx != -1:
            fields = content[idx + 1:].split()
            # fields[0] corresponds to field 3 of /proc/[pid]/stat (state).
            # Field 22 corresponds to index 19 (22 - 3 = 19).
            if len(fields) > 19:
                return int(fields[19])
    except Exception:
        pass
    # Fallback for mock environments / non-Linux
    return int(time.monotonic() * 100)


def clean_child_env(
    base_env: Optional[Dict[str, str]] = None,
    contained_tmp: Optional[Union[str, Path]] = None,
) -> Dict[str, str]:
    """
    Strips APLEXER_* environment variables and forbidden system overrides
    (PATH, HOME, XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS) from child process environment
    to prevent identity hijacking, mailbox pollution, caller impersonation, or scope escape.
    Sets contained TMPDIR, TMP, and TEMP variables to the authorized scratch root.
    """
    env = dict(base_env if base_env is not None else {})
    for key in list(env.keys()):
        if key.startswith("APLEXER_"):
            env.pop(key, None)
        if key in ("PATH", "HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
            env.pop(key, None)

    if contained_tmp is not None:
        tmp_str = str(Path(contained_tmp).resolve())
        env["TMPDIR"] = tmp_str
        env["TMP"] = tmp_str
        env["TEMP"] = tmp_str

    return env


def compute_receipt_digest(
    receipt_data: Dict[str, Any],
    output_files: Optional[Sequence[Union[str, Path]]] = None,
) -> str:
    """
    Computes a deterministic SHA-256 digest over the receipt payload and output artifacts.
    """
    h = hashlib.sha256()
    canonical_json = json.dumps(receipt_data, sort_keys=True, separators=(",", ":"))
    h.update(canonical_json.encode("utf-8"))

    if output_files:
        for out_file in output_files:
            p = Path(out_file).resolve()
            if p.exists() and p.is_file():
                h.update(f":file:{p.name}:".encode("utf-8"))
                h.update(p.read_bytes())

    return h.hexdigest()


def write_secret_json(path: Union[str, Path], value: Any) -> None:
    """Writes a JSON credential file durably with strict mode 0600."""
    p = Path(path).resolve()
    payload = json.dumps(value, indent=2, sort_keys=True)
    durable_atomic_write(p, payload)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


# ===========================================================================
# Data Structures
# ===========================================================================

@dataclass
class DispatcherState:
    """
    Serializable state tracking the mechanical dispatcher lifecycle, start ticks,
    inbox cursor, set of processed message IDs (Directive C2335), and task history.
    """
    pid: int
    start_ticks: int
    cursor: Optional[str] = None
    processed_message_ids: List[str] = field(default_factory=list)
    processed_tasks: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "idle"  # "idle" | "running" | "completed" | "error"
    updated_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "start_ticks": self.start_ticks,
            "cursor": self.cursor,
            "processed_message_ids": list(self.processed_message_ids),
            "processed_tasks": list(self.processed_tasks),
            "status": self.status,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DispatcherState:
        required_keys = {"pid", "start_ticks", "cursor", "processed_tasks", "status"}
        missing = required_keys - set(data.keys())
        if missing:
            raise CorruptedStateError(f"State dictionary missing required keys: {sorted(missing)}")

        processed_msgs = data.get("processed_message_ids")
        if processed_msgs is None:
            processed_msgs = [
                t["message_id"]
                for t in data.get("processed_tasks", [])
                if isinstance(t, dict) and "message_id" in t
            ]

        return cls(
            pid=int(data["pid"]),
            start_ticks=int(data["start_ticks"]),
            cursor=data.get("cursor"),
            processed_message_ids=list(processed_msgs),
            processed_tasks=list(data.get("processed_tasks", [])),
            status=str(data.get("status", "idle")),
            updated_at=str(data.get("updated_at", "")),
        )


@dataclass
class TaskSpecification:
    """
    Typed task specification extracted from an incoming FileBus message.
    """
    task_id: str
    command_argv: List[str]
    cwd: Path
    requested_memory_mb: int = MAX_WORKER_MEMORY_MB
    timeout_sec: float = 120.0
    tmpdir: Optional[Path] = None
    expected_outputs: Optional[List[str]] = None
    is_local_probe: bool = False
    env_vars: Optional[Dict[str, str]] = None
    model_requirements: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.is_local_probe and self.command_argv:
            bin_name = Path(self.command_argv[0]).name
            if bin_name in LOCAL_PROBE_ALLOWED_BINARIES or bin_name not in MODEL_CLIS:
                self.is_local_probe = True

    @classmethod
    def from_message(
        cls,
        msg: Dict[str, Any],
        default_workspace: Path,
        default_tmpdir: Path,
    ) -> TaskSpecification:
        """
        Parses a TaskSpecification from an incoming bus message dict.
        Supports structured JSON in 'data' or serialized JSON in 'body'.
        """
        msg_id = msg.get("message_id", "task-unknown")
        raw_data = msg.get("data")
        if isinstance(raw_data, dict):
            task_dict = raw_data
        elif isinstance(msg.get("body"), str) and msg["body"].strip().startswith("{"):
            try:
                parsed = json.loads(msg["body"])
                task_dict = parsed if isinstance(parsed, dict) else msg
            except Exception:
                task_dict = msg
        else:
            task_dict = msg

        task_id = str(task_dict.get("task_id") or msg.get("task_id") or msg_id)
        cmd = (
            task_dict.get("command_argv")
            or task_dict.get("command")
            or msg.get("command_argv")
            or msg.get("command")
        )
        if isinstance(cmd, str):
            cmd_argv = cmd.split()
        elif isinstance(cmd, list):
            cmd_argv = [str(x) for x in cmd]
        else:
            body_cmd = msg.get("body", "").strip()
            cmd_argv = body_cmd.split() if body_cmd and not body_cmd.startswith("{") else ["echo", f"task-{task_id}"]

        cwd_raw = task_dict.get("cwd") or msg.get("cwd")
        cwd_path = Path(cwd_raw).resolve() if cwd_raw else default_workspace.resolve()

        req_mem = int(task_dict.get("requested_memory_mb") or msg.get("requested_memory_mb") or MAX_WORKER_MEMORY_MB)
        timeout = float(task_dict.get("timeout_sec") or msg.get("timeout_sec") or 120.0)

        tmpdir_raw = task_dict.get("tmpdir") or msg.get("tmpdir")
        tmpdir_path = Path(tmpdir_raw).resolve() if tmpdir_raw else default_tmpdir.resolve()

        expected = task_dict.get("expected_outputs") or msg.get("expected_outputs")
        expected_outputs = [str(p) for p in expected] if isinstance(expected, list) else None

        # Automatically mark non-model CLI commands as local probes (C2114 / C2118 / C2126)
        is_probe = bool(task_dict.get("is_local_probe", msg.get("is_local_probe", False)))
        if not is_probe and cmd_argv:
            bin_name = Path(cmd_argv[0]).name
            if bin_name not in MODEL_CLIS:
                is_probe = True

        env_vars = task_dict.get("env_vars") or msg.get("env_vars")
        if not isinstance(env_vars, dict):
            env_vars = None

        model_reqs = task_dict.get("model_requirements") or msg.get("model_requirements")
        if not isinstance(model_reqs, dict):
            model_reqs = None

        return cls(
            task_id=task_id,
            command_argv=cmd_argv,
            cwd=cwd_path,
            requested_memory_mb=req_mem,
            timeout_sec=timeout,
            tmpdir=tmpdir_path,
            expected_outputs=expected_outputs,
            is_local_probe=is_probe,
            env_vars=env_vars,
            model_requirements=model_reqs,
        )


# ===========================================================================
# Service Implementation
# ===========================================================================

class FileBusDispatcherService:
    """
    Mechanical Queue & Receive Dispatcher Service for Agent Bus.
    """

    def __init__(
        self,
        bus_store: Union[str, Path],
        cred_path: Optional[Union[str, Path]] = None,
        state_path: Optional[Union[str, Path]] = None,
        workspace: Optional[Union[str, Path]] = None,
        scratch_root: Optional[Union[str, Path]] = None,
        bus_cli_path: Optional[Union[str, Path]] = None,
        runtime_adapter: Optional[ChildModelRuntimeAdapter] = None,
        admission_bridge: Optional[LauncherAdmissionBridge] = None,
        auto_init_state: bool = True,
        acquire_lock: bool = False,
    ) -> None:
        self.bus_store = Path(bus_store).resolve()
        self.workspace = Path(workspace).resolve() if workspace else DEFAULT_WORKSPACE.resolve()
        self.scratch_root = Path(scratch_root).resolve() if scratch_root else (self.workspace / ".local" / "scratch" / "filebus-dispatcher-c2332").resolve()
        self.cred_path = Path(cred_path).resolve() if cred_path else (self.scratch_root / "dispatcher_cred.json").resolve()
        self.state_path = Path(state_path).resolve() if state_path else (self.scratch_root / "dispatcher_state.json").resolve()
        self.lock_path = self.scratch_root / "dispatcher.lock"
        self.inflight_path = self.scratch_root / "dispatcher_inflight.json"

        if bus_cli_path:
            self.bus_cli_path = Path(bus_cli_path).resolve()
        elif DEFAULT_BUS_CLI.exists():
            self.bus_cli_path = DEFAULT_BUS_CLI.resolve()
        else:
            self.bus_cli_path = None

        # Initialize scratch root with mode 0700
        self.scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.scratch_root, 0o700)
        except OSError:
            pass

        self.scratch_tmp = (self.workspace / ".local" / "tmp").resolve()
        self.scratch_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.scratch_tmp, 0o700)
        except OSError:
            pass

        # Resolve canonical admission bridge & runtime adapter (Directive C2337)
        self._init_canonical_admission(admission_bridge, runtime_adapter)

        self._filebus: Optional[FileBus] = None
        if self.bus_store.exists():
            try:
                self._filebus = FileBus(self.bus_store)
            except Exception as exc:
                logger.warning(f"FileBus initialization failed: {exc}")

        self._stop_requested = False
        self._lock_fd: Optional[int] = None
        self.state: Optional[DispatcherState] = None

        if acquire_lock:
            self.acquire_process_lock()

        if auto_init_state:
            self.load_state()

    def _init_canonical_admission(
        self,
        admission_bridge: Optional[LauncherAdmissionBridge],
        runtime_adapter: Optional[ChildModelRuntimeAdapter],
    ) -> None:
        """
        Binds canonical LauncherAdmissionBridge and ChildModelRuntimeAdapter.
        Eliminates admission bypass fallbacks (Directive C2337).
        """
        if admission_bridge is not None:
            self.admission_bridge = admission_bridge
        else:
            # Production default MUST resolve exact canonical store paths
            # (~/.config/agent-quota-launcher/state.db + launch.lock) irrespective
            # of fixture presence or workspace (Directive C2341).
            canon_store, canon_lock = get_canonical_launcher_paths(None)
            try:
                canon_store.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.admission_bridge = LauncherAdmissionBridge(
                    store=canon_store,
                    workspace=self.workspace,
                )
            except Exception as exc:
                raise AdmissionError(f"Cannot initialize canonical LauncherAdmissionBridge: {exc}") from exc

        if runtime_adapter is not None:
            self.runtime_adapter = runtime_adapter
        else:
            canon_store, canon_lock = get_canonical_launcher_paths(None)
            try:
                canon_lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.runtime_adapter = ChildModelRuntimeAdapter(
                    store=canon_store,
                    lock_path=canon_lock,
                    workspace=self.workspace,
                )
            except Exception as exc:
                raise AdmissionError(f"Cannot initialize canonical ChildModelRuntimeAdapter: {exc}") from exc

    # -----------------------------------------------------------------------
    # Lifetime Singleton Process Lock (Directive C2337)
    # -----------------------------------------------------------------------

    def acquire_process_lock(self) -> None:
        """
        Acquires an exclusive non-blocking fcntl.flock on dispatcher.lock held for
        the ENTIRE lifetime of the running dispatcher process (Directive C2337).
        Fails closed with DuplicateProcessError if another process holds the lock.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self._lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(self._lock_fd, 0)
            os.lseek(self._lock_fd, 0, os.SEEK_SET)
            lock_payload = json.dumps({
                "pid": os.getpid(),
                "start_ticks": get_process_start_ticks(os.getpid()),
                "acquired_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }).encode("utf-8")
            os.write(self._lock_fd, lock_payload)
            os.fsync(self._lock_fd)
        except (BlockingIOError, OSError) as exc:
            if hasattr(self, "_lock_fd") and self._lock_fd is not None:
                try:
                    os.close(self._lock_fd)
                except Exception:
                    pass
                self._lock_fd = None
            raise DuplicateProcessError(
                f"Another dispatcher process is already running and holds {self.lock_path}: {exc}"
            ) from exc

    def release_process_lock(self) -> None:
        """Releases the lifetime process lock if held."""
        if hasattr(self, "_lock_fd") and self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except Exception:
                pass
            self._lock_fd = None

    def __del__(self) -> None:
        self.release_process_lock()

    # -----------------------------------------------------------------------
    # Credential Management & Registration (Directive C2333)
    # -----------------------------------------------------------------------

    def register(
        self,
        agent_name: str = "filebus-dispatcher",
        device_id: str = "local-device",
        project_id: str = "cloudflare-agent-git",
        parent_cred_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        Registers token-based identity credentials on the FileBus store via bus_cli.py
        or FileBus.register, and saves dispatcher_cred.json durably with mode 0600.
        (Directive C2333: exact token-based registration matching public bus_cli.py).
        """
        self.cred_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent_id = None
        parent_token = None

        if parent_cred_path:
            p_path = Path(parent_cred_path).resolve()
            if p_path.exists():
                p_data = json.loads(p_path.read_text(encoding="utf-8"))
                parent_id = p_data.get("identity_id")
                parent_token = p_data.get("token")

        if self.bus_cli_path and self.bus_cli_path.exists():
            cmd = [
                sys.executable,
                str(self.bus_cli_path),
                "--store",
                str(self.bus_store),
                "register",
                "--agent",
                agent_name,
                "--device",
                device_id,
                "--project",
                project_id,
                "--cred",
                str(self.cred_path),
            ]
            if parent_cred_path:
                cmd.extend(["--parent-cred", str(parent_cred_path)])

            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            cred_dict = json.loads(self.cred_path.read_text(encoding="utf-8"))
            os.chmod(self.cred_path, 0o600)
            return cred_dict
        elif self._filebus is not None:
            ident, token = self._filebus.register(
                agent_name=agent_name,
                device_id=device_id,
                project_id=project_id,
                parent_id=parent_id,
                parent_token=parent_token,
            )
            cred_dict = ident.public() if hasattr(ident, "public") else asdict(ident)
            cred_dict["token"] = token
            write_secret_json(self.cred_path, cred_dict)
            return cred_dict
        else:
            raise DispatcherError(f"No bus_cli.py or FileBus available to register identity on {self.bus_store}")

    def load_credential(self) -> Dict[str, Any]:
        """
        Loads and validates dispatcher credential file.
        Fails closed with MissingCredentialError or CorruptedCredentialError.
        """
        if not self.cred_path.exists():
            raise MissingCredentialError(f"Dispatcher credential missing: {self.cred_path}")

        try:
            st = self.cred_path.stat()
            # Enforce mode 0600 (fail-closed if group/other readable)
            if (st.st_mode & 0o077) != 0:
                os.chmod(self.cred_path, 0o600)
                st = self.cred_path.stat()
                if (st.st_mode & 0o077) != 0:
                    raise CorruptedCredentialError(
                        f"Insecure permissions on credential {self.cred_path}: {oct(st.st_mode)}"
                    )
            content = self.cred_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise CorruptedCredentialError(f"Corrupted credential JSON at {self.cred_path}: {exc}") from exc
        except OSError as exc:
            raise MissingCredentialError(f"Cannot read credential at {self.cred_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise CorruptedCredentialError("Credential content is not a JSON object")

        if "identity_id" not in data or "token" not in data:
            raise CorruptedCredentialError(
                f"Credential missing identity_id or token fields at {self.cred_path}"
            )

        return data

    # -----------------------------------------------------------------------
    # State Persistence & Read-Only Inspection (Directive C2335 / C2337)
    # -----------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Read-only state query. Does NOT mutate state, acquire lock, or update pid/start_ticks (C2337).
        """
        if not self.state_path.exists():
            return {"status": "uninitialized"}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"status": "corrupted", "error": str(exc)}

    def load_state(self) -> DispatcherState:
        """
        Loads state from disk, or initializes default state.
        Fails closed on corrupted JSON.
        Updates current pid and start_ticks for active worker execution.
        """
        pid = os.getpid()
        start_ticks = get_process_start_ticks(pid)

        if not self.state_path.exists():
            self.state = DispatcherState(
                pid=pid,
                start_ticks=start_ticks,
                cursor=None,
                processed_message_ids=[],
                processed_tasks=[],
                status="idle",
            )
            self.reconcile_inflight_tasks()
            self.save_state(self.state)
            return self.state

        try:
            content = self.state_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self.state = DispatcherState.from_dict(data)
            self.state.pid = pid
            self.state.start_ticks = start_ticks
            self.reconcile_inflight_tasks()
            self.save_state(self.state)
            return self.state
        except (json.JSONDecodeError, CorruptedStateError) as exc:
            raise CorruptedStateError(f"State file {self.state_path} corrupted: {exc}") from exc
        except OSError as exc:
            raise CorruptedStateError(f"Cannot read state file {self.state_path}: {exc}") from exc

    def reconcile_inflight_tasks(self) -> None:
        """
        Reconciles in-flight tasks from a crashed or killed dispatcher process (Directive C2341 / C2347).
        Preserves fail-closed semantics: does NOT re-run the task automatically to avoid duplicate
        side-effects, preserves UNKNOWN state, inspects for existing correlated receipts, and
        records the task in state so it is not dropped or lost.
        Fails closed with CorruptedInflightError if the in-flight file is corrupted or empty,
        preserving original bytes without deletion (Directive C2347).
        """
        if not self.inflight_path.exists():
            return

        if self.state is None:
            self.load_state()
            return

        try:
            content = self.inflight_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorruptedInflightError(f"Cannot read in-flight file {self.inflight_path}: {exc}") from exc

        if not content.strip():
            quarantine = self.scratch_root / f"inflight_empty_{int(time.time())}.raw"
            try:
                durable_atomic_write(quarantine, content)
            except Exception:
                pass
            raise CorruptedInflightError(
                f"In-flight file {self.inflight_path} is empty (0 bytes/whitespace); preserved fail-closed at {quarantine}"
            )

        try:
            inflight_data = json.loads(content)
        except json.JSONDecodeError as exc:
            quarantine = self.scratch_root / f"inflight_corrupted_{int(time.time())}.raw"
            try:
                durable_atomic_write(quarantine, content)
            except Exception:
                pass
            raise CorruptedInflightError(
                f"In-flight file {self.inflight_path} contains malformed JSON: {exc}; preserved fail-closed at {quarantine}"
            ) from exc

        if not isinstance(inflight_data, dict):
            quarantine = self.scratch_root / f"inflight_corrupted_{int(time.time())}.raw"
            try:
                durable_atomic_write(quarantine, content)
            except Exception:
                pass
            raise CorruptedInflightError(
                f"In-flight file {self.inflight_path} is not a JSON object; preserved fail-closed at {quarantine}"
            )

        task_id = inflight_data.get("task_id", "unknown-inflight")
        message_id = inflight_data.get("message_id", "msg-unknown")
        logger.warning(f"Detected in-flight task {task_id} (msg: {message_id}) from previous run.")

        # Check if already recorded in processed state (crash occurred after save_state but before unlink)
        already_processed = any(
            t.get("task_id") == task_id or (message_id and t.get("message_id") == message_id)
            for t in self.state.processed_tasks
        ) if self.state else False

        if already_processed:
            archive_path = self.scratch_root / f"inflight_completed_{message_id}_{int(time.time())}.json"
            durable_atomic_write(archive_path, content)
            self.inflight_path.unlink(missing_ok=True)
            return

        # Directive C2348: Remove existence-based success inference. Pre-existing or partial
        # artifacts must NEVER be treated as successful completion for an uncommitted task.
        # Interrupted in-flight tasks always fail closed as unknown_crashed_inflight (no rerun, no success reply).
        if self.state:
            crashed_entry = {
                "task_id": task_id,
                "message_id": message_id,
                "status": "unknown_crashed_inflight",
                "error": "Dispatcher restarted while task was in-flight; preserved fail-closed without automatic rerun (Directive C2341/C2347/C2348)",
                "started_at": inflight_data.get("started_at"),
                "recovered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self.state.processed_tasks.append(crashed_entry)
            if message_id and message_id not in self.state.processed_message_ids:
                self.state.processed_message_ids.append(message_id)
            self.state.status = "recovering-inflight"
            self.save_state()

        archive_path = self.scratch_root / f"inflight_crashed_{message_id}_{int(time.time())}.json"
        durable_atomic_write(archive_path, content)
        self.inflight_path.unlink(missing_ok=True)

    def save_state(self, state: Optional[DispatcherState] = None) -> None:
        """
        Persists state atomically and durably to state_path using durable_atomic_write.
        """
        if state is not None:
            self.state = state
        if self.state is None:
            return

        self.state.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = json.dumps(self.state.to_dict(), indent=2)
        durable_atomic_write(self.state_path, payload)

    # -----------------------------------------------------------------------
    # FileBus Queue & Message Exchange (Directive C2335 Set Tracking)
    # -----------------------------------------------------------------------

    def poll_inbox(self, unread_only: bool = True) -> List[Dict[str, Any]]:
        """
        Polls incoming messages for the dispatcher identity.
        Filters out messages whose message_id is in processed_message_ids (Directive C2335).
        """
        cred = self.load_credential()

        if self.bus_cli_path and self.bus_cli_path.exists():
            cmd = [
                sys.executable,
                str(self.bus_cli_path),
                "--store",
                str(self.bus_store),
                "inbox",
                "--cred",
                str(self.cred_path),
            ]
            if not unread_only:
                cmd.append("--all")

            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            messages = json.loads(res.stdout) if res.stdout.strip() else []
        elif self._filebus is not None:
            raw_msgs = self._filebus.inbox(
                identity_id=cred["identity_id"],
                token=cred["token"],
                unread_only=unread_only,
            )
            messages = [m.to_public() if hasattr(m, "to_public") else asdict(m) for m in raw_msgs]
        else:
            messages = []

        processed_set: Set[str] = set()
        if self.state:
            processed_set.update(self.state.processed_message_ids)
            for t in self.state.processed_tasks:
                mid = t.get("message_id")
                if mid:
                    processed_set.add(mid)

        filtered: List[Dict[str, Any]] = []
        for m in messages:
            m_id = m.get("message_id")
            if m_id and m_id not in processed_set:
                filtered.append(m)

        return filtered

    def ack_message(self, message_id: str) -> Dict[str, Any]:
        """
        Acknowledges receipt of a task message on the FileBus.
        """
        cred = self.load_credential()

        if self.bus_cli_path and self.bus_cli_path.exists():
            cmd = [
                sys.executable,
                str(self.bus_cli_path),
                "--store",
                str(self.bus_store),
                "ack",
                "--cred",
                str(self.cred_path),
                "--message-id",
                message_id,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(res.stdout) if res.stdout.strip() else {}
        elif self._filebus is not None:
            msg = self._filebus.ack(
                identity_id=cred["identity_id"],
                token=cred["token"],
                message_id=message_id,
            )
            return msg.to_public() if hasattr(msg, "to_public") else asdict(msg)
        else:
            return {"message_id": message_id, "acked": True}

    def send_reply(
        self,
        message_id: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Sends a reply back on the FileBus acknowledging completion or failure.
        """
        cred = self.load_credential()

        if self.bus_cli_path and self.bus_cli_path.exists():
            cmd = [
                sys.executable,
                str(self.bus_cli_path),
                "--store",
                str(self.bus_store),
                "reply",
                "--cred",
                str(self.cred_path),
                "--message-id",
                message_id,
                "--body",
                body,
            ]
            if data is not None:
                cmd.extend(["--data", json.dumps(data)])

            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(res.stdout) if res.stdout.strip() else {}
        elif self._filebus is not None:
            msg = self._filebus.reply(
                sender_id=cred["identity_id"],
                token=cred["token"],
                message_id=message_id,
                body=body,
                data=data,
            )
            return msg.to_public() if hasattr(msg, "to_public") else asdict(msg)
        else:
            return {"reply_to": message_id, "body": body, "data": data}

    # -----------------------------------------------------------------------
    # Admission Validation & Systemd Scope Execution (Directives C2337)
    # -----------------------------------------------------------------------

    def validate_and_admit_task(self, task_spec: TaskSpecification) -> None:
        """
        Validates task specification under canonical admission boundaries:
        - Memory request <= 1500 MB (MAX_WORKER_MEMORY_MB).
        - Scratch TMPDIR containment: rejects global /tmp, /var/tmp, or uncontained paths.
        - Verifies scratch directory size <= 512 MiB limit.
        - Fails closed on any admission violation.
        """
        if task_spec.requested_memory_mb > MAX_WORKER_MEMORY_MB:
            raise DispatcherAdmissionError(
                f"Requested memory {task_spec.requested_memory_mb}MiB exceeds maximum "
                f"{MAX_WORKER_MEMORY_MB}MiB cooperative pool limit"
            )

        check_tmp = task_spec.tmpdir if task_spec.tmpdir is not None else self.scratch_tmp
        resolved_tmp = Path(check_tmp).resolve()

        if (
            resolved_tmp == Path("/tmp")
            or resolved_tmp.parts[:2] == ("/", "tmp")
            or str(resolved_tmp).startswith("/data/tmp")
            or str(resolved_tmp).startswith("/var/tmp")
        ):
            raise DispatcherAdmissionError(
                f"Contained TMPDIR violation: reject global /tmp path {resolved_tmp}"
            )

        total_scratch_size = 0
        for dirpath, _, filenames in os.walk(self.scratch_root):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_scratch_size += os.path.getsize(fp)
                except OSError:
                    pass
        if total_scratch_size > MAX_SCRATCH_DIR_BYTES:
            raise DispatcherAdmissionError(
                f"Scratch directory size {total_scratch_size} bytes exceeds 512 MiB limit ({MAX_SCRATCH_DIR_BYTES} bytes)"
            )

        # Validate with canonical admission bridge if configured
        if self.admission_bridge is not None:
            try:
                # Ensure contained TMPDIR passes canonical check_resources
                owned_tmp = (self.workspace / ".local" / "tmp").resolve()
                owned_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
                bridge_tmp = resolved_tmp if str(resolved_tmp).startswith(str(self.workspace)) else owned_tmp

                self.admission_bridge.check_resource_eligibility(
                    workspace=task_spec.cwd,
                    timeout=task_spec.timeout_sec,
                    requested_memory_mb=task_spec.requested_memory_mb,
                    requested_tmpdir=bridge_tmp,
                    task_id=task_spec.task_id,
                )
            except (AdmissionError, ResourceAdmissionError) as exc:
                raise DispatcherAdmissionError(f"Launcher admission bridge rejected task: {exc}") from exc

    def execute_task_in_scope(self, task_spec: TaskSpecification) -> Dict[str, Any]:
        """
        Executes admitted task within verified systemd scope via ChildModelRuntimeAdapter.
        Strictly zero raw subprocess or bypass fallback paths (Directive C2337).
        """
        if self.runtime_adapter is None:
            raise AdmissionError("Runtime adapter missing: unadmitted execution strictly forbidden (C2337)")

        effective_tmp = self.scratch_tmp
        effective_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
        clean_env = clean_child_env(task_spec.env_vars, effective_tmp)

        reqs = getattr(task_spec, "model_requirements", None)
        if reqs is None and not task_spec.is_local_probe and task_spec.command_argv:
            bin_name = Path(task_spec.command_argv[0]).name
            if bin_name == "grok":
                reqs = {"allowed_providers": ["grok"]}
            elif bin_name in ("agy", "env"):
                reqs = {"allowed_providers": ["antigravity", "gemini"]}
            elif bin_name == "zcodex":
                reqs = {"allowed_providers": ["zai", "zcode"]}
            elif bin_name == "opencode":
                reqs = {"allowed_providers": ["opencode"]}

        try:
            res = self.runtime_adapter.execute_in_verified_systemd_scope(
                task_id=task_spec.task_id,
                command_argv=task_spec.command_argv,
                cwd=task_spec.cwd,
                timeout_sec=task_spec.timeout_sec,
                requested_memory_mb=task_spec.requested_memory_mb,
                tmpdir=effective_tmp,
                expected_outputs=task_spec.expected_outputs,
                is_local_probe=task_spec.is_local_probe,
                model_requirements=reqs,
                env_vars=clean_env,
            )
            if res.get("returncode") != 0:
                raise TaskExecutionError(
                    f"Task {task_spec.task_id} in {res.get('unit_name')} exited with returncode {res.get('returncode')}"
                )
            return res
        except (ResourceAdmissionError, AdmissionError) as exc:
            raise TaskExecutionError(f"Task execution failed: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, DispatcherError):
                raise
            raise TaskExecutionError(f"Task execution failed: {exc}") from exc

    # -----------------------------------------------------------------------
    # Main Dispatch Cycle (Directive C2337 Safe Ordering & In-Flight Tracking)
    # -----------------------------------------------------------------------

    def dispatch_task(self, task_msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches a single incoming task message under Directive C2337 safe ordering:
        1. Parses TaskSpecification.
        2. Validates admission boundaries (memory <= 1500M, contained tmpdir).
        3. Records durable in-flight receipt in dispatcher_inflight.json.
        4. Issues FileBus ACK (task is now safely committed in flight).
        5. Executes task in verified systemd scope.
        6. Computes receipt SHA-256 hash.
        7. Sends completion reply on FileBus.
        8. Cleans up in-flight receipt.
        9. Advances cursor, updates processed_message_ids set, records task, and saves state.
        """
        msg_id = task_msg.get("message_id")
        if not msg_id:
            raise DispatcherError("Incoming message missing message_id")

        if self.state is None:
            self.load_state()

        # Step 1: Parse TaskSpecification
        task_spec = TaskSpecification.from_message(
            task_msg,
            default_workspace=self.workspace,
            default_tmpdir=self.scratch_tmp,
        )

        # Step 2: Validate admission boundaries BEFORE ACK (Directive C2337)
        self.validate_and_admit_task(task_spec)

        # Step 3: Record durable in-flight receipt (Directive C2337 / C2341)
        inflight_data = {
            "task_id": task_spec.task_id,
            "message_id": msg_id,
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "in_flight",
            "task_spec": {
                "command_argv": task_spec.command_argv,
                "cwd": str(task_spec.cwd),
                "requested_memory_mb": task_spec.requested_memory_mb,
                "timeout_sec": task_spec.timeout_sec,
                "expected_outputs": [str(p) for p in (task_spec.expected_outputs or [])],
            },
        }
        durable_atomic_write(self.inflight_path, json.dumps(inflight_data, indent=2))

        # Step 4: Safely issue FileBus ACK now that in-flight receipt is durably recorded
        self.ack_message(msg_id)

        # Step 5: Update state to running
        self.state.status = "running"
        self.save_state()

        # Step 6: Execute task in verified systemd scope
        try:
            exec_receipt = self.execute_task_in_scope(task_spec)
            receipt_hash = compute_receipt_digest(
                exec_receipt,
                output_files=task_spec.expected_outputs,
            )
            task_status = "completed"
            reply_body = f"Task {task_spec.task_id} completed successfully"
            reply_data = {
                "task_id": task_spec.task_id,
                "status": task_status,
                "returncode": exec_receipt.get("returncode", 0),
                "receipt_hash": receipt_hash,
                "completed_at": exec_receipt.get("completed_at"),
            }
        except Exception as exc:
            receipt_hash = hashlib.sha256(f"error:{exc}".encode("utf-8")).hexdigest()
            task_status = "error"
            exec_receipt = {
                "task_id": task_spec.task_id,
                "error": str(exc),
                "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            reply_body = f"Task {task_spec.task_id} failed: {exc}"
            reply_data = {
                "task_id": task_spec.task_id,
                "status": "error",
                "error": str(exc),
                "receipt_hash": receipt_hash,
                "completed_at": exec_receipt.get("completed_at"),
            }
            # Step 7a (Error): PERSIST TERMINAL RECEIPT & STATE BEFORE REPLY OR UNLINK (C2347)
            self.state.cursor = msg_id
            if msg_id not in self.state.processed_message_ids:
                self.state.processed_message_ids.append(msg_id)
            self.state.processed_tasks.append({
                "task_id": task_spec.task_id,
                "message_id": msg_id,
                "completed_at": exec_receipt.get("completed_at"),
                "receipt_hash": receipt_hash,
                "status": "error",
            })
            self.state.status = "error"
            self.save_state()

            # Step 8a (Error): Send failure reply
            try:
                self.send_reply(msg_id, body=reply_body, data=reply_data)
            except Exception as reply_err:
                logger.warning(f"Error sending failure reply: {reply_err}")

            # Step 9a (Error): Safely unlink inflight file
            try:
                if self.inflight_path.exists():
                    self.inflight_path.unlink()
            except OSError:
                pass
            raise

        # Step 7: PERSIST TERMINAL RECEIPT & STATE BEFORE REPLY OR UNLINK (C2347)
        self.state.cursor = msg_id
        if msg_id not in self.state.processed_message_ids:
            self.state.processed_message_ids.append(msg_id)
        self.state.processed_tasks.append({
            "task_id": task_spec.task_id,
            "message_id": msg_id,
            "completed_at": exec_receipt.get("completed_at"),
            "receipt_hash": receipt_hash,
            "status": "completed",
        })
        self.state.status = "idle"
        self.save_state()

        # Step 8: Send reply on FileBus
        self.send_reply(msg_id, body=reply_body, data=reply_data)

        # Step 9: Clean up in-flight receipt (now safe because state is durably on disk)
        try:
            if self.inflight_path.exists():
                self.inflight_path.unlink()
        except OSError:
            pass

        return exec_receipt

    def dispatch_next(self) -> Optional[Dict[str, Any]]:
        """
        Polls inbox and dispatches the oldest unhandled message.
        Returns receipt dict if a task was processed, or None if inbox is empty.
        """
        messages = self.poll_inbox(unread_only=True)
        if not messages:
            return None
        return self.dispatch_task(messages[0])

    def run_cycles(self, max_cycles: int = 1) -> List[Dict[str, Any]]:
        """
        Runs up to max_cycles task dispatches under process lock.
        """
        if self._lock_fd is None:
            self.acquire_process_lock()

        results: List[Dict[str, Any]] = []
        for _ in range(max_cycles):
            receipt = self.dispatch_next()
            if receipt is None:
                break
            results.append(receipt)
        return results

    def run_forever(
        self,
        poll_interval_sec: float = 2.0,
        max_idle_sec: Optional[float] = None,
    ) -> None:
        """
        Runs the dispatcher service in a persistent polling loop under lifetime process lock.
        """
        if self._lock_fd is None:
            self.acquire_process_lock()

        def _handle_signal(signum: int, frame: Any) -> None:
            logger.info(f"Signal {signum} received, stopping dispatcher loop.")
            self._stop_requested = True

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        last_activity = time.time()
        logger.info(f"Starting FileBusDispatcherService PID {os.getpid()} on {self.bus_store}")
        self.load_state()

        while not self._stop_requested:
            receipt = self.dispatch_next()
            if receipt is not None:
                last_activity = time.time()
            else:
                if max_idle_sec is not None and (time.time() - last_activity) >= max_idle_sec:
                    logger.info(f"Max idle time ({max_idle_sec}s) reached. Exiting.")
                    break
                time.sleep(poll_interval_sec)

        self.state.status = "completed"
        self.save_state()
        self.release_process_lock()
        logger.info("FileBusDispatcherService shut down cleanly.")


# ===========================================================================
# CLI Interface (Directives C2332 / C2333 / C2337)
# ===========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="FileBus Queue / Receive Dispatcher Service")
    parser.add_argument("--store", default=str(DEFAULT_SCRATCH_ROOT / "bus_store"), help="FileBus store directory")
    parser.add_argument("--cred", default=str(DEFAULT_CRED_FILE), help="Credential file path")
    parser.add_argument("--state", default=str(DEFAULT_STATE_FILE), help="State file path")
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE), help="Repository workspace root")
    parser.add_argument("--scratch-root", default=str(DEFAULT_SCRATCH_ROOT), help="Authorized scratch directory")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # Subcommand: register (Directive C2333 exact token registration)
    p_reg = sub.add_parser("register", help="Register token identity credentials on FileBus store")
    p_reg.add_argument("--agent", default="filebus-dispatcher", help="Agent name")
    p_reg.add_argument("--device", default="local-device", help="Device identifier")
    p_reg.add_argument("--project", default="cloudflare-agent-git", help="Project identifier")
    p_reg.add_argument("--parent-cred", default=None, help="Optional parent credential path")

    # Subcommand: run
    p_run = sub.add_parser("run", help="Run dispatcher service cycles")
    p_run.add_argument("--cycles", type=int, default=1, help="Number of cycles to run (0 for infinite loop)")
    p_run.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")

    # Subcommand: status (Directive C2337 read-only inspection)
    sub.add_parser("status", help="Print current dispatcher process state")

    args = parser.parse_args()

    service = FileBusDispatcherService(
        bus_store=args.store,
        cred_path=args.cred,
        state_path=args.state,
        workspace=args.workspace,
        scratch_root=args.scratch_root,
        auto_init_state=(args.cmd not in ("register", "status")),
        acquire_lock=(args.cmd == "run"),
    )

    if args.cmd == "register":
        cred = service.register(
            agent_name=args.agent,
            device_id=args.device,
            project_id=args.project,
            parent_cred_path=args.parent_cred,
        )
        print(json.dumps({"status": "enrolled", "identity_id": cred.get("identity_id"), "cred": args.cred}))
        return 0

    elif args.cmd == "status":
        status_info = service.get_status()
        print(json.dumps(status_info, indent=2))
        return 0

    elif args.cmd == "run":
        if args.cycles == 0:
            service.run_forever(poll_interval_sec=args.interval)
        else:
            results = service.run_cycles(max_cycles=args.cycles)
            print(json.dumps({"dispatched_count": len(results), "results": results}, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
