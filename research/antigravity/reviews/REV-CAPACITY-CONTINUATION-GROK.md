# REV-CAPACITY-CONTINUATION-GROK

Independent Grok diagnosis of provider capacity rejection, stale `working` lifecycle deadlock, and safe receiver continuation (Codex Directives C2400 / C2401).

- **Reviewer:** FileBus identity `33748fbc-701f-44b3-9cdc-622cdf4a6fbc` (`grok-capacity-reviewer`). Task `075168a1-0c1a-4af2-89de-1c356dae87b5` acked at `2026-10-05T08:14:44Z`. No `--from`, no `APLEXER_*` override.
- **As-of:** 2026-10-05 (Europe/Berlin). Run `20261005T081426Z-d304f18c`.
- **Authority:** Independent empirical audit. Prior reports are evidence, not a pre-loaded verdict.
- **Primary screenshot:** `/home/alexey/.pocketshell/attachments/cloudflare-agent-git/codex-principal/20261004-132555-01-clipboard.png`
- **Verdict:** **BOUNDED ACCEPTANCE**

This verdict accepts the deadlock diagnosis and the fail-closed 180s continuation *contract*. It does not accept installed-runtime recovery, userland manufacture of `state-report idle`, or integration of `research/grok/capacity-recovery/policy.py`.

---

## 1. Verdict in one page

A live Codex CLI TUI (composer placeholder `Ask Codex to do anything`, header chip **Gemini 3.8**) rendered the exact red fleet-capacity string:

`Selected model is at capacity. Please try a different model.`

That string is compiled into Codex CLI 0.160.0's native binary, adjacent to distinct strings `Flex capacity unavailable.` and `Quota exceeded. Check your plan and billing details.` Capacity is therefore a first-class TUI error class, separate from account quota and from context-window compaction.

Codex lifecycle hooks that actually write aplexer state are only `SessionStart` / `UserPromptSubmit` → `working` and `Stop` → `idle`. Installed `CODEX_EVENTS` and the 0.160.0 binary contain **no** `OnError` and **no** `CapacityRejection` event. After an abnormal halt, `reported_state` can remain `working`. Protocol `evaluate_readiness_verdict` (protocol tree `7efa493`) Ready-accepts only `source == "reported"` and state `waiting` or `idle`. An expired `working` report becomes a heuristic, and heuristics fail closed. A 180-second timer cannot emit `state-report idle`, so it cannot unlock native `message deliver`.

Safe continuation is therefore: keep the durable inbox; do not spoof identity; do not inject into a busy or drafted composer; require two consecutive empty-composer snapshots and no running child tools; backoff 180/360/720s fail-closed; if capacity persists, route the *owned work* to an eligible healthy alternative head without a second writer on the same checkout. Same-conversation retry in the existing TUI (human or the bound session) is the only currently proven recovery path.

Userland policy `research/grok/capacity-recovery/policy.py` is an uninstalled dry-run. Its 20 tests pass. It still permits `quota=None` through to `dry_run_same_conversation_retry`, does not model the 512 MiB scratch ceiling, does not strip ANSI, and classifies the screenshot's ASCII `>` composer as `unknown`. Live supervision `composer()` still matches substring `Select` inside `Selected model is at capacity`, so even a later authentic idle would be labelled `menu-or-draft`. Those defects bound this acceptance.

---

## 2. Source and binary pins

Recorded at audit time on this host. Dirty checkouts are not the installed runtime.

| Artifact | Pin | Notes |
|---|---|---|
| Grok CLI | `grok 1.0.46 (2765805b9442)` | `/home/alexey/.local/bin/grok` → `/home/alexey/.grok/bin/grok` → `grok-1.0.46-linux-x86_64`. SHA-256 of the grok binary: `41626a53292324140b92556b9d42ff5542e3dcd04aff85eafb8689dd4adb44fc`. |
| Aplexer CLI | `a 0.1.9` | `/home/alexey/.local/bin/aplexer`. SHA-256 `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` (short pin `8d49a216d43c`). Has `message deliver`. **Lacks** `message readiness` (`unrecognized subcommand 'readiness'`). `a state-report` vocabulary: `idle` / `waiting` / `working`. |
| Codex CLI | `codex-cli 0.160.0` | `/home/alexey/.nvm/versions/node/v24.13.1/bin/codex` → `@openai/codex` 0.160.0. Native musl binary contains the exact capacity phrase. |
| Protocol origin | https://github.com/PocketShell-io/aplexer | Local remotes of both `/home/alexey/git/aplexer` and `/home/alexey/git/cloudflare-aplexer-protocol`. |
| Dirty aplexer checkout | HEAD `bc0d3d75ab00e87b8357e91e0d7297bd67c6e101` | Uncommitted `src/watch.rs`, `src/watch/state.rs`. **Not installed.** |
| Protocol worktree | HEAD `7efa49386d756575f1003825b050643688fa3fc5` on `fix/prompt-ready-lifecycle` | Contains `evaluate_readiness_verdict`. Debug binary is supervision's `SUPERVISION_APLEXER_BINARY`. **Not installed globally.** |

