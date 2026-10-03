# REV-L4-UI-99C3C97 — Independent review of the L4 review-UI remediation commit

## Reviewer identity

| Field | Value |
| --- | --- |
| Reviewer | `sb-reviewer-ui2` — independent cross-family reviewer (second pass) |
| Session ID | `4a7bee76-9c8a-4f87-813c-2f42bfc60c0e` |
| Parent session | `46fdb644-9b58-4e2f-aab3-9be5e1e33337` (`antigravity-head`) |
| Model route | `opencode-go/space-bunny-free` |
| Engine | shell (`opencode run`) |
| Dispatched by | `antigravity-head` |
| Reviewed worktree | `/home/alexey/git/agent-branches-l4` |
| Branch | `proto/l4-review-ui` |
| Reviewed commit | `99c3c975270637f2f7cb112bba6afdf14e239f64` |
| Commit subject | `fix(ui): address Space Bunny review findings (dead code, zero green badges on 503, scratch guard)` |
| Prior review | `REV-L4-UI-3568780.md` (verdict `REQUEST_CHANGES`, on `3568780`) |
| Review date | 2026-10-03 (Europe/Berlin) |
| Review declaration | `a work join /home/alexey/git/agent-branches-l4 --task "review-ui-99c3c97" --mode review --paths "prototype/ui/**" --paths ".gitignore"` |

Base state during review: `git status --short` empty; `HEAD = 99c3c97`.

Files in scope (all changed by the commit):

```
.gitignore                                       sha256 f95b56e63f548b074faffd026ba50fc8c529945331f2eb105f06820d2a07dd35
prototype/ui/tests/test_dom_negative_browser.py  sha256 c425064f68c5db75fed313d25871fb1b3ada8f80944cc4cef70a00190ae57df2
prototype/ui/ui.js                               sha256 b376b0d47c149a2a602a966fafbdb3e321c7605714023ad7c696bb78e8ea6d4c
```

## Verdict

**ACCEPT**

All four findings raised in `REV-L4-UI-3568780.md` are genuinely fixed, and — unlike
the previous commit — the mechanisms are real and test-enforced rather than merely
asserted. I reproduced the exact defects the prior review alleged, confirmed they are
gone, and confirmed by mutation that the new negative assertions actually fail when
the behaviour regresses.

Two mutants survived. **Neither is a defect introduced by this commit**, both are
coverage gaps that predate it, and neither blocks acceptance. They are recorded below
as follow-ups because one of them (N2) is the most safety-relevant gap found in this
whole review chain: the "not the latest change" verdict could silently invert and no
test would notice.

One informational precision correction (N3): the invariant as worded in the dispatch
and commit subject is slightly stronger than what the code and tests actually enforce.

## Baseline test results (restored tree)

| Suite | Command | Result |
| --- | --- | --- |
| Browser negative E2E | `python3 -m unittest -v prototype/ui/tests/test_dom_negative_browser.py` | **5/5 OK** (2.0s) |
| Node unit suites | `node --test prototype/ui/tests/*.test.js` | **48/48 pass, 0 fail** (270ms) |

Total 53 assertions-bearing tests, all green. Re-run after every mutant restoration to
prove restoration is functional and not merely byte-level.

Note on methodology: an initial attempt with a manual `ulimit -v 1572864` killed
Chromium with `SIGTRAP` (virtual address space limit — `chrome-headless-shell` maps far
more VA than its RSS). The 1500M cap is already enforced by the aplexer container
(`limits.memory_bytes: 1572864000`, `containment_cgroup` in `aplexer whoami --json`), so
imposing it again in the shell is wrong. Recording this because anyone else
reproducing this review with a shell memory cap will hit a false red baseline.

## Mutation results

Mutations were hand-applied as bounded single-line edits, each immediately restored
with `git checkout --` and verified by sha256 against the baseline digests above, plus
`git diff --stat` empty. No mutant was left in place.

