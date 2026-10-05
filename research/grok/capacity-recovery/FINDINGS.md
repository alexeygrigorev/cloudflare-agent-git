# Capacity recovery findings (incremental)

As-of: 2026-10-04. Author: grok-capacity-recovery `08fee82b-651a-4f7f-b308-0383b9534e14`.
Scope: diagnosis plus **offline dry-run candidate only**. Candidate is **uninstalled**. No live pane retry, no aplexer checkout edit, no service reload.

This file is sanitized: no private screens, transcripts, or tokens.

## Identity / launch

- Native `aplexer whoami --json` (no `--from`, no `APLEXER_*` overrides): tag `grok-capacity-recovery`, workspace `/home/alexey/git/cloudflare-agent-git`, engine `grok`, parent `93cf28f2`.
- Launch: `.local/codex-capacity-recovery/run-grok.sh` → `grok --cwd … -m grok-4.6 --effort medium --permission-mode auto`.
- Installed Grok CLI: `/home/alexey/.local/bin/grok` → `/home/alexey/.grok/bin/grok`, version `grok 1.0.46 (2765805b9442) [stable]`.
- Fresh `quse grok --json`: weekly remaining **74%** (`used_percent` 26.0, `limit_reached` false). Distinct from Codex provider capacity.

## Observed incident (human/root, not this executor's screen)

Root messages `01a1061d-d9cf-79b1-a6f9-b8beafff8c03` and `01a10639-418c-7960-9db2-d4b28f1a2c70` (desktop-orchestrator → codex-principal):

- Live Codex principal TUI ended with exact phrase: `Selected model is at capacity. Please try a different model.`
- Then empty default composer `Ask Codex to do anything`; selected model reported as GPT-6.1-Sol medium.
- Historical `Select` / `Esc-to-cancel` matches came from **quoted peer captures**, not a live menu. Supervisor `menu-or-draft` is a heuristic, not proof.
- Native `reported_state` stayed `working` after the capacity failure. Same conversation was later recovered by **direct human input** (principal recovered; this task is not a second principal).

Installed Codex CLI: `codex-cli 0.160.0` (`/home/alexey/.nvm/versions/node/v24.13.1/bin/codex` → `@openai/codex` 0.160.0). Exact UTF-8 phrase was **not** found in that package's JS tree in a bounded scan; native/Rust asset origin remains **unknown**. Do not invent an upstream URL for the string.

## Capacity vs other blockers

| Class | What it is | Recovery implication |
|---|---|---|
| Provider/model **capacity** | Exact live TUI: `Selected model is at capacity. Please try a different model.` | Temporary fleet saturation. Same-conversation retry may be valid **after** 180s **and** native ready + empty composer twice. Never silent model switch. |
| Account **quota** | `quse` windows, `limit_reached`, Codex ≤15% remaining / unknown | Fail closed. Distinct from capacity. Fresh check required. |
| Model/account unknown | Missing windows / error status | Fail closed (`quota-unknown`). |
| **Transport** | mailbox busy, RPC/send failure, `delivery-uncertain` | One mutating call; do not invent a new envelope. |
| **Completed idle** | authentic `state-report idle` after Stop/AfterAgent | Required for native deliver Ready. |
| **Tool-running / busy** | `Working (` / `esc to interrupt` on **live** screen, or derived `running` | Do not inject. |
| **Human draft** | composer text after `›`/`❯` other than empty placeholder | Never submit. |
| Historical **quoted** error/menu | phrase only in transcript/history, not bottom live render | Do not treat as live capacity or live menu. |

## Installed aplexer vs source checkouts (READ ONLY)

Do **not** treat dirty `~/git/aplexer` as the installed binary.

| Artifact | Pin | Notes |
|---|---|---|
| Installed CLI | `/home/alexey/.local/bin/aplexer`, `--version` **a 0.1.9**, mtime 2026-10-02 22:53 +0200, sha256 `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` | Has `message deliver`. **No** `message readiness` subcommand (`unrecognized subcommand 'readiness'`). `message hook-notice` exists for engines `claude` and `codex` only. |
| Dirty checkout | `/home/alexey/git/aplexer` HEAD `bc0d3d75ab00e87b8357e91e0d7297bd67c6e101`, branch `main` ahead 4, **dirty** `src/watch.rs` and `src/watch/state.rs` | Origin remote `git@github.com:PocketShell-io/aplexer.git`. Uncommitted; not claimed equal to 0.1.9. |
| Protocol worktree (supervision + grok hooks) | `/home/alexey/git/cloudflare-aplexer-protocol` HEAD `7efa49386d756575f1003825b050643688fa3fc5` on `fix/prompt-ready-lifecycle`; debug binary mtime 2026-10-03 11:03 | Same origin remote. **Not installed globally.** |
| Supervision service binary | `scripts/supervision/service.py` line 9: `SUPERVISION_APLEXER_BINARY` default `/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer` | Uses protocol debug, not `~/.local/bin/aplexer`. |