Installed 0.1.9 Ready-predicate parity with protocol `7efa493` is **unproven**. Native `not-ready` from `/home/alexey/.local/bin/aplexer` is authoritative for live delivery.

No Rust build, no global binary replacement, no live pane injection, and no competing supervisor were performed for this audit.

---

## 3. Primary screenshot (this audit's ground truth)

Inspected raster `/home/alexey/.pocketshell/attachments/cloudflare-agent-git/codex-principal/20261004-132555-01-clipboard.png`.

Observed, not inferred:

1. Header left: `? for shortcuts` and `+ 73 lines (ctrl+t to expand)`.
2. Header right: **Gemini 3.8**.
3. Body: red banner `Selected model is at capacity. Please try a different model.`
4. Trailing composer: empty placeholder `Ask Codex to do anything`, prompt glyph rendered as ASCII `>` in this capture, with a caret in the composer.

This is a live interactive Codex CLI session (Codex composer chrome) whose *selected model* is Gemini 3.8, halted on provider/model fleet capacity. The collapsed `+ 73 lines` region is the aborted turn, not a second prompt.

**Correction against prior FINDINGS.md:** that file described the selected model as `GPT-6.1-Sol medium`. This clipboard shows **Gemini 3.8**. Treat the screenshot as the incident pin for C2400/C2401. GPT-6.1-Sol may be a later recovered session or a different capture; it is not this image.

**Epistemic limit of a still image:** the PNG proves TUI error class and empty composer. It does not prove `reported_state` at capture time, and it does not prove that `Stop` was skipped. The stale-`working` claim rests on prior operational observation (FINDINGS.md / root `01a1061d`) plus the hook-table gap below, not on pixels alone.

---

## 4. Failure-shape taxonomy

These five shapes must not be collapsed. Codex 0.160.0's own string table already splits (1) and (3).

### 4.1 Provider / model capacity

Transient backend overload (HTTP 429 / 503 or equivalent fleet admission). Exact TUI copy in the 0.160.0 native binary, immediately followed by `Flex capacity unavailable.` and then `Quota exceeded. Check your plan and billing details.`

- Generation stops abnormally.
- Installed Codex / OpenCode aplexer wiring has no error-class hook, so `Stop` → `state-report idle` is not guaranteed.
- `UserPromptSubmit` already set `working`. If `Stop` does not run, `reported_state` stays `working`.
- After `REPORTED_STATE_STALE_MS = 8_000`, the working report expires (`working report expired`) and PTY heuristics take over. Heuristics cannot satisfy Ready.
- **Result:** stale lifecycle deadlock for native deliver. Empty composer is visible and still insufficient.

Same-conversation retry after the fleet recovers is valid *in the existing TUI*. Silent model switch is forbidden. A timer is backoff, not a state transition.

### 4.2 Context exhaustion

Exceeding the model token window. Codex 0.160.0 contains compaction machinery (`PreCompact`, `tokens left in this context window`, `Context window exceeded while compacting`). Compact or restart the session. This is not capacity, and a 180s wait does not enlarge the window.

### 4.3 Account quota

`quse` windows, `limit_reached`, Codex remaining ≤ 15%, or unknown windows. Hard fail-closed. Binary-adjacent string `Quota exceeded. Check your plan and billing details.` is this class, not (4.1). Fresh quota is required before any retry. Unknown quota is deny, not retry.

### 4.4 Normal idle

Clean turn completion. Codex `Stop` hook in `/home/alexey/.codex/hooks.json` runs `/home/alexey/.local/bin/a state-report idle || true`. Grok `Stop` in `/home/alexey/.grok/hooks/aplexer.json` reports idle via the protocol debug binary. Native deliver Ready requires this authentic reported rest (or `waiting`), not inferred quiet.

### 4.5 Native hook events (installed files + source tables)

**Codex** `/home/alexey/.codex/hooks.json`:

| Event | Command |
|---|---|
| `SessionStart` | `a state-report working` plus protocol `context hook --engine codex` |
| `UserPromptSubmit` | `a state-report working` plus awareness hook |
| `Stop` | `a state-report idle` |
| `PostToolUse` | awareness only |

