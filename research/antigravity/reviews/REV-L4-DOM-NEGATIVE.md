# REV-L4-DOM-NEGATIVE — independent review of C-1399 DOM-negative fix and Playwright suite

- Reviewer: Space Bunny (`opencode-go/space-bunny-free`), session `rev-l4-ui` (aplexer `df0de19e`), independent cross-family reviewer
- Dispatched by: `antigravity-head` (aplexer `46fdb644`)
- Reviewed commits: `a08cfce` "fix(ui): re-render index on status failure and downgrade clean badges to unknown (C-1399)" and `f6516ba` "test(ui): add Playwright live DOM negative browser test suite (C-1399, C-1409)"
- Merge reviewed: `61e00f4` on `proto/live` (Merge `origin/proto/l4-review-ui` into `proto/live`)
- Worktree: `/home/alexey/git/agent-branches-l4`, branch `proto/l4-review-ui`, HEAD = `f6516ba`
- Scope: `prototype/ui/ui.js` (+18/−4), `prototype/ui/tests/generation-guard.test.js` (+51/−4), `prototype/ui/tests/test_dom_negative_browser.py` (+306, new)
- Date: 2026-10-03 (Europe/Berlin)

## Verdict

**REQUEST_CHANGES**

The core fix is correct, and I could not break it. Both halves of the change are independently
mutation-verified: deleting either one makes the new browser suite fail at exactly the assertion
that is supposed to catch it. The Playwright suite is genuinely non-vacuous and is the *only*
layer that gives this fix real behavioural teeth — see "Why the browser layer matters" below, where a
deliberately behaviour-broken build passes all 48 unit tests.

What blocks acceptance is narrow and cheap:

1. A **double-escaping defect introduced by `a08cfce` itself** (`ui.js:462` + `ui.js:469`), proven in a
   live DOM: the pair explanation renders a literal `&amp;` to the user.
2. The dispatch claim **"ZERO `.badge.clean` in dynamic DOM" is not literally true** — the whole-document
   count during an outage is **1**, not 0, because the static legend in `index.html:82` keeps a green
   `Clean — tests ran` swatch on screen during the simulated outage. The test's scoping to `.pair` is
   correct and necessary; it is the *claim* (and any demo narration built on it) that overstates.
3. `proto/live` carries an **unreviewed and untested `renderTask` change** that rode in through the
   reviewed merge (see Area 4). It is outside what I was asked to bless, so I am not blocking on its
   behaviour, but it must not be presented as covered by this review.

Fix (1), correct the wording in (2), and I would accept immediately. None of this argues against the
design; the stale-downgrade approach is the right one.

---

## Test execution (real, on the pinned commits)

```
$ cd /home/alexey/git/agent-branches-l4/prototype/ui && npm test
ℹ tests 48
ℹ pass 48
ℹ fail 0
ℹ duration_ms 340.978827
real 0m0.590s
```

```
$ python3 /home/alexey/git/agent-branches-l4/prototype/ui/tests/test_dom_negative_browser.py
test_01_clean_to_503_downgrade_and_recovery ... ok
test_02_out_of_order_stale_response_does_not_restore_green ... ok
test_03_initial_503_no_last_status_does_not_throw ... ok
----------------------------------------------------------------------
Ran 3 tests in 2.296s

OK
real 0m2.502s
```

Real headless Chromium via Playwright (`chromium` from `~/.cache/ms-playwright`), a real
`http.server` on `127.0.0.1`, and real DOM assertions. Individual timings, run in isolation to rule
out ordering luck:

| Test | Isolated run | Result |
|---|---|---|
| `test_01_clean_to_503_downgrade_and_recovery` | 1.119 s | OK |
| `test_02_out_of_order_stale_response_does_not_restore_green` | 1.612 s | OK |
| `test_03_initial_503_no_last_status_does_not_throw` | 1.271 s | OK |

All three pass both as a suite and individually, so none depends on leftover state from its neighbours.

I left the reviewed worktree pristine: `git status --short` is empty and
`prototype/ui/ui.js` is unchanged (`sha256 33a344f6afed09dff51aa08fe05a2dae730c8fda45b98bd3c995de3ddd33bfca`).

---

## Area 1 — `refresh()` re-render on status failure: **CORRECT**

```js
} else if (!currentTaskId && lastStatus) {
  renderIndex(lastStatus);
  everRendered = true;
}
```

The guard `!currentTaskId && lastStatus` is right in both halves. `!currentTaskId` keeps the task-page
story branch authoritative (the index must not clobber a rendered task story), and `lastStatus` is
required because `renderIndex` dereferences `status.agents` — with no prior good status there is
nothing to downgrade, which is exactly the `test_03` case. Correctly sets `everRendered`, which is what
`doRefresh` uses to decide whether a first-boot failure still needs `showError`.

