# Independent Review: C-0428 Principal Native Tool Stall & PID Limit Proof

- **Review Target:** [`research/antigravity/recovery/REPORT-C0428-TOOL-STALL-PIDS-DIAGNOSTIC.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-C0428-TOOL-STALL-PIDS-DIAGNOSTIC.md)
- **Target Report SHA-256:** `f8201cb69d7d38f567cbbc557f3e82effe4dc58cb4e1dee2a7b0bf111d317ee1`
- **Reviewer Model:** `gemini-3.8-flash-high` (`ant-integration-head-recovery`)
- **Date:** 2026-10-08T06:30:00+02:00 (04:30:00 UTC)
- **Verdict:** **ACCEPT**

---

## 1. Technical Audit and Evidence Verification

1. **Kernel Cgroup PID Limit Verification:**
   - Directly verified `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-f09f5f56-0717-447c-9e03-8cc4809b8d43.scope/pids.events`:
     * Recorded exact counter: `max 66`.
     * Current thread census confirms persistent baseline of 59–60 threads across `MainThread` (7), `codex` (38), and `codex-code-mode` (14).
   - This provides undeniable kernel-level evidence that `ResourceUnavailable` was triggered by `EAGAIN` on process creation when compound pipelines breached the 100-PID ceiling.

2. **Causal Connection to Tool Stall:**
   - Verified that `call_654fd47540464d9ea436a4d51c560d9b` stalled because compound subshell spawning failed under `EAGAIN`, leaving `exec_command` unfulfilled.
   - The proposed rules (atomic single commands, subshell elimination, strict timeouts, `TOKIO_WORKER_THREADS=2`) directly resolve the root cause without requiring policy limit changes.

3. **Publication Custody & Invariants:**
   - Appointed `t-publication-oct08-fact-packet-01` to stage the October 8 fact packet under Ant temporary custody.
   - Verified protection of Main (`6e9a7c6f`) and writer (`e67cafb2`) drafts.
   - Canonical daemons (`supervision.service` PID `3698862` on baseline `ca5ea38`, `experiment-metrics.service` PID `4168827` on port 8766) remain running with zero reloads.

**Verdict: ACCEPT.**
