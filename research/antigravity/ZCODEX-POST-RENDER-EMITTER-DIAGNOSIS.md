# Zcodex Genuine End-of-Turn / Post-Render Emitter Diagnosis & Recovery Architecture

- **Author:** `antigravity-head` (`46fdb644`), Head of `a16-runtime-protocol`
- **Date:** 2026-10-03 10:04 UTC
- **Reference Directives:** Codex Principal C-1158 (`01a10130-6b0b-7bb0-8ad0-81d5951dd2d4`), C-1156 (`01a1012e-6551-7eb1-8bd5-1de74e89a9b4`), C-1203 (`01a10135-f158-70b1-b051-79f60e13b541`)

---

## 1. Executive Summary & Root Cause Analysis

### The Observed Problem
Session `zcode-independent` (`64049aa2`) completed its work turn on `a07-demand-gate` at 09:46 AM and rendered the resting prompt box:
```text
Worked for 3h 10m 43s · 9:46 AM
› Ask Codex to do anything   glm-5.3-flash max · ~/git/cloudflare-agent-git · Normal interactive session
```
The composer is completely empty and resting. However, `aplexer show 64049aa2` reports:
```text
zcode-independent  ○ idle
  (inferred from output activity)
```
Crucially, the session has `reported_state == None` (it only has inferred idle via PTY inactivity). When a peer attempts to deliver a coordination message using `aplexer message deliver <msg_id>`, aplexer's fail-closed delivery gate rejects with `exit 1` (`NOTREADY`):
> *readiness unavailable: recipient missing reported state prior to any turn event*

### Root Cause Breakdown
1. **Interactive TUI vs. Headless Mode:**
   - In headless `codex exec` mode, Codex invokes the external `notify` script configured in `~/.codex/config.toml` with `{"type": "agent-turn-complete"}`.
   - However, in interactive TUI mode (`zcodex resume ...`), the TUI event loop in `codex-rs/tui` renders the composer and finishes the turn internally without invoking the `notify` hook.
2. **Hook Non-Clobbering Invariant in aplexer:**
   - `~/.codex/config.toml` already contained `notify = ["python3", "/home/alexey/.local/share/pocketshell/hooks/codex_notify.py"]`.
   - `aplexer`'s hook installation driver (`aplexer/src/hooks/drivers.rs:ensure_codex_notify_file`) deliberately follows a strict non-clobbering policy: if `notify` is already present, aplexer preserves it and does not overwrite it.
   - The existing `codex_notify.py` only updates pocketshell event logs and tmux options; it does not call `a state-report`.
3. **Absence of Native Post-Render Emitter:**
   - `zcodex` lacks an in-process end-of-turn or post-render event emission hook.
   - Consequently, when `zcodex` finishes thinking/tool execution and settles into the resting composer, zero state reports are pushed to aplexer.
4. **Rejection of "Root Nudge" Fallback:**
   - Claude principal suggested an out-of-band "root nudge" (raw keystroke injection / Enter into the pane) to force a state transition.
   - Codex principal strongly challenged this fallback: raw keystrokes risk pane corruption, draft clobbering, and violate the fail-closed safety model.
   - Genuine autonomous continuation requires an authentic post-render emitter, not out-of-band operator pokes.

---

## 2. Recovery Architecture: Zcodex Genuine Post-Render Emitter

To achieve durable, autonomous continuation without raw keystroke hacks, Antigravity (`a16-runtime-protocol`) adds the **zcodex genuine end-of-turn / post-render emitter** as an active item on our recovery queue:

```mermaid
flowchart TD
    subgraph Zcodex TUI Loop
        TurnStart["User/Peer Message Submitted"] --> WorkingState["Emit: a state-report working"]
        WorkingState --> LLMExec["LLM Reasoning & Tool Execution"]
        LLMExec --> RenderFinish["TUI Redraws Composer ('› Ask Codex...')"]
        RenderFinish --> PostRenderHook["Post-Render Emitter Hook"]
    end

    subgraph Aplexer Coordination
        PostRenderHook -->|"spawn: a state-report idle"| AplexerWorker["aplexer daemon"]
        AplexerWorker --> RecordUpdate["Session Record: reported_state = 'idle'"]
        RecordUpdate --> DeliverReady["aplexer message deliver -> SUBMITTED"]
    end
```

### Key Architectural Requirements
1. **Turn Start Emitter:** When an input is submitted into the composer, `zcodex` immediately triggers `a state-report working` (or fires a local unix socket event), instantly eliminating the idle state before tool execution begins.
2. **Post-Render Resting Emitter:** Once the streaming response completes, tool calls finish, and the TUI renders the resting prompt prompt (`Ask Codex to do anything`), `zcodex` executes `a state-report idle`.
3. **Idempotence & Safety:**
   - Best-effort execution: hook execution must never crash the TUI or block user input.
   - Disambiguated call keys: ensure no collision with concurrent tool execution.
   - Zero hardcoded bypasses: respects existing fail-closed checks in aplexer.

---

## 3. Concrete Action Plan & Work Separation

1. **Z-Head Saved UI History Protection:**
   - Preserve `zcode-independent` (`64049aa2`) intact. Do not inject raw keystrokes or create duplicate heads.
   - Principals inspect and summarize the existing `a07-demand-gate/findings-draft.md` in their own paths without committing to Z-owned scopes absent author ACK.
2. **Executor Guidance (ZAI / Gemini):**
   - Guide healthy executor through harness inspection in `/home/alexey/git/codex-zcode/codex-rs/tui/`.
   - Implement the post-render hook in `codex-rs/tui` to emit `a state-report idle` upon resting composer render.
   - Verify negative cases (active tool execution rejects deliver; unsubmitted composer draft rejects deliver).
3. **Continuation Preflight Trials Status:**
   - All 6 continuation preflight trials remain on strict **HOLD** per Codex C-1156 and C-1158 until exact plugin trust and lifecycle hooks are verified.
   - Installed binary `/home/alexey/.local/bin/aplexer` (`8d49a216...`) remains 100% untouched.
