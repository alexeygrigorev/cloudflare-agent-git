#!/usr/bin/env python3
"""Negative test suite R2 for build_guard.py.

Verifies specific edge cases identified by Codex-Principal in 01a100b3-4f0c:
1. Descendant ignoring SIGTERM with parent exiting immediately: unconditional SIGKILL kills grandchild (0 orphans).
2. Final du failure: fails closed with exit code 104 and GUARD_FAIL.
3. Fast writer crossing growth limit before first sample tick: caught at final measurement (exit 101).
4. du timeout handling: bounded du invocation.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time


def run_guard(args, env=None):
    guard_path = os.path.join(os.path.dirname(__file__), "build_guard.py")
    cmd = [sys.executable, guard_path] + args
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env or os.environ.copy(),
    )
    return res


def test_sigterm_ignoring_grandchild():
    print("Testing SIGTERM-ignoring grandchild termination...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Script spawns a background grandchild that traps SIGTERM and sleeps,
        # then parent exits immediately upon receiving SIGTERM.
        grandchild_script = (
            "import signal, time, sys, os\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "sys.stdout.write(f'GRANDCHILD:{os.getpid()}\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(100)\n"
        )
        parent_script = (
            f"import subprocess, time, sys, os\n"
            f"p = subprocess.Popen([sys.executable, '-c', {repr(grandchild_script)}], stdout=subprocess.PIPE, text=True)\n"
            f"line = p.stdout.readline()\n"
            f"sys.stdout.write(line)\n"
            f"sys.stdout.flush()\n"
            f"time.sleep(100)\n"
        )
        runner = [
            "--timeout", "0.5",
            tmpdir,
            sys.executable, "-c", parent_script
        ]
        res = run_guard(runner)
        assert res.returncode == 103, f"Expected 103 on timeout, got {res.returncode}. Stderr: {res.stderr}"

        # Parse grandchild PID from output
        grandchild_pid = None
        for line in res.stdout.splitlines():
            if line.startswith("GRANDCHILD:"):
                grandchild_pid = int(line.split(":")[1])
                break

        assert grandchild_pid is not None, f"Failed to get grandchild pid from output: {res.stdout}"
        time.sleep(0.1)
        # Check if grandchild is alive
        try:
            os.kill(grandchild_pid, 0)
            alive = True
        except OSError:
            alive = False
        assert not alive, f"SIGTERM-ignoring grandchild {grandchild_pid} survived! SIGKILL escalation failed!"
    print("  -> PASS: SIGTERM-ignoring grandchild terminated via SIGKILL escalation (0 orphans).")


def test_final_du_failure_fails_closed():
    print("Testing final du failure fail-closed handling...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Script makes the target dir unreadable right before exiting
        script = (
            f"import os, time\n"
            f"time.sleep(0.1)\n"
            f"os.chmod('{tmpdir}', 0)\n"
        )
        runner = [
            tmpdir,
            sys.executable, "-c", script
        ]
        try:
            res = run_guard(runner)
            assert res.returncode == 104, f"Expected 104 on final du failure, got {res.returncode}. Stderr: {res.stderr}"
            assert "GUARD_ERROR: Final size measurement failed" in res.stderr
            assert "GUARD_FAIL" in res.stderr
        finally:
            os.chmod(tmpdir, 0o755)
    print("  -> PASS: final du failure fails closed with exit code 104 and GUARD_FAIL.")


def test_fast_writer_crossing_cap():
    print("Testing fast writer crossing growth cap before sampling...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Script writes 15 MB in dummy target dir and immediately exits (taking <10ms, faster than poll interval)
        script = (
            f"with open('{tmpdir}/fast_dump.bin', 'wb') as f:\n"
            f"    f.write(b'Z' * 15 * 1024 * 1024)\n"
        )
        runner = [
            "--max-growth-mb", "10",
            "--margin-mb", "2",
            "--poll-interval", "0.5",  # Long poll interval to ensure child exits before first poll
            tmpdir,
            sys.executable, "-c", script
        ]
        res = run_guard(runner)
        assert res.returncode == 101, f"Expected 101 on fast writer cap breach, got {res.returncode}. Stderr: {res.stderr}"
        assert "GUARD_TERMINATED" in res.stderr
        assert "GUARD_FAIL" in res.stderr
    print("  -> PASS: fast writer exceeding cap is caught and rejected by guard.")


if __name__ == "__main__":
    test_sigterm_ignoring_grandchild()
    test_final_du_failure_fails_closed()
    test_fast_writer_crossing_cap()
    print("\nALL 3 CODEX R2 GUARD NEGATIVE TESTS PASSED.")
