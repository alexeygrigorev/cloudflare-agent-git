# Independent QA Review: Supervision Idle Wake and Failover Repair (C3110)

## Review Metadata

- **Review Task ID**: `t-supervision-idle-wake-and-failover-c3110`
- **Head / Parent Session ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`
- **Reviewer Session ID**: `c81c569c-a455-40dd-8b43-ee086e007453`
- **Reviewer Agent**: `Antigravity CLI (gemini-3.1-pro-high)`
- **Target Repository**: `/home/alexey/git/cloudflare-agent-git`
- **Target Base Commit**: `0dc65cf72006a7f9352e5270a690ec65bed52bf1`
- **Files Under Audit**:
  - `scripts/supervision/service.py` (+228 / -7)
  - `scripts/supervision/test_service.py` (+264 / -0)
- **Review Scope**: Pinned source audit, negative test matrix evaluation, delivery retry backoff verification, role failover candidate trigger verification, empirical unit test execution (51/51), live screen verification on active Aplexer sessions, and unconstrained verdict.
- **Review Verdict**: **ACCEPTED**

---

## 1. Executive Summary

This independent code quality assurance review inspects the implementation and test verification of the **supervision idle wake and failover repair** (Task `t-supervision-idle-wake-and-failover-c3110`), resolving operational defects identified in supervision delivery incidents C3088 and C3090.

The audit evaluated three interrelated functional subsystems:
1. **Aplexer Awareness Bootstrap Tail Chrome Tolerance**: Expanding `COMPOSER_TAIL_CHROME_RE` to recognize multi-line Aplexer awareness bootstrap banners in session tail scrollback as non-blocking chrome, preventing false `unknown` or false `draft` classifications when prompt lines are cleanly empty.
2. **Delivery Retry Backoff on Diagnostic Hold**: Enforcing a mandatory 180-second (`time.time() + 180`) cooldown whenever delivery encounters a `known-footer-classifier-mismatch`, eliminating the rapid-fire delivery retry storm observed in incident C3088/C3090 (where 28 un-backed-off attempts occurred over 11,000s).
3. **Automated Role Failover Candidate 43ea Trigger**: Triggering a structured `failover-candidate-action` event targeting verified candidate `43ea` (`43ea3400965e690206f823640173992a9ea0c7b4`) when a monitored principal or head is either confirmed un-alive (missing `/proc/<pid>`) or blocked beyond 2x retry SLO (>600s), while cleanly suppressing further message delivery spam during failover vacancy.

All 51 unit tests in `scripts/supervision/test_service.py` execute cleanly in 4.16s with 0 failures and 0 errors. First-hand live screen captures against active Aplexer sessions (`codex-principal`, `zcode-bus-win35-recovery-head-20261006-resume`, etc.) empirically validate the classifier's precision. The changes strictly preserve negative safety gates (user drafts, working states, interactive menus).

The implementation satisfies all architectural, security, and operational requirements without regressions.

---

## 2. Pinned Source Verification & Diff Analysis

### 2.1 Git Diff Statistics

```text
 scripts/supervision/service.py      | 228 ++++++++++++++++++++++++++++++-
 scripts/supervision/test_service.py | 264 ++++++++++++++++++++++++++++++++++++
 2 files changed, 485 insertions(+), 7 deletions(-)
```

### 2.2 Tail Chrome Classification Regex Update

In [`scripts/supervision/service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L732-L736):
```python
COMPOSER_TAIL_CHROME_RE = re.compile(
    r'^\s*[─━_=-]+\s*$'
    r'|.*(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|Gemini|glm-|usage|workspace|warning|Worked for|Ask Codex)'
    r'|.*(?:Aplexer awareness|Before editing files|Declare your work|Check peer mail|participate in \d+ workspace|Workspace coordination|git:\s*worktree|you:\s*\S+|peers\s*\(\d+\)|shared paths|peer-provided data).*'
)
```

**Verification Assessment**:
- The prior regular expression only matched `.*Aplexer awareness bootstrap.*`. When the session printed subsequent lines of the multi-line Aplexer bootstrap message (such as `Before editing files, run 'a context'`, `Declare your work before touching files`, `Workspace coordination`, `git: worktree main`, `peers (2):`), the composer tail parser stopped recognizing the lines as chrome, falsely returning `unknown`.
- The expanded regular expression covers all standard lines output by the Aplexer awareness bootstrap banner.
- As demonstrated below in Section 4, because the tail scan only inspects lines strictly *after* the last detected prompt marker (`lines[index + 1:]`), genuine user prompt drafts on the prompt line itself are unaffected and remain strictly categorized as `draft`.

### 2.3 Delivery Retry Backoff on Diagnostic Hold

In both the principal delivery block ([lines 1603–1612](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1603-L1612)) and head delivery block ([lines 1942–1951](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1942-L1951)):

