# Empirical Active Executor Lower Bounds & Telemetry Snapshot

- **Observer:** Ant Integration HEAD (`ant-integration-head-recovery`, session UUID `c69a9f51-b751-4400-8bbd-c24cb87fe39a`)
- **Engine / Model:** `antigravity` / `gemini-3.8-flash-high`
- **Timestamp:** 2026-10-08T05:32:00+02:00 (03:32:00 UTC)
- **Status:** **CANONICAL BOUNDED TELEMETRY AUDIT**

---

## 1. Executive Summary & Metric Decoupling

In response to challenges regarding telemetry aggregation (`114 registered / 20 running / 12 ready / 358.9M tokens`), this snapshot provides an empirical, decoupled audit:
1. **Registered Catalog ≠ Active Execution:** The `114 registered agents` figure reflects the cumulative set of session metadata files discovered across all historical workspaces in `~/.local/state/aplexer/sessions/` since inception. It is **not** an active concurrency count.
2. **Database Status Rows ≠ Executable Ready / Active:** The `20 running` and `12 ready` task counts represent unpruned SQLite rows in `state.db` and legacy trackers. Actual running task units under systemd are strictly bounded.
3. **Cumulative Lifetime Tokens ≠ 24h / Request Usage:** The `358,920,718` token count is the lifetime sum of all token-bearing transcripts ever observed across all models and dates. It is **not** the 24-hour usage, not the current request usage, and must never be conflated with dollar billing.
4. **Physical Host Grounding:** `hetzner-rmthz` is the sole confirmed live execution host. `windows-desktop` (Win35) physical access and worker capacity remains **strictly unconfirmed / unknown**.

---

## 2. Timestamped Per-Host Active Lower Bounds (As of 03:32 UTC)

### Host: `hetzner-rmthz` (Canonical Linux Host, RMTHZ)

| Actor / Process | Type | PID / CGroup | Model / Engine | Actual Current Task | State |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `codex-principal` (`f09f5f56`) | Principal | `4087565`, `4088012` | `codex` | Autonomous principal oversight, bus responses, review validation | **ACTIVE** |
| `continuation-head-recovery` (`a6c9720c`) | Head | Session active | `codex` | Continuation Runtime repairs, role route 35/36 oversight | **ACTIVE** |
| `ant-integration-head-recovery` (`c69a9f51`) | Head | Session active | `gemini-3.8-flash-high` | Canonical runtime custody, metrics audit, C-0313 recovery | **ACTIVE** |
| `agent-task-crh1008-role-route-repair40` | Worker Task | `819018`, `819044` | `gemini-3.8-flash-high` | Role route repair 40 execution | **ACTIVE** |
| `agent-task-crh1007-supervision-runtime11` | Worker Task | `411233` | `glm-5.3-flash` (zcodex) | Runtime 11 final independent review | **ACTIVE** |
| `supervision.service` | Canonical Daemon | `3698862` (app.slice) | Python 3 (ca5ea38) | Autonomous supervision loop (zero production reloads) | **ACTIVE** |
| `experiment-metrics.service` | Canonical Daemon | `4168827` (app.slice) | Python 3 (:8766) | Telemetry observation server (zero production reloads) | **ACTIVE** |
| `desktop-orchestrator` (`a10d85ea`) | Root Monitoring | Session active | Shell | Remote root coordinator / operational checks | **ACTIVE** |
| `agent-dashboard-head` (`6ef7413b`) | Head | Session active | `zcodex` | Audited clean (48/48 backend pass), resting PTY | **IDLE** |
| `publication-head-recovery` (`cfe991d4`) | Head | Session active | `antigravity` | Awaiting canonical lease intake for Oct 8 article | **IDLE** |
| `main` (`6e9a7c6f`) | Writer Head | Session active | Claude Opus | Draft-protected writer session (Oct 8 standup) | **IDLE** |

- **Strict Empirical Active Concurrency Lower Bound (`hetzner-rmthz`):**
  - **Active Heads / Principal:** 3 (`codex-principal`, `continuation-head-recovery`, `ant-integration-head-recovery`)
  - **Active Autonomous Child Workers:** 2 (`crh1008` PID `819044`, `crh1007` PID `411233`)
  - **Active Canonical Daemons:** 2 (`supervision.service` PID `3698862`, `experiment-metrics.service` PID `4168827`)
  - **Total Confirmed Active Actors on Host:** **7**

### Host: `windows-desktop` (Win35)
- **Status:** **UNCONFIRMED / UNKNOWN**
- **Live Aplexer / SSH Route:** No active inbound/outbound session established.
- **Active Concurrency Lower Bound:** **0 (Unknown)**. No synthetic or assumed credit claimed.

---

## 3. Product Ownership, Tasks, and Outcomes Breakdown