| ID | Mutation | Target test | Observed | Result |
| --- | --- | --- | --- | --- |
| **M1** | `resultBadge`: stale + passed emits `.badge.clean` instead of `.badge.not_checked` "Passed (unconfirmed)" | `test_04` FAIL | `AssertionError: 1 != 0 : Zero green clean badges during outage on task view` | **KILLED** |
| **M6** | `default_scratch = "/tmp/foo"` (run with `TMPDIR` unset so the default is used) | `test_05` FAIL | `AssertionError: False is not true : default_scratch /tmp/foo must end with .local/scratch`; `/tmp/foo` was actually created | **KILLED** |
| **M7b** | `matchesHead` forced to `false` | non-`stale` path exercised | `test_04` FAIL: `'(the latest change)' not found in '... (an older change, not the latest) ... There is no passing test run for the latest change, so this change is not proven safe.'` | **KILLED** |
| **M7a** | `matchesHead` forced to `true` (own probe) | non-`stale` path | all 5 Python + 48 Node tests **pass** | **SURVIVED** → N2 |
| **M6b** | inherited `TMPDIR=/tmp` with pristine source (own probe) | `test_05` | `scratch_dir` resolves to `/tmp`, `test_05` **PASSES** | **SURVIVED** → N1 |

M1/M6/M7b killed = 3/3 of the dispatched mutants. `test_04` is the sole killer for
`evidenceHtml` — under M1, tests 01/02/03/05 all still passed. That is expected and
worth stating plainly: the node suites never load `ui.js`, so `evidenceHtml` has
**Playwright-only** coverage (confirmed by grep: no `evidenceHtml` reference in any
`*.test.js`; `not_checked` appears in `pair-status.test.js` but refers to a different
pair-status concept).

M6b was evaluated by importing the module with `TMPDIR=/tmp` and evaluating
`test_05`'s two assertions directly, deliberately avoiding a browser launch so the probe
itself did not write into `/tmp`. Evidence:

```
env TMPDIR      = /tmp
default_scratch = /home/alexey/git/agent-branches-l4/.local/scratch
scratch_dir     = /tmp
test_05 result  = PASSED   => M6b SURVIVED
```

## Remediation verification

### F1 — dead `!stale &&` prefix removed from `matchesHead` — CONFIRMED FIXED

`prototype/ui/ui.js:631` now reads `var matchesHead = !currentHead || !ev.head || ev.head === currentHead;`.

The removal is semantically safe, and I confirmed the deadness claim rather than
assuming it. `matchesHead` has exactly two consumers, both ternaries gated on `stale`:

- `ui.js:645-649` — `stale ? "(live status unconfirmed …)" : (matchesHead ? "(the latest change)" : "(an older change, not the latest)")`
- `ui.js:656` — `stale ? … : (!matchesHead || !passed ? … : "")`

When `stale` is truthy both take the `stale` arm, so under the old
`matchesHead = !stale && (…)` the variable was a constant `false` that nothing read —
genuinely dead. When `stale` is falsy it is load-bearing, which **M7b proves
empirically**: forcing it `false` flips both the "the latest change" text and the
"Unknown — not safe" verdict, and `test_04` catches it. The fix is correct and
load-bearingness is now regression-protected.

### F2 — zero green badges during a 503 outage — CONFIRMED FIXED, and structurally stronger than claimed

`resultBadge` (`ui.js:633-639`) splits on `stale`: stale + passed yields
`.badge.not_checked` "Passed (unconfirmed)"; stale + failed yields `.badge.unknown`;
both non-stale arms keep the previous behaviour.

Beyond the mutation result, I checked the stronger structural property:

```
grep -n "badge clean" prototype/ui/ui.js
  638:          ? "<span class='badge clean'>Passed</span>"
```

Line 638 is the **only** green-badge emission in the entire 36.6 kB `ui.js`, and it
sits inside the non-`stale` arm. Zero green during outage is therefore enforced by
construction, not merely by the happy path of a conditional — there is no second
emission site that a future edit could accidentally leave unguarded. The remaining
`.badge.*` emissions are `unknown` (7), `not_checked` (4) and `conflict` (1).

