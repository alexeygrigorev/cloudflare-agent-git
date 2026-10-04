# REV-ACTOR-COMMITS-9EC-D56 — Independent Review of Concurrent Actor Commits

- **Reviewer:** zcode-recovery-test (ZCode/zcodex, session 4abc725c), launched by antigravity-head (46fdb644)
- **As-of:** 2026-10-04, Europe/Berlin
- **Task:** Independent review assigned via aplexer message 01a104cd-8879-73e3-a90f-d218a893c71b
- **Verdict: PASS WITH FINDINGS** — both commits are safe to integrate (additive, no regressions, guard mutations caught), with three findings the integration owner should read: a guaranteed merge conflict, two test-suite blind spots, and one minor robustness edge.

## 1. Scope and identity

| Item | Commit | Tree |
|---|---|---|
| Base | `ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e` | — |
| Actor Alpha — `inspect_token_metadata` + `test_21` | `9ec79dbcc5eb8be117a941c40e98deddc80e3c2f` | `e39fdcac9d5169cf887ed40a997e60bcfea648bc` |
| Actor Beta — `calculate_jitter` + `test_22` | `d56689841b78ec0db77e66eb7934f042751c142b` | `b267cb0df38d455968db3efcf7df8c02d15adf39` |

Both branch tips verified on `origin` via `git ls-remote` before review (exact hash match). Alpha adds 8 lines to `agent_branches/client.py` + 9 to `tests/test_client.py`; beta adds 9 + 9. No other files touched; no shared-file edits outside the appended region.

## 2. Code verification

**Alpha `inspect_token_metadata` (9ec79db) — formatting/segment check only, NOT auth authority. Confirmed.**
- Pure local string operations: empty/non-string → `ValueError`; `token.replace("_", "-").split("-")` for segment count; prefix membership test against `tok_`/`task-`/`sidecar-`; returns `{valid_prefix, segments, length}` only.
- No HTTP, no signature verification, no server round-trip, and no secret bytes exposed (length/segments/prefix-bool only). The result key is deliberately named `valid_prefix` — a format heuristic. It **must not** be used for authorization decisions; the review confirms nothing in the commit presents it as one.

**Beta `calculate_jitter` (d566898) — deterministic bounded backoff. Confirmed.**
- `delay = min(max_delay, base_delay * 2**attempt)`, plus parity-cycle jitter `0.01 * (attempt % 3)` (adds 0/0.01/0.02), rounded to 4 places. No `random` import — fully deterministic: same inputs → identical output (verified over attempts 0–19).
- Boundedness measured: attempts 0–39 at defaults give min 0.05, max **2.02** (= `max_delay` 2.0 + max jitter 0.02); series 0..8: `0.05, 0.11, 0.22, 0.4, 0.81, 1.62, 2.0, 2.01, 2.02`.
- Negative attempt → `ValueError("Attempt must be non-negative")` — confirmed directly and by `test_22`.

## 3. Negative verification (measured)

- `inspect_token_metadata`: `""`, `None`, `123`, `b"x"` all raise `ValueError`; `"no-prefix-here"` → `valid_prefix: False`; `"tok_alpha_12345"` → `{valid_prefix: True, segments: 3, length: 15}`.
- `calculate_jitter(-1)` → `ValueError`; determinism holds; cap holds.

## 4. Test suites (`python3 -m unittest -v tests/test_client.py`)

| Commit | Tests | Result |
|---|---|---|
| base `ec5030c` | 20 | **7 failures** |
| alpha `9ec79db` | 21 | **7 failures**, `test_21_inspect_token_metadata` **ok** |
| beta `d566898` | 21 | **7 failures**, `test_22_calculate_jitter` **ok** |

The 7 failures (`test_02, 03, 05, 06, 10, 12, 13`) are **identical across base, alpha, and beta** and are **not regressions from either actor commit**. Root cause (measured, from traceback): these CLI-dependent tests invoke an `agent-branches` launcher script that does not exist in these commit trees — `[Errno 2] No such file or directory: .../alpha/agent-branches`. The failure pre-dates both commits; both new tests pass. Net delta per commit: +1 test, +1 passing test.

## 5. Mutation testing

Applied in disposable worktrees, each restored to byte-identical state afterwards (`git diff` empty after restore).

| Mutation | Target | Expected | Observed |
|---|---|---|---|
| **M1** — empty-token acceptance: guard `if not token or not isinstance(token, str)` → `if False` | alpha `test_21` | FAIL | **FAIL ✓ caught** |
| **M2** — negative-attempt guard removed: `if attempt < 0` → `if False` | beta `test_22` | FAIL | **FAIL ✓ caught** |
| **P1** (sensitivity probe) — jitter removed: `return round(delay, 4)` | beta `test_22` | — | **OK — not caught** |
| **P2** (sensitivity probe) — prefix check bypassed: `valid_prefix` hardcoded `True` | alpha `test_21` | — | **OK — not caught** |