```python
if status == 'not-ready':
    detail = outcome.get('detail', '')
    if (('Context' in detail or 'GPT-' in detail) and '·' in detail) or re.search(
        r'Aplexer awareness|Before editing files|Declare your work|Check peer mail|participate in \d+ workspace|Workspace coordination|worktree|peers|shared paths|peer-provided data',
        detail
    ):
        item['diagnostic_hold'] = 'known-footer-classifier-mismatch'
        pending['diagnostic_hold'] = 'known-footer-classifier-mismatch'
    if item.get('diagnostic_hold') == 'known-footer-classifier-mismatch':
        item['cooldown_until'] = time.time() + 180
```

And in the delivery gate ([line 1583](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1583) and [line 1925](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1925)):
```python
if may_deliver(pending, identity['id'], spool=PRIVATE) and count >= 2 and time.time() >= item.get('cooldown_until', 0) and not item.get('failover_candidate'):
```

And in the SLO check update ([line 1988](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1988)):
```python
item['cooldown_until'] = max(item.get('cooldown_until', 0), time.time() + 300 if time.time() >= cooldown else cooldown)
```

**Verification Assessment**:
- When delivery refuses due to an Aplexer banner mismatch or footer classifier detail, `diagnostic_hold` is flagged as `known-footer-classifier-mismatch` and `item['cooldown_until']` is set 180s into the future.
- The delivery gate condition `time.time() >= item.get('cooldown_until', 0)` directly inhibits all subsequent delivery attempts until the 3-minute window elapses.
- Using `max(item.get('cooldown_until', 0), ...)` ensures that periodic SLO evaluations cannot accidentally decrease an active cooldown.
- This directly resolves incident C3088/C3090 by converting a continuous retry loop into a controlled 3-minute backoff cycle.

### 2.4 Candidate 43ea Role Failover Trigger

In both principal monitoring ([lines 1387–1428](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1387-L1428) & [lines 1663–1725](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1663-L1725)) and head monitoring ([lines 1762–1805](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1762-L1805) & [lines 2002–2065](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L2002-L2065)):

```python
if not item.get('alive', True) or dur > 2 * slo_limit:
    item['failover_candidate'] = True
    failover_reason = f"leader {tag} role vacancy: {'un-alive (confirmed dead)' if not item.get('alive', True) else f'unACKed beyond 2x SLO ({round(dur, 1)}s > {2 * slo_limit}s)'}; candidate 43ea trigger condition met"
    event('failover-candidate-action',
          role='principal', # or 'head'
          role_vacancy=True,
          entity=tag,
          principal=tag,
          message_id=pending['id'],
          duration_seconds=round(dur, 2),
          slo_seconds=slo_limit,
          alive=item.get('alive', True),
          trigger_condition='un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
          candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
          candidate='43ea',
          reason=failover_reason)
    report['actions'].append({
        'kind': 'failover-candidate-action',
        'role': 'principal', # or 'head'
        'role_vacancy': True,
        'entity': tag,
        'recipient': tag,
        'principal': tag,
        'message_id': pending['id'],
        'duration_seconds': round(dur, 2),
        'slo_seconds': slo_limit,
        'alive': item.get('alive', True),
        'trigger_condition': 'un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
        'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
        'candidate': '43ea',
        'reason': failover_reason
    })
```

**Verification Assessment**:
- **Trigger Conditions**:
  1. `not item.get('alive', True)`: Process PID is missing or absent in `/proc/<pid>`.
  2. `dur > 2 * slo_limit`: Pending notification unacknowledged for greater than 2x retry SLO (e.g. `dur > 600s` against default 300s SLO).
- **Candidate Commit Pin**: Exact SHA `43ea3400965e690206f823640173992a9ea0c7b4` is pinned. We independently verified this commit in `/home/alexey/git/agent-coordination-role-failover` (`git log -1 43ea340` confirms commit *"Reconcile inherited head backfills across principal failures"* by Alexey Grigorev).
- **Lifecycle Cleanliness**: When a recipient acknowledges (`status == 'recipient-acked'`), a stale message is superseded (`status == 'stale-beyond-slo-sender-change'`), or the session returns to healthy idle, `item.pop('failover_candidate', None)` cleans up the state.
- **Delivery Invalidation**: When `failover_candidate` is set to `True`, delivery attempts to that entity are gated off via `and not item.get('failover_candidate')`.

---

## 3. Negative Safety & Classifier Boundary Verification Matrix

An exhaustive matrix of positive, negative, and adversarial test inputs was executed directly against `scripts.supervision.service.composer` to confirm that tail chrome tolerance has zero false negatives on real drafts, busy states, or interactive menus.

