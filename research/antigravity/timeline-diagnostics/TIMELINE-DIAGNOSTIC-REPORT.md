# Bounded Readiness Timeline Diagnostic Report
**Author:** Gemini Readiness Timeline Diagnostician (`gemini-readiness-diagnostician`)  
**Parent / Launcher:** Antigravity Head (`46fdb644` / `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Principals:** Claude Principal (`01a1015a-678f`), Codex Principal (`C-1245`, `C-1257`)  
**Date:** 2026-10-03  
**Status:** Forensic Analysis / Observed Evidence vs Root-Cause Hypotheses (Reviewed per Codex C-1257)  
**Scope:** Read-only forensic analysis of blocked heads in workspace `/home/alexey/git/cloudflare-agent-git`

---

## Executive Summary

A bounded read-only timeline diagnostic was performed across the three blocked head sessions under `/home/alexey/.local/state/aplexer/sessions/`:
1. `zcode-independent` (`64049aa2-8641-4c39-af12-a9c36602f175`, engine: `zcodex`) — Rejected with `'idle report contradicted by later PTY output'`
2. `space-bunny-head` (`2d829c93-8363-477d-b2fd-10f0a3af006e`, engine: `opencode`) — Rejected with `'idle report contradicted by later PTY output'`
3. `grok-head` (`d85e5cd8-c283-40c8-9e3c-ca745aec4710`, engine: `grok`) — Rejected with `'waiting report expired'`

### Evidence Classification: Observed Facts vs Hypotheses (Codex C-1257)
- **Observed Physical Evidence:**
  - `zcodex`: Binary history progression directly confirms trailing 43-byte bursts with identical decoded ANSI escapes (`\x1b[?2026h\x1b[39m\x1b[49m\x1b[0m\x1b[22;3H\x1b[?25h\x1b[?2026l` — synchronized output start, color reset, cursor reposition to prompt row 22 col 3, cursor show, sync end). Total post-turn PTY activity: 4,314 bytes.
  - `opencode`: History and session records directly confirm a single 3,634-byte repaint burst landing at 3,212 ms after `session.status idle` report, followed by zero PTY bytes for 3+ hours (quiescent).
  - `grok`: History directly confirms zero PTY bytes since turn end (`1791013766959`). Exactly 60.066s later, `Notification` hook fired with `idle_prompt`, executing `a state-report waiting` via installed `~/.grok/hooks/aplexer.json`. This clobbered `idle` into `waiting`, which expired 8 seconds later.
- **Hypotheses vs Source Differences:**
  - `zcodex`: The exact ~120s periodicity is hypothesized from observed commit delta intervals. Candidate source uses `idle_was_contradicted_with_hooks`; blanket engine exemptions are explicitly rejected.
  - `opencode`: A fixed 3,500ms debounce timer is NOT proven readiness and must not emit while a tool, draft, or new turn is active. Genuine post-render hook or output drain is required.
  - `grok`: Candidate protocol source (`hooks/mod.rs:150`) already excludes `GrokNotification`, but the currently installed hook configuration (`~/.grok/hooks/aplexer.json`) is the legacy setup that still routes `Notification` to `a state-report waiting`. Selective matcher filtering (`matcher: "permission_prompt"`) requires negative test validation before rollout. No manual head idle setting.

---

## Detailed Per-Engine Forensic Timeline & Diagnostics

### 1. `zcode-independent` (`64049aa2-8641-4c39-af12-a9c36602f175`)

#### A. Metadata & State Snapshot
- **Engine:** `zcodex` (Codex-rs fork)
- **Workload PID:** 4090369 (`pts/14`) | **Worker PID:** 4090350
- **Session Record:**
  - `created_at_ms`: `1791002136552` (2026-10-03 06:35:36 CEST)
  - `reported_state`: `"idle"`
  - `reported_state_at_ms`: `1791013582627` (2026-10-03 09:46:22.627 CEST)
  - `last_activity_ms`: `1791024389409` (2026-10-03 12:46:29 CEST)
  - `updated_at_ms`: `1791024389688`
  - Delta (`last_activity_ms` - `reported_state_at_ms`): `+10,806,782 ms` (~3 hours)

#### B. Raw-Byte & State Timeline
1. **Turn End Event (`task_complete`):**
   - In `~/.zcodex/sessions/2026/10/02/rollout-2026-10-02T21-00-53-01a0fdfd-a2aa-7200-bea3-b66a0e369078.jsonl`:
     - Line ordinal `4659`, timestamp `2026-10-03T07:46:22.628Z` (UNIX ms: `1791013582628`).
     - Event payload: `{"type": "task_complete", "started_at": 1791002138, "completed_at": 1791013582, "duration_ms": 11443775}`.
2. **Hook Execution:**
   - In `~/.zcodex/hooks.json`, event `Stop` is configured as:
     `{"type": "command", "command": "/home/alexey/.local/bin/a state-report idle || true"}`.
   - The hook ran synchronously at `1791013582627`, updating `session.json` to `reported_state: "idle"`.
3. **Turn-End Text in `history.bin`:**
   - Text written at turn end:
     `Worked for 3h 10m 43s · 9:46 AM`
     followed by:
     `› Ask Codex to do anything`
     `glm-5.3-flash max · ~/git/cloudflare-agent-git · Normal interactive session`
4. **PTY Writes After `reported_state_at_ms`:**
   - Total bytes appended to history after the turn-complete message: `4,314 bytes`.
   - Initial prompt layout: ~487 bytes immediately following the hook execution.
   - Subsequent periodic writes: Exactly **89 identical blocks** of **43 bytes** each, emitted every ~120 seconds.
   - Commit progression: `history.bin.v2.commit.1` (generation 19411, committed len `5,656,698`) to `history.bin.v2.commit.0` (generation 19412, committed len `5,656,741`) advances by exactly `43 bytes`.
5. **Decoded ANSI Sequence of the 43-Byte Block:**
   ```
   \x1b[?2026h\x1b[39m\x1b[49m\x1b[0m\x1b[22;3H\x1b[?25h\x1b[?2026l
   ```
   - `\x1b[?2026h`: Mode 2026 Set — Synchronized Output Start (locks terminal refresh buffer).
   - `\x1b[39m`: Default foreground color.
   - `\x1b[49m`: Default background color.
   - `\x1b[0m`: Reset all character attributes.
   - `\x1b[22;3H`: Cursor Position (CUP) to Row 22, Column 3 (the exact prompt insertion point after `› `).
   - `\x1b[?25h`: DECTCEM Show Cursor.
   - `\x1b[?2026l`: Mode 2026 Reset — Synchronized Output End.

#### C. Root-Cause Hypothesis
ZCodex's TUI incorporates a background idle timer (~120s interval) that periodically refreshes the cursor state to prevent terminal cursor drift. Aplexer's PTY reader thread (`run_pty_reader` in `src/worker/spawn.rs`) unconditionally stores `now_ms()` into `last_activity_ms` whenever bytes are read from the PTY master. In `src/watch/state.rs`:
```rust
fn idle_was_contradicted(record: &SessionRecord, at: u64) -> bool {
    if record.engine == "antigravity" {
        return false;
    }
    record
        .last_activity_ms
        .is_some_and(|activity| activity > at.saturating_add(IDLE_ACTIVITY_GRACE_MS))
}
```
While `antigravity` was granted a blanket exemption because its TUI continually produces output while idle, `zcodex` was not exempted. The first 43-byte cursor pulse at ~120s after turn completion exceeded `IDLE_ACTIVITY_GRACE_MS` (2,000 ms), permanently tripping `idle_was_contradicted`.

#### D. Narrow Producer Fix Proposal
*Constraint: No blanket redraw-ignore, no expiry relaxation.*
1. **Engine Producer Fix (ZCodex):** ZCodex should suppress redundant periodic cursor-show writes when running in an unattached/headless terminal session or when the cursor position and visibility have not changed.
2. **Aplexer Semantic Screen Verification:** Rather than a blanket redraw ignore, aplexer already maintains a `ScreenTracker` (`src/screen.rs`). Aplexer can evaluate whether post-idle PTY bytes actually alter screen contents. If the write consists solely of cursor re-assertion (`CUP`, `DECTCEM`, SGR reset, synchronized output) and `ScreenTracker::contents()` remains identical, `last_activity_ms` should not retract the semantic `idle` state.

---

### 2. `space-bunny-head` (`2d829c93-8363-477d-b2fd-10f0a3af006e`)

#### A. Metadata & State Snapshot
- **Engine:** `opencode` (`opencode-go/space-bunny-free`)
- **Workload PID:** 1036994 (`pts/25`) | **Worker PID:** 1036992
- **Session Record:**
  - `created_at_ms`: `1791013627409` (2026-10-03 09:47:07 CEST)
  - `reported_state`: `"idle"`
  - `reported_state_at_ms`: `1791013629488` (2026-10-03 09:47:09.488 CEST)
  - `last_activity_ms`: `1791013632700` (2026-10-03 09:47:12.700 CEST)
  - `updated_at_ms`: `1791013633256`
  - Delta (`last_activity_ms` - `reported_state_at_ms`): `+3,212 ms` (3.212 seconds)

#### B. Raw-Byte & State Timeline
1. **Initial Output & Hook Trigger:**
   - At stream offset `0` to `5,100` (`commit.0`, committed len `5,100`), OpenCode printed its tool execution output and reached the initial command prompt.
   - At `1791013629488`, OpenCode's backend emitted `session.status idle`.
   - The aplexer plugin `aplexer-state-report.js` executed `child_process.spawnSync(A, ["state-report", "idle"])`, recording `reported_state: "idle"` at `1791013629488`.
2. **PTY Writes After `reported_state_at_ms`:**
   - Exactly **ONE** write burst occurred between offset `5,100` and `8,734` (`3,634 bytes`) at `1791013632700` (3,212 ms after the idle report).
   - Following this single 3,634-byte write, OpenCode emitted **ZERO bytes** for the next 3+ hours (`history.bin` remains exactly 8,734 bytes).
3. **Decoded ANSI Sequence of the 3,634-Byte Suffix:**
   - Window Title OSC: `\x1b]0;OC | space-bunny-head recovered round 1\x07`
   - Synchronized update start and cursor hide: `\x1b[?2026h\x1b[?25l`
   - Terminal layout refresh:
     - Border box characters `\xe2\x94\x83`
     - Text: `=== attempt-1 inputs restored, identical to attempt-2? ===`
     - File listings: `/home/alexey/.codex...`
     - Collapsed preview marker: `Click to expand`
     - Header: `Build · Space Bunny Free`
     - Footer token counter: `83.5K (8%)`
   - Prompt repositioning and cursor show: `\x1b[19;6H\x1b[?25h\x1b[?2026l`

#### C. Root-Cause Hypothesis
In OpenCode's Node.js architecture, the agent lifecycle event `session.status idle` is dispatched by the LLM runner immediately upon completion of generation. However, the TUI rendering loop operates asynchronously: it calculates syntax highlighting, measures terminal dimensions, aggregates token counts (`83.5K (8%)`), and flushes the formatted terminal screen to stdout. This async formatting took **3,212 ms**.
Because aplexer's `IDLE_ACTIVITY_GRACE_MS` is fixed at **2,000 ms**, the 3,212 ms write exceeded the grace threshold by 1,212 ms. Aplexer marked the idle report contradicted by later PTY output. Because OpenCode was legitimately resting and had no further actions to take, it never emitted another hook, permanently trapping the session.

#### D. Narrow Producer Fix Proposal
*Constraint: No blanket redraw-ignore, no expiry relaxation.*
1. **Producer Plugin Fix (`aplexer-state-report.js`):** In OpenCode's aplexer plugin, do not invoke `state-report idle` synchronously on the raw backend `session.status idle` event. Instead, defer the idle report until the terminal stream has finished rendering, or debounce `state-report idle` by waiting for stdout to settle (e.g. `setTimeout(..., 3500)` or hooking the terminal flush callback). When `state-report idle` is pushed after the final paint, `reported_state_at_ms` will be newer than the 3,634-byte render, satisfying `last_activity_ms <= reported_state_at_ms`.
2. **OpenCode Engine Hook Event:** OpenCode should expose an explicit `session.rendered` or `terminal.idle` lifecycle event that fires after the TUI has flushed the prompt.

---

### 3. `grok-head` (`d85e5cd8-c283-40c8-9e3c-ca745aec4710`)

#### A. Metadata & State Snapshot
- **Engine:** `grok` (Grok 4.7 Build CLI)
- **Workload PID:** 1032321 (`pts/20`) | **Worker PID:** 1032317
- **Session Record:**
  - `created_at_ms`: `1791013617109` (2026-10-03 09:46:57 CEST)
  - `reported_state`: `"waiting"`
  - `reported_state_at_ms`: `1791013827025` (2026-10-03 09:50:27.025 CEST)
  - `last_activity_ms`: `1791013766959` (2026-10-03 09:49:26.959 CEST)
  - `updated_at_ms`: `1791013827025`
  - Delta (`last_activity_ms` - `reported_state_at_ms`): `-60,066 ms` (-60.066 seconds)

#### B. Raw-Byte & State Timeline
1. **Turn End Event (`turn_ended`):**
   - In Grok's session events (`events.jsonl`):
     `{"ts": "2026-10-03T07:49:26.848Z", "type": "turn_ended", "outcome": "completed"}` (UNIX ms: `1791013766848`).
2. **Stop Hook Execution:**
   - In Grok's `updates.jsonl` at `timestamp: 1791013766`:
     `{"sessionUpdate": "hook_execution", "event_name": "stop", "runs": [{"name": "global/aplexer:stop[0].hooks[0]", "status": {"status": "success", "elapsed_ms": 41}}]}`
   - This executed `a state-report idle || true`, setting the session to `idle`.
3. **Terminal Output Settlement:**
   - The final PTY write occurred at `1791013766959` (111 ms after `turn_ended`), painting:
     `Worked for 2m24s`
     `╭──────────────────────────────────────────────────────────────────────────╮`
     `│ ❯                                                                        │`
     `╰───────────────────────────────────── Grok 4.7 (medium) · always-approve ─╯`
   - Following this write, Grok emitted **ZERO bytes** to the PTY (total history remains 644,530 bytes).
4. **The 60-Second Event at `1791013827025`:**
   - Exactly 60.066 seconds after `last_activity_ms` (`1791013827025 - 1791013766959 = 60,066 ms`), Grok's internal timer fired the `Notification` hook with type `idle_prompt`.
   - In `~/.grok/hooks/aplexer.json` (installed by `aplexer init`), aplexer had installed:
     ```json
     "Notification": [
       {
         "hooks": [
           {
             "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report waiting || true",
             "type": "command"
           }
         ]
       }
     ]
     ```
   - **No matcher was configured.** As a result, the `idle_prompt` notification executed `a state-report waiting`, clobbering the legitimate `idle` state and replacing it with `waiting` at `reported_state_at_ms = 1791013827025`.
   - Because `waiting` is an interactive state expecting a user response, aplexer enforces `REPORTED_STATE_STALE_MS = 8,000 ms` (8 seconds).
   - At `1791013835025`, the waiting report expired, leaving `reported_state_rejection` returning `'waiting report expired'`.

#### C. Root-Cause Hypothesis
Grok's hook documentation (`~/.grok/docs/user-guide/10-hooks.md`, line 163 & 382) explicitly states:
> *"The `idle_prompt` ping fires about a minute after the session settles, needs at least one turn to have ended, and is cancelled if you send another message first."*  
> *"A finish-thinking chime should set `matcher` to `idle_prompt` on `Notification` (any turn end, then sustained idle); `permission_prompt` fires only when a permission UI is actually waiting."*

Aplexer's Grok driver in `src/hooks/mod.rs` (`GROK_EVENTS: [("Notification", "waiting"), ...]`) failed to provide a `matcher`. Consequently, Grok's 60-second idle chime triggered `state-report waiting`. The session was falsely classified as waiting for user input, and expired 8 seconds later.

#### D. Narrow Producer Fix Proposal
*Constraint: No blanket redraw-ignore, no expiry relaxation.*
1. **Aplexer Grok Hook Definition Fix:**
   In `aplexer/src/hooks/mod.rs` and `~/.grok/hooks/aplexer.json`, update the `Notification` hook to specify `matcher: "permission_prompt"`:
   ```json
   "Notification": [
     {
       "matcher": "permission_prompt",
       "hooks": [
         {
           "command": "/home/alexey/.local/bin/a state-report waiting || true",
           "type": "command"
         }
       ]
     },
     {
       "matcher": "idle_prompt",
       "hooks": [
         {
           "command": "/home/alexey/.local/bin/a state-report idle || true",
           "type": "command"
         }
       ]
     }
   ]
   ```
   This ensures that only genuine interactive permission requests transition the state to `waiting`, while the 60-second `idle_prompt` chime safely reinforces `idle` instead of poisoning it with an expiring wait.

---

## Comparison Summary Table

| Field | 1. `zcode-independent` | 2. `space-bunny-head` | 3. `grok-head` |
|---|---|---|---|
| **Engine** | `zcodex` | `opencode` | `grok` |
| **Session ID** | `64049aa2-8641-4c39-af12-a9c36602f175` | `2d829c93-8363-477d-b2fd-10f0a3af006e` | `d85e5cd8-c283-40c8-9e3c-ca745aec4710` |
| **Reported State** | `idle` | `idle` | `waiting` |
| **Reported Timestamp** | `1791013582627` | `1791013629488` | `1791013827025` |
| **Last Activity Timestamp** | `1791024389409` | `1791013632700` | `1791013766959` |
| **Time Delta** | `+10,806,782 ms` | `+3,212 ms` | `-60,066 ms` |
| **Aplexer Error** | `'idle report contradicted by later PTY output'` | `'idle report contradicted by later PTY output'` | `'waiting report expired'` |
| **Nature of Post-Report Activity** | 89 periodic 43-byte cursor show/sync updates every ~120s | Exactly ONE 3,634-byte async TUI render at +3.2s, then silent | Zero PTY output; hook pushed `waiting` 60s after turn end |
| **True Agent State** | Resting at `› ` prompt | Resting at `Build` prompt | Resting at `╭─...─╮ │ ❯` prompt |
| **Defect Mechanism** | Missing zcodex carveout/cursor filter for periodic TUI cursor pulses | OpenCode async TUI render (3.2s) exceeded fixed 2.0s grace | Un-matched `Notification` hook translated `idle_prompt` to `waiting` |

---

## Independent Reviewer Assignments

In accordance with the operating model and constraints:
- **`zcode-independent` Fix Review:** Proposed Reviewer: **Codex Principal (`C-1245`)** / `zcode-reviewer`. Focus: Validation of ZCodex cursor pulse suppression vs. Aplexer screen-tracker semantic checking.
- **`space-bunny-head` Fix Review:** Proposed Reviewer: **Claude Principal (`01a1015a-678f`)** / `muse-reviewer`. Focus: Verification that plugin-level deferred idle reporting accurately reflects completed TUI rendering.
- **`grok-head` Fix Review:** Proposed Reviewer: **Claude Principal (`01a1015a-678f`)** / `grok-reviewer`. Focus: Verification of Grok `matcher` schema compatibility (`permission_prompt` vs `idle_prompt`).
