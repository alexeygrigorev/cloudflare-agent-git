#!/usr/bin/env python3
"""
Unit Test Suite for Runtime Custody & Containment Architecture (C2059 / Codex Principal Directives).

Covers:
- Test 1: CGroup v2 presence and memory.max parsing (integer, 'max', missing, proc fallback).
- Test 2: Unbounded memory fails closed ('max', > 1500 MB ceiling, negative values).
- Test 3: Process assignment to cgroup.procs and descendant PID inspection.
- Test 4: Provider quota reservation respects 15% reserve floor.
- Test 5: Provider quota reservation rejects exhausted, unknown, stale, and out-of-window quotas.
- Test 6: Bus socket connection authentication, permissions enforcement, and message framing.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import tempfile
import threading
import time
import unittest
from zoneinfo import ZoneInfo

from research.antigravity.tooling.self_org.runtime_custody import (
    ALLOWED_PROVIDERS,
    MAX_COOPERATIVE_MEMORY_BYTES,
    BusSocketConnector,
    CGroupCustodyError,
    CGroupV2Custody,
    CGroupV2UnavailableError,
    EnrollmentError,
    FramingError,
    MemoryLimitExceededError,
    ProviderIneligibleError,
    ProviderQuotaReservation,
    QuotaExhaustedError,
    QuotaReservation,
    QuotaReservationError,
    ReservationExpiredError,
    ReservationFencingError,
    ReserveFloorViolationError,
    SocketSecurityError,
    StaleQuotaError,
    UnboundedMemoryError,
)


class TestRuntimeCustody(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch_base = Path("/home/alexey/git/cloudflare-agent-git/.local/scratch/test_runtime_custody")
        self.scratch_base.mkdir(parents=True, exist_ok=True)
        self.test_dir = Path(tempfile.mkdtemp(prefix="custody_", dir=str(self.scratch_base))).resolve()

        # Mock CGroup directory
        self.cgroup_root = self.test_dir / "sys_cgroup"
        self.cgroup_root.mkdir(parents=True, exist_ok=True)
        (self.cgroup_root / "cgroup.controllers").write_text("cpu memory io pids\n", encoding="utf-8")

        # Mock proc cgroup
        self.proc_cgroup = self.test_dir / "proc_self_cgroup"
        self.proc_cgroup.write_text("0::/user.slice/user-1000.slice\n", encoding="utf-8")

        self.custody = CGroupV2Custody(
            cgroup_root=self.cgroup_root,
            proc_cgroup_file=self.proc_cgroup,
            max_memory_limit_bytes=MAX_COOPERATIVE_MEMORY_BYTES,
        )

        # Quota reservation files
        self.quota_file = self.test_dir / "quota_telemetry.json"
        self.res_file = self.test_dir / "reservations.json"

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # Test 1: CGroup v2 presence and memory.max parsing
    # -----------------------------------------------------------------------
    def test_01_cgroup_v2_presence_and_memory_max_parsing(self) -> None:
        """
        Validates cgroup v2 unified hierarchy presence detection and memory.max
        integer parsing. Handles missing files and fallback to proc cgroup.
        """
        # 1. Hierarchy availability with cgroup.controllers
        self.assertTrue(self.custody.is_cgroup_v2_available())

        # 2. Hierarchy availability fallback using /proc/self/cgroup unified entry (0::)
        controllers_file = self.cgroup_root / "cgroup.controllers"
        controllers_file.unlink()
        self.assertTrue(self.custody.is_cgroup_v2_available())

        # 3. Hierarchy missing when both controllers and 0:: entry are absent
        self.proc_cgroup.write_text("1:name=systemd:/\n2:memory:/\n", encoding="utf-8")
        self.assertFalse(self.custody.is_cgroup_v2_available())
        with self.assertRaises(CGroupV2UnavailableError):
            self.custody.check_cgroup_v2_or_raise()

        # Restore controllers file
        controllers_file.write_text("cpu memory io pids\n", encoding="utf-8")
        self.assertTrue(self.custody.is_cgroup_v2_available())

        # 4. Valid integer memory.max parsing
        leaf_cgroup = self.cgroup_root / "workers" / "task-101"
        leaf_cgroup.mkdir(parents=True, exist_ok=True)
        memory_max_file = leaf_cgroup / "memory.max"
        memory_max_file.write_text("524288000\n", encoding="utf-8")  # 500 MB

        parsed_bytes = self.custody.get_memory_ceiling_bytes("workers/task-101")
        self.assertEqual(parsed_bytes, 524288000)

        # 5. Missing memory.max file raises CGroupCustodyError
        memory_max_file.unlink()
        with self.assertRaises(CGroupCustodyError) as cm:
            self.custody.get_memory_ceiling_bytes("workers/task-101")
        self.assertIn("does not exist", str(cm.exception))

        # 6. Malformed non-integer memory.max file raises CGroupCustodyError
        memory_max_file.write_text("not_a_number\n", encoding="utf-8")
        with self.assertRaises(CGroupCustodyError) as cm:
            self.custody.get_memory_ceiling_bytes("workers/task-101")
        self.assertIn("Non-integer", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 2: Unbounded memory fails closed
    # -----------------------------------------------------------------------
    def test_02_unbounded_memory_fails_closed(self) -> None:
        """
        CGroup with memory.max set to 'max' (unbounded), exceeding 1500 MB,
        or negative integers fails closed immediately.
        """
        leaf_cgroup = self.cgroup_root / "workers" / "unbounded-task"
        leaf_cgroup.mkdir(parents=True, exist_ok=True)
        memory_max_file = leaf_cgroup / "memory.max"

        # 1. Unbounded 'max' string fails closed with UnboundedMemoryError
        memory_max_file.write_text("max\n", encoding="utf-8")
        with self.assertRaises(UnboundedMemoryError) as cm:
            self.custody.get_memory_ceiling_bytes("workers/unbounded-task")
        self.assertIn("unbounded", str(cm.exception))

        # 2. Memory ceiling exceeding cooperative pool limit (1500 MB)
        excess_bytes = 1600 * 1024 * 1024  # 1600 MB > 1500 MB
        memory_max_file.write_text(f"{excess_bytes}\n", encoding="utf-8")
        with self.assertRaises(MemoryLimitExceededError) as cm:
            self.custody.get_memory_ceiling_bytes("workers/unbounded-task")
        self.assertIn("exceeds cooperative limit", str(cm.exception))

        # 3. Negative memory ceiling fails closed
        memory_max_file.write_text("-1024\n", encoding="utf-8")
        with self.assertRaises(CGroupCustodyError) as cm:
            self.custody.get_memory_ceiling_bytes("workers/unbounded-task")
        self.assertIn("Negative memory.max", str(cm.exception))

        # 4. Exactly 1500 MB is accepted
        memory_max_file.write_text(f"{MAX_COOPERATIVE_MEMORY_BYTES}\n", encoding="utf-8")
        self.assertEqual(
            self.custody.get_memory_ceiling_bytes("workers/unbounded-task"),
            MAX_COOPERATIVE_MEMORY_BYTES,
        )

    # -----------------------------------------------------------------------
    # Test 3: Process assignment to cgroup.procs
    # -----------------------------------------------------------------------
    def test_03_process_assignment_to_cgroup_procs(self) -> None:
        """
        Validates process assignment by writing PID to cgroup.procs and reading
        active descendant PIDs.
        """
        leaf_cgroup = self.cgroup_root / "workers" / "active-task"
        leaf_cgroup.mkdir(parents=True, exist_ok=True)
        procs_file = leaf_cgroup / "cgroup.procs"
        procs_file.write_text("", encoding="utf-8")

        # 1. Assign PID 42001
        self.custody.assign_process_to_cgroup("workers/active-task", pid=42001)
        self.assertEqual(procs_file.read_text(encoding="utf-8").strip(), "42001")

        # 2. Inspect active descendant PIDs
        pids = self.custody.get_cgroup_pids("workers/active-task")
        self.assertEqual(pids, [42001])

        # 3. Append another PID and verify multiple PIDs
        with open(procs_file, "a", encoding="utf-8") as f:
            f.write("42002\n42003\n")

        pids = self.custody.get_cgroup_pids("workers/active-task")
        self.assertEqual(pids, [42001, 42002, 42003])

        # 4. Missing procs file fails closed
        procs_file.unlink()
        with self.assertRaises(CGroupCustodyError):
            self.custody.assign_process_to_cgroup("workers/active-task", pid=99999)
        with self.assertRaises(CGroupCustodyError):
            self.custody.get_cgroup_pids("workers/active-task")

    # -----------------------------------------------------------------------
    # Test 4: Provider quota reservation respects 15% reserve floor
    # -----------------------------------------------------------------------
    def test_04_provider_quota_reservation_respects_15_percent_reserve_floor(self) -> None:
        """
        Codex provider quota reservation enforces mandatory 15% reserve floor.
        Rejects dispatches when remaining balance < 15%.
        """
        mgr = ProviderQuotaReservation(
            reservation_file=self.res_file,
            quota_file=self.quota_file,
            default_ttl_sec=30.0,
            codex_reserve_floor=0.15,
        )

        # 1. Case A: Codex at 25% remaining -> Eligible for reservation
        telemetry_ok = {
            "timestamp": time.time(),
            "providers": {
                "codex": {
                    "remaining_fraction": 0.25,
                    "remaining_percent": 25.0,
                    "status": "healthy",
                }
            }
        }
        self.quota_file.write_text(json.dumps(telemetry_ok), encoding="utf-8")

        res = mgr.acquire_reservation(provider="codex", task_id="task-codex-pass")
        self.assertEqual(res.provider, "codex")
        self.assertEqual(res.task_id, "task-codex-pass")
        self.assertEqual(res.status, "active")
        self.assertEqual(res.fence_token, 1)

        # Verify active reservations
        active = mgr.list_active_reservations(provider="codex")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].reservation_id, res.reservation_id)

        # 2. Case B: Codex at 14% remaining -> Fails closed with ReserveFloorViolationError
        telemetry_low = {
            "timestamp": time.time(),
            "providers": {
                "codex": {
                    "remaining_fraction": 0.14,
                    "remaining_percent": 14.0,
                    "status": "warning",
                }
            }
        }
        self.quota_file.write_text(json.dumps(telemetry_low), encoding="utf-8")

        with self.assertRaises(ReserveFloorViolationError) as cm:
            mgr.acquire_reservation(provider="codex", task_id="task-codex-fail")
        self.assertIn("15% reserve floor", str(cm.exception))

        # 3. Case C: Codex missing remaining percentage record -> Fails closed
        telemetry_unknown = {
            "timestamp": time.time(),
            "providers": {
                "codex": {
                    "status": "unknown",
                }
            }
        }
        self.quota_file.write_text(json.dumps(telemetry_unknown), encoding="utf-8")

        with self.assertRaises(ProviderIneligibleError):
            mgr.acquire_reservation(provider="codex", task_id="task-codex-unknown")

    # -----------------------------------------------------------------------
    # Test 5: Provider quota reservation rejects exhausted/unknown quota
    # -----------------------------------------------------------------------
    def test_05_provider_quota_reservation_rejects_exhausted_unknown_and_stale(self) -> None:
        """
        Rejects exhausted providers, rate-limit cooldowns, stale telemetry files (> 300s),
        unauthorized providers, and out-of-window GLM executions.
        """
        mgr = ProviderQuotaReservation(
            reservation_file=self.res_file,
            quota_file=self.quota_file,
            default_ttl_sec=30.0,
            max_quota_age_sec=300.0,
        )

        now_ts = time.time()

        # 1. Stale telemetry file (> 300s old) fails closed
        telemetry = {
            "timestamp": now_ts - 350.0,
            "providers": {
                "gemini": {"status": "ok", "remaining_requests": 100}
            }
        }
        self.quota_file.write_text(json.dumps(telemetry), encoding="utf-8")
        # Set file mtime to 350s in the past
        past_time = now_ts - 350.0
        os.utime(self.quota_file, (past_time, past_time))

        with self.assertRaises(StaleQuotaError) as cm:
            mgr.acquire_reservation(provider="gemini", task_id="t-stale", now=now_ts)
        self.assertIn("stale", str(cm.exception))

        # 2. Fresh telemetry with Grok in cooldown fails closed
        telemetry_grok_cooldown = {
            "timestamp": now_ts,
            "providers": {
                "grok": {
                    "status": "cooldown",
                    "cooldown_until": now_ts + 120.0,
                }
            }
        }
        self.quota_file.write_text(json.dumps(telemetry_grok_cooldown), encoding="utf-8")
        os.utime(self.quota_file, (now_ts, now_ts))

        with self.assertRaises(QuotaExhaustedError) as cm:
            mgr.acquire_reservation(provider="grok", task_id="t-grok-cool", now=now_ts)
        self.assertIn("cooldown", str(cm.exception))

        # 3. Exhausted provider status fails closed
        telemetry_exhausted = {
            "timestamp": now_ts,
            "providers": {
                "opencode": {
                    "status": "exhausted",
                    "remaining_requests": 0,
                }
            }
        }
        self.quota_file.write_text(json.dumps(telemetry_exhausted), encoding="utf-8")
        os.utime(self.quota_file, (now_ts, now_ts))

        with self.assertRaises(QuotaExhaustedError) as cm:
            mgr.acquire_reservation(provider="opencode", task_id="t-opencode-ex", now=now_ts)
        self.assertIn("exhausted", str(cm.exception))

        # 4. Unauthorized / non-whitelisted provider fails closed
        with self.assertRaises(ProviderIneligibleError) as cm:
            mgr.acquire_reservation(provider="unauthorized-llm-corp", task_id="t-bad-provider")
        self.assertIn("not in authorized whitelist", str(cm.exception))

        # 5. GLM campaign window check (17:00-03:00 Europe/Berlin)
        tz_berlin = ZoneInfo("Europe/Berlin")
        inside_window_dt = datetime.datetime(2026, 10, 4, 19, 0, 0, tzinfo=tz_berlin)
        outside_window_dt = datetime.datetime(2026, 10, 4, 11, 0, 0, tzinfo=tz_berlin)

        self.assertTrue(ProviderQuotaReservation.is_glm_window_open(inside_window_dt))
        self.assertFalse(ProviderQuotaReservation.is_glm_window_open(outside_window_dt))

        with self.assertRaises(ProviderIneligibleError) as cm:
            mgr.acquire_reservation(
                provider="glm-5.3-flash",
                task_id="t-glm-outside",
                now=outside_window_dt.timestamp(),
            )
        self.assertIn("outside eligible campaign", str(cm.exception))

        # 6. Reservation release and commit lifecycle under fencing
        telemetry_gemini = {
            "timestamp": now_ts,
            "providers": {
                "gemini": {"status": "ok", "remaining_requests": 100}
            }
        }
        self.quota_file.write_text(json.dumps(telemetry_gemini), encoding="utf-8")
        os.utime(self.quota_file, (now_ts, now_ts))

        res_gemini = mgr.acquire_reservation(provider="gemini", task_id="t-gemini-commit", ttl_sec=5.0)
        self.assertEqual(res_gemini.status, "active")

        # Commit with wrong fence token raises ReservationFencingError
        with self.assertRaises(ReservationFencingError):
            mgr.commit_reservation(res_gemini.reservation_id, fence_token=999, units_used=1.0)

        # Commit with correct fence token succeeds
        self.assertTrue(mgr.commit_reservation(res_gemini.reservation_id, fence_token=res_gemini.fence_token, units_used=1.0))
        committed_res = mgr.get_reservation(res_gemini.reservation_id)
        self.assertIsNotNone(committed_res)
        self.assertEqual(committed_res.status, "committed")

    # -----------------------------------------------------------------------
    # Test 6: Bus socket connection authentication and message framing
    # -----------------------------------------------------------------------
    def test_06_bus_socket_authentication_and_message_framing(self) -> None:
        """
        Validates UNIX domain socket authentication, length-prefixed binary framing,
        permission mode 0700 enforcement, and parent authority environment stripping.
        """
        # 1. Environment sanitization stripping parent mailbox authority
        dirty_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/alexey",
            "APLEXER_SESSION": "sess-interactive-root",
            "APLEXER_PANE": "pane-1",
            "PARENT_TAG": "antigravity-head",
            "PARENT_CONVERSATION_ID": "46fdb644-9b58-4e2f-aab3-9be5e1e33337",
            "MAILBOX_TOKEN": "secret-parent-mailbox-token",
            "CUSTOM_CONFIG": "safe-value",
        }
        clean_env = BusSocketConnector.strip_parent_authority(dirty_env)
        self.assertIn("PATH", clean_env)
        self.assertIn("HOME", clean_env)
        self.assertIn("CUSTOM_CONFIG", clean_env)
        self.assertNotIn("APLEXER_SESSION", clean_env)
        self.assertNotIn("APLEXER_PANE", clean_env)
        self.assertNotIn("PARENT_TAG", clean_env)
        self.assertNotIn("PARENT_CONVERSATION_ID", clean_env)
        self.assertNotIn("MAILBOX_TOKEN", clean_env)

        # 2. Setup secure socket directory (mode 0700) using short path (< 108 chars for AF_UNIX)
        socket_dir = self.scratch_base / "s_sec"
        if socket_dir.exists():
            shutil.rmtree(socket_dir, ignore_errors=True)
        socket_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(socket_dir, stat.S_IRWXU)  # 0700
        socket_path = socket_dir / "b.sock"

        # 3. Start a mock bus server thread
        server_running = threading.Event()
        server_stop = threading.Event()
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(socket_path))
        os.chmod(socket_path, stat.S_IRWXU)  # 0700
        server_sock.listen(5)
        server_sock.settimeout(0.5)

        received_frames: list[dict] = []

        def server_worker() -> None:
            server_running.set()
            while not server_stop.is_set():
                try:
                    conn, _ = server_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    with conn:
                        msg = BusSocketConnector.receive_message(conn, timeout_sec=2.0)
                        received_frames.append(msg)
                        if msg.get("auth_token") == "valid-token-123":
                            BusSocketConnector.send_message(
                                conn,
                                {
                                    "status": "enrolled",
                                    "client_tag": msg.get("client_tag"),
                                    "role": msg.get("role"),
                                    "bus_session_id": "bus-subagent-999",
                                },
                            )
                        else:
                            BusSocketConnector.send_message(
                                conn,
                                {
                                    "status": "rejected",
                                    "error": "Invalid bus authentication token",
                                },
                            )
                except Exception:
                    pass

        server_thread = threading.Thread(target=server_worker, daemon=True)
        server_thread.start()
        self.assertTrue(server_running.wait(timeout=2.0))

        connector = BusSocketConnector()

        # 4. Successful identity enrollment with valid token
        enroll_res = connector.enroll_identity(
            socket_path=socket_path,
            client_tag="subagent-runtime-1",
            role="executor",
            auth_token="valid-token-123",
            timeout_sec=2.0,
        )
        self.assertEqual(enroll_res.get("status"), "enrolled")
        self.assertEqual(enroll_res.get("bus_session_id"), "bus-subagent-999")
        self.assertEqual(len(received_frames), 1)
        self.assertEqual(received_frames[0].get("client_tag"), "subagent-runtime-1")
        self.assertTrue(received_frames[0].get("isolated_env"))

        # 5. Rejected enrollment with invalid token raises EnrollmentError
        with self.assertRaises(EnrollmentError) as cm:
            connector.enroll_identity(
                socket_path=socket_path,
                client_tag="subagent-runtime-1",
                role="executor",
                auth_token="invalid-token",
                timeout_sec=2.0,
            )
        self.assertIn("Invalid bus authentication token", str(cm.exception))

        # 6. Stop server thread
        server_stop.set()
        server_thread.join(timeout=2.0)
        try:
            server_sock.close()
        except OSError:
            pass

        # 7. Socket permission security check: mode with group/other write bits raises SocketSecurityError
        insecure_sock_dir = self.scratch_base / "s_insec"
        if insecure_sock_dir.exists():
            shutil.rmtree(insecure_sock_dir, ignore_errors=True)
        insecure_sock_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(insecure_sock_dir, 0o777)  # Insecure!
        insecure_sock_path = insecure_sock_dir / "i.sock"
        dummy_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        dummy_sock.bind(str(insecure_sock_path))
        os.chmod(insecure_sock_path, 0o777)

        with self.assertRaises(SocketSecurityError) as cm:
            BusSocketConnector.verify_socket_security(insecure_sock_path)
        self.assertIn("Insecure permissions", str(cm.exception))

        dummy_sock.close()

        # Clean up socket test directories
        shutil.rmtree(socket_dir, ignore_errors=True)
        shutil.rmtree(insecure_sock_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
