# Worklog — zc-bus-design (proto/aplexer-bus)

Executor for claude-principal (session `zc-bus-design` / `33f4ef2b`, parent session `b3a92dd0`).
Task: cross-machine conversation — "aplexer global bus" design + prototype (Worker+DO, bridge, demo).

## Identity

- `a whoami --json`: tag `zc-bus-design`, engine `shell`, id `33f4ef2b-9404-4ebe-8576-779c5385fcd7`,
  workspace `/home/alexey/git/cloudflare-agent-git`, parent `b3a92dd0` (claude-principal).
- Edit scope declared: `a work join /home/alexey/git/aplexer-bus --mode edit --paths bus/**`.
- Inbox checked: empty at start.

## Context read

- `scripts/orchestrator-channel-v2.py` (laptop↔desktop SSH file-drop bridge): outbox `*.json`
  with token receipts, inbox dump, ack file; identity asserted (`desktop-orchestrator`), patched
  aplexer binary used only for `--idempotency-key`.
- aplexer CLI surface: `message send/reply/inbox/wait/log/show/ack/gc --json`; tags are
  workspace-local; no `--from` (identity is session-bound) — cross-machine must not fake it.

## Plan

1. `bus/DESIGN.md` — envelope, identity, delivery semantics, security, failure modes, 3-option comparison.
2. `bus/worker/` — Worker + ChannelDO (POST /v1/messages, GET long-poll, POST /v1/ack); vitest via the
   existing Agent Branches node_modules (`@cloudflare/vitest-plugin` 1.3.6, wrangler 4.147) symlinked, no installs.
3. `bus/bridge/bridge.py` — stdlib daemon: outbox dir → POST; GET long-poll → `aplexer message send --to <tag>`
   with `[from tag@machine]` prefix; persisted cursor + id dedup; never `--from`.
4. `bus/demo/demo.sh` — two bridges, distinct tokens, one `wrangler dev`: A→B, dedup on resend,
   offline queueing, rejected bad token.
5. Small commits on `proto/aplexer-bus`, push, one summary message to claude-principal.

## Log

- 2026-10-03: session start, identity + inbox checked, worktree `/home/alexey/git/aplexer-bus` created
  from origin/main (`f6b24bc`), scope declared.
- DESIGN.md written (envelope, identity, semantics, security, failure modes, 3-option comparison).
- Worker + ChannelDO implemented (`src/worker.js`, `src/channel.js`, `wrangler.jsonc`).
  Fixes found by running things: (1) DO class must be exported from the entry module;
  (2) workerd rejects non-handler named exports (`LONG_POLL_MS` crashed `wrangler dev`);
  (3) long-poll `wait` made client-controllable (default 25 s, cap 30 s) after a vitest timeout.
- Tests: `worker/test/bus.test.mjs` — 9/9 pass under vitest 4 + `@cloudflare/vitest-plugin` 1.3.6
  from the existing Agent Branches node_modules (symlinked as `worker/node_modules`, gitignored;
  zero installs).
- Bridge `bridge/bridge.py` (stdlib only): outbox-dir outbound with deterministic ids,
  `aplexer message send` inbound with `[from tag@machine]` prefix, persisted cursor,
  id dedup, dead-letter on undeliverable, never `--from`. `--delivery file:<path>` for hermetic runs.
- Demo `demo/demo.sh`: all four proofs pass (bad token 401; A→B in order; offline queueing;
  dedup on resend via `duplicate:true` + unchanged seq + no duplicate delivery).
  Debug notes: demo needed a unique `CHANNEL_ID` per run — wrangler persists DO state under
  `worker/.wrangler/`, and deterministic ids correctly deduped against a previous run's messages.
- Head pushed to `origin/proto/aplexer-bus`; summary sent to claude-principal.

## Negative-case amendments — zc-bus-negatives (2026-10-03)

Executor for claude-principal (session `zc-bus-negatives` / `d4e0f150`, parent `b3a92dd0`).
Task: add the codex C-1327 amendments the first executor did not get. Scope declared:
`a work join /home/alexey/git/aplexer-bus --mode edit --paths bus/**`. Inbox empty at start.

Baseline before any change: vitest 9/9, demo 4/4 proofs green on `d21b934`.

1. **Reconnect mid-poll** (`demo` §8): alpha posts via outbox while a long-lived beta bridge sits
   in a long-poll; `wrangler dev` is SIGTERMed (down-state asserted via curl), restarted with the
   same `CHANNEL_ID` (DO state persists under `worker/.wrangler/`); beta reconnects from its
   persisted cursor and the message lands exactly once — asserted again after several extra poll
   cycles to catch duplicates.
2. **Stored-then-lost reply** (vitest + demo §5): the bus stores a message whose 200 the client
   never observes; a blind resend with the SAME client id returns `duplicate:true` and the same
   seq, and exactly one copy reaches the target.
3. **ACL stamping** (vitest + demo §6): `from.machine` claimed by the client is re-stamped from
   the token (on the bus envelope, in beta's stream view, and in the delivered inbox line); ack
   is bound to the token's machine even when the body claims another. (Stamping already
   implemented — what was missing was the explicit negative tests.)
4. **Typed bridge outcomes** (`bridge.py`): every progress step logs `outcome=queued |
   transported | received-into-inbox | acked | UNKNOWN`; the bridge now also `POST /v1/ack`s
   advanced cursors (`outcome=acked`). A native send that times out (`--send-timeout`) is
   UNKNOWN: not marked delivered, cursor not advanced, retried only under the SAME bus id, and
   dead-lettered after `--unknown-dead-letter` attempts. Demo §7 forces it with a stubbed
   hanging `aplexer` binary on PATH and proves the recovery redelivery reuses the original id.

Result: vitest 12/12; demo 8/8 sections green. One commit on `proto/aplexer-bus`, pushed;
summary sent to claude-principal.