The replacement class is also correct visually: `.badge.not_checked`
(`style.css:110-114`) is `background: transparent` with a grey border and grey text —
neutral, and explicitly not green. "Passed (unconfirmed)" therefore reads as a
downgrade rather than a pass, and the state is written out in words with colour
secondary, matching the file's own comment at `style.css:96`.

### F3 — `test_05_scratch_directory_pinned` + `TMPDIR` moved into `setUpClass` — CONFIRMED FIXED (with a gap, N1)

`test_05` exists at `test_dom_negative_browser.py:418-422` and killed M6 on the exact
intended assertion. The M6 probe also demonstrated the real-world consequence: the
mutant made `setUpClass` create `/tmp/foo` and point Playwright's chromium profile
directory there — genuine `/tmp` growth. I removed it with a literal path
(`rm -rf /tmp/foo`, no `$`/glob in the target, per the standing removal policy) and
verified `/tmp/foo` no longer exists.

Moving `os.environ["TMPDIR"] = scratch_dir` out of module import into `setUpClass`
(`:151-152`) is a real improvement: import no longer mutates process-wide environment
as a side effect, so merely importing the module cannot redirect another test's temp
files. The baseline run confirms Playwright still lands inside the repo scratch
(`.local/scratch/playwright_chromiumdev_profile-*`) and `/tmp` listing was unchanged
across a full run.

The limitation is that `test_05` asserts a *source-derived constant* rather than
observable behaviour — see N1.

### F4 — `.gitignore` cache patterns — CONFIRMED FIXED

```
 8  __pycache__/
 9  *.pyc
10  .pytest_cache/
```

All three are active (`.gitignore:10` matches `prototype/ui/.pytest_cache/V/cache/lastfailed`;
`.gitignore:8` matches `prototype/ui/tests/__pycache__/x.pyc`) and non-destructive:
`git ls-files | git check-ignore --stdin --no-index` returns empty (no tracked file is
shadowed by a new pattern), and no tracked path lives under a cache directory. This
matters here because both `prototype/ui/.pytest_cache/` and
`prototype/ui/tests/__pycache__/` genuinely existed on disk before the fix — the
patterns are load-bearing, not speculative.

## Follow-ups (non-blocking)

### N2 (Medium, coverage) — the "not the latest change" verdict has zero coverage

M7a forces `matchesHead = true`, which makes an **outdated** test run report
"(the latest change)" and *suppresses* the "Unknown — not safe / There is no passing
test run for the latest change, so this change is not proven safe" verdict. All 53
tests pass.

Cause: the mock fixture always has `testEvidence.head == currentHead`. In
`test_dom_negative_browser.py:117-132` the agent head and evidence head are both
`aaaa…`, and `currentHead` is derived at `ui.js:507` as
`heads[agent.agentId] || agent.head || null`, which also resolves to `aaaa…`. The
`!matchesHead` arm of the non-stale path is therefore never rendered.

This is the branch that decides "an older test run does not certify the current
change" — the core safety claim of the whole UI. A regression that inverted it would
be completely invisible.

Suggested fix (small): add a second fixture agent/task whose `testEvidence.head`
differs from `currentHead`, and assert under a 200 status that `#evidence` contains
"(an older change, not the latest)" and exactly one `.badge.unknown`.

### N1 (Low, coverage) — `test_05` asserts a constant, so an inherited `TMPDIR` defeats it

`test_05` checks `default_scratch` — the *fallback* constant — never the effective
`scratch_dir`, and never the `TMPDIR` actually installed by `setUpClass`. Because
`scratch_dir = os.environ.get("TMPDIR", default_scratch)` (`:34`) honours an inherited
value, any shell or CI that exports `TMPDIR=/tmp` makes the suite create and use
`/tmp` while `test_05` still passes (demonstrated above as M6b). The guard is real for
the mutation it was written against, but it does not hold the invariant it names.

Suggested fix: assert the effective value, e.g. `self.assertEqual(scratch_dir, default_scratch)`
or `self.assertTrue(os.environ["TMPDIR"].startswith(os.path.join(UI_DIR, "../../.local")))`
inside a test body (so `setUpClass` has already installed it).

