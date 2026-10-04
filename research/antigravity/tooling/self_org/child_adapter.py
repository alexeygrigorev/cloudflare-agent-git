#!/usr/bin/env python3
"""
Decoupled Child Process Execution Adapter Bridge (C2047 / C2051 / C2053).
Enables headless, out-of-band task execution decoupled from interactive TUI aplexer panes.

Strict Invariants & Containment (C2053):
1. Resource Admission: Enforces MemAvailable >= 10GiB, free disk >= 50GiB, memory <= 1500MB,
   and strictly rejects /tmp in favor of owned repository scratch.
2. Process Group Containment: Spawns child in a new process group (start_new_session=True).
   Termination, timeout, or lease loss signals the entire process group (os.killpg).
3. Bounded Logging: Streams subprocess stdout/stderr directly to a private bounded disk log;
   never buffers unbounded child output in memory (no unbounded capture_output).
4. Environment Isolation: Strips all inherited APLEXER_* session and mailbox authority.
5. Exact Freshness Check: Verifies artifact mtime is fresh (>= start_time - 1.0s) and >= 16 bytes.
   Pre-existing files or junk are strictly rejected.
6. Lease-Loss Termination & CAS Validation: If heartbeat loses the lease, child process group is
   immediately killed. Final atomic fence check validates the lease is still held before return.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Union

from .lease_manager import FencingTokenMismatchError, LeaseError, LeaseExpiredError, LeaseManager

logger = logging.getLogger("child_adapter")

# Resource Admission Constants (Conservative GiB/MiB)
MAX_WORKER_MEMORY_MB = 1500
MIN_MEM_AVAILABLE_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB
MIN_DISK_FREE_BYTES = 50 * 1024 * 1024 * 1024      # 50 GiB
DISK_SPIKE_BYTES = 512 * 1024 * 1024               # 512 MiB
MAX_LOG_BYTES = 32 * 1024 * 1024                   # 32 MiB bounded log ceiling


class ChildExecutionError(Exception):
    pass


class AdmissionRejectionError(ChildExecutionError):
    pass


def get_mem_available_bytes() -> int:
    """Reads MemAvailable from /proc/meminfo in bytes, failing closed to 0."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
    except Exception as exc:
        logger.warning("Failed to read /proc/meminfo: %s", exc)
    return 0


def get_proc_rss_bytes(pid: int) -> int:
    """Reads VmRSS from /proc/{pid}/status in bytes, failing closed to 0."""
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
    except Exception:
        pass
    return 0


def get_pgid_rss_bytes(pgid: int) -> int:
    """Sums VmRSS across all processes belonging to the specified process group."""
    total_rss = 0
    try:
        for entry in os.scandir("/proc"):
            if entry.name.isdigit():
                try:
                    pid = int(entry.name)
                    if os.getpgid(pid) == pgid:
                        total_rss += get_proc_rss_bytes(pid)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
    except Exception:
        pass
    return total_rss


def _make_child_preexec(requested_memory_mb: int):
    """Sets OS-level address space and file size limits in child process."""
    def _preexec():
        import resource
        max_bytes = requested_memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_LOG_BYTES, MAX_LOG_BYTES))
        except (ValueError, OSError):
            pass
    return _preexec


def check_child_admission(
    requested_memory_mb: int,
    cwd_path: Path,
    tmp_path: Path,
    repo_root: Optional[Path] = None,
) -> None:
    """
    Validates host resource admission gates before child subprocess spawn.
    """
    if requested_memory_mb > MAX_WORKER_MEMORY_MB:
        raise AdmissionRejectionError(f"Requested worker memory {requested_memory_mb}MiB > {MAX_WORKER_MEMORY_MB}MiB limit")

    mem_avail = get_mem_available_bytes()
    req_mem_bytes = requested_memory_mb * 1024 * 1024
    if mem_avail - req_mem_bytes < MIN_MEM_AVAILABLE_BYTES:
        raise AdmissionRejectionError(f"Host MemAvailable {mem_avail // (1024*1024)}MiB would drop below 10GiB floor")

    # Anti-/tmp check
    tmp_resolved = tmp_path.resolve()
    if tmp_resolved == Path("/tmp") or tmp_resolved.parts[:2] == ("/", "tmp"):
        raise AdmissionRejectionError("Child execution strictly rejects /tmp (must use owned scratch root)")

    if repo_root:
        owned_root = (repo_root.resolve() / ".local")
        if not tmp_resolved.is_relative_to(owned_root):
            raise AdmissionRejectionError(f"TMPDIR {tmp_resolved} must resolve under owned {owned_root}")

    # Check directory existence or parent existence for disk usage
    cwd_check_dir = cwd_path if cwd_path.exists() else cwd_path.parent
    tmp_check_dir = tmp_path if tmp_path.exists() else tmp_path.parent

    cwd_stat = shutil.disk_usage(str(cwd_check_dir))
    tmp_stat = shutil.disk_usage(str(tmp_check_dir))

    if cwd_stat.free < MIN_DISK_FREE_BYTES + DISK_SPIKE_BYTES:
        raise AdmissionRejectionError(f"CWD filesystem free {cwd_stat.free // (1024*1024)}MiB < 50GiB + spike")
    if tmp_stat.free < MIN_DISK_FREE_BYTES + DISK_SPIKE_BYTES:
        raise AdmissionRejectionError(f"TMPDIR filesystem free {tmp_stat.free // (1024*1024)}MiB < 50GiB + spike")


