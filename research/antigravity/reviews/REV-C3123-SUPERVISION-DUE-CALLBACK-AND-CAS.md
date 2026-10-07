# Independent Adversarial Review: Supervision Due Callbacks Binding, Resting-State Guard, Win35 Endpoint Deploy-Readiness, and Tracker CAS Reconciliation (C3123)

## Review Metadata

- **Review Identifier**: `REV-C3123-SUPERVISION-DUE-CALLBACK-AND-CAS`
- **Review Date**: 2026-10-07T06:45:00Z (08:45 CEST)
- **Review Role**: Independent Adversarial Auditor & Codebase Reviewer
- **Auditor Model**: `gemini-3.1-pro-high` (Antigravity CLI Subagent)
- **Caller Conversation ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`
- **Pinned Commit SHA**: `e211aa454fe26be8ec4be27a13c3aa41c6e1dbff` (prompt pin reference) / `e211aa44f850ef771d00cf2a39e15ce3c244a50d` (canonical git commit)
- **Associated Context Commits**:
  - `e211aa44f850ef771d00cf2a39e15ce3c244a50d` (`feat(supervision): exact recipient session binding and resting-state guard in due callbacks (C3123)`)
  - `f90c897b2acea61cc51136372f9ba5f2763418c2` (`docs(recovery): deploy-readiness evaluation and tracker CAS reconciliation (C3123)`)
- **Target Deliverables**:
  1. `scripts/supervision/service.py`: `process_due_callbacks` exact recipient binding (`recipient_session_id`), anti-tag-reassignment rejection, and resting-state protection (`busy`, `working`, `draft`, `menu-or-draft`).
  2. `scripts/supervision/test_service.py`: unit tests for exact recipient match, tag reassignment rejection, and resting-state guard.
  3. `research/antigravity/recovery/REPORT-BUS-WIN35-DEPLOY-READINESS-C3123.md`: deploy-readiness evaluation of Bus Win35 non-SSH secure endpoint candidate `e1e8e50fc828f4d65060707bce0c0b4c31d6372e`.
  4. `research/antigravity/recovery/RECEIPT-TRACKER-CAS-RECONCILIATION-C3123.md`: tracker parity at 282 rows and CAS metadata reconciliation.
  5. `research/antigravity/recovery/startup-1c0dfcf7.json`: session custody receipt for `1c0dfcf7-3431-4c7b-bec3-8412c09e1ac1`.
- **Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Verdict

This adversarial audit evaluated the C3123 recovery deliverables across the continuation runtime, live supervisor daemon, Bus Win35 candidate, and administrative task tracking:

1. **Exact Recipient Session Binding & Anti-Imposter Defense** (`scripts/supervision/service.py`):
   Prior to commit `e211aa4`, scheduled due callbacks relied solely on `recipient_tag`. If an ephemeral tag was rebound to a new or unverified session, a due prompt could inadvertently be injected into an unintended session. Commit `e211aa4` introduces explicit `recipient_session_id` binding. It strictly rejects delivery if the recipient tag has been reassigned to any session whose session ID does not match `expected_session_id`.
2. **Resting-State Guard** (`scripts/supervision/service.py`):
   `process_due_callbacks` now inspects `sess.get('reported_state')` and holds callback delivery if the target session is in `'busy'`, `'working'`, `'draft'`, or `'menu-or-draft'`. This prevents interrupting interactive drafting or in-flight model generation.
3. **Liveness Verification** (`scripts/supervision/service.py`):
   Workload PID existence is explicitly verified against `/proc/{pid}`. Delivery aborts if the PID is dead or missing.
4. **Win35 Endpoint Candidate Deploy-Readiness** (`research/antigravity/recovery/REPORT-BUS-WIN35-DEPLOY-READINESS-C3123.md`):
   Candidate `e1e8e50` in worktree `.local/wt-win35-endpoint-3273594b` was evaluated without modifying `agent-bus` canonical source or assuming unapproved task acceptance. Code inspection confirms mutual TLS with client certificate allowlisting by SHA256 fingerprint, idempotency key checks (409 Conflict), and strict separation of ack/accept/complete lifecycle calls. Port 8788 was verified free and no duplicate brokers exist.
5. **Tracker Parity & Administrative CAS Reconciliation** (`research/antigravity/recovery/RECEIPT-TRACKER-CAS-RECONCILIATION-C3123.md`):
   The audit confirms restoration of `coordination/TASKS.json` to 282 rows (SHA256 `e80ed0f97b7f6bc02da6173753dc1f1aeb86f592128128f6ab72b1f88fdcc473`). Historical checkout errors (commands 30574/30580) were documented with a strict invariant against restoring or checking out peer-owned files. Outdated metadata in `.local/codex/c3122-ant-semantic-ack/cas-result.json` (previously 280 rows) was acknowledged and reconciled.

All automated unit tests (55/55 in `test_service.py` and 59/59 in regression suites) passed cleanly. Live runtime verification confirms the supervisor daemon (`PID 3326006`) successfully reloaded `service.py` (SHA256 `29758746...`) and correctly supervises `bus327-due-0650` bound to session `3273594b-3244-45f6-87af-a6a72af7acb4`.

**Final Verdict: ACCEPTED.**

---

## 2. Test Execution & Output Log

All test suites were executed directly on the host in `/home/alexey/git/cloudflare-agent-git`.

### 2.1. Supervision Service Unit Tests
- **Command**:
  ```bash
  python3 -m unittest scripts/supervision/test_service.py
  ```
- **Output**:
  ```text
  Ran 55 tests in 6.822s

  OK
  ```
- **Result**: **PASS** (55/55 passed, including new test cases `test_process_due_callbacks_recipient_session_id_match`, `test_process_due_callbacks_tag_reassignment_rejected`, and `test_process_due_callbacks_resting_state_guard`).

### 2.2. Regression Test Suites
- **Command**:
  ```bash
  python3 -m unittest scripts/supervision/test_terminal_consumer.py scripts/supervision/test_failover_integration.py scripts/metrics/test_export.py
  ```
- **Output**:
  ```text
  Ran 59 tests in 0.608s

  OK
  ```
- **Result**: **PASS** (59/59 passed: 25 terminal consumer tests, 4 failover integration tests, 30 metrics export tests).

---

## 3. Live Runtime Endpoints & File Manifest Verification

### 3.1. Live Metrics Endpoint (`/api/latest`)
- **Command**:
  ```bash
  curl -s http://127.0.0.1:8766/api/latest
  ```
- **Verification Result**:
  - HTTP 200 returned valid structured JSON payload.
  - Collector daemon confirmed active (`PID 3271215`).
  - Active heads telemetry confirms Bus head supervised:
    ```json
    "zcode-bus-win35-recovery-head-20261006-resume": {
      "session_id": "3273594b-3244-45f6-87af-a6a72af7acb4",
      "reported_state": "idle",
      "alive": true,
      "reason": "idle-empty",
      "status": "ok"
    }
    ```

### 3.2. Supervisor Source Manifest (`.local/supervision/source-manifest.json`)
- **Command**:
  ```bash
  cat .local/supervision/source-manifest.json
  ```
- **Observed Content**:
  ```json
  {
    "service_path": "/home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py",
    "service_sha256": "297587468117093c8a5766708accb7a9bab637e32d8bce5724b7b09223187f35",
    "failover_path": "/home/alexey/git/cloudflare-agent-git/scripts/supervision/failover_integration.py",
    "failover_sha256": "a6556d6454d2d87511c0c5290289fd095f3933c836531a59f4f295b1b6c6d81c",
    "loaded_at": "2026-10-07T06:36:56.224814+00:00",
    "authority": "canonical supervision runtime source proof"
  }
  ```
- **Checksum Verification**:
  ```bash
  sha256sum scripts/supervision/service.py scripts/supervision/failover_integration.py
  ```
  - `297587468117093c8a5766708accb7a9bab637e32d8bce5724b7b09223187f35  scripts/supervision/service.py` (Exact match)
  - `a6556d6454d2d87511c0c5290289fd095f3933c836531a59f4f295b1b6c6d81c  scripts/supervision/failover_integration.py` (Exact match)
  - Live supervisor PID: `3326006` started at `08:36 CEST` (`06:36 UTC`), exactly matching `loaded_at`.

### 3.3. Due Callbacks Configuration (`.local/supervision/due_callbacks.json`)
- **Command**:
  ```bash
  cat .local/supervision/due_callbacks.json
  ```
- **Observed Content**:
  ```json
  {
    "callbacks": [
      {
        "id": "bus327-due-0650",
        "recipient_tag": "zcode-bus-win35-recovery-head-20261006-resume",
        "recipient_session_id": "3273594b-3244-45f6-87af-a6a72af7acb4",
        "due_at": "2026-10-07T06:50:00Z",
        "prompt": "BUS327-CALLBACK due 06:50: Check reviewer result for bus-win35-endpoint-impl-review-01b (REV-BUS-ENDPOINT-IMPL-01-20261007.md is APPROVED), verify endpoint worktree deliverables at commit e1e8e50, pick next useful owned Bus task.",
        "delivered": false,
        "delivered_at": null
      }
    ]
  }
  ```
- **Result**: `bus327-due-0650` correctly binds `recipient_tag: "zcode-bus-win35-recovery-head-20261006-resume"` and `recipient_session_id: "3273594b-3244-45f6-87af-a6a72af7acb4"`.

---

## 4. Adversarial Negative & Boundary Testing

Dedicated adversarial verification tests were executed against the runtime logic:

### 4.1. Negative Case 1: Tag Matches but Session ID Differs (Anti-Imposter Check)
- **Scenario**: A callback specifies `recipient_tag: "test-head"` and `recipient_session_id: "sess-legit-owner"`. An active session registers `tag: "test-head"` but has `id: "sess-imposter"`.
- **Observed Behavior**:
  - `reassigned = [s for s in sessions if s.get('tag') == target_tag and s.get('id') != expected_session_id]` evaluates to non-empty.
  - The loop executes `continue` immediately.
  - `delivered` returns `[]`.
  - Callback entry remains `delivered: false`.
  - Zero messages dispatched to the imposter session.
- **Verdict**: **PASS (Anti-imposter defense verified)**.

### 4.2. Negative Case 2: Recipient in Non-Resting State (`working`, `busy`, `draft`, `menu-or-draft`)
- **Scenario**: Callback is past `due_at`, recipient session ID and tag match, and workload PID is alive, but `reported_state` is `'working'`, `'busy'`, `'draft'`, or `'menu-or-draft'`.
- **Observed Behavior**:
  - `reported_state` check triggers `if reported_state in ('busy', 'working', 'draft', 'menu-or-draft'): continue`.
  - Callback is deferred without mutating `delivered` state.
  - No prompt injection occurs while the target session is actively executing or in draft.
- **Verdict**: **PASS (Resting-state protection verified)**.

### 4.3. Negative Case 3: Missing or Dead Workload PID in `/proc`
- **Scenario**: Session ID and tag match, but `workload_pid` is `None`, `0`, or a nonexistent PID (`999999999`).
- **Observed Behavior**:
  - `pathlib.Path(f'/proc/{pid}').exists()` returns `False`.
  - Execution branches to `continue`.
  - `delivered` returns `[]`, callback remains `delivered: false`.
  - Prevents zombie/phantom deliveries.
- **Verdict**: **PASS (Process liveness enforcement verified)**.

### 4.4. Boundary Case 4: Due Callback Binding Parity
- **Scenario**: Verify `bus327-due-0650` in `.local/supervision/due_callbacks.json` against active sessions.
- **Observed Behavior**:
  - Target session `3273594b-3244-45f6-87af-a6a72af7acb4` corresponds exactly to the live Bus head session recorded in `.supervision.heads.zcode-bus-win35-recovery-head-20261006-resume.session_id`.
  - State is currently `idle`, PID is verified alive.
- **Verdict**: **PASS (Exact recipient binding confirmed)**.

### 4.5. Negative Case 5: Port 8788 and Duplicate Broker Check
- **Scenario**: Ensure no rogue or competing broker instances are listening on port 8788 or conflicting with the Win35 adapter.
- **Observed Behavior**:
  - `ss -tlnp | grep 8788`: Returned exit code 1 (zero listeners on port 8788).
  - Process table check `ps aux | grep -E "agent-bus|adapter\.py|8788"`: Confirmed zero running instances of `adapter.py` or `agent-bus` daemons.
  - Storage path `/home/alexey/.local/share/agent-bus-win35/store` confirmed nonexistent.
- **Verdict**: **PASS (Zero port collisions or duplicate brokers)**.

---

## 5. Artifact & Reconciliation Audit

### 5.1. Bus Win35 Endpoint Deploy-Readiness (`REPORT-BUS-WIN35-DEPLOY-READINESS-C3123.md`)
The candidate worktree `/home/alexey/git/agent-bus/.local/wt-win35-endpoint-3273594b` at commit `e1e8e50fc828f4d65060707bce0c0b4c31d6372e` was verified:
- `adapter/adapter.py`: SHA256 `74ae6dff512ae09fbad909a72bd521f5598d44754238a63ffeef9ded9848074d`
- `tools/make-certs.sh`: SHA256 `b258a1faed0fab1db76725076361720afe876ea609f820ca7e7a213eceb49556`
- `tests/e2e_win35_endpoint.py`: SHA256 `4ebe24b7fb375af8b1ee73478b97bfd81f437f4217cb121d94f44c6d04dd3640`
- Reviewer deliverables present:
  - `DEPLOY-NOTES.md` (2,834 bytes)
  - `IMPLEMENTATION-LOG.md` (9,278 bytes)
  - `REV-BUS-ENDPOINT-IMPL-01-20261007.md` (3,523 bytes)
- Failed worker and reviewer task rows (`bus-win35-endpoint-impl-01` and `bus-win35-endpoint-impl-review-01b`) were diagnosed accurately: standard launcher `receipt.json` was omitted in `cwd`. The report correctly preserves these failure records rather than classifying them as false watcher bugs or force-completing them.
- Clear boundary maintained: deploy-readiness evaluation does not conflate with physical deployment. Zero changes were committed to `agent-bus` canonical main.

### 5.2. Task Tracker Parity & CAS Reconciliation (`RECEIPT-TRACKER-CAS-RECONCILIATION-C3123.md`)
- `coordination/TASKS.json`:
  - Verified count: 282 tasks.
  - Verified SHA256: `e80ed0f97b7f6bc02da6173753dc1f1aeb86f592128128f6ab72b1f88fdcc473`.
  - All team intakes intact.
- Prior CAS Metadata Reconciled:
  - `.local/codex/c3122-ant-semantic-ack/cas-result.json` had recorded stale state (`rows: 280`, `before_sha256: e8cd55a8...`).
  - Reconciled with truth: 282 rows under `e80ed0f9...`.
  - Acknowledged invariant: Ant head must never execute `git checkout`, `git restore`, `git reset`, or broad `git stash` against peer-owned tracking files (`coordination/TASKS.json`, `coordination/codex.md`). Updates must strictly serialize through `flock .local/git.lock`.

---

## 6. Residual Risks & Operational Recommendations

1. **Unbounded Callback Retention on Reassigned Tags**:
   - *Risk*: If a callback's `recipient_session_id` expires or is permanently killed, and a new session assumes the tag, the callback will remain held indefinitely (`delivered: false`).
   - *Recommendation*: Consider adding a callback expiration threshold (`expires_at` or `max_retries`) or emitting an alert to supervision logs if a callback is overdue by more than 3600 seconds without a matching session ID.
2. **Atomic Session Inspection Granularity**:
   - *Risk*: `sessions` is passed as a snapshot to `process_due_callbacks`. If a session transitions from `idle` to `working` between snapshot capture and `recorded_send`, a small race window exists.
   - *Mitigation*: The current check is sufficiently protective for daemon poll intervals (60s), but real-time interactive safety will benefit from verifying the target session's state immediately prior to `recorded_send`.
3. **Physical Win35 Bootstrap Execution**:
   - *Risk*: As noted in `REPORT-BUS-WIN35-DEPLOY-READINESS-C3123.md`, the code and cert tooling are ready, but physical provisioning requires real CA generation in `/home/alexey/.local/share/agent-bus-win35/secrets` and root device bootstrap.
   - *Recommendation*: Await explicit Win35 root coordination before initiating certificate issuance or starting the systemd service.

---

## 7. Audit Conclusion

All components of commit `e211aa4` and associated deliverables in `f90c897` satisfy the rigorous requirements of the technical, architectural, and security contracts:
- Exact session binding and anti-tag-reassignment defense are functional and tested.
- Resting-state protection prevents spurious interruptions of busy/drafting sessions.
- Process liveness checks in `/proc/{pid}` prevent dead deliveries.
- Bus Win35 deploy-readiness is properly fenced without unauthorized mutations.
- Tracker parity at 282 rows and CAS metadata reconciliation are completely restored and verified.

**VERDICT: ACCEPTED**
