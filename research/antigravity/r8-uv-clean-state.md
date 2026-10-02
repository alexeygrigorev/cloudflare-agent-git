# Workspace-Doctor D1: Clean-State Controlled Benchmark & Bytecode Normalization

**Date:** 2026-10-02  
**Owner:** `antigravity-head` (`research/antigravity/r8-uv-clean-state.md`)  
**Evidence Artifact:** [`r8_uv_clean_state_results.json`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clean_state_results.json)  
**Execution Script:** [`r8_uv_clean_state_benchmark.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clean_state_benchmark.py)  
**Host Budget:** Unique ephemeral directory `tempfile.mkdtemp(prefix="aplexer-uv-spike-")` (peaked at 68.80 MiB / 100 MiB cap; floor 67.93 GiB free / 8 GiB floor; zero host worktrees touched; zero cargo rebuilds; fully cleaned up).

---

## 1. Executive Summary & Resolution of Confounds

In response to Desktop-Orchestrator's **HEARTBEAT2224 STORAGE REVIEW**, Antigravity implemented and executed a fully controlled clean-state benchmark resolving all five identified confounds:

1. **Unique Owned Scratch Control:** Created ephemeral directory via `tempfile.mkdtemp(prefix="aplexer-uv-spike-", dir="/tmp")`. Cleaned up strictly its own path on exit, with zero startup deletion of fixed paths.
2. **Cache Isolation & Manifest Integrity:** Populated an immutable template cache once (455 files, sha256 manifest recorded). Every arm received an independent, pristine copy of the cache with pre- and post-run manifest verification. No arm ever shared or mutated another arm's cache.
3. **Controlled Bytecode Normalization:** Evaluated arms under both (a) default execution and (b) normalized bytecode execution (`PYTHONDONTWRITEBYTECODE=1` across all arms, including baseline copy).
4. **Threat Model Empirical Validation:** Proved that `chmod a-w` reliably catches accidental file writes (`PermissionError`), but owner process can execute `chmod u+w` to reverse it. Established formal threat model: accidental-write guard, not security sandbox.
5. **Active Process-Group Peak Guard:** Implemented live polling thread with active process-group termination (`os.killpg(SIGKILL)`) if scratch ever exceeded 100 MiB. Scratch peaked at 68.80 MiB.

---

## 2. Empirical Matrix: Default vs Normalized Bytecode

```
+-----------------------------------------------------------------------------------------------------------------------+
|                                    PART A: DEFAULT BYTECODE (BYTECODE ASYMMETRY)                                      |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
| Metric              | Arm A (Naive Copy)| Arm B (uv clone)  | Arm C (Hardlink Mitigated)| Arm D (uv symlink)  | Notes |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
| Post-run Trees Union| 27,418,624 B      | 16,580,608 B      | 11,796,480 B              | 8,880,128 B         | Trees |
| Post-run Trees Sav. | Baseline (0.0%)   | 39.53% savings    | 56.98% savings            | 67.61% savings      | Trees |
| Whole Footprint     | 49,782,784 B      | 28,106,752 B      | 23,322,624 B              | 31,244,288 B        | Total |
| Whole Footprint Sav.| Baseline (0.0%)   | 43.54% savings    | 53.15% savings            | 37.24% savings      | Total |
| Whole Gate Verdict  | FAIL (<50%)       | FAIL (<50%)       | WITHHELD (Confounded)     | FAIL (<50%)         | Gate  |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+

+-----------------------------------------------------------------------------------------------------------------------+
|                              PART B: NORMALIZED BYTECODE (PYTHONDONTWRITEBYTECODE=1 ALL ARMS)                         |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
| Metric              | Arm A (Naive Copy)| Arm B (uv clone)  | Arm C (Hardlink Mitigated)| Arm D (uv symlink)  | Notes |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
| Post-run Trees Union| 22,634,496 B      | 11,796,480 B      | 11,796,480 B              | 4,096,000 B         | Trees |
| Post-run Trees Sav. | Baseline (0.0%)   | 47.88% savings    | 47.88% savings            | 81.90% savings      | Trees |
| Whole Footprint     | 44,998,656 B      | 23,322,624 B      | 23,322,624 B              | 26,460,160 B        | Total |
| Whole Footprint Sav.| Baseline (0.0%)   | 48.17% savings    | 48.17% savings            | 41.20% savings      | Total |
| Whole Gate Verdict  | FAIL (<50%)       | FAIL (<50%)       | FAIL (48.17% < 50.0% Gate)| FAIL (<50%)         | Gate  |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
```

---

## 3. Critical Findings & Mathematical Proof of the Confound

### A. The Bytecode Divergence Confound Dissected
- In Part A (Default Execution), Arm C appeared to save **53.15%** of the whole footprint.
- However, when baseline Arm A was normalized with `PYTHONDONTWRITEBYTECODE=1` (Part B), Arm A's whole footprint dropped from 49.78 MiB to 44.99 MiB because unlinked `.pyc` files were not generated.
- Consequently, under like-for-like normalized bytecode comparison, Arm C's true package deduplication savings is **48.17%** (23.32 MiB vs 44.99 MiB).
- **Gate Verdict:** **48.17% is strictly below the >50% gate.** Across 2 concurrent tasks, static package sharing alone achieves 48.17% whole-footprint reduction. The earlier >50% reading was an artifact of `.pyc` suppression asymmetry.

### B. Threat Model Empirical Validation (Accidental Guard vs Security Sandbox)
- **Accidental Write Guard (Validated):** A normal in-place write attempt (`open(..., "a")`) into a `chmod a-w` protected virtualenv fails immediately with `PermissionError: [Errno 13] Permission denied`. This fully protects against accidental debugger writes, naive agent file modifications, and cache inode corruption (`mutation_leaked_to_t2: False`).
- **Owner Reversibility (Validated):** Because the agent or developer process runs under user UID (`alexey`), a deliberate command executing `chmod u+w <file>` succeeds, permitting subsequent writes.
- **Formal Boundary:** Workspace-Doctor's permissions mitigation is an **accidental-write coordination guard**, NOT a sandboxing mechanism against hostile code. True isolation requires Linux user namespaces, chroots, or container boundaries.

---

## 4. Final D1 Status & Recommendation
- **Status:** Complete empirical characterization logged in [`r8_uv_clean_state_results.json`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clean_state_results.json).
- **Gate Conclusion:** D1 whole-footprint gate for 2 concurrent tasks is **NOT MET (48.17% measured vs >50% requirement)** when evaluated under strict like-for-like bytecode controls.
- **Scaling Property:** For $N=2$ tasks, cache amortisation yields 48.17%. For $N \ge 3$ tasks, the mathematical bound $\frac{(N-1) \times \text{Deps}}{N \times \text{Deps} + \text{Cache}}$ exceeds 50% (e.g. $N=3 \implies \sim 64\%$). But on the strict $N=2$ gate, it is truthfully recorded as 48.17%.
