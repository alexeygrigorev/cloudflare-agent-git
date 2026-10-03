# Change-Story Card: Startup Pane Race Verification, Prompt Draft Safety, and Continuation Queue

## Intent
Eliminate false-positive pane message delivery by verifying PTY submission against screen echo or correlated working-state transitions, protect unsubmitted user drafts across interactive TUIs (OpenCode, Grok, Codex, Shell) by failing closed on unsubmitted input or unknown captures, and provide finite durable continuation queue delivery for unacknowledged inbox tasks.

## Risk Tier
Tier 1 — Core messaging delivery and state-machine transport. Regressions risk clobbering active user prompts, dropping unacknowledged agent tasks, or false-confirming delivered bytes into unready PTY terminals.

## Evidence Links
- Target Repository: `/home/alexey/git/cloudflare-aplexer-protocol`
- Branch: `fix/continuation-readiness-pane-race`
- Commit Chain:
  - `422ab1f` (initial pane verification loop, deferred prompt check, `--next` continuation queue)
  - `7a0907d` (structural draft parser, fail-closed capture error handling, workspace-scoped continuation delivery)
  - `7a9b46d` (tri-state `PromptState` classification: `Empty`, `Draft`, and fail-closed `Unknown`; exact OpenCode `╹▀`/`┃`, Grok `╰─`/`│ ❯`, Codex prompt/footer matching)
- Test Suites:
  - Unit tests: `cargo test --bin aplexer` (212 passed in 6.07s)
  - Integration tests: `cargo test --test messaging_deferred` (31 passed in 3.84s)
- Physical Growth Guard: Net zero target growth (compaction from 4.526 GiB to 4.523 GiB; well under 512 MiB ceiling).
- Real TUI Fixtures: Captured live screens from running sessions `muse-reviewer` (OpenCode), `grok-head` (Grok), and `zcode-independent` (Codex/GLM) verified against `classify_composer_prompt`.

## Decision Summary
1. **Startup Pane Race Verification (`verify_pane_delivery`)**:
   - `rpc_send_submitted` writes bracketed-paste bytes to the recipient's PTY.
   - `verify_pane_delivery` polls the screen capture and live session status over a configurable window (default 3.0s, tested down to 150ms).
   - Delivery is confirmed only if the message UUID/needle is observed on screen or in PTY history, or if a correlated transition from non-working to working occurs (`pre_state != "working"`).
   - If verification times out without confirmation, it fails closed to `SubmissionStatus::DeliveryUncertain` and preserves the `.attempt` reservation so that the message remains safe in inbox and is never freely re-injected.

2. **Tri-State Prompt Classification (`PromptState`)**:
   - Instead of binary draft heuristics, screen captures are classified into `PromptState::Empty`, `PromptState::Draft(String)`, or `PromptState::Unknown(String)`.
   - `Empty`: Positively identified idle prompt with no unsubmitted draft (e.g. OpenCode `╹▀` border with empty/build indicator, Grok `│ ❯ │` with empty input, Codex `› ` / `› Ask Codex to do anything` with clean footer, Shell prompt `$ ` with no command).
   - `Draft`: Unsubmitted user input detected within active composer borders or prompt lines. Bails fail-closed with `SubmissionStatus::NotReady` to preserve user/agent WIP.
   - `Unknown`: Screen captures that fail, are empty, or do not match a positively recognized engine prompt structure bail fail-closed with `SubmissionStatus::NotReady`.

3. **Continuation Queue Delivery (`aplexer message deliver --next`)**:
   - Calling sessions can invoke `aplexer message deliver --next` (or deliver without `message_id`) to automatically claim and deliver the oldest queued, unattempted inbox message addressed to them in the target workspace.
