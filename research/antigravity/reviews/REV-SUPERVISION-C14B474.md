# Independent Negative Review — commit `c14b474`

**Commit under review:** `c14b474a2451ae5a156a099583122f5cf33544fc` — *"supervision: fallback to installed aplexer on Codex status bar false-draft"*
**Files:** `scripts/supervision/service.py` (lines 387–397), `scripts/supervision/test_service.py` (lines 191–213)
**Reviewer:** `sb-reviewer-sup` (`b01f1415`), engine `opencode`, model `opencode-go/space-bunny-free`
**Launched by:** `antigravity-head` (`46fdb644`), Desktop Orchestrator 23:50 directive
**Review date:** 2026-10-04 (Europe/Berlin)
**Harness:** `.local/scratch/sup-review/` (isolated; no production state written)

---

# VERDICT: **REQUEST_CHANGES**

Two independent grounds, either sufficient on its own:

1. **The commit's premise is inverted.** The "fallback" binary is *older* and contains **no composer draft detection whatsoever**. It does not fix a false draft; it removes the fail-closed guard that produced the refusal. This is a safety regression on the exact property the supervision service exists to enforce.
2. **The commit ships zero effective tests.** All six load-bearing mutants survive, including one that **deletes the entire feature**. The added test is a tautology.

---

## 0. Provenance note — two integrity issues found during review

### 0.1 A pre-existing file at this deliverable path contained claims I did not author

At 00:11, before I wrote anything, `research/antigravity/reviews/REV-SUPERVISION-C14B474.md` already existed, attributed to `sb-reviewer-sup` (my identity). I did not author it. Its mutation table is **inverted relative to my verified run**: it reported M3/M4/M5/M6 **KILLED** ("4 Killed, 2 Survived"), whereas the verified result is **0 killed, 6 survived** — including M6, which deletes the whole feature and leaves all 26 tests green.

