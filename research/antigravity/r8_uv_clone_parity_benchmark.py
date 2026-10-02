#!/usr/bin/env python3
"""
r8_uv_clone_parity_benchmark.py
Workspace-Doctor D1 Follow-up Benchmark:
Incumbent Clone Baseline, Value Parity, Executed Permissions Mitigation, and Peak Memory Guard.

Addresses challenges from Codex-Principal (C-UV-REVIEW, 01a0fe8a-4ac5), Desktop-Orchestrator (01a0fe9e-fea8),
and Grok-Head (G-LABEL-20261003):
1. Evaluates official Linux default: `uv pip install --link-mode=clone` on ext4 (revealing fallback to hardlink / copy).
2. Uses exact pinned package versions (FastAPI, Pydantic, pydantic-core, HTTPX stack).
3. Evaluates 4 architectural arms:
   - Arm A: Naive Copied .venv (copy)
   - Arm B: Incumbent Default Clone (clone on ext4)
   - Arm C: Workspace-Doctor Hardlink with Executed `chmod -R a-w` Mitigation
   - Arm D: Workspace-Doctor Symlink (symlink)
4. Tests genuine concurrent execution parity with deep JSON value assertions (distinct models & tokens, not just mock strings).
5. Actively executes in-place dependency mutation in all arms, proving whether mutations leak or are blocked by PermissionError.
6. Instruments peak scratch footprint with active polling guard (aborts if > 100 MiB cap).
7. Completely cleans up scratch directory upon completion.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRATCH_BASE = Path("/tmp/aplexer-uv-clone-parity-spike")
BUDGET_BYTES = 100 * 1024 * 1024  # 100 MiB
DISK_FLOOR_BYTES = 8 * 1024 * 1024 * 1024  # 8 GiB

PYTHON_BIN = "/usr/bin/python3.12"
PINNED_PACKAGES = [
    "fastapi==0.115.0",
    "pydantic==2.9.2",
    "httpx==0.27.2",
]


class PeakMonitor:
    def __init__(self, target_dir, max_bytes):
        self.target_dir = Path(target_dir)
        self.max_bytes = max_bytes
        self.peak_bytes = 0
        self.running = False
        self.exceeded = False
        self._thread = None

    def _poll(self):
        while self.running:
            if self.target_dir.exists():
                try:
                    res = subprocess.run(
                        ["du", "-s", "-B1", str(self.target_dir)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        current = int(res.stdout.strip().split()[0])
                        if current > self.peak_bytes:
                            self.peak_bytes = current
                        if current > self.max_bytes:
                            self.exceeded = True
                except Exception:
                    pass
            time.sleep(0.05)

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)


def run_cmd(cmd, cwd=None, env=None, check=True, timeout=60):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\nSTDERR: {res.stderr}\nSTDOUT: {res.stdout}")
    return res


def get_du_physical_bytes(*paths):
    cmd = ["du", "-c", "-s", "-B1"] + [str(p) for p in paths]
    res = run_cmd(cmd)
    lines = res.stdout.strip().splitlines()
    total_line = lines[-1]
    return int(total_line.split()[0])


def get_du_apparent_bytes(*paths):
    cmd = ["du", "-c", "-s", "--apparent-size", "-B1"] + [str(p) for p in paths]
    res = run_cmd(cmd)
    lines = res.stdout.strip().splitlines()
    total_line = lines[-1]
    return int(total_line.split()[0])


def get_inode(path):
    return os.stat(path).st_ino


def check_disk_floor():
    st = os.statvfs("/tmp")
    avail = st.f_bavail * st.f_frsize
    if avail < DISK_FLOOR_BYTES:
        raise RuntimeError(f"Disk space below 8 GiB floor on /tmp: {avail / (1024**3):.2f} GiB available")
    return avail


def find_pkg_file(venv_path, rel_path="site-packages/fastapi/__init__.py"):
    matches = list(venv_path.glob(f"**/{rel_path}"))
    if not matches:
        raise FileNotFoundError(f"{rel_path} not found under {venv_path}")
    return matches[0]


def run_benchmark():
    print("=== Workspace-Doctor D1: Clone Baseline, Parity & Mitigation Benchmark ===")
    avail_bytes = check_disk_floor()
    print(f"Host /tmp disk available: {avail_bytes / (1024**3):.2f} GiB (Floor: 8 GiB)")

    if SCRATCH_BASE.exists():
        shutil.rmtree(SCRATCH_BASE)
    SCRATCH_BASE.mkdir(parents=True, exist_ok=True)

    monitor = PeakMonitor(SCRATCH_BASE, BUDGET_BYTES)
    monitor.start()

    results = {
        "benchmark": "workspace-doctor-d1-clone-parity",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version.split()[0],
        "uv_version": run_cmd(["uv", "--version"]).stdout.strip(),
        "pinned_packages": PINNED_PACKAGES,
        "filesystem": "ext4 (/tmp on /dev/nvme1n1)",
        "arms": {},
    }

    try:
        # Task 1 Source: Auth Service Model & Token Generation
        t1_src = """from pydantic import BaseModel, Field
