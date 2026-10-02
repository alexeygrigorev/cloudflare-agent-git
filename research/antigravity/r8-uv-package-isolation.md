# Workspace-Doctor D1: Real Package Isolation Benchmark (Python `uv`)

**Date:** 2026-10-02  
**Owner:** `antigravity-head` (`research/antigravity/r8-uv-package-isolation.md`)  
**Evidence Artifact:** [`r8_uv_package_isolation_results.json`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_package_isolation_results.json)  
**Execution Script:** [`r8_uv_package_isolation.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_package_isolation.py)  
**Host Budget:** Ephemeral scratch `/tmp/aplexer-uv-isolation-spike/` (allocated 70.2 MiB / 100 MiB cap; floor 68.3 GiB free / 8 GiB floor; zero host worktrees touched; zero cargo rebuilds).

---

## 1. Executive Summary & Hypotheses Tested

In response to Claude's host reality check (Heartbeat 2054, identifying that Python `.venv` copies dominate developer disk consumption at 57.3 GiB across 215 directories) and Orchestrator directive `HEARTBEAT2124`, Antigravity executed the **Workspace-Doctor D1** physical storage and isolation benchmark on a real Python web stack (`fastapi`, `pydantic`, `pydantic-core`, `httpx`, `starlette`, `anyio` — 14 packages, ~11.5 MiB).

We evaluated 2 concurrent tasks (`t1` and `t2`) performing simultaneous code editing, model validation, and test executions across three architectural arms:
1. **Arm A (Naive Copied `.venv`):** Standard per-worktree environment copies (`uv pip install --link-mode=copy`).
2. **Arm B (Workspace-Doctor Hardlink Store):** Shared immutable package cache with hardlinked `.venv` (`UV_LINK_MODE=hardlink`).
3. **Arm C (Workspace-Doctor Symlink Store):** Shared package cache with symlinked `.venv` (`UV_LINK_MODE=symlink`).

```
+-----------------------------------------------------------------------------------------+
|                                    EMPIRICAL MATRIX                                     |
+---------------------+-------------------+-------------------+-------------------+-------+
| Metric              | Arm A (Naive Copy)| Arm B (Hardlink)  | Arm C (Symlink)   | Notes |
+---------------------+-------------------+-------------------+-------------------+-------+
| Pre-run Trees Union | 23,142,400 B      | 12,095,488 B      | 4,333,568 B       | Static|
| Pre-run Savings %   | Baseline (0.0%)   | 47.73% savings    | 81.27% savings    | Deps  |
| Post-run Trees Union| 29,483,008 B      | 18,436,096 B      | 10,674,176 B      | Exec  |
| Post-run Savings %  | Baseline (0.0%)   | 37.47% savings    | 63.80% savings    | >50%  |
| Total Physical Union| 52,129,792 B      | 30,044,160 B      | 33,337,344 B      | w/cach|
| Total Footprint Sav.| Baseline (0.0%)   | 42.37% savings    | 36.05% savings    | Total |
| Source Inode Separ. | PASS (Isolated)   | PASS (Isolated)   | PASS (Isolated)   | Safe  |
| Output Inode Separ. | PASS (Isolated)   | PASS (Isolated)   | PASS (Isolated)   | Safe  |
| Package Permissions | 0664 (Writable)   | 0664 (Writable!)  | Symlink -> Cache  | Alert |
| In-Place Mut. Leaks | NO (Safe copy)    | YES (CORRUPTS T2!)| YES (CORRUPTS T2!)| Hazard|
+---------------------+-------------------+-------------------+-------------------+-------+
```

---

## 2. Key Findings & Critical Hazard Disclosures

### A. The In-Place Dependency Mutation Hazard (Hardlink Inode Leakage)
- **Empirical Demonstration:** In Arm B (`UV_LINK_MODE=hardlink`), package files in `t1/.venv` and `t2/.venv` share identical filesystem inodes (`st_ino: 27140557`).
- **Default Permissions:** Unlike `pnpm` (which marks store files read-only `0444`), `uv` leaves installed package files with wheel permissions (`0664` — writable by the current user).
- **The Failure Mode:** When Task 1 opened `site-packages/fastapi/__init__.py` and performed an in-place write (`open(..., 'a').write(...)`), the write directly mutated the shared disk inode. Consequently:
  - Task 2's `site-packages/fastapi/__init__.py` was **silently mutated** (`mutation_leaked_to_t2: True`).
  - The shared `uv` cache was also **permanently corrupted**.
- **Required Mitigation for Workspace-Doctor:**
  Any tool managing shared hardlinked virtualenvs **must enforce read-only permissions** (`chmod -R a-w .venv/lib/*/site-packages`) immediately following installation. This causes accidental in-place modifications by agents or debuggers to fail immediately with `PermissionError` (EACCES) rather than silently corrupting sibling worktrees.

### B. The Python Runtime Bytecode (`__pycache__`) Divergence
- At install time (pre-run), Arm B achieves **47.73% physical savings** on worktrees (12.09 MiB vs 23.14 MiB) because all `.py` files share inodes.
- During execution, the Python interpreter dynamically generates unlinked `.pyc` bytecode files into each worktree's `site-packages/` directory (`st_nlink: 1`).
- Because bytecode files are compiled locally per worktree, post-run hardlink savings drop to **37.47%** (18.43 MiB vs 29.48 MiB).
- **The Symlink Advantage (Arm C):** In symlink mode, directory entries are symlinks pointing directly into the cache. Python either references cached bytecode or symlinks remain minimal, yielding **63.80% physical savings** post-run (10.67 MiB vs 29.48 MiB), exceeding the $>50\%$ pass criterion.

### C. The Cross-Device Mount Point Boundary
- Linux hardlinks cannot span filesystem mount points. On the user's host, `/` (`/dev/nvme0n1p3`) and `/tmp` (`/dev/nvme1n1`) are separate NVMe block devices.
- If `UV_CACHE_DIR` resides on `/` and worktrees reside on `/tmp`, `uv` emits a warning and falls back to full copy (`--link-mode=copy`).
- Symlinking (`--link-mode=symlink`) completely bypasses this limitation, allowing cross-device sharing with 63.8% physical savings.

---

## 3. Strict Scope & Product Boundary

- **Tiny-Fixture Scope:** This benchmark measures a real 14-package web stack across 2 concurrent tasks. It proves the mechanism and physical block allocation behavior of `uv` package deduplication.
- **Truthful Claim Boundary:** We do **not** extrapolate these results into an unverified claim of reducing total user-host storage by 63%, nor do we infer a proprietary Cloudflare product from local filesystem tests. Host-wide savings depend entirely on project dependency breadth, compiler artifacts, and cache residency.
- **Artifacts:**
  - Script: [`research/antigravity/r8_uv_package_isolation.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_package_isolation.py)
  - Data: [`research/antigravity/r8_uv_package_isolation_results.json`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r8_uv_package_isolation_results.json)
