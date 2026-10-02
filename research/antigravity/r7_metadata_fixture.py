#!/usr/bin/env python3
"""
Round 7 Empirical Verification Fixture:
1. Git Notes vs Commit Trailers vs In-Tree Task Files across clones, fetches, and HEAD advancement.
2. Checkable Invariant Probes (CIP / A04) vs Standard Merged-Tree Tests under test tampering.

Artifacts and repos are created in temporary directory and automatically cleaned up.
Outputs JSON summary of findings and timings.
"""

import tempfile
import subprocess
import time
import os
import json
import sys

def run_metadata_experiment():
    results = {}
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        bare = os.path.join(td, "bare.git")
        subprocess.run(["git", "init", "--bare", bare], check=True, capture_output=True)
        
        # Repo A: Authoring repo
        repo_a = os.path.join(td, "repo_a")
        subprocess.run(["git", "clone", bare, repo_a], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AntigravityTester"], cwd=repo_a, check=True)
        subprocess.run(["git", "config", "user.email", "tester@antigravity.internal"], cwd=repo_a, check=True)
        
        # Commit 1 with plan file, in-tree task file, and trailer
        os.makedirs(os.path.join(repo_a, ".agent", "tasks"), exist_ok=True)
        with open(os.path.join(repo_a, "src.txt"), "w") as f:
            f.write("v1\n")
        with open(os.path.join(repo_a, "plan.md"), "w") as f:
            f.write("# Task Plan v1\nObjective: build auth module\n")
        with open(os.path.join(repo_a, ".agent", "tasks", "task-101.json"), "w") as f:
            json.dump({"task_id": "T101", "agent": "worker-1", "phase": "executing", "sha": "head"}, f)
            
        commit_msg = "feat: initial commit with task context\n\nAgent-Capsule: {\"task_id\": \"T101\", \"status\": \"in_progress\", \"digest\": \"e3b0c44\"}\n"
        subprocess.run(["git", "add", "."], cwd=repo_a, check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_a, check=True, capture_output=True)
        
        # Add git note to commit 1
        subprocess.run(["git", "notes", "add", "-m", "{\"note_type\": \"recovery_capsule\", \"tokens\": 1420}"], cwd=repo_a, check=True, capture_output=True)
        
        # Push commit and notes
        subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=repo_a, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "refs/notes/*"], cwd=repo_a, check=True, capture_output=True)
        
        # Test 1: Standard git clone (Repo B)
        repo_b = os.path.join(td, "repo_b")
        subprocess.run(["git", "clone", bare, repo_b], check=True, capture_output=True)
        
        plan_exists_b = os.path.exists(os.path.join(repo_b, "plan.md"))
        task_file_exists_b = os.path.exists(os.path.join(repo_b, ".agent", "tasks", "task-101.json"))
        
        trailer_res_b = subprocess.run(["git", "log", "-1", "--format=%(trailers:key=Agent-Capsule,valueonly=true)"], cwd=repo_b, capture_output=True, text=True)
        trailer_b = trailer_res_b.stdout.strip()
        
        notes_res_b = subprocess.run(["git", "notes", "show", "HEAD"], cwd=repo_b, capture_output=True, text=True)
        notes_exit_b = notes_res_b.returncode
        
        # Test 2: Clone with notes fetch refspec (Repo C)
        repo_c = os.path.join(td, "repo_c")
        subprocess.run(["git", "clone", "-c", "remote.origin.fetch=+refs/notes/*:refs/notes/*", bare, repo_c], check=True, capture_output=True)
        notes_res_c = subprocess.run(["git", "notes", "show", "HEAD"], cwd=repo_c, capture_output=True, text=True)
        notes_exit_c = notes_res_c.returncode
        notes_content_c = notes_res_c.stdout.strip()
        
        # Test 3: Commit 2 in Repo A (HEAD moves forward)
        with open(os.path.join(repo_a, "src.txt"), "w") as f:
            f.write("v2\n")
        subprocess.run(["git", "add", "src.txt"], cwd=repo_a, check=True)
        subprocess.run(["git", "commit", "-m", "feat: update to v2"], cwd=repo_a, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=repo_a, check=True, capture_output=True)
        
        # Pull in Repo C
        subprocess.run(["git", "pull", "origin", "main"], cwd=repo_c, capture_output=True)
        notes_head_after_pull = subprocess.run(["git", "notes", "show", "HEAD"], cwd=repo_c, capture_output=True, text=True).returncode
        notes_parent_after_pull = subprocess.run(["git", "notes", "show", "HEAD~1"], cwd=repo_c, capture_output=True, text=True).returncode
        
        # Test 4: Timing benchmarks (50 iterations)
        t_trailer = []
        for _ in range(50):
            t0 = time.perf_counter()
            subprocess.run(["git", "log", "-1", "--format=%(trailers:key=Agent-Capsule,valueonly=true)"], cwd=repo_b, capture_output=True)
            t_trailer.append((time.perf_counter() - t0) * 1000)
            
        t_notes = []
        for _ in range(50):
            t0 = time.perf_counter()
            subprocess.run(["git", "notes", "show", "HEAD~1"], cwd=repo_c, capture_output=True)
            t_notes.append((time.perf_counter() - t0) * 1000)
            
        t_taskfile = []
        for _ in range(50):
            t0 = time.perf_counter()
            with open(os.path.join(repo_b, ".agent", "tasks", "task-101.json"), "r") as tf:
                _ = json.load(tf)
            t_taskfile.append((time.perf_counter() - t0) * 1000)
            
        results["metadata_experiment"] = {
            "default_clone": {
                "in_tree_plan_exists": plan_exists_b,
                "in_tree_task_file_exists": task_file_exists_b,
                "commit_trailer_extracted": trailer_b != "",
                "git_notes_exit_code": notes_exit_b,
                "verdict": "Default git clone retains in-tree files and commit trailers, but completely drops git notes (exit 1)."
            },
            "configured_notes_clone": {
                "commit_1_notes_exit": notes_exit_c,
                "notes_payload": notes_content_c,
                "head_advance_notes_on_head_exit": notes_head_after_pull,
                "head_advance_notes_on_parent_exit": notes_parent_after_pull,
                "verdict": "When HEAD advances, git notes remain pinned to parent commit SHA; git notes show HEAD fails (exit 1)."
            },
            "latency_ms_50_iterations": {
                "in_tree_taskfile_p50": sorted(t_taskfile)[25],
                "in_tree_taskfile_max": max(t_taskfile),
                "commit_trailer_p50": sorted(t_trailer)[25],
                "commit_trailer_max": max(t_trailer),
                "git_notes_p50": sorted(t_notes)[25],
                "git_notes_max": max(t_notes)
            }
        }
    return results