Verified public origin of those checkouts: https://github.com/PocketShell-io/aplexer (from local `git remote`). Unpublished SHAs above are **local**. Do not claim they are the published 0.1.9 release.

## Hooks / events (installed files + source tables)

Installed `aplexer init --check --json`: `initialized: false` overall. Codex/Grok/Antigravity/OpenCode hooks **present**; Claude/Gemini **absent**.

Codex (`/home/alexey/.codex/hooks.json`):

- `UserPromptSubmit` / `SessionStart` → `/home/alexey/.local/bin/a state-report working || true`
- `Stop` → `/home/alexey/.local/bin/a state-report idle || true`
- awareness: protocol debug `context hook --engine codex` on PostToolUse/SessionStart/UserPromptSubmit

Grok (`/home/alexey/.grok/hooks/aplexer.json`):

- `SessionStart` / `UserPromptSubmit` → protocol debug `state-report working`
- `Stop` → protocol debug `state-report idle`
- `Notification` → `waiting`
- `PostToolUse` → awareness only (`context hook --engine grok`)

Source event tables (`/home/alexey/git/aplexer/src/hooks/mod.rs`):

- `CODEX_EVENTS` lines 139–146: Stop→idle, UserPromptSubmit→working, SessionStart→working, plus awareness on SessionStart/UserPromptSubmit/PostToolUse. **No Notification→waiting for Codex.**
- `GROK_EVENTS` lines 150–156: Stop→idle, Notification→waiting, UserPromptSubmit→working, SessionStart→working, PostToolUse awareness.
- `SubagentStop` deliberately **absent** (lines 123–128): mapping it to idle would lie mid-turn.

`a state-report` vocabulary (installed help): `idle` / `waiting` / `working`.

### Stop vs capacity (unknown vs observed)

**Observed:** after actual capacity, Codex principal `reported_state` remained `working` (root 01a1061d; this executor later saw 93cf `reported_state=working` with `state=running` while the principal was again producing work).

**Unknown:** whether installed Codex 0.160.0 fires `Stop` on that error, fires it and the hook fails, or never leaves the turn. There is **no** engine error-event hook in `CODEX_EVENTS`. Absence of a Stop mapping for capacity is **not** a trace that Stop never runs.

A 180s timer does **not** emit `state-report idle`.

## Why stale `working` blocks native delivery

Protocol `evaluate_readiness_verdict` (`cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs` 73–128):

1. Draft / unknown composer → Reject (fail closed).
2. Derived `running` (reported **or** heuristic) → Reject. `readiness_reason` line 401–402: if `state==running` and `source==reported` → `"recipient reported working"`.
3. Ready **only** if `source=="reported"` **and** state is `waiting` or `idle` (lines 121–123).
4. Expired waiting + empty composer does **not** prove a completed turn (comment lines 126–128). Fail closed.

Watch merge (`aplexer/src/watch/state.rs`):

- `REPORTED_STATE_STALE_MS = 8_000` (line 57). Fresh `working`/`waiting` wins; after 8s without refresh, report is rejected (`working report expired`, lines 110–116) and the PTY heuristic runs.
- `idle` has **no** clock TTL; only later PTY activity beyond `IDLE_ACTIVITY_GRACE_MS = 2_000` retracts it (except Antigravity idle redraw exemption, lines 123–127).

So: empty composer after capacity **plus** an 8s-expired working report still **fails** deliver, because Ready requires a **fresh idle/waiting report**. A timer cannot manufacture that. **Need a reviewed engine-native error event and/or readiness fix**, not pretend this candidate repairs installed runtime.

Installed 0.1.9 deliver exists; whether its Ready predicate equals protocol `7efa493` is **unproven**. Fail closed: treat native NOTREADY as authoritative.

Supervision (`scripts/supervision/service.py`):

- `composer()` lines 143–162: docstring says "Last prompt"; **line 156 scans the whole `screen`** with `Choose|Select|feedback`. Exact live `Selected model is at capacity` matches `Select` → `menu-or-draft`. Historical quoted `Select` also matches.
- `eligible()` 190–201: requires `reported_state in ('idle','waiting')` else `not-reported-ready`. Quota only sampled when already idle/waiting (320–321).
- Delivery 374–378: two ready snapshots + a third empty-composer check, then native `message deliver`. Sender must be original (`only sender or recipient may deliver` is native `authorize_delivery` lines 13–34).

