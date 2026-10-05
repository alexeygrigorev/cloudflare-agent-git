# DRAFT-OCT5-PRODUCT-REPORT — Four-Product Engineering Report & Operational Ledger

- **Author / Reconciler:** Hourly Payload Reconciler (tag: `reconcilerd698`)
- **Authority / Dispatched By:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337` / harness: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Governance Directives:** Codex Principal C2059, C2105, C2108, C2120, C2124, C2136, C2143, C2145, C2147; Human Delivery Reset (2026-10-04)
- **Publication Status:** **DRAFT** (held in research recovery path pending publication coordinator integration ACK; zero website mutations)
- **Analytical Baseline:** [`.local/metrics/hourly_24h_payload.json`](file:///home/alexey/git/cloudflare-agent-git/.local/metrics/hourly_24h_payload.json) (SHA256: `34137ef9d8a04f255fe9df9293871436b2e761034d7795f7743ae845e098f077`, schema `2.3.0-c2136`)
- **Audit Verification:** [`research/antigravity/reviews/REV-HOURLY-PAYLOAD-34137.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-HOURLY-PAYLOAD-34137.md) (**BOUNDED ACCEPTANCE**)
- **Rolling Window:** `[2026-10-04T00:06:45Z, 2026-10-05T00:06:45Z)` (24 contiguous half-open UTC hourly buckets)
- **Host Compiler Hold:** Exactly **0 cargo / rustc invocations** under human hold
- **Credential Validation:** [`research/antigravity/tooling/publication_guard.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py) (Clean: Exit 0)

---

## 1. Executive Summary & Epistemic Baseline

Under Codex Principal directive C2147, this engineering report consolidates verified outcomes, cryptographic receipts, and remaining delivery gates across the four canonical products (`agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`) and unattributed infrastructure for the preceding 24-hour cycle.

### 1.1 Strict Epistemic Boundaries & Invariants
1. **Grounded Strictly in Accepted Outcomes:** Narrative claims are restricted to code commits, independent review sign-offs (`REV-*`), and frozen testbed executions. Unreviewed proposals, staged evaluations, and pending tasks are explicitly marked as candidates or held.
2. **Decoupling of Presence vs. Productive Work:** Process occupancy (presence hours) is strictly separated from affirmative active hook telemetry (verified working hours). Hook-absent periods disclose an uninstrumented observation boundary; physical CPU dormancy is explicitly declared unmeasured (`resting_or_menu_hours: null`).
3. **Truthful Telemetry & Zero Fabrication:** Token usage (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `reasoning_output_tokens`) and provider spending (`provider_cost_cents`, `provider_usage`) were not affirmatively hooked during this rolling window and are recorded as `null` / `"unobserved"`. Synthetic `0.0` or fake `100%` usage assertions are strictly prohibited.
4. **Bounded Observed Contributor Scope:** The observed active working census for this cycle comprises exactly four harness contributors:
   - `reviewer259` (Independent Payload & Consumer Reviewer)
   - `architect06` (Self-Organization Architect)
   - `reviewer37` (Independent Challenger & Negative Reviewer)
   - `reconcilerd698` (Hourly Payload Reconciler)
   Plus one logical external review outcome:
   - `zcode-sdk-reviewer` (session `369e1e44-678f-4918-a061-e8400651d6eb`, two execution attempts deduplicated into one single outcome).
   Whole-night fleet totals and private token expenditures remain unknown.

---

## 2. Product 1: Agent Branches — Pure Fail-Closed Semantics & Two Generals Trial

### 2.1 SDK / CLI Fail-Closed Review & Hygiene Cleanup
- **Commits Audited:**
  - `71dade6` — `docs(cli): clarify push-batch max-retries and retry-backoff as compatibility parameters (C2046)`
  - `f4f6c3e` — `fix(sdk): enforce pure fail-closed on mutating push (remove automatic 429 retry per C1672)`
- **Independent Audit:** [`research/antigravity/reviews/REV-SDK-CLI-TIMEOUT-ZCODE.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-SDK-CLI-TIMEOUT-ZCODE.md) (**BOUNDED ACCEPTANCE**).
- **Verification:** Unit test suite in `/home/alexey/git/agent-branches/tests/` passed 61/61 tests in 21.16s.
- **Changed Behavior:** Mutating `push` and `push-batch` subcommands strictly enforce pure fail-closed semantics. The SDK will not automatically retry upon receiving HTTP 429 rate-limit responses, avoiding silent side effects and preserving the Two Generals invariant.
- **Documentation & Token Cleanup:** Commit `10d9d50` (`docs(sdk): fix push_batch docstring summary and remove dead import time`) resolved minor review hygiene findings by eliminating unused imports and correcting parameter documentation.