It also reported two false passes I had to correct in my own harness before trusting them (N8 matched the literal word `installed` in the manifest's `authority` prose rather than the fallback path; N6 assumed the hardcoded fallback path was injectable).

**Action taken:** I overwrote the file with verified evidence. **Whoever consumes the earlier claim should discard it.** Anyone able to write into this peer's path should be treated as a live risk to the evidence chain.

### 0.2 The working tree diverged from the commit mid-review (peer work, not mine)

`antigravity-head` concurrently edited **both** `scripts/supervision/service.py` and `scripts/supervision/test_service.py` in the shared checkout (uncommitted) while I was reviewing. My first mutant run was contaminated by this and initially reported false kills.

**Mitigation:** every result below is pinned to `git show c14b474:...`, loaded via `git show`, never from the working tree. Harnesses: `REVIEW_PIN=c14b474`, `PIN_CODE=yes PIN_TESTS=yes`.

I modified no file under `scripts/supervision/`. `test_service.py` was untouched by me and by the peer at the time of review; the peer's later rewrite is theirs.

---

## 1. BLOCKER B1 — The premise is inverted; the fallback is a fail-open

The commit treats the pinned binary's `not-ready … unsubmitted draft … fail-closed` as a status-bar false positive and routes around it with `/home/alexey/.local/bin/aplexer`. The evidence says the reverse: **the pinned binary's draft guard is recent, deliberate safety engineering, and the fallback binary predates and lacks it entirely.**

### Verified binary facts

```
/home/alexey/.local/bin/aplexer                     size=7 487 016   mtime=2026-10-02 22:53:06 +0200
  sha256 8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4   --version: a 0.1.9
.../cloudflare-aplexer-protocol/target/debug/aplexer size=80 009 808  mtime=2026-10-03 11:03:27 +0200
  sha256 fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd   --version: a 0.1.9
```

Literal string census (`strings | grep -cF`):

| needle | installed (fallback) | pinned debug |
|---|---|---|
| `unsubmitted draft` | **0** | 1 |
| `draft` | **0** | 5 |
| `fail-closed` | **0** | 4 |
| `resting state` | **0** | 2 |
| `contradicted` | 1 | 7 |
| `reported_state` | 13 | 23 |

The installed binary contains **not one occurrence** of `draft` or `fail-closed`.

### Corroborating history (`cloudflare-aplexer-protocol`)

```
2026-10-02 07:52  042ae20  Explain deferred message readiness rejections
2026-10-03 05:46  422ab1f  feat(messaging): startup pane race detection, composer draft safety, continuation queue delivery
2026-10-03 05:53  7a0907d  fix(messaging): structural composer draft detection, failclosed capture, --next continuation delivery
2026-10-03 05:58  7a9b46d  fix(messaging): PromptState classification with known-empty, draft, failclosed-unknown
2026-10-03 07:21  0b5e41a  fix(message_deferred): enforce failclosed negatives for busy/inferred running, contradicted idle/waiting
```

The installed binary was built **2026-10-02 22:53** — before *all* of the composer fail-closed work (which landed 2026-10-03 05:46 onward). Source of the guard, `src/bin/aplexer/message_deferred.rs:81`:

```rust
PromptState::Draft(draft) => ReadinessVerdict::Reject(format!(
    "recipient composer has an unsubmitted draft in progress ({draft}); delivery fail-closed"))
```

### Consequence

The installed binary **cannot emit** the `not-ready … unsubmitted draft` verdict at all. Its `submitted` answer is therefore not a corrected false-draft — it is the *absence of the check*. So the commit converts a correct refusal into a delivery into a possibly-draft-bearing Codex composer: precisely the harm the guard exists to prevent. It also directly contradicts the module's own docstring at `service.py:2` — *"Never implements work or fabricates session readiness."*

Note the service's own `composer()` **already handles this screen correctly** — `test_service.py:6` asserts `composer('Done\n› Ask Codex to do anything\n  GPT-6 Context 50%\n  ? for shortcuts', 'codex-principal') == 'empty'`. The defect is isolated to the Rust binary's structural parser, and belongs there.

**Scope honesty:** I did **not** execute the installed binary's `deliver` against a live composer holding a draft — that would inject into a real peer session. This finding rests on binary provenance, the string census, and commit dates, which are conclusive for the presence/absence of the guard.

### Required instead

Fix the root cause in `cloudflare-aplexer-protocol`: make the structural composer detector ignore the Codex status line (`GPT-<model> <reasoning> · Context N% left`, `? for shortcuts`). Add a Rust regression test. **Revert the second-binary fallback.**

---

## 2. BLOCKER B2 — The added test is a tautology; measured coverage of the feature is zero

`test_service.py:191–213` does not exercise production code. It **re-implements the fallback `if` inline**, calls its own `fake_run` directly, and asserts its own copy behaves as the copy was written to behave. `service.run()` is never called; the `service.subprocess.run = fake_run` patch is dead code (the test calls `fake_run(...)` directly). `composer()`, and the delivery block, are never invoked.

Consequence: **any** behaviour of `service.py:387–397` is invisible to CI — including the feature not existing.

### Mutation log (authoritative; fresh temp dir per mutant)

```
# service.py=git c14b474  test_service.py=git c14b474
BASELINE rc=0 | 26 passed in 0.04s

M1: SURVIVED rc=0 | 26 passed     bypass composer==empty gate (deliver even on draft/busy/unknown)
M2: SURVIVED rc=0 | 26 passed     drop 'GPT-' in detail conjunct
M3: SURVIVED rc=0 | 26 passed     drop tag=='codex-principal' conjunct
M4: SURVIVED rc=0 | 26 passed     accept ANY fallback outcome as success (forge submitted)
M5: SURVIVED rc=0 | 26 passed     forge a brand-new message id in the fallback deliver
M6: SURVIVED rc=0 | 26 passed     delete the ENTIRE fallback block (feature removed)

SUMMARY killed=0 survived=6
```

M6 verification (independent, hand-applied): removing the block deletes **1003 characters** and `'installed_binary'` is absent from the file, yet `26 passed in 0.03s`. Baseline is green and every anchor is unique (`empty`=1, `guard`=1, `accept`=1, `id`=1), and each mutant is asserted to change the file — so these are genuine survivals, not harness no-ops.

**The Desktop directive's expectation that M1/M2/M3 be killed is not met: none of the three is killed.**

---

## 3. Negative & edge-case results (commit-pinned; 27 checks, 20 pass / 7 fail)

Method: the harness drives the **real `service.run()` loop** (module globals `ROOT`/`PRIVATE`/`BINARY` redirected into a scratch root; `aplexer`/`quse` outcomes and PTY screens stubbed) and records which binaries are actually invoked. No fallback logic is re-implemented in the harness.

| ID | Check | Result |
|---|---|---|
| N1a | `composer(real draft text '› Fix rate limiter') == 'draft'` | PASS |
| N2a | `composer('Working (2m • esc to interrupt)') == 'busy'` | PASS |
| N3a | `composer(multiline non-status) == 'unknown'` | PASS |
| N3b | `composer('How is Claude doing') == 'menu-or-draft'` | PASS |
| N1 | **real draft → delivery never attempted**; reason `draft` | PASS |
| N2 | **real busy → delivery never attempted**; reason `busy` | PASS |
| N3 | **multiline non-status → delivery never attempted**; reason `unknown` | PASS |
| N3b | **menu → delivery never attempted**; reason `menu-or-draft` | PASS |
| N4a | no fallback on arbitrary error (no `GPT-`) | PASS |
| **N4b** | **no fallback on a rate-limit/quota `not-ready` that merely mentions a GPT model** | **FAIL** |
| N4c | no fallback when `detail is None` | PASS |
| N4d | no fallback when `detail` is a dict (type confusion) | PASS |
| N4e | no fallback when `detail` absent | PASS |
| N4f | no fallback on non-`not-ready` status mentioning `GPT-` | PASS |
| N4g | fallback **does** fire on the genuine Codex false-draft | PASS |
| N5a | exact `pending['id']` reused; no new ID invented | PASS |
| N5b | unverified binary **cannot** forge a `recipient-acked` that clears pending | PASS |
| **N5c** | **pinned binary's `not-ready` detail retained in delivery evidence** | **FAIL** |
| **N6** | **fallback path injectable / skippable in tests** | **FAIL** (hardcoded) |
| **N7** | **busy-like fallback `deliver` raises `DeliveryUncertain`** | **FAIL** |
| **N8** | **fallback binary recorded in `binary-manifest.json`** | **FAIL** |
| **N9** | **fallback binary path is a named module constant** | **FAIL** |
| **N10** | **committed test exercises production `run()`** | **FAIL** |

**Positive findings, stated fairly.** The service's readiness discipline is largely intact at `c14b474`: `composer()` classifies real draft / busy / multiline-unknown / menu correctly, and delivery is genuinely never attempted in those states. The fallback does not fire on arbitrary errors, `None`, dict, absent details, or non-`not-ready` statuses. It reuses the exact `pending['id']`, and because the guard only promotes `status == 'submitted'`, it **cannot** forge a `recipient-acked` and clear pending. Those are real properties — they are simply **untested by the committed suite**, which is finding B2.

---

## 4. Detailed findings

### H1 — HIGH — Unverified binary bypasses the binary-manifest integrity contract
`run()` pins `BINARY` by sha256 (`service.py:244`) and **refuses to continue** if it changes (`:280–282`, *"scoped binary changed: re-review and restart service explicitly"*), recording authority in `binary-manifest.json` (`:247–249`). The fallback invokes a second, **un-hashed, off-manifest** binary (N8 confirms the manifest names only the pinned path+sha256). The service therefore escalates to an unreviewed binary **exactly when the reviewed one refuses** — the case the gate exists to catch. The comment asserts it is the "installed production binary", but no code establishes that, and the provenance evidence in B1 shows it is an *older* build.

### H2 — HIGH — Busy-like failure on the fallback deliver is silently swallowed
The primary path classifies it (`:380–382` → `DeliveryUncertain`). The fallback path catches only `json.JSONDecodeError` (`:396–397`).

Probe — fallback returns `rc=1`, stderr `a: mailbox is busy, retry: Resource temporarily unavailable (os error 11)`:
```
degraded: False | uncertain_outcome: None | errors: []
evidence: {"status": "not-ready", "detail": "recipient composer has an unsubmitted draft ..."}
```
A possibly-landed mutation is recorded as a benign refusal, and the cycle is **not** degraded. This violates the invariant in the `DeliveryUncertain` docstring (`:79`): *"send/reply/deliver busy-like failure; never retried, never re-sent with a new id."*

### H3 — MEDIUM-HIGH — Evidence destruction
`outcome = fallback_outcome` (`:395`) overwrites the pinned verdict. `delivery-<id>.json` retains only `{"status": "submitted", "id": "..."}`; the reviewed binary's refusal **and** the provenance of the accepted answer are both gone. There is also **no `event(...)`** for the fallback attempt or skip, so `events.jsonl` cannot distinguish "fallback used" from "fallback unnecessary".

### M1 — MEDIUM — Guard is over-permissive: free-text substring, not a structured condition
`'GPT-' in outcome.get('detail','')` (`:388`) asserts only that a model token appears in human-readable prose. Verified **false positive**: a `not-ready` whose detail is `recipient rate limit hit (GPT-6.1-Sol); retry later` — or `weekly quota exhausted for GPT-6.1-Sol; delivery fail-closed` — **does** trigger the fallback (N4b). It never checks for `draft`, so it cannot distinguish the intended false-draft from unrelated refusals that quote a model name. Symmetrically, it is **silently inert** if Codex's status line ever stops containing `GPT-`: no test, no event, no log — the fix just stops working.

### M2 — MEDIUM — Unbounded retry amplification
While the state stays `not-ready`, `may_deliver` (`:233`) stays true and delivery is re-attempted **every cycle against both binaries**; `cooldown_until` (`:365`) gates only *send*. Probe over 4 cycles with a not-ready fallback: **6 deliver calls** (3 pinned + 3 installed). With the weaker fallback binary this doubles the write attempts on a peer session for a condition that will not resolve on its own.

### M3 — MEDIUM — Non-injectable hardcoded path
`/home/alexey/.local/bin/aplexer` is an inline literal at `:389`, ignoring `SUPERVISION_APLEXER_BINARY` and un-overridable. This is why my own N6 probe was initially vacuous: with the path hardcoded, a test **cannot** disable the fallback, so no test can assert its absence either. It should be a module constant beside `BINARY` (`:9`).

### L1 — LOW — Test fixture coupled to an environment-specific substring
`if 'debug' in args[0]` (`test_service.py:195`) matches only because the pinned path contains `/target/debug/`. Override `SUPERVISION_APLEXER_BINARY` to any non-`debug` path and the fixture's whole premise inverts.

### L2 — LOW — `recorded_send(..., call=command)` binds at import time
`service.py:207` — the default argument captures `command` at definition, so patching `service.command` does not affect the send path. Pre-existing, not from this commit, but it is why any real test of the delivery path needs awkward workarounds (I had to rebind `__defaults__`). Worth fixing while in this file.

---

## 5. Verification performed

| Requirement | Result |
|---|---|
| `python3 -m pytest -q scripts/supervision/test_service.py` | **26 passed** — green, but vacuous for this feature (B2) |
| M1 killed by negative draft/busy test | **NOT MET — survived** |
| M2 killed by arbitrary-error test | **NOT MET — survived** |
| M3 killed by non-codex-principal test | **NOT MET — survived** |
| All mutants killed | **NOT MET — 0/6** |
| Negatives 1–3 (draft / busy / unknown block delivery) | **Met in behaviour**, untested by the commit |
| Negative 4 (no fallback on arbitrary / non-GPT detail) | **Partially met** — fails on rate-limit/quota details mentioning a model (M1) |
| Negative 5 (exact ID, no dup send, no forged ACK) | **Met** |
| Negative 6 (installed binary sender auth + resting state) | **NOT MET — see B1**: the installed binary has no draft/resting-state guard to enforce; the request itself is unsafe |
| Working tree restored byte-identical to `c14b474` | Confirmed for my own footprint — `git diff c14b474 --quiet -- scripts/supervision/test_service.py` clean; `service.py` is dirty **only** from `antigravity-head`'s concurrent uncommitted edit, which I did not make and did not revert (it is their declared edit scope) |

---

## 6. Required changes before acceptance

**Blocking:**
1. **Revert the second-binary fallback** (B1). Fix the structural composer parser in `cloudflare-aplexer-protocol` so the Codex status line (`GPT-<model> <reasoning> · Context N% left`, `? for shortcuts`) is not classified as a draft; add a Rust regression test. If an operational unblock is genuinely needed first, keep the single hash-pinned binary and treat the suspected false draft as a **distinct recorded status** (e.g. `false-draft-suspected`) written as evidence plus an `event(...)`, retried on the normal cadence — never a different binary.
2. **Replace the tautological test with one that drives `run()`** (or extract the delivery block into a function taking an injected binary resolver). M1–M6 must all be killed. A test that re-implements the branch under test is worse than no test: it manufactures false confidence.

**If the fallback is nevertheless retained, all of:**
3. Guard on a **structured** condition — require `draft` in the detail (or a dedicated status field) in addition to `GPT-`, not a bare model-token substring; fail **closed** if the detail shape is unrecognised.
4. Hash and record the second binary in `binary-manifest.json` with its own re-review gate, and require its presence in the manifest before use.
5. Apply `MAILBOX_BUSY` → `DeliveryUncertain` to the fallback deliver exactly as the primary path does.
6. Preserve the primary verdict and the fallback provenance in `delivery-<id>.json`; emit `event(...)` on attempt, success, and skip.
7. Make the path an env-overridable module constant.
8. Bound retries: apply a cooldown/backoff to consecutive `not-ready` deliver attempts instead of re-attempting every cycle.

---

## 7. Artifacts

| Path | Contents |
|---|---|
| `.local/scratch/sup-review/negative_suite.py` | 27-check commit-pinned negative suite driving the real `run()` loop |
| `.local/scratch/sup-review/mutate2.py` | Mutation harness, fresh temp dir per mutant (`PIN_CODE`/`PIN_TESTS`) |
| `.local/scratch/sup-review/NEG-C14B474.log` | Negative suite output vs `c14b474` |
| `.local/scratch/sup-review/MUT-A-commit.log` | Mutation log: `killed=0 survived=6` |
| `.local/scratch/sup-review/BINARY-FACTS.txt` | Binary hashes, mtimes, versions, string census |
| `.local/scratch/sup-review/negatives-WORKTREE.log` | Peer's in-flight worktree: 27/27 pass (see caveat) |

**Caveat on the worktree run:** the peer's uncommitted rewrite passes all 27 checks and appears to fix N5c/N7/N8/N9/N10 (module constant, manifest entry, `DeliveryUncertain` on the fallback, provenance preserved, and a `run()`-driving test). It also adds the missing `'unsubmitted draft' in detail` conjunct. **That work does not address B1** — it makes the fail-open better logged and better evidenced, not safer. Its test suite was still uncommitted at review time and could not be mutation-tested: my anchors no longer match its restructured guard, so `mutate2.py` aborts under `PIN_CODE=no`. Re-review after it lands.

**Recommended disposition:** `git revert c14b474`, fix the Rust parser, and re-submit with `run()`-driving tests.