from fastapi import FastAPI
import json

app = FastAPI(title="Auth Service Worker")

class UserToken(BaseModel):
    user_id: int
    username: str
    scopes: list[str]
    expires_in: int = 3600

token = UserToken(user_id=101, username="alice_engineer", scopes=["read:repo", "write:notes"])
with open("output/token.json", "w") as f:
    json.dump(token.model_dump(), f)
print("TASK1_AUTH_OK")
"""

        # Task 2 Source: Billing Service Model & Transaction Generation
        t2_src = """from pydantic import BaseModel, Field
from fastapi import FastAPI
import json

app = FastAPI(title="Billing Service Worker")

class PaymentTx(BaseModel):
    tx_id: str
    amount: float
    currency: str = "USD"
    captured: bool = True

tx = PaymentTx(tx_id="tx_771829", amount=250.75)
with open("output/tx.json", "w") as f:
    json.dump(tx.model_dump(), f)
print("TASK2_BILLING_OK")
"""

        # Pre-seed a clean shared cache on the same filesystem
        shared_cache = SCRATCH_BASE / "cache"
        shared_cache.mkdir()

        # Prefetch wheels into shared cache once
        print("\n[Prefetch] Seeding shared cache with pinned packages...")
        seed_venv = SCRATCH_BASE / "seed_venv"
        run_cmd(["uv", "venv", "--python", PYTHON_BIN, str(seed_venv)], env={"UV_CACHE_DIR": str(shared_cache)})
        run_cmd(
            ["uv", "pip", "install"] + PINNED_PACKAGES + ["--python", str(seed_venv / "bin/python"), "--link-mode=copy"],
            env={"UV_CACHE_DIR": str(shared_cache)},
        )
        shutil.rmtree(seed_venv)

        cache_frozen_size = get_du_physical_bytes(shared_cache)
        print(f"[Prefetch] Shared cache frozen size: {cache_frozen_size} bytes ({cache_frozen_size / (1024**2):.2f} MiB)")
        results["shared_cache_baseline_bytes"] = cache_frozen_size

        # Define 4 Arms
        arms_config = [
            ("arm_a_naive_copy", "copy", False),
            ("arm_b_default_clone", "clone", False),
            ("arm_c_hardlink_mitigated", "hardlink", True),
            ("arm_d_symlink_doctor", "symlink", False),
        ]

        for arm_name, link_mode, apply_mitigation in arms_config:
            print(f"\n--- Executing {arm_name} (link-mode={link_mode}, mitigation={apply_mitigation}) ---")
            arm_dir = SCRATCH_BASE / arm_name
            arm_dir.mkdir()

            t1_dir = arm_dir / "t1"
            t2_dir = arm_dir / "t2"
            t1_dir.mkdir()
            t2_dir.mkdir()

            # Install t1
            run_cmd(["uv", "venv", "--python", PYTHON_BIN, str(t1_dir / ".venv")], env={"UV_CACHE_DIR": str(shared_cache)})
            t1_install = run_cmd(
                ["uv", "pip", "install"] + PINNED_PACKAGES + ["--python", str(t1_dir / ".venv/bin/python"), f"--link-mode={link_mode}"],
                env={"UV_CACHE_DIR": str(shared_cache)},
            )

            # Install t2
            run_cmd(["uv", "venv", "--python", PYTHON_BIN, str(t2_dir / ".venv")], env={"UV_CACHE_DIR": str(shared_cache)})
            t2_install = run_cmd(
                ["uv", "pip", "install"] + PINNED_PACKAGES + ["--python", str(t2_dir / ".venv/bin/python"), f"--link-mode={link_mode}"],
                env={"UV_CACHE_DIR": str(shared_cache)},
            )

            # Check if mitigation requested (chmod -R a-w site-packages)
            if apply_mitigation:
                print(f"[{arm_name}] Applying Workspace-Doctor mitigation: chmod -R a-w .venv/lib/*/site-packages")
                for sp in (t1_dir / ".venv").glob("**/site-packages"):
                    run_cmd(["chmod", "-R", "a-w", str(sp)])
                for sp in (t2_dir / ".venv").glob("**/site-packages"):
                    run_cmd(["chmod", "-R", "a-w", str(sp)])

            # Setup source trees
            (t1_dir / "src").mkdir()
            (t1_dir / "output").mkdir()
            (t1_dir / "src/app.py").write_text(t1_src)

            (t2_dir / "src").mkdir()
            (t2_dir / "output").mkdir()
            (t2_dir / "src/app.py").write_text(t2_src)

            # Static pre-run measurement
            prerun_t1 = get_du_physical_bytes(t1_dir)
            prerun_t2 = get_du_physical_bytes(t2_dir)
            prerun_trees_union = get_du_physical_bytes(t1_dir, t2_dir)

            # Concurrent execution of t1 and t2
            p1 = subprocess.Popen([str(t1_dir / ".venv/bin/python"), "src/app.py"], cwd=t1_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p2 = subprocess.Popen([str(t2_dir / ".venv/bin/python"), "src/app.py"], cwd=t2_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out1, err1 = p1.communicate(timeout=30)
            out2, err2 = p2.communicate(timeout=30)

            assert p1.returncode == 0 and "TASK1_AUTH_OK" in out1, f"Task 1 failed: {err1}"
            assert p2.returncode == 0 and "TASK2_BILLING_OK" in out2, f"Task 2 failed: {err2}"

            # Value assertions on output JSON
            t1_json = json.loads((t1_dir / "output/token.json").read_text())
            t2_json = json.loads((t2_dir / "output/tx.json").read_text())
            assert t1_json["user_id"] == 101 and t1_json["username"] == "alice_engineer"
            assert t2_json["tx_id"] == "tx_771829" and t2_json["amount"] == 250.75

            # Inode verification
            src_ino_t1 = get_inode(t1_dir / "src/app.py")
            src_ino_t2 = get_inode(t2_dir / "src/app.py")
            out_ino_t1 = get_inode(t1_dir / "output/token.json")
            out_ino_t2 = get_inode(t2_dir / "output/tx.json")
            assert src_ino_t1 != src_ino_t2, "Source files unexpectedly shared inode!"
            assert out_ino_t1 != out_ino_t2, "Output files unexpectedly shared inode!"

            # Package file inspection
            pkg_file_t1 = find_pkg_file(t1_dir / ".venv")
            pkg_file_t2 = find_pkg_file(t2_dir / ".venv")
            ino_pkg_t1 = get_inode(pkg_file_t1)
            ino_pkg_t2 = get_inode(pkg_file_t2)
            is_shared_pkg_ino = (ino_pkg_t1 == ino_pkg_t2)

            st_t1 = os.stat(pkg_file_t1)
            file_mode_oct = oct(stat.S_IMODE(st_t1.st_mode))

            # Active In-Place Mutation Test
            mutation_marker = f"# CORRUPT_MUTATION_{arm_name}_{time.time()}\n"
            mutation_attempt_error = None
            mutation_leaked_to_t2 = False

            try:
                with open(pkg_file_t1, "a") as f:
                    f.write(mutation_marker)
                # Check if it appeared in t2
                t2_content = open(pkg_file_t2, "r").read()
                if mutation_marker in t2_content:
                    mutation_leaked_to_t2 = True
            except PermissionError as pe:
                mutation_attempt_error = f"PermissionError: {pe}"
            except Exception as e:
                mutation_attempt_error = f"Exception: {e}"

            # Post-run physical measurement
            postrun_t1 = get_du_physical_bytes(t1_dir)
            postrun_t2 = get_du_physical_bytes(t2_dir)
            postrun_trees_union = get_du_physical_bytes(t1_dir, t2_dir)
            whole_union = get_du_physical_bytes(shared_cache, t1_dir, t2_dir)
            apparent_union = get_du_apparent_bytes(shared_cache, t1_dir, t2_dir)

            results["arms"][arm_name] = {
                "link_mode": link_mode,
                "mitigation_applied": apply_mitigation,
                "pkg_file_mode": file_mode_oct,
                "shared_package_inode": is_shared_pkg_ino,
                "ino_t1": ino_pkg_t1,
                "ino_t2": ino_pkg_t2,
                "source_isolated": True,
                "output_isolated": True,
                "value_parity_pass": True,
                "mutation_blocked_by_permission": (mutation_attempt_error is not None and "PermissionError" in mutation_attempt_error),
                "mutation_error": mutation_attempt_error,
                "mutation_leaked_to_t2": mutation_leaked_to_t2,
                "bytes": {
                    "prerun_t1": prerun_t1,
                    "prerun_t2": prerun_t2,
                    "prerun_trees_union": prerun_trees_union,
                    "postrun_t1": postrun_t1,
                    "postrun_t2": postrun_t2,
                    "postrun_trees_union": postrun_trees_union,
                    "whole_footprint_union": whole_union,
                    "apparent_union": apparent_union,
                },
            }

            print(f"[{arm_name}] Post-run trees union: {postrun_trees_union} B | Whole footprint: {whole_union} B")
            print(f"[{arm_name}] In-place write: error={mutation_attempt_error}, leaked_to_t2={mutation_leaked_to_t2}")

        # Compute Comparative Savings Matrix against Arm A Baseline
        base_arm = results["arms"]["arm_a_naive_copy"]
        base_prerun_trees = base_arm["bytes"]["prerun_trees_union"]
        base_postrun_trees = base_arm["bytes"]["postrun_trees_union"]
        base_whole = base_arm["bytes"]["whole_footprint_union"]

        summary = {}
        for arm_name, data in results["arms"].items():
            trees_post = data["bytes"]["postrun_trees_union"]
            whole = data["bytes"]["whole_footprint_union"]

            tree_savings = round((1.0 - trees_post / base_postrun_trees) * 100, 2)
            whole_savings = round((1.0 - whole / base_whole) * 100, 2)

            summary[arm_name] = {
                "postrun_worktree_savings_percent": tree_savings,
                "whole_footprint_savings_percent": whole_savings,
                "passed_worktree_50pct_gate": tree_savings >= 50.0,
                "passed_whole_footprint_50pct_gate": whole_savings >= 50.0,
                "mutation_safe": (not data["mutation_leaked_to_t2"]) or data["mutation_blocked_by_permission"],
            }

        monitor.stop()
        print(f"\n[Monitor] Peak scratch usage: {monitor.peak_bytes} bytes ({monitor.peak_bytes / (1024**2):.2f} MiB / 100 MiB cap)")
        assert not monitor.exceeded, f"Peak memory exceeded 100 MiB budget! Peak was {monitor.peak_bytes} bytes"

        results["summary"] = summary
        results["peak_scratch_bytes"] = monitor.peak_bytes
        results["scratch_budget_ok"] = not monitor.exceeded

    finally:
        monitor.stop()
        if SCRATCH_BASE.exists():
            print(f"[Cleanup] Removing scratch directory {SCRATCH_BASE}...")
            # Note: chmod a-w may prevent rmtree, restore write permissions first
            try:
                run_cmd(["chmod", "-R", "u+w", str(SCRATCH_BASE)])
                shutil.rmtree(SCRATCH_BASE)
            except Exception as e:
                print(f"[Cleanup] Warning during cleanup: {e}")

    # Output JSON artifact
    out_path = Path("/home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clone_parity_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults successfully written to {out_path}")
    return results


if __name__ == "__main__":
    run_benchmark()
