# aplexer global bus — design (proto/aplexer-bus)

Status: prototype, 2026-10-03, zc-bus-design for claude-principal. Goal: let agent sessions on
different machines (laptop, desktop/Hetzner, others) hold one conversation, without SSH file-drop
plumbing and without breaking local aplexer semantics.

## Goals

- One durable, ordered conversation log shared across machines; remote messages land in the local
  aplexer inbox as first-class messages, tagged with their origin `[from tag@machine]`.
- Machines are authenticated; no machine can impersonate another (the bus stamps origin, never the client).
- At-least-once wire delivery with client-side dedup → effectively-once into the local mailbox.
- Works offline: an offline machine's messages queue on the bus and arrive on next connect, in order.
- Same stack as Agent Branches (Workers + Durable Objects), Python-stdlib bridge, zero new runtime deps.

## Non-goals

- No pane injection, no `deliver` into busy panes, no `--from` spoofing — inbound delivery uses the
  ordinary local `aplexer message send` path only.
- No secrets, private transcripts, or large payloads in message bodies; not a file-transfer channel.
- No end-to-end encryption or signing yet (TLS + machine tokens only; see Open questions).
- No deploy to production in this prototype; everything runs under `wrangler dev`.

## Message envelope

```json
{
  "id": "b-<uuid or deterministic client id>",
  "seq": 42,
  "channel": "global",
  "from": { "machine": "laptop", "tag": "zc-bus-design", "session_id": "33f4ef2b…" },
  "to":   { "machine": "desktop", "tag": "claude-principal" },
  "kind": "note",
  "body": "text, ≤ 64 KiB",
  "reply_to": null,
  "created_at": "2026-10-03T12:34:56.789Z"
}
```

`id` — client-supplied for idempotent resend, else server UUID; dedup key everywhere. `seq` — dense
per-channel sequence assigned by the bus; the cursor unit per machine. `to.machine` optional:
absent = broadcast to all machines. `kind` ∈ note/question/status/event. `reply_to` links to a bus
`id`, keeping threads meaningful across machines.

## Identity

- Per-machine bearer token; the Worker maps token → machine id from a server-side registry
  (`BUS_MACHINES`, a secret in production). The server overwrites `from.machine`; a client claim is
  ignored. Unknown/missing token → 401.
- Display identity is `tag@machine`. `tag`/`session_id` are display claims from the client: they name
  the originating session but are not authenticated yet (documented limitation; signing is future work).
- `GET ?machine=` must match the token's machine or the request is rejected — the bridge cannot read
  another machine's stream by accident or config error.

## Delivery semantics

- Durable append-only log in one Durable Object (`ChannelDO`, SQLite storage) per channel: `msg:<seq>`
  records, `seen:<id>` dedup set, `ack:<machine>` cursors. Append is a single-DO atomic step.
- Wire delivery is at-least-once: `GET /v1/messages?after=<cursor>` long-polls (≤ 25 s) and returns
  matching messages; after a crash the bridge replays from its persisted cursor and redelivery is
  possible. The bridge dedups by `id` → effectively-once into the local aplexer inbox.
- Cursor/ack per machine: the bridge persists its cursor in local state on every delivered message
  (deliver-then-save; a crash between the two can redeliver once — accepted, dedup-visible).
  `POST /v1/ack` records the machine's cursor server-side for observability and future log trimming;
  the bridge calls it after every poll that advanced the cursor.
- Bridge log outcomes are typed: `outcome=queued` (accepted for the bus, id assigned),
  `outcome=transported` (stored on the bus; `duplicate=true` marks a deduped resend),
  `outcome=received-into-inbox` (provably landed locally), `outcome=acked` (cursor persisted
  server-side), `outcome=UNKNOWN` (a local native send timed out — it may or may not have landed).
  An uncertain send is NEVER retried under a new id: the message stays undelivered, the cursor does
  not move past it, and the next poll redelivers under the SAME bus id; after
  `--unknown-dead-letter` attempts it is dead-lettered so one wedged target cannot block the stream.
- Ordering: bus seq order per channel; the bridge delivers in seq order, so remote readers see the
  same order senders produced.

## Readiness / integration with local aplexer

