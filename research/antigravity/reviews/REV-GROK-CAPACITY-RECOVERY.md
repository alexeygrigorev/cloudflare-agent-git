# REV-GROK-CAPACITY-RECOVERY — Independent Review: Grok Capacity Recovery Policy and Findings Audit

- **Reviewer:** Independent Grok Capacity Recovery Reviewer (tag: `grok-capacity-reviewer`).
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1818, User 26/32, and latest C182x directives.
- **As-of:** 2026-10-04 13:55 CEST (11:55 UTC).
- **Target Directory Audited:** [`research/grok/capacity-recovery/`](file:///home/alexey/git/cloudflare-agent-git/research/grok/capacity-recovery/).
- **Target Files:**
  - [`research/grok/capacity-recovery/FINDINGS.md`](file:///home/alexey/git/cloudflare-agent-git/research/grok/capacity-recovery/FINDINGS.md)
  - [`research/grok/capacity-recovery/policy.py`](file:///home/alexey/git/cloudflare-agent-git/research/grok/capacity-recovery/policy.py)
  - [`research/grok/capacity-recovery/test_policy.py`](file:///home/alexey/git/cloudflare-agent-git/research/grok/capacity-recovery/test_policy.py)
- **Deliverable Path:** [`research/antigravity/reviews/REV-GROK-CAPACITY-RECOVERY.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-GROK-CAPACITY-RECOVERY.md).
- **Scratch Workspace:** `.local/scratch/grok-capacity-review/` (mode `0700`, measured disk: 8.0 KB $\le$ 512 MB, `TMPDIR` strictly within scratch root, zero net `/tmp` growth).
- **Verdict:** **BOUNDED ACCEPTANCE (OFFLINE DRY-RUN SPECIFICATION & ADVISORY GATES VERIFIED; RUNTIME UNINSTALLED; PARITY UNPROVEN)**.

---

## 1. Executive Summary & Verdict

Under Codex Principal directives C1818, User messages 26 and 32, and Desktop Orchestrator instructions, this independent audit conducts a rigorous negative test and edge-case review of the Grok capacity recovery policy and findings deliverable in `research/grok/capacity-recovery/`.

The primary incident under investigation occurred when a live Codex principal TUI session encountered capacity rejection:
`Selected model is at capacity. Please try a different model.`
Followed by the default empty composer `Ask Codex to do anything`. Aplexer reported state remained stale `working`, preventing native delivery because the installed runtime requires an authentic reported `idle` or `waiting` transition.

### Core Audit Verdict:
**BOUNDED ACCEPTANCE.** The offline dry-run recovery policy, classification heuristics, and 20 offline unit tests authored by Grok (`08fee82b`) are mechanically verified, soundly structured, and remain strictly uninstalled. However, this acceptance is bounded by several critical epistemic and implementation boundaries:
1. **Installed Parity Unproven:** The installed runtime (`~/.local/bin/aplexer` v0.1.9) lacks the `message readiness` query verb and lacks native capacity/error hook mappings in `~/.codex/hooks.json`. An offline 180s timer cannot manufacture `state-report idle`. Automatic runtime recovery on installed 0.1.9 remains unproven and non-functional without native protocol-level error event handling.
2. **Identified Policy Gaps (Must be corrected before any integration):**
   - **Unsampled Quota Bypass (`quota=None`):** `classify_blocker()` fails to enforce fail-closed behavior when `obs.quota` is omitted (`None`), permitting `dry_run_same_conversation_retry` instead of returning `block_quota_unknown`.
   - **Unmodelled 512 MB Scratch Ceiling:** `ResourceSample` and `policy.py` only model host root disk space (50 GiB / 8 GiB) and available memory (10 GiB), with zero modeling or enforcement of the per-task 512 MB scratch budget.
   - **ANSI Sequence Vulnerability:** Terminal escape sequences on prompt symbols cause `classify_composer()` to fail closed (`unknown` -> `block_unknown`), causing availability failure if unstripped raw PTY screen buffers are ingested.
3. **Non-Interference Invariants Upheld:** Zero binary replacements, zero cargo/rustc invocations, zero competing daemons, and zero uncoordinated core production edits.

---

## 2. Pinned Source & Parity Demarcation Audit

### 2.1 Artifact Demarcation Matrix

The audit inspected the local filesystem to establish the exact epistemic boundary between the protocol source tree, supervision service defaults, and installed runtime:

| Component | Pinned Location & Identity | Verified Capabilities & Gaps | Epistemic Status |
| :--- | :--- | :--- | :--- |
| **Installed CLI Runtime** | `/home/alexey/.local/bin/aplexer`<br>Version: `a 0.1.9`<br>SHA-256: `8d49a216d4...`<br>Build mtime: 2026-10-02 22:53 +0200 | Has `message deliver`.<br>**Lacks** `message readiness` subcommand (`error: unrecognized subcommand 'readiness'`).<br>Hooks: `claude` and `codex` `hook-notice` only. | **Authoritative Host Runtime.** All real deliveries must pass through this binary. |
| **Protocol Worktree (Supervision Target)** | `/home/alexey/git/cloudflare-aplexer-protocol`<br>Branch: `fix/prompt-ready-lifecycle`<br>HEAD: `7efa49386d...`<br>Debug binary: `target/debug/aplexer` (mtime: 2026-10-03 11:03) | Contains `evaluate_readiness_verdict` in `src/bin/aplexer/message_deferred.rs`.<br>Rejects `running`, requires `reported` source + `idle`/`waiting`. Used by `scripts/supervision/service.py` (`SUPERVISION_APLEXER_BINARY`). | **Experimental Protocol Tree.** Unmerged, uninstalled globally. |
| **Dirty Main Checkout** | `/home/alexey/git/aplexer`<br>Branch: `main` (ahead 4)<br>HEAD: `bc0d3d75ab...`<br>Dirty files: `src/watch.rs`, `src/watch/state.rs` | Contains 8,000ms reported-state TTL logic and PTY heuristic fallbacks. | **Dirty Local Workspace.** Not installed, not authoritative. |

### 2.2 Hook Lifecycle & The Stale `working` Deadlock

The installed Codex hooks configuration (`/home/alexey/.codex/hooks.json`) reveals:
- `UserPromptSubmit` / `SessionStart` $\rightarrow$ `/home/alexey/.local/bin/a state-report working || true`
- `Stop` $\rightarrow$ `/home/alexey/.local/bin/a state-report idle || true`

**The Root Cause of Stalled Recovery:**
When Codex encounters `Selected model is at capacity. Please try a different model.`, the model provider halts generation abnormally. Crucially:
1. Codex does **not** fire the `Stop` event (or if fired, fails to transition state), leaving `reported_state` locked at `working`.
2. There is no `OnError` or `CapacityRejection` hook event in installed Codex CLI (v0.160.0) or in `CODEX_EVENTS` (`src/hooks/mod.rs`).
3. Under both protocol source `7efa493` (`message_deferred.rs` lines 73–128) and installed runtime `0.1.9`, delivery requires an authentic `idle` or `waiting` state report from the recipient session.
4. An expired `working` report (after 8s TTL) falls back to PTY screen heuristics, but PTY heuristics cannot synthesize a `reported` status; `evaluate_readiness_verdict` explicitly rejects inferred states for deferred message submission.
5. Therefore, **an offline timer (even after 180s, 360s, or 720s) cannot clear the stale working lock**. Any attempt to deliver via installed aplexer results in `not-ready: recipient reported working`.

### 2.3 Evaluation of Grok's FINDINGS.md Claims vs Owner Summaries

In [`FINDINGS.md`](file:///home/alexey/git/cloudflare-agent-git/research/grok/capacity-recovery/FINDINGS.md), Grok explicitly and accurately details this boundary:
- Line 83: *"A 180s timer does not emit state-report idle."*
- Line 99: *"So: empty composer after capacity plus an 8s-expired working report still fails deliver, because Ready requires a fresh idle/waiting report. A timer cannot manufacture that. Need a reviewed engine-native error event and/or readiness fix, not pretend this candidate repairs installed runtime."*
- Line 101: *"Installed 0.1.9 deliver exists; whether its Ready predicate equals protocol 7efa493 is unproven. Fail closed: treat native NOTREADY as authoritative."*

However, in earlier summary communications (flagged by Codex Principal in `01a106bd-f1ec`), statements referencing an "installed deliver Ready predicate" risked conflating protocol source predicates with installed binary behavior. The audit confirms:
- **FINDINGS.md is factually bounded and truthful:** It correctly treats installed 0.1.9 parity as unproven and NOTREADY as authoritative.
- **Runtime Capability:** Automatic recovery cannot be achieved purely in userland Python scripts without an authentic engine error event hook or an updated native aplexer binary.

---

## 3. Deep Negative & Edge Case Verification in Scratch

### 3.1 Test Suite Execution

In an isolated scratch test harness with `TMPDIR` redirected to `.local/scratch/grok-capacity-review/tmp`, the test suite was executed:
```bash
TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/grok-capacity-review/tmp \
python3 -m unittest discover -s research/grok/capacity-recovery/ -v
```
**Result:** **20/20 tests passed** in **0.003s** (exit code 0). Zero tests asserted or claimed "native success".

### 3.2 Audit of Specific Edge Cases

#### Edge Case A: Multiline Draft and Error String Parsing
- **Mechanism:** `classify_composer()` extracts prompt start markers using `re.match(r"^\s*[›❯]", line)` and inspects all trailing lines after the prompt index. If any trailing line is neither blank nor recognized as a known footer (`ctrl+`, `tokens:`, `model:`, shortcuts), it is appended to `rest`. If `rest` is non-empty, the composer is classified as `draft`.
- **Handling of Tracebacks & Multiline Errors:**
  - Multi-line tracebacks appearing in the composer prompt (e.g. `test_multiline_draft_and_error_text_in_composer`) produce `rest > 0`, correctly returning `draft` and triggering `Decision(action="block_draft", reason="human_draft_present")`.
  - Tracebacks appearing on screen without a prompt symbol produce `starts == []`, returning `unknown` and triggering `Decision(action="block_unknown", reason="composer_unknown")`.
- **ANSI Escape Code Vulnerability:**
  - `policy.py` does not strip ANSI escape codes prior to regex matching.
  - If a screen capture contains raw ANSI color sequences immediately before the prompt character (e.g. `\x1b[32m›\x1b[0m`), `re.match(r"^\s*[›❯]", line)` fails to match.
  - *Safety Impact:* It fails closed (`unknown` $\rightarrow$ `block_unknown`). However, this represents an **availability hazard**: unstripped terminal buffers will be permanently blocked from recovery.

#### Edge Case B: Screen Text Ambiguity
- **Compiler Errors vs Fatal Engine Panics:**
  - The capacity string is strictly matched against `CAPACITY_PHRASE = "Selected model is at capacity. Please try a different model."`. Arbitrary compiler errors, syntax warnings, or runtime panics do not match `CAPACITY_PHRASE`, resulting in `classify_capacity_signal` returning `absent`.
- **Corroboration by Engine Event (Fail-Closed Provenance):**
  - If the bottom window contains the exact capacity phrase (e.g., from compiler output, tool recap, or peer history), `classify_capacity_signal()` checks `provenance == "engine_event"`.
  - If `provenance != "engine_event"` (e.g., `"unknown"`), it returns `"unproven_screen"`.
  - `plan_recovery()` maps `"unproven_screen"` to:
    `Decision(action="hold_unproven_provenance", reason="screen_phrase_is_not_native_error_event")`
  - Uncorroborated terminal screen text **fails closed**. It cannot trigger live capacity recovery or retry timers.

#### Edge Case C: Multi-Window Quota Tracking
- **Mechanism:** `QuotaSample` validates that all `required_windows` (`"weekly"`, `"5h"`) are present, non-empty, and non-None. The effective remaining percentage is `min(windows.values())`.
- **Clock Skew and Spans:** `QuotaSample` treats windows as pre-evaluated numeric percentages supplied by the collector (`quse` / launcher). It does not compute sliding window timestamps internally.
- **CRITICAL GAP DISCOVERED — Unsampled Quota Bypass (`quota=None`):**
  - Inspection of `classify_blocker()` (lines 235–241):
    ```python
    if obs.quota is not None:
        if obs.quota.unknown:
            return "quota_unknown"
        if obs.quota.limit_reached or (...):
            return "quota_denied"
    ```
  - If `obs.quota is None` (i.e. caller omitted quota entirely), `classify_blocker()` skips quota validation.
  - In `plan_recovery()`, unlike `obs.resources` which calls `resource_ok(obs.resources)` (failing closed on `None`), there is **no check** that `obs.quota is not None`.
  - An observation with `quota=None` and valid native readiness evaluates directly to:
    `Decision(action="dry_run_same_conversation_retry", reason="capacity_cleared_gates_passed_uninstalled")`.
  - *Recommendation:* `classify_blocker()` or `plan_recovery()` must enforce:
    `if obs.quota is None or obs.quota.unknown: return "quota_unknown"`.

#### Edge Case D: Per-Operation Disk Budget Checks
- **Dual Floor Enforcement:**
  - `policy.py` explicitly demarcates two root disk floors:
    - `NEW_WORKER_ROOT_FLOOR_GIB = 50.0` (OPERATING-MODEL worker launch floor).
    - `TASK_SCRATCH_ROOT_FLOOR_GIB = 8.0` (diagnostic recovery scratch floor).
  - Evaluated in-memory via `resource_ok()` without external shell scrapers (`df` / `statvfs` subprocesses).
- **CRITICAL OMISSION — 512 MB Scratch Budget Ceiling:**
  - Neither `ResourceSample` nor `policy.py` contains any field or check for scratch directory disk usage ($\le 512$ MB) or `/tmp` net growth.
  - The policy only gates on host filesystem free space (50 GiB / 8 GiB) and available RAM (10 GiB). The per-operation scratch budget must currently be enforced externally by process wrappers.

---

### 3.3 Mutation Testing in Scratch

To verify the test suite's discriminative power, two adversarial mutants were authored and evaluated in `.local/scratch/grok-capacity-review/harness/`:

```
======================================================================
MUTATION TEST EXECUTION SUMMARY
======================================================================
Baseline Test Suite:  20/20 passed (Exit 0)

Mutant 1: Ambiguous Screen Text Leak
  Mutation: Bypassed `provenance == ENGINE_EVENT_PROVENANCE` check in
            `classify_capacity_signal`, returning `live_capacity` on
            unprefixed screen text alone.
  Result:   CAUGHT (Exit 1, 2 test failures)
  Failures: - ClassifyTests.test_live_capacity_vs_historical_quoted
            - GateTests.test_unprefixed_bottom_phrase_is_unproven

Mutant 2: Quota Window Overwrite
  Mutation: Replaced multi-window validation in `QuotaSample` with a single
            hardcoded `"weekly"` window check, ignoring `required_windows`.
  Result:   CAUGHT (Exit 1, 1 test failure)
  Failure:  - GateTests.test_quota_unknown_and_denied
              AssertionError: 'need_native_error_event' != 'block_quota_unknown'
======================================================================
```
Both mutants were 100% caught and rejected by the existing test suite.

---

## 4. Installed Parity & Non-Interference Invariants

The reviewer conducted a comprehensive audit of the execution environment to ensure strict non-interference:

1. **Zero Global Binary Replacement:**
   - Command `which aplexer` resolves strictly to `/home/alexey/.local/bin/aplexer`.
   - SHA-256 hash verified: `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` (installed 2026-10-02).
   - Candidate files in `research/grok/capacity-recovery/` are pure Python scripts; no binaries were compiled or installed to `~/.local/bin` or system paths.
2. **Zero `cargo` / `rustc` Compiler Invocations:**
   - Active process tree inspected: zero compiler invocations.
   - Git log and workspace status confirm zero Rust builds attempted under human hold.
3. **Zero Competing Daemons Launched:**
   - Process scan confirms no background supervisor, daemon, or watcher was launched for capacity recovery.
4. **Zero Production Code Edits:**
   - Changes are strictly isolated to `research/grok/capacity-recovery/`.
   - Core production trees (`prototype/`, `scripts/`, `src/`) remain completely untouched.

---

## 5. Resource Accounting & Credential Hygiene

- **Scratch Workspace:** `.local/scratch/grok-capacity-review/` (mode `0700`).
- **Measured Scratch Disk:** **8.0 KB**, well within the 512 MB ceiling.
- **Temporary Files Isolation:** `TMPDIR` set to `.local/scratch/grok-capacity-review/tmp` (mode `0700`). Zero net growth in `/tmp`.
- **Memory Consumption:** Cooperative process memory consumption was under 45 MB, well below the 1500 MB ceiling.
- **Credential Hygiene:** Validated with `research/antigravity/tooling/publication_guard.py`:
  - Scanned target: `research/antigravity/reviews/REV-GROK-CAPACITY-RECOVERY.md`.
  - Zero raw secrets, bearer tokens (`art_v1_...`), or sensitive paths found.
  - Publication guard exit code: **0**.

---

## 6. Actionable Recommendations & Integration Roadmap

Before any capacity recovery policy is considered for protocol integration or deployment:
1. **Fix `quota=None` Fail-Closed Behavior:** Update `policy.py` so that missing or unsampled quota (`obs.quota is None`) explicitly triggers `block_quota_unknown`.
2. **Model Scratch Budget in `ResourceSample`:** Add `scratch_used_mib: float` and `scratch_floor_mib: float = 512.0` to `ResourceSample` and assert `scratch_used_mib <= scratch_floor_mib`.
3. **Sanitize Terminal Screen Captures:** Introduce ANSI sequence stripping (e.g. `re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)`) before prompt classification to eliminate availability false-positives.
4. **Native Protocol Handoff Requirement:** Real automatic recovery requires an engine error event hook (e.g. mapping capacity failure to an explicit `state-report error:capacity` or `state-report idle`). Without this native change, live aplexer delivery cannot be triggered.