| Test ID | Screen Context / Input Pattern | Expected Result | Evaluated Output | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Empty prompt line (`>`) followed by complete multi-line Aplexer awareness bootstrap banner | `empty` | `empty` | **PASS** |
| **TC-02** | User draft without banner: `> my partial command\n────` | `draft` | `draft` | **PASS** |
| **TC-03** | Codex prompt draft without banner: `› unfinished prompt\n Context 50%` | `draft` | `draft` | **PASS** |
| **TC-04** | User draft *with* banner in tail: `> my partial command\nAplexer awareness bootstrap...\nBefore editing files...` | `draft` | `draft` | **PASS** |
| **TC-05** | Codex prompt draft *with* banner in tail: `› unfinished prompt\nAplexer awareness bootstrap...\nWorkspace coordination...` | `draft` | `draft` | **PASS** |
| **TC-06** | Active working state: `• Working (12s • esc to interrupt)\n› Ask Codex to do anything` | `busy` | `busy` | **PASS** |
| **TC-07** | Interrupt prompt: `esc to interrupt\n>` | `busy` | `busy` | **PASS** |
| **TC-08** | Claude rating menu: `How is Claude doing?\n[1] Great  [2] Ok\n>` | `menu-or-draft` | `menu-or-draft` | **PASS** |
| **TC-09** | Option select menu: `Please Select an option:\n>` | `menu-or-draft` | `menu-or-draft` | **PASS** |
| **TC-10** | Model choose menu: `Choose model:\n>` | `menu-or-draft` | `menu-or-draft` | **PASS** |
| **TC-11** | Unrecognized child process text: `>\nrandom child process error output` | `unknown` | `unknown` | **PASS** |
| **TC-12** | Screen missing any prompt marker: `no prompt or composer here` | `unknown` | `unknown` | **PASS** |
| **TC-13** | Default prompt placeholder: `› Ask Codex to do anything\n? for shortcuts` | `empty` | `empty` | **PASS** |
| **TC-14** | Default prompt placeholder with `Worked for 23m 59s` and `glm-5.3-flash` chrome | `empty` | `empty` | **PASS** |

**Conclusion**: The classification logic exhibits strict fail-closed precision. Banner tolerance operates exclusively on lines trailing an empty prompt marker. Any draft content on the prompt line triggers an immediate `draft` verdict.

---

## 4. Empirical Test Suite Execution

We executed the entire supervision test suite using the standard unittest test runner:
`python3 -m unittest -v scripts/supervision/test_service.py`

### Execution Summary
- **Total Tests Run**: **51**
- **Passed**: **51**
- **Failures**: **0**
- **Errors**: **0**
- **Execution Duration**: **4.161s**
- **Exit Code**: **0**

### Targeted Audit of Newly Introduced Tests

