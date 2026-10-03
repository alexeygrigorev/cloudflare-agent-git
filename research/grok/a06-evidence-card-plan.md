# A06 evidence-card comparison plan

2026-10-03. Owner: grok-head `39e95f91-19ee-48fc-8a83-c25e199813b6`. Assignment `01a0fef7-0d7a` (`C-A06-REAL-REVIEW-PLAN2324`). Handoff `01a0ff27-dd22` (`G-IDLE-HANDOFF-20261003` / `A-A06-PLAN-HANDOFF`). This file is the read-only packet. It is documentation. No live trial, no writer, no harness run, and no dupexec patch.

Dupexec production remains closed. Codex `01a0ff25-eb60` says this plan does not wait on that gate. A01 `G-A01-SHADOW-CONSUME-20261003` stays unlaunched. Shortlist draft 7 is unsigned. This packet is not a sign-off and not a new primary.

## Decision

Accept the bounded milestone: one evidence card per claim, same bytes in both review conditions, tie and unresolved allowed. Modify the timing rule: grok-head has now read these diffs, so cards D1 and R1 cannot supply blind review time or catch rate. The prospective comparison is specified below and is not run in this turn.

## CodeRabbit navigation and snapshots

Read on 2026-10-03 from the vendor pages [Navigate a change](https://docs.coderabbit.ai/change-stack/navigation) and [Snapshots and freshness](https://docs.coderabbit.ai/change-stack/snapshots). Change Stack is labeled preview. This is a document reading, not a product session.

Navigation already offers a layer rail ordered as a reading order, a file tree, in-browser search over paths, diff text, indexed content, summaries, and comments, viewed-file progress stored per snapshot, and links that can address a view, layer, file, or range. Search is capped (a blank query returns at most 60 records; a query returns at most 200). A link without review-run and commit parameters follows the latest snapshot. A signed public locator expires after 24 hours. GitHub viewed-state sync is provider-specific. The activity timeline pages at 30 events, and non-GitHub timelines are synthesized review checkpoints.

Snapshots pin reading to one review run and one head commit, keep earlier snapshots, and send comments, suggestion commits, and merges to the live pull request. The merge control refuses a stale artifact. Freshness compares the open snapshot with the live head, except on Azure DevOps, where that comparison is absent. The selector shows at most 25 snapshots. A synthetic stack stands in for a missing generation and is documented as incomplete. Chat stays on the snapshot where it started.

Those controls already cover grouped reading, per-snapshot progress, and stale-head refusal. A layer summary or a viewed checkbox does not record which sentence was checked against which probe, which binary hash was named, or which guarantee was excluded. The open A06 question is whether a card changes an accept, reject, or unresolved decision when the baseline reviewer can open the same commits. Another generated summary does not answer it. Codex's novelty drop to 2 in `research/codex/retained-lanes-review-2324.md` matches this reading. Effectiveness of CodeRabbit is unmeasured here.

## A05 is a different gate

`retained-lanes-review-2324.md` asks A05 for one real decision with two plausible alternatives, the same task, acceptance policy, tools, and evidence, with ties allowed and every discarded attempt counted. The fair A01 pair gave the two writers complementary jobs, so it does not score best-of-N selection. That limit stands. This packet does not register an A05 tournament. A correct claim label is not a selection among task implementations. Running them as one comparison would blur both gates.

## Card fields

Each card has: claim text, repo and commit, path, checker, named binary or artifact, observed outcome, excluded guarantee, and a decision of accept, reject, or unresolved. Both the ordinary-diff condition and the card condition may open the same files. The card gets no extra test, no hidden corrected label, and no stronger model.

## Retrospective cards

These two cards are a smoke reading of corrections that already landed. Familiarity disqualifies them as a timed study.

### D1. Dupexec arm 3 was labeled retry

Claim at `d020e5e0479e67cb55c86bfb93bd99bb227c14de` in this repo, `research/antigravity/r8-dupexec-count-verification.md`: "Arm 3 (Retry / Continuation): Total side-effects remained exactly 1 per operation ID across retries/continuations." The JSON at that commit set `retry_continuity_verified` to true. The script `research/antigravity/r8_dupexec_count_benchmark.py` builds the inner process with `create_stub_zcode_js` and routes the installed `/home/alexey/.local/lib/zcodex/zcodex` through `ZCODE_NODE`. The doc names binary SHA-256 `dce345ed47fb4190bb85771ad8ff1dc39cc8c19665fa433475c715689f7268e9`. This turn did not rehash that file and did not re-run the probe.

Correction `56f02a0efb5d66f948988ca8be59ac4dc73c60ee` renames arm 3 to sequential per-operation isolation and sets `production_live_resume` to `pending_owner`. The two probe lines use `op_arm3_retry` and `op_arm3_retry_attempt2`. `coordination/antigravity.md` in that commit leaves production CJS permission denial and live model resume with owner `82d375cd`. The script docstring in the current tree still says "Arm 3 (Retry / Resume)". `56f02a0` did not edit the script.

Decision: reject the retry/continuation claim and `retry_continuity_verified: true`. The published COUNT 2 to COUNT 1 lines are the author's adapter result on two ephemeral operation ids. Excluded guarantees: integrated production `zcode.cjs` denial without the stub adapter, live multi-turn resume, and a re-executed probe. Unresolved: whether today's installed zcodex still double-executes without the adapter. The live trial stays blocked.

### R1. Readiness tests mutated HOME, then isolated one case

`9de9527d2049933ad90042eacf12436de7eb935f` in `~/git/aplexer` and `~/git/cloudflare-aplexer-protocol` gates the Antigravity idle exemption on lifecycle hooks and implements the unit test by `std::env::set_var("HOME", ...)`. `dd7e4c1e27db4d1af1d8066b07a9abc14710fb08` passes hook capability as an argument and removes that process-global mutation from `src/watch.rs`. `6d6938fddc6e4f283c538c0a705f2aa455b087f4` gives `antigravity_with_installed_hooks_permits_idle_delivery_despite_tui_output` its own temporary `HOME` and `hooks.json`. That test sets `reported_state_at_ms` to 1000 and `last_activity_ms` to 3001, which is 1 ms past the 2000 ms grace. It is a boundary fixture, not a multi-second redraw sample.

`cf6b2bb88aa5bd6b0e649c302ca63786005822f6` keeps the exemption on Antigravity and adds OpenCode and zcodex tests whose activity past the grace retracts idle even when hooks are installed. Antigravity's handoff says two Bunny cycles were clean. This seat did not re-run the tests and did not witness those cycles. The debug digest `a9beb7d8d624c852af358db024d2ccfe28d35f8d5265dac62698d1a13e4ad831` recorded in `56f02a0` is a protocol-checkout `target/debug/aplexer`, not an identity proof for `~/.local/bin/aplexer` or for `cf6b2bb`.

Decision: reject a reading of `9de9527` as an isolated hook test. Accept `6d6938f` as isolating the one positive Antigravity delivery test from the caller's `HOME`. Excluded: host hook installation, Bunny cycle evidence, and byte equality between `cf6b2bb` and the installed binary. Unresolved: whether the binary that submitted `01a0feac-18ee` is `cf6b2bb`. That submission happened while Antigravity PTY activity was about 2.1 million ms after the idle report, which is the behavior the exemption describes.

## Prospective comparison, not started

1. Pick the next unfamiliar claim from an already-owned useful task. The author of the claim does not write the final label. Do not seed a bug and do not launch a writer pair to manufacture one.
2. Freeze the evidence set: commits, paths, logs, and the checker command. Hash the packet before either reviewer starts. Both conditions receive that set and the same instructions.
3. Baseline condition: ordinary source and report reading. Card condition: the fields above, filled only from that set.
4. Record, per claim: accept, reject, or unresolved; a false accept; a rejected true claim; commands and files opened. Allow a tie and a null benefit.
5. First eligible reviewer is a head who has not authored or previously reviewed that claim. grok-head is ineligible for D1 and R1 timing.
6. Muse reviews the protocol and the labels after this file is committed. Acceptance of the protocol is not acceptance of A06 as a product.
7. The shortlist sentence of at least 30 percent shorter review at equal catch on a seeded-bug sample stays on the books until a principal revision. It is not the measure for this packet. A Workers or Artifacts demo stays a separate gate.

Architecture for a later build is a Worker index of versioned evidence references on task forks, with ordinary Git paths as the fallback. This packet does not add that Worker. Summaries do not verify source, and nothing here merges.

## Falsification

On the next unfamiliar claim, park the card if both conditions reach the same decision and the card does not reduce the source files the reviewer has to open. Also park it if the card accepts a claim the baseline rejects. One retrospective correction does not pass either test.

## Limits

Checker commands named in the cards were not re-run. Binary hashes were copied from the cited docs and were not recomputed. CodeRabbit behavior beyond the two doc pages is unknown.
