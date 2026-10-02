# Peer review: aplexer idempotency repair (9730367 → tip b69787f) — ROUND 2 (corrected)

Reviewer: muse-reviewer, genuinely interactive session
`07d34106-3a36-44f9-baa5-f98a27cb8dd9` (prior headless round: c0838d96).
Repo: /home/alexey/git/cloudflare-aplexer-protocol, branch experiment/cloudflare-cross-host.
Inputs since round 1: heartbeat-1920, heartbeat-1950 snapshot, desktop-orchestrator
USER14-CORRECTION + EVIDENCE-CORRECTION, recovery addendum (four review dimensions),
Claude consultation-2026-10-02 (Task Passports disposition), Antigravity evidence.md
(E-A035..037 status). Re-read identity.rs resolve_identity; no new builds.

## Overall verdict: WITHHOLD INTEGRATION (corrected from approve-with-corrections)

Round 1 was wrong in two places: it certified the bounds test as "genuine binding"
and graded the data/quota defects as low-priority. Corrected position: the tip's
direction (scoped keys, conflict rejection, lock-held write, reply inheritance) is
sound, but **no global integration and no dirty-checkout touch** until the mandatory
items below are fixed AND a genuinely bound test passes. Review alone never
authorizes integration.

## Correction 1 (retraction): APLEXER_SESSION_ID override is impersonation, not binding proof
Round 1 §7 claimed "Genuine binding." Retracted. `test-idempotency-correct.sh` does
start two real sessions, but every send is stamped `APLEXER_SESSION_ID=$SENDER_ID`
from an unbound caller. Per `process.rs:73-76` + `identity.rs:116-128`, that env var
is exactly the identity the resolver trusts, so the test exercises the
storage-layer dedup keyed on *asserted* identity — it proves nothing about whether
a message attributed to a tag originated inside that tag's workload. Worse,
`identity.rs:107-115` shows `--from <tag>` needs no proof of possession either:
any local process can send as any tag that ever existed in the workspace.
Consequences, all confirmed by code:
- **Scope is cooperative, not a security boundary.** A buggy or hostile local actor
  can squat another actor's (tag, key): first writer with (victim-tag, K, attack
  payload) wins, and the victim's legitimate send then fails as "conflict" —
  a key-squat DoS. Keys are safe only among mutually-trusting local actors.
  The docs (§4 correctly limits correlation to routing geometry) should say this
  sentence explicitly.
- The unsets at correct.sh L9–11 prevent *accidental* inheritance but the explicit
  per-command overrides are deliberate impersonation mechanics. A genuine bound
  test must originate sends inside the workload (see §8).

## Correction 2 (severity upgrades — all MANDATORY, integration-blocking)
1. **DEBUG body leak** (`message_routing.rs:161`): every send/reply body to stderr —
   observed in my own run. Mandatory: delete. (Was already must-fix; confirmed mandatory.)
2. **`data` excluded from conflict compare** (`store.rs:91` vs `envelope.rs:93-94`):
   same key + same body + different `--data` silently returns the old message.
   Recovery addendum dimension 2 requires `data` in the tuple. Mandatory: add
   `m.data == envelope.data`, no document-instead option.
3. **Quota/prune rollback parity** (`store.rs:104` `let _ = prune_workspace_locked`):
   sibling `write_message_limited` (L133–144) rolls the write back when quota
   enforcement fails; the idempotent path reports success over hard limits.
   Sibling quota paths audited: `check_body_size` (send/reply entry), envelope cap
   in `serialized_envelope`, and the `too large` bail all fail loudly — the prune
   swallow is the lone silent path (plus best-effort `maybe_gc_in`, acceptable as
   cleanup). Mandatory: mirror the rollback contract.
4. Dead code (`finish_and_print_existing`, empty `if` at `message_delivery.rs:120–122`)
   and the two stale scripts (duplicate.sh asserts the old clobbering behavior and
   fails on tip by design; test-idempotency.sh uses invalid start syntax): remove/
   retire before integration so no runner mistakes them for spec. Stray
   `src/messaging/tests/wait.rs.orig`: remove.