### 2.2 Feature Gate Status
- **Independently Accepted Features (1):**
  - `ab-real-consumer-work`: Platform consumer dogfooding trial verified in [`research/antigravity/reviews/REV-AB-REAL-CONSUMER-WORK.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-AB-REAL-CONSUMER-WORK.md) (ACCEPT). Bounded strictly to local fixture service `demo-target/` measuring worktree branching latency (0.44s vs 0.99s); does not assert external fleet adoption.
- **Candidates Pending Independent Review (3):**
  - `ab-safe-main-restore`: Safe checkout restoration without remote overwrite.
  - `delivery-intake-reconciliation`: Operational intake mapping.
  - `ab-standalone-private-source-project`: Independent source tree extraction.

---

## 3. Product 2: Agent Bus / Coordination — Idempotency Diagnosis & Portability Gap

### 3.1 Conclusive Diagnosis of Duplicate Reply Event
During the ZCode SDK consumer trial, identical duplicate replies were delivered to executor session `369e1e44` under message IDs `48139464` and `a0a53b68`, sharing exact payload digest:
- **Body SHA256:** `3fb31c92bb2aa686919f60c3215a3be828a02aec17385ad7c331b242e901ee92`
- **Root Cause:**
  1. `reply()` in canonical `agent-bus` generated unkeyed random UUIDs via `_new_id()`.
  2. Cursor lookup `_cursors.lookup_send()` preceded recipient authorization, returning messages before validating caller permissions.
  3. Client-generated explicit idempotency keys across different task targets were not scoped, creating semantic collision hazards.

### 3.2 Reviewed Snapshot Patch & Verification
- **Patch Artifact:** [`research/antigravity/recovery/bus-default-idempotency-and-semantic-replay.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/bus-default-idempotency-and-semantic-replay.patch) (68 lines, SHA256: `6494985f...`, commit `f91901d`).
- **Independent Audit:** [`research/antigravity/reviews/REV-BUS-DEFAULT-IDEMPOTENCY.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BUS-DEFAULT-IDEMPOTENCY.md) (**BOUNDED ACCEPTANCE**; ratified by Codex Principal in C2143).
- **Core Mitigations:**
  - Upfront recipient authorization: `_require_reply_target_locked` evaluates caller before cursor check, raising `BusError('not_recipient')` for unauthorized actors.
  - Deterministic default idempotency: Calculates `default_key = f"reply-default:{reply_to}:{sha256(body)}"` when no client key is supplied.
  - Explicit key task binding: Binds client keys to `(task_id, kind)`, preventing note/reply cross-talk.
- **Test Evidence:** 34/34 snapshot tests pass, including 8 real functional FileBus negative tests.

### 3.3 Cross-Computer & Windows Portability Gap (C2145)
- **Independent Audit:** [`research/antigravity/reviews/REV-BUS-TYPED-SSH-PORTABILITY.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BUS-TYPED-SSH-PORTABILITY.md) (**REQUEST_CHANGES**).
- **Target Inspected:** `/home/alexey/git/agent-bus/` (read-only, commit `f3295f9`).
- **Blocking Deficiencies:**
  1. **Source Manifest Gaps:** Three critical transport modules referenced in cross-computer architecture (`coordination/envelope.py`, `coordination/transport.py`, `coordination/ssh.py`) are **missing** from `agent-bus` and remain stranded in legacy `agent-coordination`.
  2. **Fatal Windows Incompatibilities:** Hardcoded `fcntl.flock` and `os.O_DIRECTORY` in `coordination/durable.py` cause fatal runtime crashes on Windows (`nt`).
  3. **Transport Overhead:** Subprocess OpenSSH execution without multiplexed control sockets incurs heavy latency and lacks framed stream boundaries.
- **Next Owner:** `agent-coordination-head` for manifest synchronization, cross-platform file-locking abstraction, and SSH transport integration.

---

## 4. Product 3: Agent Dashboard — Staged Consumer Review & Integration Boundary

### 4.1 Minimal Decoupled Patch Scope
To prevent destabilizing existing work in `/home/alexey/git/agent-dashboard/`, changes were prepared as decoupled minimal patches:
- **Backend Patch (`007a6ef3`, 136 lines):** Added project alias normalization (`agent-quota-launcher` -> `quota-launcher`), registered fourth product `agent-coordination`, and bound server to port 8923.
- **Static Frontend Patch (`f2e29142`, 38 lines):** Updated `PROJECT_IDS` array in `static/dashboard.js` and added the `agent-coordination` livecard container to `static/index.html`.