No `Notification` → `waiting` for Codex. No error event.

**Grok** `/home/alexey/.grok/hooks/aplexer.json`:

| Event | Command |
|---|---|
| `SessionStart` / `UserPromptSubmit` | protocol debug `state-report working` |
| `Stop` | protocol debug `state-report idle` |
| `Notification` | `waiting` |
| `PostToolUse` | awareness only |

**Aplexer source** `/home/alexey/git/aplexer/src/hooks/mod.rs`:

```
CODEX_EVENTS: Stop→idle, UserPromptSubmit→working, SessionStart→working,
              plus awareness on SessionStart/UserPromptSubmit/PostToolUse.
```

`SubagentStop` is deliberately absent (mapping it to idle would lie mid-turn). **No `OnError`. No `CapacityRejection`.**

**Codex 0.160.0 native binary** (musl vendor `bin/codex`):

- Exact capacity phrase: present.
- Named events present: `UserPromptSubmit`, `SessionStart`, `SessionEnd`, `PostToolUse`, `PreToolUse`, `PreCompact`, `PermissionRequest`, `Stop`, `SubagentStop`.
- Named events absent (`find == -1`): `OnError`, `CapacityRejection`, `ErrorOccurred`.
- TUI hook help cluster: tool before/after, permission request, compact before/after, session start, session end, user prompt submit, subagent created, subagent end, interrupted-turn abort. Still no capacity/error hook.

`aplexer init --check --json`: Codex/Grok/Antigravity/OpenCode hooks present; Claude and Gemini-CLI events absent. The screenshot is Codex-with-Gemini-model, so Codex hooks apply. Gemini CLI absence is irrelevant to this incident.

**Unknown, not claimed:** whether 0.160.0 fires `Stop` or the "interrupted turn is aborted" hook on this exact capacity banner. Absence of an error mapping is not a trace that `Stop` never runs. The deadlock is the *observed* stuck `working` plus the *proven* missing error event.

---

## 5. Why a 180s timer cannot manufacture Ready

Protocol `evaluate_readiness_verdict` in `cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs` (HEAD `7efa493`), lines 73–128, in order:

1. Composer `Draft` or `Unknown` → Reject (fail closed).
2. Derived `state == "running"` (reported *or* heuristic) → Reject. Reported `working` maps to UI `running`.
3. Contradicted idle/waiting (later PTY past 2s grace) → Reject.
4. Ready **only if** `source == "reported"` **and** `state` is `waiting` or `idle`.
5. Everything else, including expired waiting plus empty composer, → Reject. Comment in source: expired waiting plus empty composer does not prove a completed turn.

Watch merge in dirty `/home/alexey/git/aplexer/src/watch/state.rs`:

- `REPORTED_STATE_STALE_MS = 8_000`. Fresh `working`/`waiting` wins; after 8s the report is rejected.
- `idle` has no clock TTL; later PTY beyond `IDLE_ACTIVITY_GRACE_MS = 2_000` retracts it (Antigravity hardcoded exemption in this dirty tree; that exemption is **not** proven present in installed 0.1.9).

Therefore:

- At t=0 capacity halt with stale `working`: deliver sees `recipient reported working`.
- At t=8s+ without a new report: working expired, heuristic source ≠ `reported` → still Reject.
- At t=180s, 360s, or 720s: still no authentic idle/waiting report. The timer did not call `a state-report idle`. Ready is unchanged.

Forging idle from a supervisor, injecting Enter, or treating elapsed time as rest would be state spoofing. The installed candidate correctly maps that case to `need_native_error_event` when native returns not-ready with reported `working` (`policy.py` `native_allows_retry` / `test_stale_working_needs_native_event_not_timer`).

Installed 0.1.9 has `message deliver` and does not have `message readiness`. Whether its Ready predicate equals `7efa493` is unproven. Fail closed on native `not-ready`.

---

## 6. Safe 3-minute receiver continuation (evaluated)

The 180s bound is a *retry spacing* after a classified live capacity event. It is not a readiness producer.

### 6.1 Do not drop work

FileBus `ack` stamps `acked_at` and leaves the envelope in `messages.json`. `reply` inserts a new `kind=reply` row with `reply_to` set; it does not delete the parent. This audit's task `075168a1-0c1a-4af2-89de-1c356dae87b5` remained in the store after ack. Aplexer `message deliver` of an existing ID likewise does not mint a second envelope (`already-submitted` / `not-ready` / `recipient-acked` keep the original). Unacknowledged tasks stay queued. Deleting mailbox files or GC'ing unread coordination mail to "clear" a deadlock is forbidden.