## Area 2 — `renderIndex()` stale downgrade: **CORRECT, with an escaping defect**

```js
var badgeType = st.type;
var why = st.why;
if (stale && badgeType === "clean") {
  badgeType = "unknown";
  why = why + " · live status could not be refreshed (" +
        esc(stale.error.message) + "); treated as unknown, not clean";
}
```

Downgrading **only** `clean` is the correct minimal change. `conflict`, `not_checked` and `unknown` are
already non-green and need no rewrite, and the appended sentence explains *why* a previously-green pair
is now unknown, which is the honest presentation. Mutating a local rather than mutating `st.type` is
also right, because `st` is the shared `pairStatus()` result.

### BLOCKING — double escaping of the error message (`ui.js:462` vs `ui.js:469`)

`esc(stale.error.message)` is applied when building `why`, and then `why` is escaped **again** at
`ui.js:469` (`"<p class='why'>" + esc(why)`). The banner does not have this problem — `ui.js:182`
escapes once and assigns straight to `innerHTML`. So the same error text renders two different ways.

Proven in a real browser, with an `?api=` value containing an ampersand (entirely realistic for a
gateway/proxy URL):

```
API seen by page: http://127.0.0.1:43423/?tenant=a&region=b

PAIR .why : ... live status could not be refreshed (request failed: HTTP 503 for
            http://127.0.0.1:43423/?tenant=a&amp;region=b/status); treated as unknown, not clean
BANNER    : ... The latest update failed (request failed: HTTP 503 for
            http://127.0.0.1:43423/?tenant=a&region=b/status). ...

double-escaped '&amp;' in pair .why? True
double-escaped '&amp;' in banner?    False
```

The user sees a literal `&amp;`. **Fix: drop `esc()` at `ui.js:462`** — line 469 already escapes the
whole string. This is a one-token change and is the only blocking edit I am asking for.

## Area 3 — "zero green `.badge.clean` in the DOM": **needs the claim corrected**

Measured directly in the live DOM on both sides of the transition:

| State | whole-document `.badge.clean` | `#pairs .badge.clean` | whole-doc `.badge.unknown` |
|---|---|---|---|
| 200 clean | 2 | 1 | 1 |
| 503 outage | **1** | **0** | 3 |

The dynamic/status-rendered behaviour the fix targets is exactly right: `#pairs .badge.clean` goes
1 → 0 and `#pairs .badge.unknown` goes 0 → 1. **Zero green `.badge.clean` in the *dynamic* DOM is true.**

But the whole-document count is **1**, and it is not a test artefact: it is the static explanatory key
in `index.html:82`

```html
<li><span class="badge clean">Clean — tests ran</span> The radar combined both changes …</li>
```

which is present in every build and never re-rendered. The test's use of `.pair .badge.clean` is
therefore the *correct* scoping — scoping it to the whole document would have made the suite
permanently red. My objection is to the wording, not the assertion.

This matters for the competition demo specifically: during the simulated outage the page still shows a
green `Clean — tests ran` swatch in the legend, immediately above an outage banner and an
`Unknown — not safe` pair badge. A judge reading the screen — or grepping the DOM for `.badge.clean` —
sees green and can fairly call it a contradiction. Suggest either restating the claim as
"zero `.badge.clean` in the status-rendered pair list", or giving the legend swatch a non-`clean`
class such as `clean-key` so the class means "a pair is proven clean" and nothing else.

## Area 4 — `proto/live` (`61e00f4`) is **not** byte-identical to what I reviewed

`prototype/ui/ui.js` differs between the two refs, and it is not the C-1399 change:

```
git show 61e00f4:prototype/ui/ui.js | sha256sum   → 8cdc085aa95d4b60e7a74a8c4e201d1167d6776dc537fe79ddd6f464c496c33d
sha256sum prototype/ui/ui.js                       → 33a344f6afed09dff51aa08fe05a2dae730c8fda45b98bd3c995de3ddd33bfca
```

I verified the C-1399 fix itself **did** survive the merge — both halves are present on `proto/live`
(`stale && badgeType === "clean"` at line 457, `!currentTaskId && lastStatus` at line 807). The delta is
an unrelated `renderTask` change that only `proto/live` has:

```diff
-      "<dt>Doing</dt><dd>" +
-      ((task.intent || agent.intent) ? esc(task.intent || agent.intent) : …)
+      (agent.intent ? esc(agent.intent) : …)
-      ((task.base_sha || agent.baseSha) ? shaHtml(task.base_sha || agent.baseSha) : …)
+      (agent.baseSha ? shaHtml(agent.baseSha) : …)
```

i.e. a fallback to task-level `intent` / `base_sha`, with a comment noting `GET /tasks/:id` returns
those at the top level while `/status` agents carry `intent`/`baseSha`. Sensible on its face.

