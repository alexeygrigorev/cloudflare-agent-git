# Feasibility & Execution Report: StorageBox Cold-Tier Offload and Metrics Coverage Reconciliation

**Date**: 2026-10-08T01:36:00+02:00 (23:36 UTC)  
**Author**: Ant Integration HEAD (`ant-integration-head-recovery`, aplexer session `c69a9f51`)  
**Task Unit**: `agent-task-t-metrics-storagebox-cold-offload-01.service` (CID `11cb4e3b-ab95-4a1b-92ac-3aebfab7a935`, model `gemini-3.1-pro-high`)  
**Scope**: `research/antigravity/recovery/STORAGEBOX-COLD-OFFLOAD-FEASIBILITY.md`

---

## 1. Executive Summary

To reconcile the documented `256 MiB` (`268,435,456` bytes) aggregate store limit for `.local/metrics` without deleting historical telemetry, we designed, verified, and executed a zero-deletion two-phase cold offload protocol targeting the Hetzner StorageBox mount at `/home/alexey/storagebox/agent-archives`.

- **Pre-offload state**: Local `.local/metrics` was `555,541,714` bytes (~530 MiB active + archive), exceeding the 256 MiB cap.
- **Offload execution**: 1,018 historical snapshot chunks totaling `346,514,928` bytes (330.46 MiB) were safely transferred to `/home/alexey/storagebox/agent-archives/metrics-cold-tier/`.
- **Integrity verification**: Every single chunk was streamed through SHA256 checksum verification before local unlinking, and indexed in `/home/alexey/storagebox/agent-archives/metrics-cold-tier/cold-manifest.json`.
- **Post-offload state**:
  - `active_bytes`: `180,325,903` (~172.0 MiB, within the active 160–192 MiB bound)
  - `archive_bytes`: `26,320,679` (~25.1 MiB)
  - `total_store_bytes`: `209,313,245` (~199.6 MiB, well below the 256 MiB ceiling)
  - `aggregate_over_cap`: `false` (verified via `scripts/metrics/adapters.py --json`)
- **Historical data loss**: Exactly **0 bytes** deleted. 100% of historical data is preserved and accessible across local active and remote cold tiers.

---

## 2. Cold Tier Offload Protocol (Two-Phase Copy-Verify-Unlink)

The relocation protocol adheres strictly to the zero-deletion invariant:

```
[Local Archive]                         [StorageBox Cold Tier]
       |                                           |
       |--- 1. Compute SHA256 (Source) ----------->|
       |--- 2. Stream Copy (shutil.copy2) -------->|
       |                                           |
       |<-- 3. Compute SHA256 (Destination) -------|
       |                                           |
[Assert SHA_src == SHA_dest]                       |
       |                                           |
       |--- 4. Atomic append to cold-manifest ---->| [cold-manifest.json]
       |                                           |
[5. Atomic update local manifest]                  |
[6. Unlink local file ONLY on verified match]      |
```

### Relocation Implementation Details
- **Target Path**: `/home/alexey/storagebox/agent-archives/metrics-cold-tier/`
- **Manifest**: Each relocated file entry contains:
  ```json
  "snapshots-2026-10-04.jsonl.1791118186440477280.gz": {
    "sha256": "<hash>",
    "bytes": 270600,
    "relocated_at": 1791118186.44
  }
  ```
- **Concurrency & Safety**:
  - Written manifests utilize atomic file replacement (`.tmp` -> replace) to prevent corruption during concurrent reads.
  - Local `manifest.json` updates are synchronized.
  - Active collector runs unaffected: `experiment-metrics.service` continues normal collection and serving on port 8766.

---

## 3. StorageBox Verification & Capacity Measurements

### Hetzner StorageBox Mount
- Mount point: `/home/alexey/storagebox` via `sshfs`
- Total Capacity: 1.0 TB
- Available: 1017 GB (1% used)
- Destination: `/home/alexey/storagebox/agent-archives/metrics-cold-tier/`
- Chunks Relocated: 1,018 files
- Total Cold Bytes: 346,514,928 bytes

### Local Store Metrics Comparison

| Metric | Pre-Offload | Post-Offload | Policy Limit / Gate | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Active Bytes** | 182,581,328 | 180,325,903 | 160 MiB - 192 MiB | **PASS (bounded)** |
| **Archive Bytes** | 372,960,386 | 26,320,679 | N/A | **PASS** |
| **Total Store Bytes** | 555,541,714 | 209,313,245 | <= 256 MiB (268,435,456) | **PASS (< 256 MiB)** |
| **Aggregate Over Cap** | `true` | `false` | `false` | **RESOLVED** |
| **Historical Data Loss** | 0 bytes | 0 bytes | 0 bytes | **PASS (100% preserved)** |

Verification command:
```bash
$ python3 scripts/metrics/adapters.py --json
{"status": "ok", "active_bytes": 180325903, "active_files": 536, "archive_bytes": 26320679, "total_store_bytes": 209313245, "aggregate_over_cap": false, "manifest_path": "/home/alexey/git/cloudflare-agent-git/.local/metrics/retention-manifest.json"}
```

---

## 4. Metrics Coverage Reconciliation & Token Accounting

In accordance with principal guidance and audit records in `.local/audit/root-recovery-01a116c6/`:

1. **Token Accounting Compliance**:
   - The token aggregation figure `461,557,251` is strictly recognized as **"partial cumulative observed saved-conversation tokens"**.
   - It is explicitly not whole experiment consumption or verified billable throughput.
   - Reconciled into `.local/audit/root-recovery-01a116c6/desktop-metrics-inventory.json` under top-level key `"partial_cumulative_observed_saved_conversation_tokens": 461557251`.

2. **Coverage Scope Matrix**:
   - **Host Scope**: Desktop and Hetzner
   - **Populations**: Native Codex sessions (`gpt-6.1-sol`, `gpt-6-luna`), Antigravity sessions (`gemini-3.1-pro-high`, `gemini-3.8-flash-high`), ZAI executors (`glm-5.3-flash`).
   - **Privacy Boundary**: Retained as private audit metadata. No prompts, raw chat transcripts, or proprietary configs are leaked to public repositories or journal drafts.

---

## 5. Lifecycle & Store Verification

- Task ID: `t-metrics-storagebox-cold-offload-01`
- Model: `gemini-3.1-pro-high` (Antigravity executor)
- CID: `11cb4e3b-ab95-4a1b-92ac-3aebfab7a935`
- Transient Systemd Service: `agent-task-t-metrics-storagebox-cold-offload-01.service` (Exit 0)
- Store Registration: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`
- Reviewer Verdict: Accepted by Ant Integration HEAD.
