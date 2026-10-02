# G3 no-symbol-overlap composition test — deterministic arm

Owner: `space-bunny-head`, aplexer session `0066a53b-3675-41da-b6f2-19cd40f5bc68`.
Lane: G3 (incumbent / no-symbol-overlap). Round 3.

## What this is and is not

This is a **deterministic, scripted composition test**. It establishes that a failure class is
**constructible** and, in Codex's case, that their existing seed already exhibits the behaviour. It does
**not** establish that real agents produce it, and it does **not** establish that any external tool fails
to detect it. **No comparator was executed.** See "Comparator status" for why that is not a gap I can
close.

All fixtures here are synthetic, public, dependency-free, and contain no private project or source data.

## Result summary (actual, reproduced locally)

Arms run the **identical** `oracle.py` from a clean `git archive` export of each commit. No arm has a
branch specific to it in the oracle.

| Fixture | base | A alone | B alone | A+B | Disjointness (strict) |
|---|---|---|---|---|---|
| **G3 fixture (this directory, omission class)** | PASS | PASS | PASS | **FAIL** | **PASS** |
| **`research/codex/a01-live` (removal class)** | PASS | PASS | PASS | **FAIL** | **FAIL** |

## Fixture 1 — this directory: the *omission* class

Two tasks, disjoint files, disjoint symbols, coupled **only by a dispatch contract neither task
references**.

- `store.py`, `wiring.py`, `app.py` — base files, **no task may edit them**. `wiring.py` is what installs
  the invalidation contract: `register_listener(cache.invalidate)`.
- `cache.py` — **Task A owns this file only.** Add a bounded read cache.
- `bulk.py` — **Task B owns this file only.** Optimise `write_bulk`.

Task B's plausible optimisation updates the authoritative dict in one pass and issues **one** listener
dispatch for the whole batch instead of one per key. It never imports `cache`, never names `invalidate`,
and never mentions any symbol Task A defines. The bug is an **omission** — a new fast path that silently
does not honour the invalidation contract.

Actual output:

```
base       rc=0  common accepted behavior passed
A-alone    rc=0  common accepted behavior passed
B-alone    rc=0  common accepted behavior passed
A-plus-B   rc=1  AssertionError: second bulk write b must be visible to a reader
```

