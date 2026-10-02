# G3 signposting-comparison PLAN — neutral brief, same seed, composition only

Owner: `space-bunny-head`, aplexer session `3acb40d2-c915-410e-8ad7-ba466ee62570`, workspace
`/home/alexey/git/cloudflare-agent-git`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
Status: **PLAN ONLY.** No executor launched, no harness written, no mutation outside
`research/space-bunny/` and `coordination/space-bunny.md`, as instructed by control message
`01a0ff02-6838-7a70-bd55-f1070e8db164` (C-BUNNY-RECOVERY-FIRSTUSE2324). Supersedes nothing; this is the
corrected form of the "remove signposting" step I announced in `e75fae3`.

---

## 0. Identity verification (performed first, no overrides)

`aplexer whoami --json` → id `3acb40d2-c915-410e-8ad7-ba466ee62570`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, engine `opencode`, phase `running`,
conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`, `env: {}` (no identity or environment override present).
Matches the required real session and experiment workspace. No mismatch to report.

Original assignment read and ACKed: `01a0fe86-03b1-7f72-831f-0f5da3ed97f2` (C-G3-CORRECTION2124).
Inbox read once and ACKed.

---

## 1. Correction I owe Codex principal, stated precisely

Codex wrote: *"Claimed our Task B must remove invalidate remains incorrect: public wrapper avoidance
alone, actual pair preserves invalidate."*

**Codex is right about the wording, and I withdraw it.** My round-3 message said Codex's Task B "must know
about and remove the `reader.invalidate` call from `put`." That is wrong: a correct Task B **preserves**
invalidation, it does not remove it.

**But the structural conclusion survives, and here is the reasoning so it can be checked.** In
`research/codex/a01-live`:

- `writer.put` is the only caller of `reader.invalidate` (`writer.py:7`).
- `writer.update_many` currently loops over `put`.
- Task B's goal is to avoid that per-item public-wrapper call.

So a Task B that is *both* correct *and* actually optimises has exactly two options: keep calling `put`
(which achieves no optimisation), or write the values directly **and call `reader.invalidate(key)` per
key**. The second is the only real optimisation, and it necessarily references `invalidate`, a symbol
defined in `reader.py` — Task A's file.

Therefore: **the cross-file reference is real; "removal" was the wrong word.** The precise statement is
*"a correct and optimised Task B must reference a symbol defined in Task A's file."* I withdraw "remove" and
keep that. If a correct optimised `update_many` could avoid naming `invalidate` — for example by an
invalidation channel that is not the `reader` module — my structural claim would fail too, and I would
expect that to be pointed out.

This is also a reminder about my own method: I derived that property from **my own reference patch** for
their fixture, and I should have checked whether the fixture forced it rather than whether my patch did it.

---

## 2. What this experiment is, and what it is not

**IS:** a single-variable test of whether *brief signposting* changes whether competent agents produce
omission-class composition failures. Composition only. Same seed, same oracle, same available context.

**IS NOT, explicitly:**
- **Not an uptake/warning pair.** No notice is delivered, no interface is varied, no warning is consumed.
  Codex asked for no another uptake pair and this is not one.
- **Not a new harness.** Reuses the committed fixture and `overlap-check.py` I already own.
- **Not a duplicate of Grok's matched warning pair.** That is Grok's single owned comparison.
- **Not a prevalence or rate estimate.** Two task pairs cannot support one.
- **Not a forced bug.** No prompt describes a defect, and no patch is chosen to fail.
- **Not a new primary direction and not a shortlist position.** No consensus, no SIGNOFF.

---

## 3. Design — signposting as the ONLY variable

Codex's requirement: *"same seed and scope as relevant prior pair; if different fixture, state confounded
rather than signposting causal comparison."* Accordingly this reuses **arm 1** exactly:

| | Arm 1 (already run, signposted) | Arm 3 (this plan) |
|---|---|---|
| Seed commit | `2cf59e1` | **`2cf59e1` — identical** |
| Fixture | `g3-no-symbol-overlap/seed/` | **identical, byte for byte** |
| Oracle | `seed/oracle.py` | **identical** |
| Task A file | `cache.py` only | identical |
| Task B file | `bulk.py` only | identical |
| Available context | same modules, same `store.py`/`wiring.py`/`app.py` | identical |
| Executor | `zcodex exec`, z.ai | same, unless quota forces a change |
| **Brief wording** | **signposted** | **neutral — the only change** |

A different fixture would confound fixture and brief. I am using the same fixture so the comparison is
clean. If the executor family must change for quota reasons, that is recorded as a second variable and the
comparison is downgraded to "not causal".

### Prior arm-1 provenance (for the reviewer)

- seed `2cf59e1755a3f75f7614c2ccb204be4a565d40c9`
- A `685f3f88f65836a289d5d8954884efd025e6dacd`, B `91d1b75258a69773ad5268335309dd8b20a1be3c`
- composition `64c101e` (first attempt, superseded) and the corrected composition recorded in
  `results-real-agents.md`
- outcome: **base PASS, A PASS, B PASS, A+B PASS** — signposted agents were correct
- signposted brief hashes (16-hex prefix of sha256): A `a4fa685945babba1`, B `3ba2898cd229dbbb`

---

## 4. The neutral brief text — exact, reviewable before any execution

Same task, same scope, same available context. **Removed:** every sentence that flags the behaviour under
risk, names the coupling, or asks the agent to reason about file shape. **Kept:** the file-ownership
boundary, the no-installs/no-network rules, the ban on deliberately introducing a defect, and a single
generic preservation clause. Deliberately **not** kept: any invitation to consider "duplicate keys",
"more rows than today", "records the service might produce", or post-write visibility.

> **Task A — bounded read cache**
>
> You are working in a tiny disposable Python project: flat modules, standard library only, no
> dependencies.
>
> You own and may edit: `cache.py`. You must not edit `store.py`, `bulk.py`, `wiring.py` or `app.py`.
>
> `cache.read(key)` currently fetches from the store on every call. Repeated reads of the same key repeat
> that work. Add a small in-process cache so a repeated `read(key)` does not re-fetch a key it already
> fetched. Make the cache bounded to a fixed capacity, choose and name an eviction policy, and leave
> `read(key)`'s signature and its behaviour for keys that were never written as they are.
>
> Preserve existing behaviour. Use ordinary engineering judgement and write the most straightforward
> implementation you can.
>
> Rules: edit only `cache.py` plus a short `cache-notes.md`. No installs, no network, no other files, no
> git remote operations, no new agents. Do not deliberately introduce a defect. Do not claim a check you
> did not run. Make intermediate commits with explicit paths. State what you changed and what you ran.

> **Task B — efficient bulk writes**
>
> You are working in a tiny disposable Python project: flat modules, standard library only, no
> dependencies.
>
> You own and may edit: `bulk.py`. You must not edit `store.py`, `cache.py`, `wiring.py` or `app.py`.
>
> `bulk.write_bulk(items)` currently pays the full cost of a single-row write for every row. Make it
> efficient for the multi-row case. Keep `write_bulk(items)`'s signature, keep `items` possibly empty, and
> keep `read_all(keys)` working as it does now.
>
> Preserve existing behaviour. Use ordinary engineering judgement and write the most straightforward
> implementation you can.
>
> Rules: edit only `bulk.py` plus a short `bulk-notes.md`. No installs, no network, no other files, no
> git remote operations, no new agents. Do not deliberately introduce a defect. Do not claim a check you
> did not run. Make intermediate commits with explicit paths. State what you changed and what you ran.

**Symmetry check before launch:** the two briefs must be isomorphic in length, structure and specificity.
An asymmetry reintroduces the confound. I will diff their section structure and reject the run if one
brief is materially more specific about risk than the other.

---

## 5. Available-context inventory — what each executor can see

Both worktrees are `git archive` exports of seed `2cf59e1` with **`oracle.py` removed**, exactly as in
arm 1, so acceptance stays controller-owned:

```
app.py  bulk.py  cache.py  store.py  wiring.py     (+ cache-notes.md / bulk-notes.md created by agent)
```

Absent for both: `oracle.py`, the other task's brief, the other worktree, any patch of mine, the word
"conflict", "interference", "stale", or "race".

Not given to either: any sibling result, my deterministic reference patches, or any prior arm outcome.

---

## 6. Changed-path composition protocol (the part that failed me before)

Arm 1's first composition **clobbered Task A's work** because I extracted Task B's whole tree, and the
resulting "A+B passes" was a broken harness. Protocol, now fixed and to be followed literally:

1. Create the composition worktree at **A's head commit**, not at base.
2. For each path in `git diff --name-only <seed> <B-head>`, copy **only that path** from B.
3. Never extract a whole tree from the other arm.
4. **Inspect the composed `cache.py` and `bulk.py` and confirm they are the agents' versions** before
   running anything.
5. Record the composition commit SHA and the composition command.

---

## 7. Gates — all required before any executor starts

Re-verified at launch, not carried over:

- `quse zai --json`: `limit_reached: false`, and record the 5h and 7d remaining values in the report.
- Disk: `/` and `/tmp` both above the **8 GiB** floor; measured, not assumed.
- Trial scratch capped at **512 MiB** aggregate; fixture is a few files, so this is not a risk.
- Real Codex launches: **≤15% remaining** gate unchanged and **not applicable here** — these are z.ai
  executors, not OpenAI Codex. Recorded so the distinction is explicit.
- No banked quota resets redeemed.
- Per human26, no fixed two-executor cap. Executor count is chosen by usefulness. **Concurrency is an
  adaptive decision, not a fixed number**, and if two are started the host-contention failure mode below is
  recorded against whichever run it hits.

### Host-contention handling — correcting my overreach

I previously told root "this host cannot reliably start two zcodex executors concurrently." Codex is right
that **one `ThreadPoolBuildError … Resource temporarily unavailable` with 17 `zcodex` processes on the box
is a contention data point, not proof the host cannot start two.** Corrected position: concurrent start is
*permitted and attempted*; on failure, record worker PID, first-tool event, the exact error, the retry
decision, and whether the retry succeeded, then fall back to serial execution and say so. Both arms in
arm 2 eventually completed, one after a serial relaunch.

---

## 8. Measurement and decision rules — pre-registered before execution

Primary: does `A+B` pass or fail under the identical oracle, all four arms.

- **Signposting matters** if the neutral-brief composition FAILS while arm 1's signposted composition
  PASSED. One pair each way; this is a **hypothesis-generating contrast, not a measured effect**, and n=1
  per cell.
- **No difference** if both PASS. Then signposting did not measurably change the outcome in this pair.
- Either way I record the four arm outcomes, both compositions' SHAs, both briefs' hashes, the changed-path
  composition, and the executors' actual model and exit status.
- **Disjointness** re-checked with `overlap-check.py` on the real patches, reporting executable-code
  cross-mention separately from documentation cross-mention, and cross-mention measured against symbols
  **newly defined or behaviourally changed** by the other task rather than pre-existing base API. That last
  refinement is a known open defect in my checker (it false-positived on `export_line` in arm 2) and is to
  be fixed before the run, not during it.

---

## 9. What this experiment will NOT be used to claim

Stated up front so a result cannot be stretched later:

- **No prevalence, rate or reliability claim.** Two task pairs, one model family, one executor per cell.
- **No claim that any comparator or incumbent would miss anything.** No comparator is executed; Collide
  still requires an account and its advertised plugin still 404s.
- **No claim that agents create this class.** Arm 3 tests a brief variable, not agent behaviour in the wild.
- **No product or shortlist conclusion.** Not a new primary, not a slot-six candidate, not a SIGNOFF.
- **If neutral briefs produce the failure**, the honest description is still *"a constructed case our
  fixture and brief can produce"*, and the demo must be labelled as a constructed capability test.

---

## 10. Reproducibility for an independent reviewer — no private environment needed

Everything needed is committed under `research/space-bunny/g3-no-symbol-overlap/`. No `.local` path, no
private env var, no credential, and no absolute host path is required.

```
git clone <this repo> && cd cloudflare-agent-git
BASE=2cf59e1   # seed
# 1. confirm the fixture is byte-identical to what was executed
sha256sum research/space-bunny/g3-no-symbol-overlap/seed/oracle.py
#    expected prefix 94474bce8b8fd48b
# 2. reproduce any arm: export that commit, drop nothing else, run the SAME oracle
git archive <arm-sha> | tar -x -C /tmp/arm && cd /tmp/arm
python3 -B oracle.py          # rc=0 pass, rc!=0 fail
# 3. compose per section 6 only: start at A's head, copy only B's changed paths
# 4. disjointness
python3 -B research/space-bunny/g3-no-symbol-overlap/overlap-check.py <A-repo> <B-repo> $BASE <A-head> <B-head>
```

Executors' own commits are quoted by SHA in `results-real-agents.md`; their private logs stay private and
are **not** required for reproduction.

---

## 11. Status and next owner

Blocked on nothing I can act on unilaterally except the stated precondition: **the zcodex duplicate-exec
live path must be verified before I launch anything.** I have not launched, written a harness, or mutated
anything in this round beyond the owned documentation paths.

Requested handoff at plan completion: Codex principal and Muse reviewer for (a) the neutral-brief symmetry
check in §4 and (b) agreement that §9's claim limits are acceptable **before** execution. Antigravity owns
monitoring actual working/final-idle during the run; I will not manually report idle state.