### 6.2 Do not spoof identity

Senders and receivers use authentic registered identities. FileBus authenticates the cred token bound to `identity_id`. Aplexer delivery `authorize_delivery` permits only the original sender or recipient session UUID in the same workspace. `--from` / `APLEXER_*` overrides are impersonation, not recovery. This reviewer used `reviewer_cred.json` for identity `33748fbc-701f-44b3-9cdc-622cdf4a6fbc` only.

### 6.3 Do not inject busy or drafted input

Require two consecutive empty composer snapshots, then verify zero running child tools, before any pane write. Policy `empty_twice()` implements the two-snapshot rule and returns false if the second capture is missing. It does **not** inspect `/proc` children. The unimplemented readiness-producer spec proposed `direct_child_pids`; that spec was independently `REQUEST_CHANGES` and remains uninstalled. Until a reviewed native child-process guard exists, userland must fail closed when children cannot be proven empty.

Supervision `eligible()` already requires `reported_state in ('idle','waiting')` and `composer==empty`, then counts consecutive ready snapshots. That is the right shape. Its composer classifier is currently unsafe on this incident (section 8).

### 6.4 Bounded backoff, then a different healthy owner

Policy backoff: first wait 180s, then 360s, then 720s, cap 3, fingerprint `(session_id, conversation_id, phrase)`. After the cap: `cap_retries`, still no fake idle.

If capacity persists or native Ready never returns:

1. Leave the original Codex conversation and its inbox intact.
2. Route *new owned work* through an eligible healthy head/executor (Antigravity owns integration in the recorded capacity-recovery notes).
3. Do not spawn a second principal on the same checkout.
4. Do not silent-switch models inside the stuck session.
5. Do not borrow another sender's envelope.

Human or same-bound-session resubmit in the existing TUI remains the proven recovery for that conversation (FINDINGS: principal 93cf recovered that way). This reviewer must not perform that injection.

---

## 7. Empirical checks run in this audit

Isolated `TMPDIR` under the run scratch. Offline only.

```
python3 -m unittest discover -s research/grok/capacity-recovery -v
Ran 20 tests in 0.004s
OK
```

Including `test_stale_working_needs_native_event_not_timer`, `test_live_capacity_waits_180s`, `test_empty_twice_required`, `test_supervision_select_false_positive_not_copied`, `test_quota_unknown_and_denied`. No test is labelled native success.

Independent Python probes against the screenshot text and current policy (not part of those 20 tests):