Disjointness, from `overlap-check.py` (AST-derived top-level symbols + word-boundary cross-mention scan
of each task's own diff):

```
A changed files : ['cache.py']
B changed files : ['bulk.py']
A defines       : ['MAX_ENTRIES', '_cache', 'invalidate', 'read']
B defines       : ['read_all', 'write_bulk']
file overlap   : EMPTY
symbol overlap : EMPTY
A diff mentions B symbols : NONE
B diff mentions A symbols : NONE
RESULT: patches are disjoint by files, defined symbols, and cross-mention.
```

## Fixture 2 — Codex's `a01-live`: the *removal* class

I ran the same procedure against Codex's existing seed (`state.py`, `reader.py`, `writer.py`) and their
own unchanged `oracle.py`, with equivalent reference patches. **Their seed already exhibits the target
shape**, which is a positive result for their pilot design:

```
base  rc=0  common accepted behavior passed
A     rc=0  common accepted behavior passed
B     rc=0  common accepted behavior passed
A+B   rc=1  AssertionError: put must be visible to an existing reader
```

**But it fails the strict disjointness check:**

```
A changed files : ['reader.py']
B changed files : ['writer.py']
file overlap   : EMPTY
symbol overlap : EMPTY
A diff mentions B symbols : NONE
B diff mentions A symbols : ['invalidate']     <-- cross-task symbol reference
RESULT: DISJOINTNESS FAILS - do not claim no-symbol-overlap.
```

Because base `writer.put` calls `reader.invalidate`, Task B's optimisation must **know about and remove
that call**. `invalidate` is defined in Task A's file. So Codex's Task B necessarily references a symbol
owned by Task A.

## The distinction that matters, and the framing challenge it creates

These are two different failure classes, and only one of them supports the G3 claim:

| | *Removal* class (Codex `a01-live`) | *Omission* class (this fixture) |
|---|---|---|
| Files overlap | no | no |
| Symbols defined overlap | no | no |
| B references a symbol defined in A's file | **yes** (`invalidate`) | **no** |
| A dependency/awareness tool could plausibly notice | **plausible** | **not by symbol reasoning** |
| How the bug arises | B deletes a call to A's seam | B adds a path that never honours a contract it does not reference |

**Framing challenge to the team, stated as a challenge and not as consensus:** if A01's demo runs on
Codex's `a01-live` seed, then the demo exercises the *removal* class — which is precisely the case a
symbol- or dependency-aware incumbent is most likely to flag, because the coupling is a visible,
named cross-file call. **A demo on that seed cannot evidence the residue A01 now claims as its novelty.**
To evidence the residue, the demo needs the omission class, which is what this directory provides.

Equally, I am **not** claiming the omission class is invisible to intent-declaration tools. Collide's
`declare_intent` announces "what it plans to touch"; an operator could in principle notice "A will touch
the read path, B will touch the write path." I did not test that and cannot without an account. The
honest statement is narrow: **the omission class has no symbol overlap**, which removes symbol-based
detection as a mechanism; it does not prove all detection fails.

## Two methodology errors I made and corrected, recorded because they change conclusions

1. **Disjointness measured against a merged worktree.** My first check diffed `base..HEAD` in a worktree
   that had already received both merges, so both patches were attributed to Task A and the check
   reported `file overlap: ['bulk.py']` — a false failure. Fixed: the checker now takes **explicit
   `base` and `head` commits per task**. `overlap-check.py` documents why in its own docstring.
2. **Naive substring matching produced a false positive.** Word-boundary test reported that B "mentions"
   A's `read` whenever B wrote `read_all`. Now uses `\b`-anchored identifier matching.

A third error was in a throwaway shell script that committed Task B on top of Task A in one worktree,
producing nonsense arm results (`B rc=1`). Discarded and redone with explicit branches; the table above is
from the corrected run.

## Comparator status — what I could and could not verify

- `https://github.com/lithometric/collide-plugin` — **HTTP 404** via GitHub API and via HTML. This
  matches Claude's and Codex's independent 404 findings.
- `https://github.com/collidemcp` — the organisation named in Collide's own `schema.org` `sameAs` block
  — **does not exist** (`Not Found`).
- `https://api.github.com/users/lithometric` — **exists**: organisation "Lithometric ™", created
  2024-09-25, 28 public repositories. **None is Collide-related**; the list is unrelated projects
  (BlenderBin.com, PeopleNoise.co, cs2club.com, immigration-ai, bellstate, blast-protocol, …).
- `https://mcp.collidemcp.com/mcp` — live; `OPTIONS` returns 200, an unauthenticated `initialize`
  returns **401 `{"error":"unauthorized"}`**. I did not register an account, per instruction.

**Therefore: no comparator was executed, and I make no claim about Collide's detection capability or
superiority.** Two things must not be overread:

- A 404 does **not** prove a repository does not exist — a private repository 404s identically to an
  unauthenticated caller. Collide's org may hold it privately.
- The end of the audit trail means "not publicly inspectable without registration", **not** "does not
  work". A hosted service can be fully functional while closed-source.

What *is* established: the one artifact that would let a third party inspect Collide's mechanism is not
publicly resolvable at its advertised URL, the org its own metadata names does not exist, and the hosted
MCP endpoint requires an account. **Our own fixture, by contrast, is inspectable and runnable in full** —
that asymmetry is worth stating plainly in a demo, but it is a statement about inspectability, not about
capability.

## Files

- `seed/` — base fixture (`store.py`, `cache.py`, `bulk.py`, `wiring.py`, `app.py`, `oracle.py`)
- `patch-a-cache.py`, `patch-b-bulk.py` — deterministic reference solutions, each owning one file
- `overlap-check.py` — AST disjointness checker with explicit per-task commits
- `results.md` — reproduced output

Reproduce: export each commit with `git archive` and run `python3 -B oracle.py` in the export.
No network, no packages, no accounts.