- Outbound: the bridge watches an outbox dir (`--outbox-dir`, default `.local/bus-outbox/*.json`) with
  `{"to": "tag@machine" | {"machine","tag"}, "kind", "body", "reply_to"}`; a deterministic message id
  (hash of filename+content) makes resends after crashes free. Log-watching `aplexer message log` for
  `tag@machine` recipients is supported as a secondary mode but cannot be produced by the stock CLI
  (tags are workspace-local), so the outbox dir is the honest primary path.
- Inbound: delivered as `aplexer message send --to <local-tag> "[from <tag>@<machine>] <body>"` in the
  workspace. Delivery is pluggable (`--delivery file:<path>`) so tests/demos stay hermetic. Local
  native deliver rules, inbox semantics, and ack flows are untouched; remote messages are ordinary
  local messages once landed. Never `--from`, never pane injection.

## Security

- TLS everywhere (Workers terminate), bearer tokens per machine, token rotation = registry update.
- No secrets in bodies; size cap 64 KiB per message; per-machine rate limit (default 60 msg/min, 429
  otherwise); 401 on any bad token; `?machine=` mismatch → 403. No PII beyond what agents already
  exchange; bodies are treated as public-to-the-team text.

## Failure modes

- Offline machine: bus retains the log (durable DO storage); the machine catches up from its cursor.
  No per-machine inbox on the server — replay from cursor is the recovery path.
- Replay/duplication: possible on any reconnect; killed by id dedup client-side (and by `seen:<id>`
  server-side for idempotent POSTs).
- Clock skew: irrelevant to correctness — ordering is bus `seq`, not timestamps; `created_at` is
  display-only.
- Bridge crash: cursor + delivered-set persist in one state file written atomically after each
  message; worst case is one redelivered (deduped) message.
- Poison message (undeliverable locally, e.g. unknown tag): dead-lettered into state with the error,
  cursor advances — one bad message must not block the queue.
- Bus outage: bridges fail with nonzero exit and retry on next start; local aplexer keeps working.

## Options compared

1. **Cloudflare Worker + Durable Object (recommended, built here).** Same stack and account as the
   Agent Branches prototype; DO gives a serialized, durable log with strong ordering for free;
   long-poll fits the free-tier request model; no infrastructure to operate. Cost: egress latency
   (~10–100 ms), needs a Cloudflare deploy for real use.
2. **SSH file-drop (current `orchestrator-channel-v2.py`).** Works today with zero cloud dependency
   and no server; but per-peer plumbing (outbox dirs, receipts, ack files per channel), no shared log,
   no broadcast, ordering by filename timestamps, and it only connects machines with SSH access to
   each other. Good fallback; poor core.
3. **Self-hosted broker (NATS/Redis).** Best throughput/latency and real pub/sub semantics; but a new
   always-on service to run, back up, secure and monitor on Hetzner, plus client libraries on every
   machine (bridge is no longer stdlib-only). Overkill for tens of messages per hour.

## Repo layout & run

- `worker/` — `src/worker.js` (auth/routing/rate-limit), `src/channel.js` (`ChannelDO`),
  `wrangler.jsonc` (demo tokens in vars; production uses secrets), `test/bus.test.mjs` (vitest via the
  Agent Branches node_modules — no installs; `node_modules` is a symlink, gitignored).
  Run tests: `cd worker && node_modules/.bin/vitest run`. Run locally: `node_modules/.bin/wrangler dev`.
- `bridge/bridge.py` — stdlib daemon (see `--help`); `--max-cycles` for one-shot runs.
- `demo/demo.sh` — one `wrangler dev`, bridges `alpha` and `beta` with different tokens; proves
  A→B delivery, dedup on resend (including a blind resend after a lost 200), offline queueing, a
  rejected bad token, forged-from ACL re-stamping, `outcome=UNKNOWN` with same-id retry, and
  reconnect after killing `wrangler dev` mid-poll (no loss, no duplicates).

## Open questions

- Tag authentication (signing or server-issued per-session credentials) — needed before any
  enforcement-level trust in `tag@machine`.
- Log trimming policy: when may the bus drop `seq ≤ min(ack)`? Default: keep everything for now.
- Whether `aplexer` should grow a native `--bus` flag so the bridge becomes a library inside aplexer.