def run_cip_vs_merged_test_experiment():
    results = {}
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        repo = os.path.join(td, "repo")
        subprocess.run(["git", "init", "-b", "main", repo], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AntigravityTester"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "tester@antigravity.internal"], cwd=repo, check=True)
        
        # Base code and unit test
        with open(os.path.join(repo, "calc.py"), "w") as f:
            f.write("def add(a, b): return a + b\n")
        with open(os.path.join(repo, "test_calc.py"), "w") as f:
            f.write("from calc import add\ndef test(): assert add(2, 2) == 4\nif __name__ == '__main__': test(); print('UNIT TEST OK')\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base implementation and unit tests"], cwd=repo, check=True, capture_output=True)
        
        # Rogue agent branch: modifies code buggily AND tampers unit test
        subprocess.run(["git", "checkout", "-b", "agent-rogue"], cwd=repo, check=True, capture_output=True)
        with open(os.path.join(repo, "calc.py"), "w") as f:
            f.write("def add(a, b): return 5  # Bug: returns 5\n")
        with open(os.path.join(repo, "test_calc.py"), "w") as f:
            f.write("from calc import add\ndef test(): assert add(2, 2) == 5 # Tampered assertion to pass!\nif __name__ == '__main__': test(); print('TAMPERED TEST PASSED')\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "rogue: tampered implementation and test"], cwd=repo, check=True, capture_output=True)
        
        # Innocent agent branch: adds docs
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "agent-innocent"], cwd=repo, check=True, capture_output=True)
        with open(os.path.join(repo, "README.md"), "w") as f:
            f.write("# Math Library\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "innocent: add documentation"], cwd=repo, check=True, capture_output=True)
        
        # Merge tree verification
        merge_res = subprocess.run(["git", "merge-tree", "--write-tree", "agent-innocent", "agent-rogue"], cwd=repo, capture_output=True, text=True)
        tree_sha = merge_res.stdout.strip()
        merge_success = (merge_res.returncode == 0) and bool(tree_sha)
        
        # Checkout agent-rogue (simulating merged state containing rogue changes)
        subprocess.run(["git", "checkout", "agent-rogue"], cwd=repo, check=True, capture_output=True)
        test_run = subprocess.run(["python3", "test_calc.py"], cwd=repo, capture_output=True, text=True)
        
        # Immutable CIP Benchmark Probe (immutable contract external to branch)
        cip_code = """
import sys
from calc import add
try:
    assert add(2, 2) == 4, 'Invariant violation: add(2, 2) != 4'
    print('CIP PROBE OK')
except AssertionError as e:
    print(f'CIP PROBE FAILED: {e}')
    sys.exit(1)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py") as tf:
            tf.write(cip_code)
            tf.flush()
            cip_run = subprocess.run(["python3", tf.name], cwd=repo, capture_output=True, text=True)
            
        results["cip_vs_merged_tests"] = {
            "git_merge_tree_exit": merge_res.returncode,
            "git_merge_tree_clean": merge_success,
            "merged_tree_test_suite_exit": test_run.returncode,
            "merged_tree_test_suite_output": test_run.stdout.strip(),
            "immutable_cip_probe_exit": cip_run.returncode,
            "immutable_cip_probe_output": cip_run.stdout.strip(),
            "verdict": "Standard merged-tree test run exits 0 (false negative due to test tampering). External CIP invariant probe exits 1 (catches semantic regression)."
        }
    return results

if __name__ == "__main__":
    meta = run_metadata_experiment()
    cip = run_cip_vs_merged_test_experiment()
    full = {**meta, **cip}
    print(json.dumps(full, indent=2))
