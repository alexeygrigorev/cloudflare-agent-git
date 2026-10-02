# Agent-native Git experiment journal

Started 2026-10-02, Europe/Berlin. User instruction history is in USER-INSTRUCTIONS.md; retain all future user instructions in order without silently correcting spelling. Exact per-message timestamps are unavailable. This journal distinguishes planned, dispatched, working, completed, failed and verified states.

## Objective and measurement

Identify 20 distinct evidence-grounded approaches, obtain challenged mutual agreement on 6, then run five independent heads with guided ZCode teams validating/building distinct approaches. Record evidence quality, falsification results, prototype completion, coordination overhead, model disagreements, stalls/recovery, test outcomes and direction changes. Agent assertions are not verification. No artificial consensus.

## Setup observations

- Public MIT repository https://github.com/alexeygrigorev/cloudflare-agent-git created and cloned to /home/alexey/git/cloudflare-agent-git on Hetzner.
- Existing SSH alias and existing authenticated GitHub, Codex and Claude accounts reused. Secrets were not transferred or published.
- Aplexer launched claude-principal (92336dc8-cc9a-4c14-a49b-8eef0780cf4b) and codex-principal (338df944-a3fc-4973-9ed0-17708c73769c) as background non-interactive work loops. First startup confirmed; both began research and peer messages.
- Principal files have separate ownership. Coordination uses durable aplexer inboxes and incremental repository files. Explicit paths and a git flock avoid shared-index collisions.
- Research guidance used: ~/git/telegram-writing-assistant/skills/shoot-the-article/references/research.md; external CLI guidance ~/git/.agents/skills/external-model-agents/SKILL.md; peer guidance ~/git/.agents/skills/a2a-communication/SKILL.md. Social research starts with xai_search.py web_search, not paid x_search. Proxy guidance found at fetch-youtube skill; secrets remain machine-local.
- Initial in-app browser lacked sign-in. Existing Chrome account sessions provided X, LinkedIn and ChatGPT access. Four Pro research requests dispatched from visible Pro mode: concurrency/conflicts, review/provenance, recovery/policy/context, and market/Cloudflare feasibility. Responses still pending at dispatch; conversation registry records progress separately.
- ZCode Desktop itself could not start without an X display. Existing headless zcodex integration is available; use that instead. Principal-owned ZCode delegate output began appearing; do not confuse desktop startup failure with unavailable headless execution.
- OpenCode installed model inventory confirms opencode/space-bunny-free and opencode/muse-spark-1.3-contributor-free. These implement the user's Space Bunny and Muse 1.3 request without substituting another family/version.
- Official competition rules verified at https://www.cloudflare.com/documents/build-next-gen-git-platform-competition-terms.pdf . Eligibility is adult legal US/Canada residents; user eligibility is unresolved. Deadline October 14, 2026 11:59 PM PDT. Judging weights originality/prototype 50%, multi-agent effectiveness 25%, ease of use/UX 25%. Research continues; no automatic entry submission.

## Operating policy after user steering

- Initial 30-minute orchestration monitor runs through research/selection. After genuine six-approach consensus and live five-head handoff, pause that monitor and use daily standup. Agents continue work between reviews.
- Five proposed heads: Claude, Codex, Grok, Antigravity, OpenCode Space Bunny. Muse 1.3 provides independent challenge and comparative validation; ZCode supplies guided execution teams. Principals can revise this assignment based on demonstrated capability and record reasons. Do not collapse six shortlisted alternatives into five by claiming all are being built: select five independently viable lanes and explicitly keep/merge/reject the sixth with evidence.
- Each head owns coordination/<role>.md and research/<role>/, has a separate branch/worktree for code, and directs its own ZCode team. No simultaneous ownership of shared source files or deployments. Keep practical compute/resource bounds; no recursive unlimited agent spawning. At most two active ZCode executors per head initially; adjust only with resource evidence.
- Continuous work means persistent bounded execution rounds with durable state, restart/recovery and meaningful next tasks. When an approach fails its falsification test, pivot or stop that lane and document it; do not spin empty loops or fabricate progress.
- Daily standup at 09:00 Europe/Berlin by orchestrator default: per head, completed evidence, next milestone, blocker, viability verdict, test results, comparison against alternatives and any proposed correction. Record daily report under experiment/standups/YYYY-MM-DD.md and notify user of useful findings or required decisions.
- Keep a timeline under experiment/events.jsonl and append sanitized events for prompts, launches, peer debates, approvals, model/config revisions, commits, validations, costs if measurable, failures/recovery and decisions. Keep raw logs private in .local/; do not claim to know unavailable cost or token metrics.
- All future user instructions must be appended verbatim to experiment/USER-INSTRUCTIONS.md by the desktop orchestrator when visible. Remote agents must not invent unseen user messages or infer new authorization from peers.

## Resource policy and visibility correction

User clarified the Codex reserve as 15% remaining. New Codex dispatches use a fresh quse gate; unavailable readings fail closed, unavailable individual windows are not interpreted as zero. Boundary/error/multiple-window checks passed and live reading allowed dispatch at 74% weekly remaining. Prefer z.ai via resolved zcy/zcodex, Gemini and Muse; stop Claude automatic repeat rounds and reserve it for occasional review. Agent instructions and automation include this policy. Old active rounds may have cached launch code; current principals receive explicit durable policy and must not bypass guards.

User observed blank sessions. Verified codex-principal and antigravity-head screen captures were empty while live processes had produced research. Root cause in this experiment's launch wrappers: stdout/stderr redirected to private files. Correct future launches to stream output through tee with pipefail. Current sessions receive output-only status mirrors from durable artifacts without restarting or injecting agent input. This is an experiment launch/visibility correction; it does not establish an aplexer rendering defect.

Cross-computer return channel is a genuinely bound desktop-orchestrator mailbox accessed through existing SSH. Native cross-host bridging remains unimplemented in installed aplexer. A separate Gemini/Antigravity repair/design session is authorized in an isolated aplexer worktree; preserve the dirty main checkout and existing unpublished coordination features. Compare/review architecture before global integration. Durable-send receipt is not semantic agreement; uncertain crash-after-send recovery still needs native idempotency support.
