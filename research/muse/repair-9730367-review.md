# Peer review: aplexer idempotency repair (9730367 → tip b69787f)

Reviewer: muse-reviewer (bound session c0838d96, engine shell, OpenCode Muse Spark 1.3).
Repo: /home/alexey/git/cloudflare-aplexer-protocol, branch experiment/cloudflare-cross-host.
Method: read actual code at tip; diffed 9730367 vs b69787f; ran test-idempotency-correct.sh
against the tip binary (target/debug/aplexer, built Oct 2 21:10, has --idempotency-key).
No builds, no installs, no peer files touched.

## Overall verdict: APPROVE-WITH-CORRECTIONS

The tip genuinely fixes the four load-bearing flaws the orchestrator's heartbeat
withheld 9730367 for (unscoped key dedup, silent payload clobbering, list-then-write
race, reply bypass). The bounds test provisions real sessions with valid syntax and
passes. Integration should wait for the small corrections below — none requires
re-architecture.

## Per-target findings (file:line evidence)

### 1. src/messaging/store.rs — write_message_idempotent (lines 64–106): approve with corrections
- Scoping (L81–88) compares logical identity: `m.from.tag == envelope.from.tag &&
  m.from.workspace == envelope.from.workspace`, recipient Tag match on tag string only
  (session_id ignored). Restarted sender sessions replaying a key dedup correctly;
  a different sender reusing a key falls through to a fresh write. Correct.
- Payload conflict (L91–95): same key + different `body`/`reply_to`/`kind` → hard
  `bail!("idempotency conflict...")`. Correct as far as it goes.
- Atomicity (L74, L77): exclusive `FileLock::exclusive(&mailbox_lock_path(mp))` is held
  across scan (`list_messages_in`, itself lock-free) and write. All other writers
  (`write_message_limited` L122, `submit_message_in`, cursor, GC) take the same
  per-mailbox lock, so scan+write is race-free among cooperating writers. Concurrent
  `list` takes no lock, but persistence is temp-file+rename (`atomic_write_bytes`,
  L103), so readers see whole old or whole new files — no torn reads. Pre-existing
  list-during-prune sensitivity is unchanged, not introduced here.
- CONFIRMED ISSUE (medium-low): `data` is part of the payload (`envelope.rs:93-94`,
  set from `--data` in both send and reply) but is NOT in the conflict comparison
  (L91). Same key + same body + different `--data` silently returns the old message.
  Fix: add `m.data == envelope.data` to L91, or document that keys cover
  body/kind/reply_to only.
- CONFIRMED ISSUE (low): anonymous senders (`MessageFrom::anonymous`, tag None,
  workspace None) all satisfy `None == None`, so distinct anonymous actors sharing a
  key collide. Document or mix in `external`/session fallback.
- CONFIRMED ISSUE (low): prune failure is swallowed (`let _ =` L104) while the
  sibling `write_message_limited` (L133–144) rolls the write back on quota failure.
  An idempotent send can report success with the mailbox over hard limits. Make them
  consistent.

### 2. src/bin/aplexer/cli_message_args.rs: approve
Both `MessageSendArgs` (L138–139) and `MessageReplyArgs` (L160–161) expose
`--idempotency-key`. Clean.

### 3. src/bin/aplexer/message_routing.rs: approve with corrections
- Reply inherits dedup: `cmd_message_reply` (L262–295) builds the envelope with the
  key and funnels through `finish_and_print` → `finish_send` → idempotent write.
  Inherited, as docs claim. `reply_to` is in the conflict tuple, so replies to
  different originals under one key correctly conflict.
- CONFIRMED ISSUE (must-fix, trivial): stray `eprintln!("DEBUG: body={}", ...)`
  (L161) prints every message body to stderr on every send/reply — observed twice in
  my own test run. Leaks content into logs. Delete.
- CONFIRMED ISSUE (must-fix, trivial): `finish_and_print_existing` (L143–150) is
  now dead code — the Phase-1 early-dedup block in `cmd_message_send` was correctly
  removed (diff confirms), leaving no caller. Delete or the build will carry
  dead-code warnings.

### 4. src/bin/aplexer/message_delivery.rs — finish_send (L109–128): approve with cleanup
- The idempotent write is the single choke point for send and reply. Correct placement.
- Pane double-delivery on retry is SAFE, but via the submission layer, not this
  function: a retried key returns the same envelope id, and `submit_message_in`
  (`submission.rs:45-47,57-63`) short-circuits on `delivery == Pane` /
  `.attempt` marker / recipient ack. No second PTY injection. Verified by reading,
  not by live pane test.
- CONFIRMED ISSUE (trivial): empty no-op block L120–122
  (`if envelope.delivery == Delivery::Pane && !pane.pane { // duplicate... }`)
  does nothing. Delete it to avoid implying a check that doesn't exist.

### 5. src/messaging/envelope.rs: approve
`idempotency_key: Option<String>` (L96–97) with serde default + skip — old mailbox
files without the field still load. Backward compatible.

### 6. docs/experiment-cross-host-ergonomics.md: approve (retractions match code)
- §3 retracts the two-computer roundtrip claim; §4 limits correlation fields to
  routing geometry, not consensus; §2.5 bounds the dedup window by GC retention;
  §5 records child-mailbox inheritance and expired-peer routing. All verified
  against code. "No concurrent retries can race" (§2.3) holds among lock-taking
  writers in one workspace mailbox — accurate for every current writer.
  "Completely closing the crash-after-send window" is true for inbox sends; pane
  sends are equally safe via the submission reservation (above).

### 7. Shell bounds tests: correct.sh passes; two legacy scripts are stale
- Ran `test-idempotency-correct.sh` (timeout 110s) against the tip binary: PASSED —
  duplicate returns same id, differing payload rejected with "idempotency conflict",
  reply dedup returns same id. It provisions two strictly bound sessions with valid
  `start --tag ... --workspace ...` syntax (help-verified) and unsets inherited
  `APLEXER_SESSION_ID`/`APLEXER_WORKSPACE`/`APLEXER_TAG` (L9–11). Genuine binding.
- Coverage gaps (not failures): no cross-sender same-key case, no restarted-sender
  same-tag replay, no concurrent parallel sends, no `--data`-divergence case.
  Recommend adding the first two; they are the exact behaviors the repair claims.
- CONFIRMED ISSUE (must-fix): `test-idempotency-duplicate.sh` asserts the OLD buggy
  behavior — same id for "hello world" vs "hello world 2" under one key — and
  therefore FAILS on tip code by design. `test-idempotency.sh` uses invalid
  `start shell test-recipient` positional syntax and rebuilds via `cargo run`.
  Retire or clearly mark both superseded by `test-idempotency-correct.sh`, or a
  future runner will read them as the spec.
- Hygiene: stray `src/messaging/tests/wait.rs.orig` file present in the repo —
  remove.

## Must-fix before global integration (all small)
1. Delete DEBUG eprintln (message_routing.rs:161).
2. Delete dead `finish_and_print_existing` and dead empty if-block (message_delivery.rs:120–122).
3. Retire/annotate the two legacy idempotency scripts; extend correct.sh with
   cross-sender and restarted-sender cases.
4. Include `data` in the conflict comparison, or document the exclusion.
Recommended soon: anonymous-sender scope note; prune-error consistency; remove .orig file.