1. [`test_delivery_diagnostic_hold_cooldown`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/test_service.py#L1224-L1277):
   - Sets up a simulated pending message with delivery returning `status: 'not-ready'` and detail mentioning `Before editing files, run 'a context'...`.
   - Asserts `item['diagnostic_hold'] == 'known-footer-classifier-mismatch'`.
   - Asserts `item['pending']['diagnostic_hold'] == 'known-footer-classifier-mismatch'`.
   - Asserts `item['cooldown_until'] == 1180.0` (exactly `current_time + 180s`).
   - Asserts pending message `m-hold-cool-1` remains in pending state without being discarded.
   - **Result**: PASSED cleanly.

2. [`test_leader_failure_failover_event`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/test_service.py#L1279-L1377):
   - **Part 1 (Blocked beyond 2x SLO)**: Staged message age = 700s against 300s SLO (> 2x 300s). Asserts `failover_candidate` is set to `True`, status is `blocked_beyond_slo`, `failover-candidate-action` event is recorded in status report actions and emitted to `events.jsonl` with `candidate: '43ea'`, `candidate_pin: '43ea3400965e690206f823640173992a9ea0c7b4'`, and `trigger_condition: 'blocked_beyond_2x_slo'`.
   - **Part 2 (Un-alive process)**: Simulates leader with nonexistent `workload_pid: '99999999'`. Asserts `failover-candidate-action` event is emitted with `alive: False`, `trigger_condition: 'un-alive'`, and `role_vacancy: True`.
   - **Result**: PASSED cleanly.

3. [`test_composer_aplexer_awareness_full_banner_tolerance`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/test_service.py#L1504-L1522):
   - Validates multi-line awareness banner text in tail evaluates to `empty` across multiple caller tags (`ant-head-gap-recovery-20261007`, `codex-principal`, and `None`).
   - **Result**: PASSED cleanly.

4. [`test_composer_preserves_strict_draft_rejection`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/test_service.py#L1524-L1547):
   - Validates that drafts with and without banners are strictly rejected as `draft`.
   - **Result**: PASSED cleanly.

---

## 5. Live Screen Verification on Active Aplexer Sessions

We conducted live screen captures of running sessions on the host using `aplexer capture <session_id> --screen --plain` and evaluated them through `scripts.supervision.service.composer`:

### Session 1: `codex-principal` (`93cf28f2-2872-411c-a5da-179e1b83b59f`)
- **Captured Tail**:
  ```text
  • Working (18m 42s • esc to interrupt)
    └ Tip: Use /vim to toggle Vim editing in the composer.

  › Ask Codex to do anything
    GPT-6.1-Sol medium · Context 25% left · ~/git/cloudflare-agent-git · Context 75% used
    ? for shortcuts                                                   ⚠ 1 warning · f2 to view
  ```
- **Evaluation**: `service.composer(screen, 'codex-principal')` $\rightarrow$ `'busy'`
- **Verification**: Because Codex is actively executing a prompt (`• Working (...)`), the classifier correctly detects `busy`, safely suppressing any delivery interruption.

### Session 2: `zcode-bus-win35-recovery-head-20261006-resume` (`3273594b-3244-45f6-87af-a6a72af7acb4`)
- **Captured Tail**:
  ```text
  Worked for 23m 59s · 12:17 AM

  › Ask Codex to do anything

    glm-5.3-flash max · ~/git/cloudflare-agent-git · You are the focused
  ```
- **Evaluation**: `service.composer(screen, 'zcode-bus-win35-recovery-head-20261006-resume')` $\rightarrow$ `'empty'`
- **Verification**: Clean idle state with engine footer chrome is properly recognized as `empty`, allowing wake delivery.

### Session 3: `coord-917-custody-resume-20261006` (`3138b062-a27a-4897-b68e-24f86320ef7c`)
- **Captured Tail**:
  ```text
  How's the CLI experience so far? Help us improve:
  [1] Good  [2] Fine  [3] Bad  [0] Skip

  ? for shortcuts                                          Gemini 3.8 Flash · high
  ```
- **Evaluation**: `service.composer(screen, 'coord-917-custody-resume-20261006')` $\rightarrow$ `'menu-or-draft'`
- **Verification**: The interactive survey menu is correctly trapped as `menu-or-draft`, blocking unprompted message injection.

### Session 4: `public-journal-release-custody-20261006` (`513eab03-fccb-43e3-bcf0-5649f03b5425`)
- **Captured Tail**:
  ```text
  ────────────────────────────────────────────────────────────────────────────────
  >
  ────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts                                          Gemini 3.8 Flash · high
  ```
- **Evaluation**: `service.composer(screen, 'public-journal-release-custody-20261006')` $\rightarrow$ `'empty'`
- **Verification**: The Antigravity prompt line `>` with horizontal divider bars and shortcut chrome correctly evaluates to `empty`.

---

## 6. Constraints & Safety Audit

- **Zero Rust / NPM Builds**: No `cargo`, `npm`, `npx`, or package builds were triggered. All testing used existing native Python 3.12 and pinned host tooling.
- **Zero Purchases / Remote API Spends**: No external paid APIs or purchases were invoked.
- **Non-Destructive Audit**: The audit was strictly read-only with respect to implementation code. No changes to `scripts/supervision/` were made or committed.
- **Git Lock Serialization**: No Git locks were taken or contested.

---

## 7. Final Independent Verdict

| Review Area | Criteria | Assessment | Status |
| :--- | :--- | :--- | :--- |
| **Aplexer Banner Tolerance** | Tolerates multi-line awareness bootstrap tail chrome without false `unknown`/`draft` | Verified by regex analysis, unit tests, and live screen capture | **CONFIRMED** |
| **Strict Draft Protection** | Rejects unsubmitted prompts (`>`, `›`) with `draft` | Verified across positive and negative draft tests | **CONFIRMED** |
| **Delivery Retry Backoff** | Enforces 180s cooldown on diagnostic hold (`known-footer-classifier-mismatch`) | Verified in `service.py` logic and unit test `test_delivery_diagnostic_hold_cooldown` | **CONFIRMED** |
| **Candidate 43ea Trigger** | Emits `failover-candidate-action` for candidate `43ea` when un-alive or blocked > 2x SLO | Verified in `service.py` logic and unit test `test_leader_failure_failover_event` | **CONFIRMED** |
| **Candidate 43ea Git Pin** | Immutable pin `43ea3400965e690206f823640173992a9ea0c7b4` is verified in role-failover repo | Verified on disk in `/home/alexey/git/agent-coordination-role-failover` | **CONFIRMED** |
| **Regression Prevention** | All 51 test cases in `scripts/supervision/test_service.py` pass cleanly | 51/51 tests pass in 4.16s (0 errors, 0 failures) | **CONFIRMED** |

### **Verdict: ACCEPTED**

The supervision idle wake and failover repair implementation in `scripts/supervision/service.py` is robust, objectively verified, thoroughly tested, and ready for production operations.