### N3 (Informational, wording) — "zero green badges anywhere in the DOM" is overstated for the index page

The true, tested invariant is **zero *dynamic* `.badge.clean` badges**. `index.html:82`
carries a static documentation legend swatch `<span class="badge clean">Clean — tests
ran</span>`, which `test_01:214` deliberately preserves and asserts
(`assertEqual(page.locator(".legend .badge.clean").count(), 1, "Static documentation
legend swatch preserved")`). That is a sound design choice — a legend swatch is not a
status claim — but the commit subject and dispatch phrasing should say "zero dynamic
green badges", not "zero anywhere in the DOM across both index and task pages". On the
task page (`#evidence`) the count genuinely is zero, which is what `test_04:396` checks.

No code change recommended; wording precision only.

### N4 (Informational, style) — duplicated branches introduced by the fix

`resultBadge` repeats the `.badge.unknown` "Failed — exit …" arm verbatim in both the
stale and non-stale halves (`ui.js:636` and `:639`), where it could be hoisted above
the ternary. Likewise the "Unknown — not safe" paragraph exists twice at `ui.js:654`
and `:657`. Both are harmless duplication; flagging only so it is not mistaken for
intentional divergence later.

## Invariant checks

| Invariant | Method | Result |
| --- | --- | --- |
| Native provenance first | `aplexer whoami --json` as first action | PASS — tag `sb-reviewer-ui2`, parent `46fdb644`, engine shell, `memory_bytes: 1572864000`, containment cgroup present |
| Work declared | `a work join … --mode review --paths "prototype/ui/**" --paths ".gitignore"` | PASS — declared before touching files; review mode is non-exclusive, so no overlap with `antigravity-head`'s `prototype/**` edit declaration |
| TMPDIR confined to `.local/scratch/` | `TMPDIR` set to repo scratch; `/tmp` listing diffed before/after a full run | PASS — `NO /tmp GROWTH`; Playwright profile written to `.local/scratch/` |
| No stray `/tmp` residue from mutation | M6 probe created `/tmp/foo`; removed with literal path and re-checked | PASS — `/tmp/foo` absent |
| Memory cap 1500M | `aplexer whoami --json` `limits.memory_bytes` | PASS — 1572864000 = 1500 MiB, enforced by aplexer containment. Do **not** also impose `ulimit -v` (see baseline note) |
| Working tree byte-identical to `99c3c97` | sha256 of all 3 changed files vs baseline digests; `git diff 99c3c97 --quiet` | PASS — `EXACT_MATCH_CONFIRMED`, all three digests match |
| Clean `git status` | `git status --short` after every restoration and after the final full run | PASS — empty throughout, including after test runs |
| Tests do not dirty the tree | `git status --short` after full Python + Node run | PASS — `TREE_CLEAN_AFTER_RUNS` |
| Secrets redacted | `git show 99c3c97 \| grep -iE "token\|secret\|api[_-]?key\|password\|bearer\|authorization\|CF_\|ACCOUNT_ID"` | PASS — no matches |
| Nothing deployed to Cloudflare | reviewed file list; no `wrangler`/`deploy`/`publish` artifacts | PASS — commit touches only `.gitignore`, the test file, and `ui.js`. **Public deploy remains HELD; this review performed and authorized no deployment.** |
| Recovery path intact | HEAD unmoved at `99c3c97`, no reset/force/rebase | PASS — plain `git checkout --` of tracked files only |

## Recommendation

Accept `99c3c97` and let the lane proceed. The three dispatched mutants were killed by
the exact assertions written for them, and F2 is stronger than requested — zero green
during outage is structural, since `ui.js:638` is the only green emission and it is
gated on `!stale`.

Before this UI is treated as demo-ready, file N2. A demo that shows a stale test run
being correctly rejected as "not the latest change" is currently unbacked by any test,
and that is the single most quotable safety claim the product makes. N1 and N3 are
cheap and can ride along with it.