class ChildAdapter:
    def __init__(
        self,
        task_id: str,
        executor_tag: str,
        fence_token: int,
        project_id: str,
        lease_manager: Optional[LeaseManager] = None,
        heartbeat_interval_sec: float = 5.0,
        lease_ttl_sec: float = 30.0,
        scratch_dir: Optional[Union[str, Path]] = None,
        requested_memory_mb: int = 1500,
        admission_bridge: Optional[Any] = None,
        bus_bridge: Optional[Any] = None,
    ) -> None:
        self.task_id = str(task_id)
        self.executor_tag = str(executor_tag)
        self.fence_token = int(fence_token)
        self.project_id = str(project_id)
        self.lease_manager = lease_manager or LeaseManager(default_ttl=lease_ttl_sec)
        self.heartbeat_interval_sec = float(heartbeat_interval_sec)
        self.lease_ttl_sec = float(lease_ttl_sec)
        self.scratch_dir = Path(scratch_dir).resolve() if scratch_dir else Path("/home/alexey/git/cloudflare-agent-git/.local/scratch/child_adapter").resolve()
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.requested_memory_mb = int(requested_memory_mb)
        self.admission_bridge = admission_bridge
        self.bus_bridge = bus_bridge

        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._lease_lost = False
        self._lease_loss_reason: Optional[str] = None
        self._active_proc: Optional[subprocess.Popen] = None
        self._active_pgid: Optional[int] = None

    def _start_heartbeat(self, log_file_path: Optional[Path] = None) -> None:
        def _loop():
            max_rss_bytes = self.requested_memory_mb * 1024 * 1024
            while not self._stop_heartbeat.wait(self.heartbeat_interval_sec):
                # 1. Lease renewal
                try:
                    self.lease_manager.heartbeat(
                        task_id=self.task_id,
                        holder=self.executor_tag,
                        fence_token=self.fence_token,
                    )
                    logger.debug("Heartbeat renewed for task %s (fence=%d)", self.task_id, self.fence_token)
                except LeaseError as exc:
                    logger.error("Heartbeat rejected for %s: %s (stopping child process group)", self.task_id, exc)
                    self._lease_lost = True
                    self._lease_loss_reason = str(exc)
                    self._kill_process_group()
                    break
                except Exception as exc:
                    logger.warning("Heartbeat error for %s: %s", self.task_id, exc)

                # 2. Child RSS memory monitoring across entire process group (C2054)
                pgid = self._active_pgid
                if pgid is not None:
                    rss = get_pgid_rss_bytes(pgid)
                    if rss > max_rss_bytes:
                        logger.error(
                            "Child process group %d RSS %d MiB exceeded limit %d MiB (terminating group)",
                            pgid, rss // (1024 * 1024), self.requested_memory_mb,
                        )
                        self._lease_lost = True
                        self._lease_loss_reason = f"Child group RSS {rss // (1024*1024)}MiB exceeded limit {self.requested_memory_mb}MiB"
                        self._kill_process_group()
                        break

                # 3. Bounded Log File monitoring (C2054)
                if log_file_path and log_file_path.is_file():
                    try:
                        cur_log_size = log_file_path.stat().st_size
                        if cur_log_size > MAX_LOG_BYTES:
                            logger.error(
                                "Child log size %d MiB exceeded limit %d MiB (terminating group)",
                                cur_log_size // (1024 * 1024), MAX_LOG_BYTES // (1024 * 1024),
                            )
                            self._lease_lost = True
                            self._lease_loss_reason = f"Log size {cur_log_size // (1024*1024)}MiB exceeded limit {MAX_LOG_BYTES // (1024*1024)}MiB"
                            self._kill_process_group()
                            break
                    except Exception:
                        pass

        self._heartbeat_thread = threading.Thread(target=_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat_loop(self) -> None:
        self._stop_heartbeat.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)

    def _kill_process_group(self) -> None:
        """Kills the active child process group safely using SIGTERM then SIGKILL."""
        pgid = self._active_pgid
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                return

            def _escalate():
                time.sleep(1.0)
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass

            threading.Thread(target=_escalate, daemon=True).start()

    def execute_command(
        self,
        command: List[str],
        cwd: Union[str, Path],
        artifact_path: Union[str, Path],
        timeout_sec: float = 60.0,
        env: Optional[Dict[str, str]] = None,
        repo_root: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a bounded subprocess command with process group containment,
        private disk logging, admission verification, and fresh artifact receipt.
        """
        cwd_path = Path(cwd).resolve()
        art_path = Path(artifact_path).resolve()
        art_path.parent.mkdir(parents=True, exist_ok=True)
        root_path = Path(repo_root).resolve() if repo_root else Path("/home/alexey/git/cloudflare-agent-git").resolve()

        # Enforce owned TMPDIR under repo_root / .local / tmp
        tmp_dir = root_path / ".local" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # 1. Admission Check (C2053 & C2070 Canonical Launcher Delegation)
        if self.admission_bridge is not None:
            self.admission_bridge.check_resource_eligibility(
                workspace=cwd_path,
                timeout=timeout_sec,
                requested_memory_mb=self.requested_memory_mb,
                requested_tmpdir=tmp_dir,
                repo_root=root_path,
            )
        else:
            check_child_admission(
                requested_memory_mb=self.requested_memory_mb,
                cwd_path=cwd_path,
                tmp_path=tmp_dir,
                repo_root=root_path,
            )

        # Notify bus bridge of dispatch initiation if enrolled
        if self.bus_bridge is not None:
            try:
                if hasattr(self.bus_bridge, "send_envelope") and self.executor_tag in getattr(self.bus_bridge, "_enrolled_identities", {}):
                    self.bus_bridge.send_envelope(
                        sender_name=self.executor_tag,
                        recipient_id=self.task_id,
                        body=f"Task {self.task_id} dispatch initiated",
                        data={"task_id": self.task_id, "fence_token": self.fence_token, "phase": "dispatch"},
                        kind="dispatch",
                    )
            except Exception as b_exc:
                logger.debug("Bus bridge dispatch notification skipped: %s", b_exc)

        # 2. Build Isolated Environment (Strip parent APLEXER_* identity)
        eff_env = dict(os.environ)
        if env:
            eff_env.update(env)
        for key in list(eff_env.keys()):
            if key.startswith("APLEXER_"):
                del eff_env[key]
        eff_env["TMPDIR"] = str(tmp_dir)
        eff_env["TASK_ID"] = self.task_id
        eff_env["EXECUTOR_TAG"] = self.executor_tag
        eff_env["FENCE_TOKEN"] = str(self.fence_token)

        # 3. Private Bounded Disk Log (No unbounded capture_output in RAM)
        log_file_path = self.scratch_dir / f"child_{self.task_id}_{self.fence_token}.log"

        initial_art_existed = art_path.exists()
        self._lease_lost = False
        self._lease_loss_reason = None
        self._start_heartbeat(log_file_path=log_file_path)
        start_time = time.time()

        try:
            logger.info("Spawning child process group: %s (cwd: %s)", command, cwd_path)
            with open(log_file_path, "wb") as log_file:
                proc = subprocess.Popen(
                    command,
                    cwd=str(cwd_path),
                    env=eff_env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Creates a distinct process group
                    preexec_fn=_make_child_preexec(self.requested_memory_mb),
                )
                self._active_proc = proc
                self._active_pgid = proc.pid

                try:
                    proc.wait(timeout=timeout_sec)
                except subprocess.TimeoutExpired:
                    self._kill_process_group()
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except (ProcessLookupError, OSError):
                            pass
                        proc.wait()
                    raise ChildExecutionError(f"Child process group timed out after {timeout_sec}s")

            duration = time.time() - start_time

            # Check if lease was lost or limit breached during execution
            if self._lease_lost:
                if not initial_art_existed:
                    art_path.unlink(missing_ok=True)
                raise ChildExecutionError(
                    f"Child execution aborted: task lease lost during run ({self._lease_loss_reason})"
                )

            if proc.returncode != 0:
                # Read tail of log file for bounded error description
                log_tail = ""
                if log_file_path.is_file():
                    with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(max(0, log_file_path.stat().st_size - 1024))
                        log_tail = f.read()
                raise ChildExecutionError(
                    f"Child process failed with returncode {proc.returncode}: {log_tail}"
                )

            # 4. Exact Freshness Check (C2053)
            if not art_path.is_file():
                raise ChildExecutionError(f"Output artifact {art_path} was not created!")
            st = art_path.stat()
            if st.st_mtime < start_time - 1.0:
                raise ChildExecutionError(
                    f"Output artifact {art_path} is stale (mtime {st.st_mtime} < start {start_time})"
                )
            if st.st_size < 16:
                raise ChildExecutionError(
                    f"Output artifact {art_path} is junk (< 16 bytes: {st.st_size} bytes)"
                )

            # 5. Final Fence Check (CAS validation before success)
            lease = self.lease_manager.get_lease(self.task_id)
            if not lease or not lease.is_valid(self.executor_tag, self.fence_token):
                if not initial_art_existed:
                    art_path.unlink(missing_ok=True)
                raise ChildExecutionError(
                    "Final fence validation failed: lease expired or fence token changed during execution"
                )

            content = art_path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()

            # Read bounded log preview
            preview = ""
            if log_file_path.is_file():
                with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                    preview = f.read(500)

            # Notify bus bridge of completion if enrolled
            if self.bus_bridge is not None:
                try:
                    if hasattr(self.bus_bridge, "send_envelope") and self.executor_tag in getattr(self.bus_bridge, "_enrolled_identities", {}):
                        self.bus_bridge.send_envelope(
                            sender_name=self.executor_tag,
                            recipient_id=self.task_id,
                            body=f"Task {self.task_id} execution completed (rc={proc.returncode})",
                            data={
                                "task_id": self.task_id,
                                "fence_token": self.fence_token,
                                "returncode": proc.returncode,
                                "artifact_path": str(art_path),
                                "output_digest": digest,
                            },
                            kind="completion",
                        )
                except Exception as b_exc:
                    logger.debug("Bus bridge completion notification skipped: %s", b_exc)

            return {
                "task_id": self.task_id,
                "project_id": self.project_id,
                "executor_tag": self.executor_tag,
                "fence_token": self.fence_token,
                "duration_seconds": round(duration, 3),
                "artifact_path": str(art_path),
                "artifact_bytes": st.st_size,
                "output_digest": digest,
                "returncode": proc.returncode,
                "log_file": str(log_file_path),
                "stdout_preview": preview,
            }
        finally:
            self._active_proc = None
            self._active_pgid = None
            self._stop_heartbeat_loop()

    def execute_zcode_headless(
        self,
        prompt: str,
        cwd: Union[str, Path],
        artifact_path: Union[str, Path],
        model: str = "glm-5.3-flash",
        timeout_sec: float = 120.0,
        repo_root: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        ZCode headless model execution is strictly HELD under Codex C2053/C2054
        pending verified hard custody, fresh real quota reservation, and bus enrollment.
        """
        raise NotImplementedError(
            "ZCode headless model execution strictly HELD under C2053/C2054 "
            "pending verified hard custody, fresh real quota reservation, and bus enrollment."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Decoupled Child Execution Adapter Bridge")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--executor-tag", required=True)
    parser.add_argument("--fence-token", type=int, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument("--mode", choices=["command", "zcode"], default="command")
    parser.add_argument("--prompt", help="Prompt for zcode mode")
    parser.add_argument("--command", nargs="+", help="Command line for command mode")
    parser.add_argument("--timeout", type=float, default=60.0)

    args = parser.parse_args()

    adapter = ChildAdapter(
        task_id=args.task_id,
        executor_tag=args.executor_tag,
        fence_token=args.fence_token,
        project_id=args.project_id,
    )

    if args.mode == "zcode":
        if not args.prompt:
            parser.error("--prompt required for zcode mode")
        res = adapter.execute_zcode_headless(
            prompt=args.prompt,
            cwd=args.cwd,
            artifact_path=args.artifact_path,
            timeout_sec=args.timeout,
        )
    else:
        if not args.command:
            parser.error("--command required for command mode")
        res = adapter.execute_command(
            command=args.command,
            cwd=args.cwd,
            artifact_path=args.artifact_path,
            timeout_sec=args.timeout,
        )

    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
