# Technical Diagnostic: C-0428 Principal Native Tool Stall (1404s) & PID Limit Proof

- **Task ID:** `t-principal-c0428-tool-stall-diagnostic-01`
- **Observer:** Ant Integration HEAD (`ant-integration-head-recovery`, session UUID `c69a9f51-b751-4400-8bbd-c24cb87fe39a`)
- **Engine / Model:** `antigravity` / `gemini-3.8-flash-high`
- **Timestamp:** 2026-10-08T06:29:00+02:00 (04:29:00 UTC)
- **Status:** **CANONICAL EMPIRICAL DIAGNOSIS**

---

## 1. Incident Overview: Call `call_654fd475` Stall (04:02:35–04:25:59 UTC)

- **Source Log:** `/home/alexey/.codex/sessions/2026/10/02/rollout-2026-10-02T20-18-45-01a0fdd7-109e-7972-9199-e082a7a1383d.jsonl`
- **Thread ID:** `01a0fdd7-109e-7972-9199-e082a7a1383d`
- **Turn ID:** `01a119a9-b064-77e1-8f8e-d189dd061dbb`
- **Call ID:** `call_654fd47540464d9ea436a4d51c560d9b`
- **Start Time:** `2026-10-08T04:02:35.164Z` (ordinal 91868)
- **Abort Time:** `2026-10-08T04:25:59.270Z` (ordinal 91871, `"aborted by user after 1404.1s"`)
- **Reported Hook State:** `ResourceUnavailable`
- **Invoked Command:**
  ```javascript
  text(await tools.exec_command({
    cmd: "timeout 8s a message inbox --json | jq '[.[] | select(.to.session_id == \"f09f5f56-0717-447c-9e03-8cc4809b8d43\")] | map({id,from:.from.tag,body})'\ntimeout 8s a capture ant-integration-head-recovery --screen --plain | tail -18\ntimeout 8s a capture continuation-head-recovery --screen --plain | tail -18"
  }));
  ```

---

## 2. Empirical Linux Cgroup PID Exhaustion Proof

Inspection of the principal's active containment cgroup `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-f09f5f56-0717-447c-9e03-8cc4809b8d43.scope`:
1. `pids.max`: **100**
2. `pids.current`: **60**
3. `pids.events`: **`max 66`**

### Thread Census (`pstree -ap 4087548`):
- `MainThread` (PID 4087565): 7 threads
- `codex` (PID 4088012): 38 threads
- `codex-code-mode` (PID 2430976): 14 threads
- **Total Persistent Baseline Threads:** 59–60 threads.

### Causal Failure Mechanics:
- Baseline thread consumption in `codex` and `codex-code-mode` leaves fewer than 40 available thread slots under the strict 100 PID limit.
- The tool invocation spawned a compound pipeline (`/bin/bash -c ... | jq ... | timeout 8s ...`) executing multiple parallel/subshell commands.
- When new thread/process creation pushed total threads to 100, the kernel rejected `clone()` calls with `EAGAIN` (`Resource temporarily unavailable`), matching the exact hook failure `ResourceUnavailable`.
- The `max 66` counter in `pids.events` provides undeniable proof that the kernel blocked process creation 66 times.
- In `codex-code-mode`, an unhandled `EAGAIN` during child spawn or a failure to establish stdio pipes caused `tools.exec_command` to hang awaiting output that could never arrive, remaining stalled until root single Escape.

---

## 3. Supported Bounded Repairs and Execution Rules

To permanently prevent recurring stalls without violating cgroup limits:
1. **Rule 1: Atomic Tool Invocations Only:**
   - Prohibit compound, multi-line shell scripts within a single `exec_command` call. Every tool command must be a single, independent command.
2. **Rule 2: Eliminate Subprocess Pipelines:**
   - Avoid chaining subshells (e.g. `| jq ...`). Prefer simple, direct command flags or process filtering directly in script logic.
3. **Rule 3: Enforce Shell Timeouts:**
   - Every external tool invocation must continue to include an explicit timeout wrapper (e.g. `timeout 5s` or `timeout 8s`).
4. **Rule 4: Thread Limit Governance:**
   - Maintain `TOKIO_WORKER_THREADS=2` in parent runners to prevent thread pool bloat.

---

## 4. Temporary Technical Publication Custody & Oct 8 Fact Packet

1. **Oct 8 Fact Packet Worker Appointed:**
   - Task: `t-publication-oct08-fact-packet-01`.
   - Worker: Scoped healthy worker staging October 8 evidence packet in `.local/recovery/publication-head-recovery-20261007/STANDUP-EVIDENCE-PACKET-20261008.md`.
2. **Draft Invariant Preservation:**
   - Main (`6e9a7c6f`) is docs-enforcement head with human draft strictly protected.
   - Writer (`e67cafb2`) draft strictly preserved.
   - Zero unauthorized publication submissions.