### 1. Continuation Runtime & Supervision
- **Product Owner:** `continuation-head-recovery` (`a6c9720c`) + `ant-integration-head-recovery` (`c69a9f51`, canonical installation custody)
- **Current Tasks:**
  - `crh1008-role-route-repair40`: Role route source 35 executed by terminal `gemini-3.1` (CID `35a67d0a`); undergoing distinct model review 36 (`gemini-3.8-flash-high`) under unit `agent-task-crh1008-role-route-repair40-gemini38-a6.service`.
  - `crh1007-supervision-runtime11`: Runtime 11 final review under unit `agent-task-crh1007-supervision-runtime11-review-a6.service` (PID `411233`, `glm-5.3-flash`).
- **First Tools / Actions:** Proved via `ROLE35-REVIEW36-ACTUAL-PLACEMENT-FIRST-TOOLS.json` and transient systemd invocation journals.
- **Accepted Outcomes:** SOURCE28 and MODEL31 supported REJECTED_ONCE; ROLE29 supported REJECTED_ONCE by distinct review 32.
- **Next Task:** Verify completion of review 36; execute bounded canary test before any canonical installation. Canonical runtime remains untouched on baseline `ca5ea38`.

### 2. Agent Dashboard (C-0313 Readiness Miss Recovery)
- **Product Owner:** `ant-integration-head-recovery` (`c69a9f51`) in coordination with `agent-dashboard-head` (`6ef7413b`)
- **Executed Tasks:**
  - Audit Task: `t-dashboard-c0313-readiness-diagnostic-02` (worker PID `677233`, CID `3b2dcf70`, `gemini-3.1-pro-high`).
  - Review Task: `t-dashboard-c0313-readiness-review-02` (reviewer CID `81cc736f`, `gemini-3.8-flash-high`).
- **First Tools / Actions:**
  - Read-only inspection of `/home/alexey/git/agent-dashboard`, execution of `PYTHONPATH=src pytest tests/` (48/48 backend tests passed in 0.69s), audit of 9 untracked provenance files with commit `6863b99` validation, negative boundary tests execution (4/4 passed). Emitted `REPORT-DASHBOARD-READINESS-AUDIT-02.md` (SHA-256: `44947cb5...`).
  - Replicated SHA computation, replicated unit tests (48/48) and boundary tests (4/4), confirmed zero working tree diffs. Emitted `REV-DASHBOARD-READINESS-AUDIT-02.md` (SHA-256: `ad83e6b6...`, verdict ACCEPT). Committed at `84c0c5f`.
- **Accepted Outcomes & Store Integration:**
  - Both tasks accepted in Store via `launcher accept` at `03:27:18`.
  - Store Receipt #49 recorded in `review_receipts` table at `03:28:10`.
  - Qualification Addendum authored and committed at `1c124b1` (`research/antigravity/reviews/REV-DASHBOARD-READINESS-AUDIT-02-QUALIFICATION.md`, SHA-256: `c8ca977ca1...`).
  - Independent negative boundary test suite committed at `83b0c64` (`tests/test_dashboard_readiness_negative.py`, 4/4 passed in 0.03s).
- **Next Task:** Maintain NOTREADY guard on resting CLI sessions without active heartbeat pushes, preventing premature synthetic delivery; verify clean backlog resumption.

### 3. Experiment Metrics & Telemetry Grounding
- **Product Owner:** `ant-integration-head-recovery` (`c69a9f51`)
- **Current Tasks:**
  - Disentangle cumulative session registry entries from active processes.
  - Distinguish historical transcript tokens (`358.9M`) from 24h / per-task usage.
- **Accepted Outcomes:** Canonical `experiment-metrics.service` PID `4168827` active on port 8766 with zero reloads.
- **Next Task:** Bounded snapshot submission and publication of grounded telemetry.

### 4. Public Documentation & Journal (October 8 Standup / Article)
- **Product Owner:** `publication-head-recovery` (`cfe991d4`) and `main` (`6e9a7c6f`, Claude Opus writer)
- **Current Status:** Standup draft and article intake held pending canonical lease intake.
- **Protected Assets:** Human draft (`6e9a7c6f`) and writer draft (`e67cafb2`) strictly preserved without resets or overwrites.

---

## 4. Knowns and Precise Unknowns

### Confirmed Knowns:
1. **Zero Production Reloads:** `supervision.service` PID `3698862` (baseline `ca5ea38`) and `experiment-metrics.service` PID `4168827` running continuously.
2. **Mailbox Preservation:** Message `01a1197f-d3b0` safely preserved in `/home/alexey/.local/state/aplexer/messages/03c9ec4101be7a25620818707fb14ec7/msgs/`.
3. **Dual Model Validation:** Gemini 3.1 Pro (author) vs Gemini 3.8 Flash (reviewer) verified for C-0313 recovery; GLM-5.3 Flash (reviewer) verified for Runtime 11.

### Precise Unknowns:
1. **Non-OpenCode 24-Hour Token Delta:** Because CLI sessions without OpenCode telemetry adapters do not emit fine-grained interval accounting, the exact 24-hour token consumption and list-price cost for non-instrumented runs is **UNKNOWN**.
2. **Win35 Host Availability:** Windows desktop physical host connectivity and execution readiness is **UNKNOWN**.
3. **Remote Hetzner Capacity:** Additional remote nodes beyond `hetzner-rmthz` are **NOT ALLOCATED / UNKNOWN**.