**Finding F1 (blind spots):** `test_22` does not pin jitter behavior — the task brief's suggested "unjittered delay" mutation is *not* caught, because pure exponential growth still satisfies `j1 > j0`. Boundedness and determinism are likewise unasserted. `test_21` has no negative-prefix case, so a bypassed prefix check is invisible. Suggested follow-ups (for the branch owners, not blockers): assert a specific expected value (e.g. `calculate_jitter(1, base_delay=0.1) == 0.21`), cap-bound (`<= max_delay + 0.02`), and one invalid-prefix assertion (`valid_prefix is False`).

## 6. Integration warning

**Finding F2 (guaranteed merge conflict):** `git merge-tree --write-tree 9ec79db d566898` reports `CONFLICT (content)` in **both** `agent_branches/client.py` and `tests/test_client.py` (conflict tree `7cb2195813a099476f608ffdb18b89a08f39dba0`). Both commits append at the same anchor (end of class / before `__main__`). Resolution is mechanical — keep both helpers and both tests — but must be done by hand, and the integrator should re-run both suites afterwards.

**Finding F3 (minor robustness note, beta):** attempts ≥ ~1024 raise `OverflowError` (`int too large to convert to float` from `base_delay * 2**attempt`) instead of capping at `max_delay`. Unreachable with sane retry caps; optionally compute `min(base_delay * min(2**attempt, cap_exponent), max_delay)` or short-circuit when `delay >= max_delay`.

## 7. Invariants and method

- **Memory:** all test runs under `ulimit -v 1500000` (1500 MB cooperative cap).
- **Zero Rust builds, zero global installs, zero dependency changes.**
- **No secrets:** helpers were exercised with synthetic tokens only; report contains hashes, paths, and measured numbers only.
- **Workspace:** verification ran in disposable worktrees `.local/scratch/zcode-rev-9ec-d56/{base,alpha,beta}` (detached HEADs at the exact commits); sources restored byte-identical after every mutation; scratch to be removed after publication.
- **Reproduction:** `git fetch origin proto/actor-alpha-maintenance proto/actor-beta-maintenance`, then per-commit `python3 -m unittest -v tests/test_client.py`; mutation diffs are single-line `sed` substitutions as described in §5.

## 8. Amendment (2026-10-04, C1571 challenge) — both challenges CONFIRMED

Antigravity-head challenged the review (aplexer 01a104d0). Both challenges reproduce empirically; the original review under-tested both helpers (synthetic prefixes only, no cap-bound assertion). Verdict remains PASS WITH FINDINGS, now with two confirmed defects added (F4, F5).

**F4 (alpha, real-token false negative — CONFIRMED).** `inspect_token_metadata("art_v1_da4f4519")` → `{'valid_prefix': False, 'segments': 3, 'length': 15}` at 9ec79db. `art_v1_` is a genuine coordinator-minted token prefix (documented across `research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`, `research/antigravity/dogfood/WARNING-CONSUMER-RESOLUTION-REPORT.md` on origin/main, which records this exact defect and its fix in a later lane). `git grep art_v1_ 9ec79db` finds no occurrence in these commit trees — the prefix whitelist predates knowledge of real tokens. Impact: real coordinator tokens are flagged invalid by a helper whose result key reads as a validity verdict. Mitigant (unchanged from §2): the helper is formatting-only and nothing in these commits feeds it an authorization decision.

**F5 (beta, cap and input-validation gaps — CONFIRMED).**
- Cap violation: `calculate_jitter(8)` at defaults = **2.02 > max_delay 2.0** — jitter (0.01·(attempt%3)) is added *after* the `min(max_delay, …)` cap, so the documented bound does not hold for the returned delay.
- `base_delay=-1` → returns `-1.0`; `max_delay=-5` (attempt 3) → returns `-5.0` (`min` selects the negative cap). Negative delays are returned without any validation.
- Non-finite: `max_delay=nan` → returns `nan` (propagates); `base_delay=nan` → silently returns `max_delay`+jitter (`min` drops NaN comparisons). No finite-input guard.

**Kill log — suite does not guard either defect (worktrees restored byte-identical after each):**

| Check | Mutation | Result |
|---|---|---|
| K1 (alpha) | add `art_v1_` to the prefix whitelist | `test_21` **still OK** — suite does not pin the prefix list; neither the defect nor its fix is detected |
| K2 (beta) | fold jitter under the cap: `min(max_delay, base·2**attempt + jitter)` | `test_22` **still OK** — cap semantics unpinned; post-restore sanity re-measured 2.02 |

Receipts for the C1571-1 probe and all F5 cases are the literal outputs quoted above, run in `.local/scratch/zcode-rev-9ec-d56/{alpha,beta}` at the exact commit hashes. Combined with §5 this completes the mutation kill log: caught M1, M2; uncaught P1, P2, K1, K2.
