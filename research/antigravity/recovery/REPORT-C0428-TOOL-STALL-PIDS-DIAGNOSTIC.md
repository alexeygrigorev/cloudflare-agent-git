# Technical Diagnostic: C-0428 Principal Native Tool Stall (1404s) & PID Limit Analysis

- **Task ID:** `t-principal-c0428-tool-stall-diagnostic-01` (canonical Store admission confirmed)
- **Review Task ID:** `t-principal-c0428-tool-stall-review-01`
- **Observer:** Ant Integration HEAD (`ant-integration-head-recovery`, session UUID `c69a9f51-b751-4400-8bbd-c24cb87fe39a`)
- **Engine / Model:** `antigravity` / `gemini-3.8-flash-high`
- **Timestamp:** 2026-10-08T06:31:00+02:00 (04:31:00 UTC)
- **Status:** **CANONICAL EMPIRICAL DIAGNOSIS (SANITIZED EXPORT)**

---

## 1. Incident Overview: Call Stall (04:02:35–04:25:59 UTC)

- **Source Log:** `<codex-sessions-rollout>/rollout-...-01a0fdd7...jsonl` (private provenance retained)
- **Call Fingerprint:** `call-654fd475...` in turn `turn-01a119a9...`
- **Start Time:** `2026-10-08T04:02:35.164Z` (ordinal 91868)
- **Abort Time:** `2026-10-08T04:25:59.270Z` (ordinal 91871, `"aborted by user after 1404.1s"`)
- **Reported Hook State:** `ResourceUnavailable`
- **Invoked Command Structure:**
  Compound multi-command execution containing `timeout 8s a message inbox --json | jq ...` followed by concurrent captures against sibling sessions.

---

## 2. Empirical Linux Cgroup PID Analysis & Hypothesis Scrutiny

Inspection of the principal's active containment cgroup (`aplexer-workload-f09f5f56...scope`):
1. `pids.max`: **100**
2. `pids.current`: **60**
3. `pids.events`: **`max 66`**

### Thread Census (`pstree -ap <principal-pid>`):
- `MainThread`: 7 threads
- `codex`: 38 threads
- `codex-code-mode`: 14 threads
- **Total Persistent Baseline Threads:** 59–60 threads.

### Rigorous Diagnostic Evaluation:
1. **Historical vs Timed Delta:**
   - The kernel cgroup controller records `max 66` exhaustion events cumulatively over the lifetime of the scope. While it proves that the cgroup reached 100 threads/PIDs 66 times historically, it does not provide millisecond-precision timestamps establishing that exhaustion coincided exactly with `04:02:35Z`.
2. **Available Headroom:**
   - With 60 current threads, 40 process/thread slots remained available. Standard shell commands separated by newlines execute sequentially in subshells, making continuous saturation non-guaranteed.
3. **Plausible Operational Hypothesis:**
   - When `tools.exec_command` spawns compound shell pipelines (`/bin/bash -c ... | jq ... | timeout 8s ...`), brief concurrency bursts during tokio/Node thread allocation and subshell creation can spike thread counts towards 100.
   - If `clone()` returned `EAGAIN` (`Resource temporarily unavailable`), matching `hook ResourceUnavailable`, an unhandled error or stdio pipe deadlock in the tool execution runner is a highly plausible mechanism for the 1404s stall.
   - This remains a strong working hypothesis rather than an absolute mathematical certainty.

---

## 3. Reversible Mitigation Trial (No Blanket Policy)

Rather than imposing permanent constraints from hypothesis alone:
1. **Atomic CLI Execution Trial:**
   - In automated oversight turns, test single, atomic tool invocations rather than compound multi-line pipelines.
   - Observe whether single-command execution eliminates `ResourceUnavailable` hook triggers while maintaining responsive oversight.
2. **Subshell Elimination:**
   - Avoid chaining subshells (e.g. `| jq ...`) inside external CLI calls where native parsing is feasible.
3. **Preserve Subprocess Timeouts:**
   - Continue using explicit timeouts (`timeout 8s ...`) on all external shell calls.

---

## 4. Reconciliation of Store Receipt #49 (`rejected_terminal_replay`)

- **Root Cause Reconciliation:**
  * Task `t-dashboard-c0313-readiness-diagnostic-02` was accepted at `03:27:18` via `launcher accept`.
  * When `launcher record-review` was subsequently called at `03:28:10`, the task had already transitioned to terminal state `accepted`.
  * The store logic records `rejected_terminal_replay` to prevent double-acceptance of terminal tasks.
  * The receipt row (id: 49, report_sha256: `ad83e6b6...`) is immutable and preserved in `review_receipts` table without rewriting.
  * The acceptance of the underlying audit artifacts remains fully valid.

---

## 5. Canonical Store Admission & Oct 8 Publication Custody

1. **Admitted Canonical Store Tasks:**
   - Diagnostic Task: `t-principal-c0428-tool-stall-diagnostic-01` admitted in canonical Store (`agent-quota-launcher/.local/launcher-config/state.db`).
   - Review Task: `t-principal-c0428-tool-stall-review-01` admitted in canonical Store.
   - Publication Task: `t-publication-oct08-fact-packet-01` admitted and queued in canonical Store for staging October 8 evidence packet in `.local/recovery/publication-head-recovery-20261007/STANDUP-EVIDENCE-PACKET-20261008.md`.
2. **Draft Protection:**
   - Main (`6e9a7c6f`) is docs-enforcement head with human draft strictly protected.
   - Retained writer (`e67cafb2`) draft strictly preserved.
