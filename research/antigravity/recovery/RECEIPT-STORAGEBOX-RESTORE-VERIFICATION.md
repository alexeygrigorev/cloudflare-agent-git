# Restore Receipt: StorageBox Cold-Tier Telemetry Verification

**Date**: 2026-10-08T01:41:00+02:00  
**Verifier**: Ant Integration HEAD (`ant-integration-head-recovery`, session `c69a9f51`)  
**Scope**: `research/antigravity/recovery/RECEIPT-STORAGEBOX-RESTORE-VERIFICATION.md`

---

## 1. Scope & Qualification

This receipt validates the integrity, retrievability, and restoration fidelity of historical metrics snapshot chunks relocated from `.local/metrics/archive/` to the Hetzner StorageBox cold tier at `/home/alexey/storagebox/agent-archives/metrics-cold-tier/`.

### Terminology Clarification
- **Operation Type**: **Verified relocation with retained remote bytes**.
- **Local Disposition**: Local copies were unlinked strictly after cryptographic verification of destination chunk integrity. Remote copies are retained with 100% data preservation on Hetzner StorageBox.
- **Reviewer Qualification**: The initial review `t-metrics-storagebox-review-01` (`REV-METRICS-STORAGEBOX-COLD-OFFLOAD-01.md`) represents **independent-actor corroboration** (executed by an isolated transient unit under Gemini 3.1 Pro High). Full distinct-model review remains pending once hostwide ZAI capacity/quota headroom permits.

---

## 2. Cold Manifest & StorageBox Volume Verification

- **StorageBox Mount**: `/home/alexey/storagebox` (sshfs mount, 1017 GB available)
- **Cold Tier Path**: `/home/alexey/storagebox/agent-archives/metrics-cold-tier/`
- **Cold Manifest**: `cold-manifest.json`
- **Total Relocated Files**: **1,018 files**
- **Total Preserved Cold Bytes**: **346,514,928 bytes (330.46 MiB)**
- **Integrity Protocol**: Source SHA256 == Destination SHA256 check asserted prior to local unlinking.

---

## 3. Empirical Restore Test (Decompression & Content Validation)

A random historical chunk from the cold tier was selected and tested for retrieval, checksum matching, decompression, and JSONL record parsing:

```python
Sample Chunk: snapshots-2026-10-03.jsonl.1791002646999455606.gz
Recorded SHA256: 33654d0fedae760a47ac2c72c4325fe960f8b20a3c8089f253c4b5ee7fd5afe0
Computed SHA256: 33654d0fedae760a47ac2c72c4325fe960f8b20a3c8089f253c4b5ee7fd5afe0
Byte Size Match: 292,300 bytes recorded == 292,300 bytes on disk (EXACT MATCH)
Decompression:   PASS (valid gzip stream)
Record Count:    70 valid JSONL metrics records parsed
```

Sample record header:
```json
{"timestamp": 1791002647, "services": {"active": true}, ...}
```

---

## 4. Foreign Audit Scope Integrity

- **Root Audit Directory**: `.local/audit/root-recovery-01a116c6/`
- **Integrity**: Prior modification to `.local/audit/root-recovery-01a116c6/desktop-metrics-inventory.json` has been **reverted to its exact beforeimage** (zero foreign edits).
- **Ant Recovery Intake**: Token reconciliation metadata is housed exclusively within Ant's declared scope at:
  `research/antigravity/recovery/METRICS-COVERAGE-DESKTOP-RECONCILIATION.json`.
- **Classification**: `461,557,251` is strictly recognized as *partial cumulative observed saved-conversation tokens* across native Codex desktop rollouts, not billable experiment spend.

---

## 5. Live Service Chronology

- **Service**: `experiment-metrics.service`
- **PID**: `4168827`
- **Start Timestamp**: `Wed 2026-10-07 11:08:34 CEST` (active for >14h)
- **Verification**: Service was not restarted, reloaded, or mutated during this recovery session. It remains running continuously on port 8766.
- **Supervisor**: `supervision.service` (PID `3587751`, loaded from baseline `ca5ea38`) remains active with zero reload.