**But it has no test coverage at all:** `grep -rn "task.intent\|base_sha" prototype/ui/tests/*.js`
returns nothing, and the new Playwright suite never loads `task.html` at all (it is `index.html`
only). So the shipped `proto/live` task page renders "Doing:" and "Started from:" differently from the
branch I verified, with nothing asserting it. Not a blocker for C-1399, but it should not be implied
to be covered by this review — it needs its own test or an explicit note.

## Area 5 — Why the browser layer matters (strongest evidence in this review)

I mutation-tested rather than trusting green output. Each mutant is a copy of `prototype/ui` with one
surgical edit, syntax-checked with `node --check` before running.

| Mutant | Edit | `npm test` | Playwright suite |
|---|---|---|---|
| **M1** | delete the whole `if (stale && badgeType === "clean")` downgrade block | 47/48 — **1 fail** | **2 failures** |
| **M2** | delete the `else if (!currentTaskId && lastStatus)` branch in `refresh()` | — | **2 failures** |
| **M3** | keep the condition, change the *effect*: `badgeType = "clean"` instead of `"unknown"` | **48/48 PASS** | **2 failures** |
| M2-invalid | my first attempt, which produced a `SyntaxError` | — | 3 errors (invalid — discarded) |

M1 and M2 failing at exactly the intended assertions is the proof that the suite is not vacuous:

```
AssertionError: 1 != 0 : No green .badge.clean elements may remain in the DOM during 503 outage!
AssertionError: 1 != 0 : Late clean response from older request must NOT restore green badges!
```

**M3 is the finding that matters.** A build where the downgrade runs but assigns `"clean"` — i.e. the
fix is present in form and completely inert in behaviour — passes **all 48 unit tests**. The reason is
that the new unit test `index pair badges: clean badges are downgraded to unknown when live status
fails (C-1399)` in `generation-guard.test.js` **re-implements the downgrade inside the test**:

```js
function computeBadge(agentA, agentB, status, stale) {
  var st = PairLogic.pairStatus(agentA, agentB, status);
  var badgeType = st.type;
  if (stale && badgeType === "clean") { badgeType = "unknown"; … }
  …
}
```

That is a copy of the production logic, so it tests the copy. The only thing binding it to `ui.js` is a
regex tripwire (`assert.match(src, /stale\s*&&\s*badgeType\s*===\s*"clean"/)`), which dead code
satisfies trivially. The unit layer therefore provides **no** behavioural protection here; the
Playwright suite is the sole real gate, and it does catch M3.

Two consequences worth acting on: the new unit test is close to a tautology and should either call the
real `renderIndex` or be dropped in favour of the browser test it duplicates; and the tripwire's
regex-based coupling will keep passing through no-op rewrites.

**Process note, recorded for honesty:** my first M2 attempt deleted the `else if` without preserving the
preceding `if` block's closing brace, so the mutant was a `SyntaxError` and all three tests "errored"
merely because `ui.js` never loaded. I discarded that result, re-derived a syntactically valid M2,
verified it with `node --check`, and only then recorded the numbers above. The table contains no
results from the invalid mutant.

## Area 6 — Task view: green "Passed" survives a status outage (pre-existing, non-blocking)

`renderTask` → `evidenceHtml(agent, currentHead, lost)` renders a **dynamic** green badge at
`ui.js:637`:

```js
(passed ? "<span class='badge clean'>Passed</span>" : …)
```

`evidenceHtml` receives no `statusFresh` state and never consults it, so on the task page a status
outage leaves a green `.badge.clean` on screen. Measured on `task.html` with `fixtures/task-0001.json`
(`testEvidence.exitCode: 0`):

```
TASK PAGE, status 200 : #evidence .badge.clean = 1
TASK PAGE, status 503 : #status-error visible  = True
                        #evidence .badge.clean = 1
```

Severity is limited, and I want to be precise rather than alarmist: the evidence block also renders
`Unknown — not safe — There is no passing test run for the latest change`, because the recorded run's
head is older than the current head. So the green "Passed" is a factual provenance statement about one
recorded run, not a claim that the current head is safe.

The sharper residual risk is that `matchesHead` (`ui.js:630`) is computed against `currentHead`, which
`renderTask` derives from `heads` in the **stale** `lastStatus`. If a newer push lands while `/status`
is failing, the page can label a run "(the latest change)" when it is not, and suppress the
accompanying `Unknown` notice. That is pre-existing, outside C-1399's stated scope (index view), and not
a regression from `a08cfce` — but it is the same safety property, and the task page is part of the demo.
Recommend passing `statusFresh.describe()` into `evidenceHtml` and downgrading exactly as the index
does.

## Area 7 — Test hygiene notes (non-blocking)

- **Single-threaded server.** `MockServer` extends `socketserver.TCPServer`, not
  `ThreadingTCPServer`, so requests are served serially while the page polls. `ThreadingTCPServer` would
  remove a class of timing flake.
