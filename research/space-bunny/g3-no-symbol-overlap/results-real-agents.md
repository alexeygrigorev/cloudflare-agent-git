# G3 round 3 — real-agent arm: NEGATIVE result, with a mechanism

Owner: `space-bunny-head`, aplexer session `3acb40d2-c915-410e-8ad7-ba466ee62570` (recovered; same
OpenCode conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`). Lane: G3 incumbent / no-symbol-overlap.

Supersedes nothing in `results.md`; this file adds the **real-agent** arm to the deterministic arm.

## Executors actually used

Two `zcodex exec` (z.ai / ZCode) executors, launched separately, each in its own `git worktree` off the
same seed commit `2cf59e1`. Fresh `quse zai` before launch: 5h 100% remaining, 7d 82% remaining,
`limit_reached: false`. Banked resets were **not** redeemed. Private logs mode-controlled under
`.local/space-bunny/g3-agents/`. Each executor received **only its own task brief** and its own
single-file worktree. **Neither was told the other task exists, neither was told to create a conflict,
and neither was given the oracle** — `oracle.py` was removed from both worktrees so acceptance could
only be judged by the controller afterwards.

This is not Grok's pilot, not Codex's `a01-live` harness, and not a second A01 live comparison. It is a
single narrow question: **do competent agents, told only to optimize honestly, spontaneously produce
omission-class interference on disjoint files?**

## Headline result: they did not

Identical `oracle.py`, each arm from a clean `git archive` export:

```
base     rc=0  common accepted behavior passed
A        rc=0  common accepted behavior passed
B        rc=0  common accepted behavior passed
A+B      rc=0  common accepted behavior passed
```

**A+B passes.** Both agents produced correct implementations. Agent A wrote a bounded LRU cache
(`CAPACITY = 128`, `OrderedDict`, `move_to_end`, `popitem(last=False)`) with listener-based invalidation.
Agent B wrote a bulk fast path that commits all values then notifies **once per key**, with a fallback to
the correct single-row path if `store` internals are unavailable.

## The counterfactual proves the test was not vacuous

Same Agent A cache, same oracle, only Agent B's implementation swapped for my deterministic
omission-class B (single dispatch for the batch):

```
rc=1  AssertionError: second bulk write b must be visible to a reader
```

So Agent A's cache is genuinely vulnerable to the omission class. **The class is reachable on real agent
output; these agents simply did not fall into it.**

## Non-vacuity, measured rather than assumed

My first liveness probe was wrong and I corrected it: it counted `store.fetch` calls *after a write*,
which measures invalidation, not caching, and it looked for an attribute name (`_cache`) the agent did not
use. Corrected measurement on the composed A+B tree:

```
1. write b,c in bulk, then read both   -> cache entries {'b': 10, 'c': 20}   POPULATED: True
2. read 'b' again with no write        -> store.fetch calls during that read: 0   SERVED FROM CACHE: True
3. risky second bulk write over b,c    -> cache entries {}  (both listeners evicted)
   read b -> 11  (correct)
4. listeners registered: 2
```

The cache was **live and holding the stale values at exactly the moment** Agent B's optimisation could
have broken it. It did not.

## Disjointness: code is disjoint, documentation is not

Running `overlap-check.py` on the **real** agent patches:

```
A changed files : ['cache-notes.md', 'cache.py']
B changed files : ['bulk-notes.md', 'bulk.py']
file overlap   : EMPTY
symbol overlap : EMPTY
A diff mentions B symbols : ['write_bulk']
B diff mentions A symbols : ['invalidate', 'read']
RESULT: DISJOINTNESS FAILS
```

The raw-text cross-mention check flagged both directions. Inspecting where those mentions occur: **every
one is in a markdown notes file or a docstring, none in executable code.** Stripping docstrings via AST:

```
A cache.py executable identifiers: ['CAPACITY','OrderedDict','_entries','fetch','invalidate','key',
                                    'len','move_to_end','pop','popitem','register_listener','value']
B bulk.py  executable identifiers: ['data','fetch','fn','getattr','items','k','key','keys',
                                    'listeners','store','value','write']
```

Neither references the other's symbols. **The code is disjoint; the reasoning is not.** My
scripted reference patches had no cross-mention anywhere, including prose.

## The mechanism behind the negative result — and the framing challenge it forces

This is the finding I consider most important, and it is not in the headline table.

Agent B's own notes describe what it did:

> "a scratch script against `store`/`wiring`/`app` with a **memoizing cache patched over `cache`**
> (memoizing `read`, real `invalidate`, registered before wiring import) … the stale-read trap; notification
> keys recorded matched the batch exactly"

**Agent B did not avoid this bug by luck or by luck of a strong model. It avoided it because it explicitly
modelled a memoizing cache and tested its fast path against it.** It inferred the cache's existence from
`store.py` and `wiring.py` — base files it was required to read — and reasoned about the invalidator
contract in prose.

So the negative result has a mechanism, and it is a mechanism that applies to any agent worth having:

> **The no-symbol-overlap residue is not "two patches that share no executable symbol." It is two patches
> that share no executable symbol AND whose coupling is not discoverable from the source the agents read.**

My fixture tested only the first half of that. `wiring.py` is a base file in the seed that both executors
read, and it states the invalidation contract explicitly. **So my fixture's coupling was discoverable, and
capable agents found it.** Calling this "no-symbol-overlap" was, in the round-2 framing, a weaker and
slightly misleading label for what the experiment actually exercised.

### What this does to A01's novelty thesis

Round 2 I proposed Gate 3 as "≥3 task pairs where `check_collisions` returns no collision." **That gate is
not sufficient and I am withdrawing it in this form.** A pair with no symbol overlap that both agents can
discover from the source is not evidence of an uncovered residue — this run is the counterexample: code
disjoint by every mechanical measure, and both agents handled it correctly.

For the residue to be real, the coupling must be invisible in what the agents read. Candidate couplings
that are genuinely not in either task's source:

1. **Producer/consumer across a service or repository boundary.** A changes a response field's semantics; B
   consumes it. Neither file names the other; the contract lives in a schema, a spec, or another repo.
2. **Time or feature-flag window.** A assumes a flag is on; B assumes it is off. Individually correct.
3. **Documented-but-unread contract.** The rule exists only in a README/spec the agents are not given — the
   honest version of "an omission nobody can see", without seeding a defect.
4. **Operational assumption.** A assumes batch size ≤ N; B now emits N+1.

### The honest demo consequence, which cuts against the lane

If agents do not spontaneously produce the omission class on a discoverable contract, then a demo that
**seeds** such a fixture is demonstrating a capability, not measuring a rate — which is exactly the
dishonesty Pro-2 warned about ("a deliberately faulty fixture … must not be presented as a naturally
occurring failure from a live agent run"). The lane needs to either find a coupling class that agents
genuinely miss, or **label the demonstration as a constructed capability test** and stop implying agents
create this at an observable rate. Neither of my runs supports a rate claim. One trial, one fixture, two
executors, one model family.

## Errors I made in this round, all of which changed or nearly changed conclusions

1. **Composition clobbered Agent A's work.** I extracted Agent B's **entire tree** over the composed
   worktree, which overwrote `cache.py` with B's unmodified base copy. Result: `cache.py` was the
   pass-through, `cache._cache` did not exist, and **A+B "passed" for the wrong reason.** The first
   corrected run still showed `CACHE LIVE: False`; the composed `cache.py` proved the cause. Fixed by
   extracting **only `git diff --name-only` changed files**. A negative result that was really a broken
   harness — and it would have been very easy to publish as a finding.
2. **`git worktree add` refused the reused branch name**, leaving a half-built tree; `rm -rf` of the
   directory without `git worktree prune` made the next attempt fail with a confusing "not a git
   repository". Rebuilt under a fresh branch name after pruning.
3. **Liveness probe measured the wrong thing** and used a non-existent attribute name (see above).
4. **`overlap-check.py` crashed on markdown.** It AST-parsed every changed file, and Agent A's
   `cache-notes.md` contains an em-dash, raising `SyntaxError`. Fixed to parse only `.py`. Also had to
   restrict cross-mention scanning to code, because prose cross-references produced a misleading
   "DISJOINTNESS FAILS".

Every one of these was caught by instrumenting rather than trusting, which is the only reason the headline
result is trustworthy.

## Comparator status unchanged

No comparator was executed and I make **no claim** about Collide's detection capability or about our
superiority. `github.com/lithometric/collide-plugin` → 404 (matching Claude's and Codex's independent
checks). `github.com/collidemcp`, the org named in Collide's own `schema.org` `sameAs` → does not exist.
`lithometric` exists but has 28 public repos, **none Collide-related**. `mcp.collidemcp.com/mcp` → live,
`OPTIONS` 200, unauthenticated `initialize` → **401**, and **no account was created**.

A 404 does not disprove a private repository. The end of the audit trail means *not publicly inspectable
without registration*, **not** *incapable*.

## Capability limitations of this experiment, stated plainly

- **n = 1 pair, 2 executors, one model family (z.ai).** No prevalence, no reliability, no rate.
- Both executors ran the same brief wording and the same seed, so shared phrasing cannot be excluded as a
  cause of both solving it.
- Executors had no oracle, so each self-verified. Their own scratch checks were reported honestly by both
  (Agent B even corrected its own miscalibrated benchmark numbers in a later commit).
- The composition test only shows the **combined tree passes**; it does not test whether an early warning
  would have changed anything, because no warning was delivered.
- I did not measure whether Agent B's approach is faster in a way that matters; its benchmark numbers are
  its own, and I did not reproduce them.

## Next owned step (recorded, not awaiting approval)

Build the **non-discoverable coupling** fixture — coupling that is genuinely absent from what either agent
reads — and re-run the same two-executor design against it. Concretely: producer/consumer across a
simulated service boundary with the contract in a schema file neither task is given, plus a flag-window
variant. Pre-register: if agents solve those too, the residue claim is empty and A01 must be re-framed as
"a diagnostic capability" rather than "a rate we prevent". If they miss them, that is the first actual
evidence for the residue, and it will still be n = 1.

Secondary: fold the two checker fixes (`only .py` parsing, code-only cross-mention scanning) into a
reusable form so other lanes' disjointness claims are checked the same way.