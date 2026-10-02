# Workspace-Doctor D1: Clone Baseline, Value Parity & Executed Mitigation Benchmark

**Date:** 2026-10-02  
**Owner:** `antigravity-head` (`research/antigravity/r8-uv-clone-parity.md`)  
**Evidence Artifact:** [`r8_uv_clone_parity_results.json`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clone_parity_results.json)  
**Execution Script:** [`r8_uv_clone_parity_benchmark.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clone_parity_benchmark.py)  
**Host Budget:** Ephemeral scratch `/tmp/aplexer-uv-clone-parity-spike` (peaked at 62.38 MiB / 100 MiB cap; floor 68.11 GiB free / 8 GiB floor; zero host worktrees touched; zero cargo rebuilds; fully cleaned up).

---

## 1. Executive Summary & Resolution of Peer Challenges

This follow-up benchmark directly addresses the mutual challenges and reviews from **Codex-Principal** (`C-UV-REVIEW`, `01a0fe8a-4ac5` / `01a0fea2-2850`), **Desktop-Orchestrator** (`01a0fe9e-fea8` / `01a0fe9e-ffd9`), and **Grok-Head** (`G-LABEL-20261003`):

1. **Incumbent `clone` Baseline on Linux ext4:** Evaluated official Linux default `uv pip install --link-mode=clone` against `copy`, `hardlink`, and `symlink`.
2. **Exact Pinned Packages:** Pinned `fastapi==0.115.0`, `pydantic==2.9.2`, and `httpx==0.27.2` (resolving 13 packages with compiled binary wheels `pydantic-core==2.23.4`, executed against system CPython 3.12.3).
3. **Execution Parity with Value Assertions:** Two concurrent worker processes (`t1` Auth Service and `t2` Billing Service) executing distinct business logic, generating independent Pydantic models and tokens, with strict JSON content validation (not mock strings).
4. **Executed In-Place Dependency Mutation in ALL Arms:** Actively executed in-place writes to package files across all arms to prove whether mutations leak to sibling worktrees or are caught by permissions boundaries.
5. **Executed `chmod -R a-w` Mitigation:** Directly tested the Workspace-Doctor read-only mitigation on hardlinked virtualenvs.
6. **Continuous Peak Allocation Guard:** Polled peak physical scratch usage continuously; peaked at 62.38 MiB (strictly within 100 MiB cap).

---

## 2. Empirical Matrix

```
+-----------------------------------------------------------------------------------------------------------------------+
|                                                   EMPIRICAL MATRIX                                                    |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
| Metric              | Arm A (Naive Copy)| Arm B (uv clone)  | Arm C (Hardlink Mitigated)| Arm D (uv symlink)  | Notes |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
| Link Mode           | copy              | clone (ext4 fb)   | hardlink + chmod a-w      | symlink             | Args  |
| Package Permissions | 0664 (Writable)   | 0664 (Writable!)  | 0444 (Read-Only)          | 0444 (Read-Only)    | Perms |
| Shared Inode?       | NO (Isolated)     | YES (ino 27162541)| YES (ino 27162541)        | YES (via cache link)| Inodes|
| Value Parity Assert | PASS (Distinct)   | PASS (Distinct)   | PASS (Distinct)           | PASS (Distinct)     | JSON  |
| In-Place Mutation   | No leak (safe)    | LEAKED TO T2!     | BLOCKED (PermissionError) | BLOCKED (PermError) | Hazard|
| Pre-run Trees Union | 22,626,304 B      | 11,788,288 B      | 11,788,288 B              | 4,087,808 B         | Static|
| Post-run Trees Union| 27,418,624 B      | 16,580,608 B      | 11,796,480 B              | 8,880,128 B         | Exec  |
| Post-run Trees Sav. | Baseline (0.0%)   | 39.53% savings    | 56.98% savings (PASS >50%)| 67.61% (PASS >50%)  | Trees |
| Whole Footprint     | 49,782,784 B      | 28,114,944 B      | 23,339,008 B              | 31,268,864 B        | Total |
| Whole Footprint Sav.| Baseline (0.0%)   | 43.52% savings    | 53.12% savings (PASS >50%)| 37.19% savings      | Gate  |
| Whole Gate Verdict  | FAIL (<50%)       | FAIL (<50%)       | PASS (>50% Gate Met!)     | FAIL (<50%)         | Gate  |
+---------------------+-------------------+-------------------+---------------------------+---------------------+-------+
```

---

## 3. Key Findings

### A. The Ext4 `clone` Fallback Reality Check
- Official `uv` documentation states that `--link-mode=clone` is the default on Linux.
- However, Linux `clone` relies on copy-on-write ioctl (`ioctl(FICLONE)` / reflink), which requires filesystem support (`btrfs`, `xfs`, `zfs`).
- On the user's host (ext4 on `/dev/nvme0n1p3` and `/tmp` on `/dev/nvme1n1`), `ioctl(..., FICLONE, ...)` returns `[Errno 95] Operation not supported`.
- **Empirical Behavior:** When `uv` encounters unsupported FICLONE on the same filesystem, it silently falls back to **hardlinks** (`shared_package_inode: true`, `ino: 27162541`).
- **Hazard Consequence:** Because default `clone` degrades to hardlinks without setting read-only permissions, an in-place edit in Task 1 silently leaks to Task 2 (`mutation_leaked_to_t2: True`).
- **Gate Result:** Arm B achieved **39.53%** worktree savings and **43.52%** whole-footprint savings, **failing both >50% gates**.

### B. Workspace-Doctor Arm C Passes the Whole-Footprint Gate (>50%)
- When Workspace-Doctor applies the read-only mitigation (`chmod -R a-w .venv/lib/*/site-packages`):
  1. **Safety:** An accidental in-place write by Task 1 fails immediately with `PermissionError: [Errno 13] Permission denied`, preventing any silent mutation of Task 2 or the shared cache (`mutation_leaked_to_t2: False`).
  2. **Bytecode Suppression:** Because `site-packages/` is read-only, Python does not emit local unlinked `.pyc` bytecode files into `site-packages/` during execution (post-run trees union grew by only +8 KiB vs +4.8 MiB in Arm B).
  3. **Whole Footprint Savings:** With bytecode growth suppressed and static packages deduplicated, Arm C achieved **56.98% worktree savings** and **53.12% whole-footprint savings** (23.34 MiB vs 49.78 MiB), **fully passing the >50% whole-footprint gate**.

### C. Symlink Mode (Arm D)
- Symlink mode achieves the highest worktree savings (**67.61%** post-run), but because the shared cache (22.36 MiB) is included in the whole-footprint calculation across 2 small tasks, its whole-footprint savings is **37.19%** (below the 50% gate).
- Symlinks operate across cross-device mount boundaries (e.g. `/` to `/tmp`), whereas hardlinks and ext4 clone fail across mount points.

---

## 4. Scope & Recovery
- Peak scratch footprint: 62.38 MiB (well below 100 MiB cap).
- All scratch trees removed immediately after benchmark.
- Data captured in [`r8_uv_clone_parity_results.json`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_clone_parity_results.json).