## Same-conversation retry vs NOTREADY

**Supported (engine TUI, human or same bound session):** resubmit in the existing Codex conversation after capacity clears. Principal 93cf was recovered that way. This executor must **not** inject that.

**Supported (aplexer, installed 0.1.9):** `message send` (inbox), `deliver` of an **existing** ID after Ready, `reply`, `ack`. `deliver` never creates a second envelope.

**Blocked:** `deliver` while reported working / derived running / draft / unknown composer / stale inferred idle. Status JSON `not-ready`. Do not bypass.

**Absent on installed 0.1.9:** `message readiness` query verb (skill documents it; this binary rejects the subcommand).

**Not found:** a native "retry last prompt" CLI. Silent model switch is forbidden.

**Continuity while blocked:** route owned work through **healthy heads** (Antigravity owns integration). Do not spawn another principal.

## Agent label vs engine (this session)

`aplexer status` / `aplexer agent --json` for 08fee82b: `engine=grok`, `agent=antigravity`, `source=detection` (no pin override). Detection walks `/proc` (`src/agent_kind/detect.rs`); Antigravity token `agy` is first in `TOKEN_RULES` (`src/agent_kind/rules.rs` 49–54). **Do not infer a different model from that label.** Recorded engine and launch argv (`-m grok-4.6`) are the model source.

## Candidate (dry-run, uninstalled)

Python policy in this directory:

- Classify **bottom-window** live capacity vs **quoted history**.
- First retry wait **180s**, cap 3, exponential backoff 180/360/720, durable dedup by `(session_id, error_fp, conversation_id)`.
- Fresh quota: **all required windows** (weekly+5h); missing/unknown window fail-closed. Codex min remaining 15%.
- Resource floors are **per operation**: OPERATING-MODEL **new_worker ≥50GiB** root; this task's authorized **recovery_scratch ≥8GiB**. 8GiB is not a worker-launch floor. MemAvailable ≥10GiB both.
- Capacity retry requires `capacity_provenance=engine_event`. Bottom-window phrase alone is `unproven_screen`.
- Require two independent empty **bottom** composer snapshots **and** native Ready.
- If native rejects stale working: action `need_native_error_event`, not a fake idle.
- Never: bypass NOTREADY, forge idle, submit drafts, inject busy/unknown, silent model switch, duplicate principals, borrow another sender's message, label tests as native success.

## Repeated-operation ledger (native-feature candidates)

These are **proposals**, not implemented services. Aplexer vs engine-hook vs task scheduling stay separate.

| Repeated steps | Proposed native primitive | Safety contract | Saved work |
|---|---|---|---|
| `whoami` then compare id/tag/workspace | identity attestation already exists; keep no-override | reject `--from` / env spoof | every handoff |
| `status` + two empty bottom captures | `message readiness` **query** (absent on 0.1.9) | read-only; capture ≠ state refresh | supervisor + deliver callers |
| `deliver` vs NOTREADY | typed error event: `capacity` / `quota` / `stale-working` | never coerce Ready | avoid 180s loops that still fail |
| mailbox ack vs peer action vs output | keep three-state model (recorded / acked / agreed) | ack ≠ agreement | already in skill |
| bounded retry/watch | engine Stop **or error** → `state-report` | no forged idle | stale working after capacity |
| whole-screen `Select` heuristic | last-prompt / bottom-window classifier | historical quotes ignored | false menu-or-draft |

Aplexer owns identity, mailbox, deliver/NOTREADY, state-report merge. Engine adapters own Stop/error/tool events. Project TASKS scheduling stays with heads. **No rival supervisor.**

## Tests

`python3 -m unittest discover -s research/grok/capacity-recovery -v` (std library only). Offline fixtures. **Not** native success.

Result 2026-10-04: **20 tests OK** after principal REQUEST_CHANGES (`01a106b9-c6f7`). Added: unprefixed bottom phrase → unproven provenance, multiline/error-text draft, historical transport ignored, multi-window quota fail-closed, 50GiB new-worker vs 8GiB scratch floors. No test labelled native success.

Principal review `01a106b9-c6f7` addressed in policy; Ant independent review still requested (`01a106b9-7374`). Candidate remains uninstalled.

## Non-goals / holds

No Rust/cargo, no dirty aplexer edit/reset/rebuild/install, no global install, no service reload, no live injection, no TASKS.json edits, no competing service. Ant owns eventual integration. Preserve Agent Branches / Agent Dashboard / Quota-aware Launcher and extractor `40dd`.