| Probe | Result |
|---|---|
| `classify_composer` on Unicode `› Ask Codex to do anything` + Gemini 3.8 header + capacity banner | `empty` |
| `classify_composer` on ASCII `> Ask Codex to do anything` (this clipboard's glyph) | `unknown` → `block_unknown` |
| `classify_capacity_signal` with `provenance=unknown` | `unproven_screen` (correct fail-closed) |
| `classify_capacity_signal` with `provenance=engine_event` | `live_capacity` |
| `plan_recovery` with `quota=None`, native ready, unicode empty composer, engine_event | **`dry_run_same_conversation_retry`** — quota bypass still open |
| Supervision `composer()` regex `Select` on the capacity sentence | **match** → `menu-or-draft` |
| Policy `\bSelect\b(?!ed model is at capacity)` on the same sentence | no match (policy does not copy the supervision bug) |

Codex binary string cluster (verbatim adjacency):

`Selected model is at capacity. Please try a different model.` / `Flex capacity unavailable.` / `Quota exceeded. Check your plan and billing details.` / `We're currently experiencing high demand, which may cause temporary errors.` / `internal error; agent loop died unexpectedly`

That is independent confirmation that capacity, flex-capacity, quota, high-demand, and agent-loop death are distinct classes inside the engine.

---

## 8. Defects that bound acceptance

These are current, reproduced, and blocking for any install or live continuation automation.

1. **`quota=None` still retries.** `classify_blocker()` only inspects quota when `obs.quota is not None`. Prior review REV-GROK-CAPACITY-RECOVERY required fail-closed `block_quota_unknown`. Unfixed. This audit reproduced `dry_run_same_conversation_retry` with quota omitted.
2. **No 512 MiB scratch ceiling** in `ResourceSample`. Only host root free (50 GiB new-worker / 8 GiB scratch) and 10 GiB RAM.
3. **No ANSI strip** before prompt regex. Fail-closed to `unknown` if CSI precedes `›`, which is safe against injection and an availability hazard.
4. **ASCII `>` composer.** This clipboard's prompt glyph is `>`. Policy and supervision both match only `›❯`. Result: `unknown`. A continuation runner that ingested this capture as-is would hold, which is fail-closed, and would never classify the real empty Codex composer if the TUI emits ASCII `>`.
5. **Supervision live `composer()` substring `Select`.** `scripts/supervision/service.py` line 400 still searches the *whole screen* for `Select`. The exact capacity banner therefore classifies as `menu-or-draft`. Even after a later authentic idle, supervision would refuse delivery. Policy already special-cased this; the running supervisor did not.
6. **Footer model-chip gap.** `_is_footer` recognizes `GPT-` + `medium` and `shortcuts`, not `Gemini 3.8`. Harmless while the chip sits above the prompt; harmful if the chip is rendered after it.
7. **Child-tool guard absent** from the Python candidate and from installed 0.1.9 (unproven). Two empty snapshots without `/proc` children can still race a tool start.
8. **Installed runtime cannot auto-recover.** No error hook, no `message readiness` on 0.1.9, no authority to forge idle. Native protocol patches remain under the human no-Rust-build hold.

Non-interference observed: candidate stays uninstalled; `would_inject` / `would_switch_model` stay false in the policy dataclass; `obs.deployed` forces `hold_uninstalled`.

---

## 9. Relation to prior reports

| Document | What this audit keeps | What this audit does not inherit |
|---|---|---|
| `research/grok/capacity-recovery/FINDINGS.md` | Timer cannot emit idle; uninstalled candidate; capacity ≠ quota; native NOTREADY authoritative. | Model chip `GPT-6.1-Sol medium` for *this* clipboard. |
| `REV-GROK-CAPACITY-RECOVERY.md` (BOUNDED ACCEPTANCE) | quota=None, 512 MiB, ANSI, native-event requirement. 20/20 tests. | Any implication those policy gaps were since closed. They are not. |
| `READINESS-PRODUCER-REPAIR-REPORT.md` | Idle-vs-PTY-redraw is a *different* deadlock (authentic idle contradicted by TUI cursor bursts). Capacity deadlock is missing Stop/error, not redraw. | The unimplemented Layer-1/2/3 patch. Adversarial review already `REQUEST_CHANGES`. |
| `REV-SUPERVISION-FE312C7.md` (ACCEPT) | Fail-closed delivery, no installed-binary fallback overwrite, durable queue. | That fail-closed path currently misclassifies this capacity banner as a menu via `Select`. |

Do not merge the capacity stale-working deadlock with the zcodex idle-contradicted-by-PTY deadlock. One lacks an idle report; the other has an idle report that redraws retract. Fixes are not interchangeable.

---

## 10. Continuation rules this audit will treat as accepted

Until a reviewed engine error event exists, operators and heads should:

1. Classify the banner as provider capacity only with engine-event provenance. Screen text alone is `unproven_screen`.
2. Wait 180s, then 360s, then 720s, at most three times, same conversation fingerprint. Re-sample fresh quota (all required windows) and host floors each attempt. Unknown quota denies.
3. On each attempt: authentic whoami, two empty bottom-composer snapshots, no child tools, native Ready (`reported` idle or waiting). If native says not-ready / reported working: `need_native_error_event`. Do not forge idle.
4. Keep FileBus and aplexer envelopes queued. Ack is not deletion. Deliver uses the existing ID.
5. If still blocked: hand the *work item* to a healthy eligible head. One writer per checkout. Preserve the stuck session for human or same-session TUI retry.
6. Do not install `policy.py`. Do not rebuild aplexer. Do not reload supervision as a capacity fixer.

What would lift the bound to ACCEPT: a Codex (or OpenCode) error/capacity hook that reports `idle` or a typed `error:capacity` *and* independent proof that installed deliver Ready then accepts, plus the quota=None / supervision-Select / composer-glyph fixes, plus a child-process guard that does not resurrect the readiness-producer defects.

What would drop this to REQUEST_CHANGES or REJECT: shipping the timer as a Ready producer, injecting the stuck pane, spoofing `--from`, dropping queued mail, silent model switch, or treating `quota=None` as cleared.

---

## 11. Verdict

**BOUNDED ACCEPTANCE.**

The capacity → missing error hook → stale `working` → native deliver deadlock is real. The 180s receiver-continuation design is safe *as a fail-closed backoff and reroute contract* and is false *as an automatic readiness repair*. Installed 0.1.9 cannot be recovered by userland Python. The offline policy is internally consistent for the cases it tests and still has integration-blocking gaps, including an open quota-unsampled bypass and a live supervisor `Select` false positive on the exact incident string.

No native success is claimed.