## Unchanged approvals (re-affirmed)
Scoping on logical tag+workspace ignoring session ids (`store.rs:81-88`); conflict
rejection for body/reply_to/kind; lock-held scan+write with all writers on the same
mailbox lock and rename-atomic reads for lock-free listers; reply inheritance via
the single `finish_send` choke point; pane-retry safety via the submission
reservation (`submission.rs:45-63`), not the empty if-block; envelope
backward-compat; docs retractions (§3 two-computer, §4 geometry-vs-consensus, §2.5
GC window) match code.

## New: tag-reuse / GC-boundary semantics (addendum dimension 4)
- Tag match ignores `session_id`, so after kill + same-tag restart, replay dedups
  (intended), but a *different* actor later holding a reused tag replaying the same
  key also dedups against the stale message and inherits its id/reply chain.
  That is the documented logical-identity semantic, but it is currently neither
  documented nor tested. Require a docs sentence + a tag-reuse test case.
- Post-GC replay mints a new message (duplicate downstream delivery). Docs §2.5
  admits the retention bound — sufficient, but needs the matching test case.
  True cross-host SSH roundtrip and concurrent-send races remain unproven; they are
  the acceptance bar, not review material.

## §8. Genuine bound-test design (proposal for Antigravity's repair lane)
Antigravity owns the isolated protocol patch; I review independently and never
touch `~/git/aplexer` (dirty, unrelated) or integrate globally. Constraints: work
only in the isolated protocol checkout/branch, prebuilt binary or existing
`target/`, ≤512MiB/≤120s per run, no package installs. Design:
- Start sessions A, B in a scratch workspace. Drive sends **from inside the
  workload**: `aplexer send <tag> -- 'aplexer message send --to ... --idempotency-key K ...'`
  (spawn-stamped identity; harness never exports APLEXER_SESSION_ID).
- Cases: (a) A retry same key+payload → same id; (b) B same key+payload, B's own
  identity → NEW id (no cross-sender dedup); (c) kill A, start A′ same tag, A′
  retries K → same id (logical-identity replay); (d) same key different body and
  different `--data` → both conflict; (e) squat case: B sends as… (must use
  workload B's own identity; `--from` spoof case asserts the cooperative-scope
  warning, not a pass); (f) tag-reuse + GC-window documented behaviors; (g) two
  shells in A racing the same K (concurrency smoke).
- Acceptance: all green + my independent re-review of the patch diff. Then, and
  only then, can integration be re-proposed — still requiring orchestrator approval.

## Outstanding asks (superseded — see Round 3 below)
- Repair owner (Antigravity): patch items 1–4 + §8 test; request my re-review.
- Orchestrator: nothing needed; no blockers on my side.

## ROUND 3 — independent re-review of patch bf593f0 (PASS)

Antigravity's patch (message 01a0fe39) verified by reading the full diff and by
executing the tests myself against a freshly rebuilt tip binary (cargo build +
cargo test, existing target/, no installs; ~/git/aplexer untouched):
- (1) DEBUG leak deleted (message_routing.rs); (2) `m.data == envelope.data` added
  to the conflict tuple (store.rs:94); error text now matches the sibling quota
  message; (3) prune/rollback parity mirrors write_message_limited exactly,
  including dir fsync (store.rs:105-116); (4) dead `finish_and_print_existing`,
  empty if-block, both stale scripts and the .orig backup all removed; docs gain
  the cooperative-scope sentence, tag-reuse semantics and post-GC replay.
- Rust: 4 new store tests pass 4/4; full lib suite 443 passed, 0 failed, 3/3 runs
  single-threaded. Parallel-mode runs show 1 varying failure in
  messaging::wait timing tests (legacy_publication / lock_contention) that also
  fail on the unpatched base in this environment and pass solo — pre-existing
  flakes, unrelated to this patch. Recorded, not blocking.
- Shell: rewritten test-idempotency-correct.sh drives every send from inside the
  workload PTY via `aplexer send` (spawn-stamped identity, whoami-verified,
  restart proven by fresh UUID). All 7 cases (a)–(g) PASS: retry dedup,
  cross-sender independence, restart replay, body + data conflicts, cooperative
  scope doc, tag-reuse/GC docs, concurrency race → identical id.

Verdict on bf593f0: **PASS — all round-2 mandatory items resolved and proven by
genuinely bound tests.** Integration gate: Antigravity (implementation owner)
executes any branch→mainline merge inside the isolated protocol repo only, after
this PASS; I hold no integration role. Global install / ~/git/aplexer off-limits
until the orchestrator names a separate integration owner and window.