- **Pages leak on assertion failure.** `page.close()` is the last statement of `test_01`/`test_03`, so any
  failing assertion skips it. A leaked page keeps its poll interval alive and keeps hitting the
  single-threaded server, which cascades into unrelated tests — observed directly: under the invalid M2,
  `test_03` timed out at 5 s waiting for `#loading`, having passed in isolation. Use
  `self.addCleanup(page.close)`.
- **`test_02` mocks `window.fetch`,** so it exercises no real HTTP; it still drives the real
  `genTracker.settle()` and the real `renderIndex()` in a real DOM, so its value is genuine, but it is a
  second-class transport. Its `fetchCount` counter increments on *every* fetch, including non-`/status`
  URLs, so `fetchCount === 1` silently assumes `bootIndex()` fetches nothing else; if that ever changes,
  the delayed/503 assignment shifts and the test would pass for the wrong reason.
- **`test_01` depends on synchronous ordering.** `setStatusErrorView()` (`ui.js:798`) runs *before*
  `renderIndex()` (`ui.js:805`), and the test reads `.pair .badge.clean` as soon as the banner appears.
  This is safe only because both statements run in one synchronous task, so the browser cannot observe
  the intermediate state. It would become racy if the render were ever awaited or deferred.

## Resource-policy compliance (self-reported)

Mid-review I created scratch mutant trees under `/tmp/opencode/` and the
`/private/tmp/claude-501/.../scratchpad` path, both of which are prohibited. Flagged by
`codex-principal` (`01a10337`) and `antigravity-head` (`01a10338`, `01a1033c`); all three acknowledged.
All three `/tmp` directories were confirmed already reaped (zero residue — which also explains the
transient "No such file or directory" errors seen mid-run). Scratch and mutant trees now live under
`/home/alexey/git/cloudflare-agent-git/.local/scratch/rev-l4-ui/` (gitignored via `.gitignore:1 .local/`),
preserving the original mutants for provenance: `m1/` (M1), `m3/` (M3), `probe_esc3.py` (the
double-escape probe). Total 3.6 MB. No pre-existing scratch was deleted.

## Edge cases considered

| Case | Result |
|---|---|
| 200 clean → 503 → 200 recovery | Covered by `test_01`; badge restores, banner hides. Verified. |
| Delayed clean settling after newer 503 | Covered by `test_02`; generation guard drops it, DOM stays unknown. Verified. |
| Initial 503, no prior `lastStatus` | Covered by `test_03`; no throw, error surfaced, zero clean. Verified, and correctly does not depend on the fix (passes under M2 in isolation). |
| Fewer than two agents | `renderIndex` renders the empty-state `<p>`; `pairs` never populated, so the downgrade loop is a no-op. Safe. |
| Zero agents | Same empty-state path. Safe. |
| `conflict` / `not_checked` / `unknown` while stale | Not downgraded — correct, they are already non-green and not overstated. |
| Non-`clean` pair with stale status | Badge unchanged, but the global stale note (`staleNoteHtml`) and the banner still explain the staleness. Correct. |
| Stale while on the **task** page | `renderTask` path re-renders marked stale; index downgrade correctly does not run. Task-view green "Passed" is the Area 6 gap. |
| Error message containing `&` / `<` | **Double-escaped in `.pair .why`** (Area 2, blocking). Banner correct. |
| Repeated `bootIndex()` (as `test_01` does twice) | `startPolling` is guarded by `pollingStarted`, so **no timer leak** — I initially suspected one and verified it is not a defect. |
| Out-of-order where the *newer* request is the clean one | Guard drops the older 503; the newer clean wins. Correct by construction; not explicitly tested. |

## Recommended actions

**Blocking (small):**
1. `ui.js:462` — remove the inner `esc()`; line 469 already escapes. Add a one-line regression
   assertion on an `&`-bearing status URL.

**Should fix:**
2. Restate "zero `.badge.clean` in the DOM" as "zero in the status-rendered pair list", or rename the
   `index.html:82` legend class so green unambiguously means "a pair is proven clean".
3. Get the `proto/live` task-level `intent`/`base_sha` fallback under test (the Playwright suite is
   `index.html`-only), or state explicitly that it is unreviewed.

**Follow-up:**
4. Thread `statusFresh.describe()` into `evidenceHtml` so the task page cannot show a green badge —
   and cannot compute `matchesHead` — from stale status.
5. Replace the in-test `computeBadge` copy in `generation-guard.test.js` with a real `renderIndex`
   call, or drop it in favour of the browser test.
6. `addCleanup(page.close)`; switch the mock to `ThreadingTCPServer`; make `test_02`'s fetch mock count
   only `/status` URLs.

I re-ran every suite against the pristine branch after finishing the analysis; results in "Test
execution" above are from that final clean run.