### 4.2 Testbed Verification & Live DOM Rendering
- **Testbed Execution:** Verified in isolated scratch workspace `.local/scratch/dashboard-consumer-review-cycle2/` without modifying canonical repository files.
- **Independent Audits:** [`research/antigravity/reviews/REV-DASHBOARD-STAGED-CONSUMER.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-STAGED-CONSUMER.md) and [`research/antigravity/reviews/REV-HOURLY-PAYLOAD-34137.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-HOURLY-PAYLOAD-34137.md).
- **Observed Behavior:**
  - Live HTTP endpoints (`/api/status`, `/api/projects`) respond with valid four-product JSON.
  - Node.js MockDOM simulation confirms the `agent-coordination` card actively renders metrics (`unique-agent-coordination` = 1, `hours-agent-coordination` = 1.00 h, 24 bucket bars, and token usage rows), rather than displaying empty or static HTML placeholders.

### 4.3 Integration Boundary
- Direct blanket `git apply` onto dirty canonical `/home/alexey/git/agent-dashboard/` was formally **withdrawn**.
- Clean integration and merge into canonical main remains strictly owned by `agent-dashboard-head`.

---

## 5. Product 4: Quota Launcher — Containment Hardening & Held Deployment Gate

### 5.1 Temporary Directory Leakage Root Cause
Forensic source and binary analysis documented in [`research/antigravity/recovery/REPORT-ZCODEX-SOURCEPIN-PARITY.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-ZCODEX-SOURCEPIN-PARITY.md) and [`research/antigravity/recovery/REPORT-TMPDIR-CONTAINMENT-RECEIPT.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-TMPDIR-CONTAINMENT-RECEIPT.md) conclusively identified the mechanism of `/tmp` leakage:
- **Upstream Source Location:** `/home/alexey/git/codex-zcode/codex-rs/core/src/client.rs` line 944 (`write_zcode_prompt_file`).
- **Mechanism:** The function calls `std::env::temp_dir().join(...)`. In the Rust standard library on Linux, `temp_dir()` evaluates the `TMPDIR` environment variable; if empty or unset, it falls back directly to `/tmp`.

### 5.2 Dual-Layer Containment Hardening
To guarantee strict filesystem confinement within the user's workspace:
1. **Outer Systemd Scope:** `launcher_bus_bridge.py` explicitly injects `-E TMPDIR={tmpdir_path} -E TEMP={tmpdir_path} -E TMP={tmpdir_path}` into the `systemd-run` command line.
2. **Inner Process Prelude:** Injected Python prelude script binds `os.environ["TMPDIR"] = str(tmpdir_path)` immediately prior to `os.execvp`.
- **Test Evidence:** Test 33 in `tests/test_launcher_bus_bridge.py` verifies local Python temp file creation inside the 1500M scope strictly in `.local/tmp/` with zero `/tmp` writes (PASS in 0.340s; full suite 33/33 PASS in 9.57s).

### 5.3 Deployment Gate & Compiler Hold
- **Source-Pin & Binary Parity:** Deployed executable `/home/alexey/.local/lib/zcodex/zcodex` (GNU Build ID `9ddfd453...`, SHA256 `dce345ed...`) matches upstream repository `/home/alexey/git/codex-zcode/` cleanly pinned at commit `bf9d7ed`.
- **Compiler Invariant:** Exactly **0 cargo / rustc invocations** were executed across the entire cycle, strictly adhering to the human compiler hold.
- **Model Route Status:** Live external model adapter launches remain strictly **HELD** under Codex C2118 pending verified producer attribution and end-to-end sandbox proof.

---

## 6. Analytical Utilization Matrix: 24h Rolling Window (C2136)

**Measured Snapshot Instant:** `2026-10-05T00:06:45Z`  
**Rolling Window:** `[2026-10-04T00:06:45Z, 2026-10-05T00:06:45Z)` (24 half-open UTC hourly buckets)  
**Analytical Payload:** [`.local/metrics/hourly_24h_payload.json`](file:///home/alexey/git/cloudflare-agent-git/.local/metrics/hourly_24h_payload.json) (SHA256: `34137ef9...`, schema `2.3.0-c2136`)  
**Independent Review:** [`research/antigravity/reviews/REV-HOURLY-PAYLOAD-34137.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-HOURLY-PAYLOAD-34137.md)

### 6.1 Product Utilization & Concurrency Summary

| Product ID | Status | Observed Window ($W_{\text{obs}}$) | Coverage Ratio | Presence (h) | Avg Concurrency ($W_{\text{obs}}$) | 24h Presence Lower Bound | Verified Work (h) | Avg Work Concurrency ($W_{\text{obs}}$) | 24h Work Lower Bound | Hook-Absent Presence (h) | Accepted Features |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`agent-branches`** | Observed | 12.9722 h | 0.5405 | **26.6873** | **2.0573** | **1.1120** | **7.1094** | **0.5480** | **0.2962** | 19.5779 | **1** |
| **`agent-dashboard`** | Observed | 12.9722 h | 0.5405 | **50.4029** | **3.8854** | **2.1001** | **0.0000** | **0.0000** | **0.0000** | 50.4029 | **0** |
| **`quota-launcher`** | Observed | 12.9722 h | 0.5405 | **43.6973** | **3.3685** | **1.8207** | **0.0000** | **0.0000** | **0.0000** | 43.6973 | **0** |
| **`agent-coordination`** | Observed | 12.4322 h | 0.5180 | **5.8817** | **0.4731** | **0.2451** | **0.0000** | **0.0000** | **0.0000** | 5.8817 | **0** |
| **`unattributed`** | Observed | 24.0000 h | 1.0000 | **361.3193** | **15.0550** | **15.0550** | **10.7286** | **0.4470** | **0.4470** | 350.5907 | **0** |

*Note: In accordance with Codex C2062 and C2120, cross-product totals are non-additive to prevent conflating distinct team baselines.*

### 6.2 Dedicated Project Delivery vs. Oversight Principal Disaggregation

| Product ID | Dedicated Delivery Presence (h) | Delivery Presence Actors | Oversight Principal Presence (h) | Oversight Principal Actors | Dedicated Delivery Working (h) | Oversight Principal Working (h) |
| :--- | :---: | :--- | :---: | :--- | :---: | :---: |
| **`agent-branches`** | **13.8168** | `antigravity-head`, `muse-reviewer-auth-ui` | **12.8705** | `codex-principal` | **5.8413** | **1.2682** |
| **`agent-dashboard`** | **50.4029** | `ad-backend-exec`, `ad-frontend-exec`, `ad-independent-reviewer`, `agent-dashboard-head` | **0.0000** | *None* | **0.0000** | **0.0000** |
| **`quota-launcher`** | **30.9621** | `quota-launcher-core-3`, `quota-launcher-head`, `quota-platform-coordinator`, `quota-platform-sidecar` | **12.7352** | `desktop-orchestrator` | **0.0000** | **0.0000** |
| **`agent-coordination`** | **5.8817** | `agent-coordination-head` | **0.0000** | *None* | **0.0000** | **0.0000** |
| **`unattributed`** | **290.9750** | 24 workers/services (`grok-head`, `zcode-independent`, `public-journal-site`, `relay`, etc.) | **70.3443** | `codex-principal`, `desktop-orchestrator`, `experiment-metrics`, `experiment-supervision` | **10.2393** | **0.4893** |

---

## 7. Remaining Product Gates & Next Handoff Ownership

| Product | Current Status | Blocking Gate / Invariant | Next Owner | Next Concrete Action |
| :--- | :---: | :--- | :--- | :--- |
| **Agent Branches** | Production Fixture Verified | Candidate features await independent review; Two Generals pure fail-closed verified | `antigravity-head` | Dispatch independent review of candidates (`ab-safe-main-restore`, `ab-standalone-private-source-project`) |
| **Agent Coordination** | Local POSIX Idempotency Accepted | Cross-computer manifest gaps (`coordination/ssh.py`, etc.) and Windows `fcntl.flock` failure | `agent-coordination-head` | Implement cross-platform locking abstraction and synchronize transport manifests per `REV-BUS-TYPED-SSH-PORTABILITY.md` |
| **Agent Dashboard** | Staged Consumer Verified | Canonical repository integration pending; blanket patch application withdrawn | `agent-dashboard-head` | Integrate minimal backend (`007a6ef3`) and static (`f2e29142`) changes cleanly into `/home/alexey/git/agent-dashboard/` |
| **Quota Launcher** | Containment Hardened | Live external model launch held; host-wide cargo/rustc compiler hold strictly maintained | `quota-launcher-head` | Complete sandbox validation; await gate verification before model admission |
| **Public Site** | Publication Guard Clean | Subagents strictly prohibited from editing `website/**` or executing git commits | Publication Coordinator | Review this draft report, perform editorial integration, and commit per operating model |

---

## 8. Verification & Publication Guard Sign-Off

Executed automated credential exposure validation:

```bash
python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/DRAFT-OCT5-PRODUCT-REPORT.md
```

- **Target:** `research/antigravity/recovery/DRAFT-OCT5-PRODUCT-REPORT.md`
- **Violations:** `0`
- **Exit Code:** `0`
- **Status:** **CLEAN** — Zero secret keys, bearer tokens, or unredacted credentials exposed.
- **Subagent Rule Adherence:** Zero git commits executed; deliverable preserved in owned research path for parent/coordinator pickup.
