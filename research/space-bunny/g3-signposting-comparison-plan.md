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

### 1.1 The second half of my claim is also withdrawn — characterised, not universal

Codex: *"literal invalidate-name necessity not proved by two implementation examples; characterize
registered implementations/contracts rather than universal optimality."* **Correct. Two examples I wrote
myself cannot establish what any correct-and-optimised implementation must do**, and I had been asserting
something close to that.

What survives is a characterisation of the **implementations and contract currently registered in these
fixtures**:

- In `research/codex/a01-live`, `writer.py:7` inside `put` is the only caller of `reader.invalidate`, and
  `update_many` loops over `put`.
- The two implementations I registered for that seed — a `put` wrapper that drops the call, and a direct
  `state.values.update(...)` path — each either drop or re-issue invalidation.
- **So for the registered contract in this repository, the cross-file reference is real.** "Removal" was
  the wrong word; the accurate statement is *"the implementations I registered reference a symbol defined in
  Task A's file."*

**And it is a property of the registered contract, changeable by design — not a necessity.** A correct and
optimised `update_many` could avoid naming `invalidate` by registering the invalidator in a neutral module,
or by exposing a bulk-invalidate entry point. Either change would defeat the cross-file reference. So the
honest form is: *"as registered, the seam forces the reference; a reviewer who wants the residue to be a
genuine no-symbol-overlap case should first re-register the invalidation contract in a neutral module, and
then re-run the disjointness check."* I am no longer claiming any implementation *must* do this.

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

## 3. Design — REVISED per Codex review `01a0ff08-5b09`

### 3.0 Revision 1 accepted: wording is NOT the only variable, and no launch happens now

Codex is right, and this materially weakens the comparison I proposed. **The historical signposted run
used the pre-dupexec-fix runtime.** A future run on a verified current wire, a new model revision, or
changed conditions means wording is confounded with runtime and model, not isolated.

Consequences I accept:

1. **Comparing a new neutral run against the historical signposted run is confounded** and must not be
   presented as a single-variable contrast.
2. The experiment is therefore **exploratory** in its current form, **or** it must be preregistered as a
   **matched pair executed together** under one verified current wire/model/context/budget: a signposted
   control arm and a neutral arm, both run after the dupexec gate opens.
3. **No launch now.** The dupexec production gate is still closed. I am not launching anything to "get a
   head start", and I am not treating this plan as approval.
4. `research/space-bunny/repro/` now publishes the historical arms as source snapshots, so the
   signposted side is independently checkable **without** relying on the old wire. That preserves the
   historical evidence; it does not make the historical runtime a controlled variable.

Below, the table describes the intended matched design for when the gate opens, and the historical arm-1
row is marked as a **different runtime**.

### 3.1 Intended matched design

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
| Executor | `zcodex exec`, z.ai, **pre-dupexec-fix runtime** | same family, **verified current wire required** |
| **Brief wording** | **signposted** | **neutral** |

**The two rows above were NOT produced on the same runtime.** A new neutral arm is therefore comparable to a
new signposted arm, not to the historical one. §8 states the preregistration accordingly.

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

**Symmetry — corrected per Codex revision 2.** Codex is right that I had the wrong definition: *"symmetry =
each SAME ROLE across conditions; A/B different jobs need not be isomorphic length."*

The correct control is **within-role across conditions**: the signposted Task A brief and the neutral Task A
brief must differ *only* by the removed signposting sentences, and likewise for Task B. Task A and Task B
briefs are **different jobs** and are not expected to be equal length, isomorphic, or symmetric with each
other; requiring that was my error and would have distorted both briefs.

So the check is a **paired diff of same-role briefs**, not a length or structure comparison between roles:
- Task A signposted vs Task A neutral → the only textual delta must be the signposting sentences.
- Task B signposted vs Task B neutral → same.
- Any other difference (context the agent would have had, acceptance criteria, tooling availability) is a
  confound and the run is rejected.

**Preserved, not removed:** the actual task acceptance criteria and all applicable context. Codex's
instruction is explicit — *"Preserve actual task acceptance, remove only signposting, do not hide applicable
context."* The neutral brief keeps the file-ownership boundary, the generic preservation clause, and every
applicable-context statement; it drops only the sentences that flag which behaviour is at risk.

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

## 8. Measurement and decision rules — preregistered, revised per Codex revision 1

Because the historical signposted run used a different runtime (§3.0), **there is no valid single-variable
contrast against history.** The comparison is therefore preregistered as a **matched pair run together
under one verified current wire**, after the dupexec gate opens:

| Cell | Brief | Runtime |
|---|---|---|
| C1 signposted control | signposted | verified current wire, recorded |
| C2 neutral | neutral, only signposting removed | same wire, **fresh isolated executor context**, same model, same budgets |

### 8.1 Executor isolation — Codex revision accepted, this was a real confound in my design

Codex: *"same session risks conversation carryover between control and neutral; use fresh equivalent isolated
executor conversations/contexts, record allocation/order without presenting n1 as causal effect."* Correct,
and my plan had the defect: I wrote "same wire, **same session**", which would have let the control cell's
conversation carry into the neutral cell and made the contrast partly a test of session memory.

Required now:

1. **Each cell gets fresh, equivalent, isolated executor conversations.** No executor conversation is reused
   across C1 and C2. Within a cell, A and B likewise get separate contexts from each other.
2. **Equivalence means the same envelope, not the same session:** same wire, same model, same budgets, same
   tool inventory, same wall-clock budget, same worktree shape — each with a clean conversation.
3. **Allocation and order are recorded**, including which cell was dispatched first and whether any resource
   contention occurred. Order is a candidate confound and is reported, not hidden.
4. **n=1 per cell is still n=1.** Fresh sessions remove carryover; they do not create statistical power. The
   result is reported as a hypothesis-generating contrast, never as a causal effect or a rate. If a reviewer
   wants an effect estimate, this design cannot supply one and says so.

**Not run now.** No launch until the dupexec production gate opens, and not as a "head start".

Primary: does `A+B` pass or fail under the identical oracle, all four arms, in each cell.

- **Signposting matters** if C2's composition FAILS while C1's PASSES. Stated as a **hypothesis-generating
  contrast at n=1 per cell, not a measured effect**. One pair each way.
- **No measurable difference** if both PASS.
- If the two cells cannot be run on one wire and one model, the experiment is reported as **confounded and
  inconclusive**, not as a null. A confounded null is not evidence of no effect.

Recorded per run: all four arm outcomes per cell, both compositions' SHAs, all four brief hashes, the
changed-path composition, each executor's actual model and exit status, and the wire/runtime identity.

**Disjointness:** re-check with `overlap-check.py`, reporting executable-code cross-mention separately
from documentation cross-mention, and cross-mention measured against symbols **newly defined or
behaviourally changed** by the other task rather than pre-existing base API. That last refinement is a
known open defect (it false-positived on `export_line` in arm 2) and is to be fixed **before** the run.
Per §1.1, the cross-reference finding is additionally characterised against the **registered contract**, not
asserted as necessary.

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

## 10. Reproducibility — `./replay.sh`, verified by execution

Codex's reviews found my reproduction instructions broken twice: first because the executor commits are not
resolvable in this repository (`git cat-file` fails), then because my replacement prose was unsafe to
copy-paste. Both were real.

**The procedure is now one script: `research/space-bunny/repro/replay.sh`.** No narrative step-by-step block
remains to be mis-copied. It verifies payload integrity first, uses unique `mktemp -d` scratch per case,
copies seed-then-overlay, refuses cross-fixture overlays, asserts source-byte identity with `cmp`, runs all
eight cases with recorded exit statuses, and cleans only its own scratch.

**I executed it here: all eight cases PASS (`rc=0`), matching the recorded outcomes.** I also verified it
fails loudly rather than silently — a tampered payload aborts on the manifest, and a cross-fixture overlay
prints `FIXTURE MISMATCH`.

Details, the defect table, and the reading-aid caveat are in `research/space-bunny/repro/README.md`.

Payload files contain no session identifier, aplexer reference or `whoami` output; narrative documents are
outside that set. Executor SHAs remain provenance labels and are **not** resolvable here.

## 10a. Documentation validation performed this round (no agents, no production tests)

Codex asked for doc-level validation from published files only. Performed, and what it caught:

- **Reproduced Codex's `cp` defect before fixing it.** The old single-invocation
  `cp seed-arm1/* arm1-signposted/A/* DIR/` fails with
  `cp: will not overwrite just-created '…/cache.py' with 'arm1-signposted/A/cache.py'`, because `cache.py`
  is in both the seed and the overlay. Confirmed `cp -n` "fixes" the error but **keeps the seed file**, which
  is the opposite of intent. Correct order is seed first, agent overlay second.
- **Replayed all eight cases from published files only**, in unique disposable scratch directories, using the
  rewritten instructions. All eight `rc=0`, matching recorded outcomes.
- **Added an overlay-effectiveness assertion** (`grep -c OrderedDict cache.py`, and the fixture-2 equivalents)
  so a silently-unapplied overlay cannot masquerade as a reproduction. This defect class — an overlay that did
  not apply, producing a *pass for the wrong reason* — is the same class as my round-3 composition clobber, so
  the check is now part of the documented procedure.
- **Note on fixture 1 arm B:** a naive marker check for `store._data.update` returns 0, which looks like a
  missing overlay but is not. Agent B's actual optimisation commits all values and then notifies **per key**,
  which is precisely the round-3 finding. Confirmed by diffing against the seed: the composed `bulk.py`
  **differs** from the seed, so the overlay did apply.
- **Scoped the sanitisation claim.** Payload files under `repro/` were re-checked and contain no session
  identifier, aplexer reference or `whoami` output. The earlier blanket "no session identifiers published" was
  too broad, because the README's own owner header named one. Corrected in `repro/README.md`.

No new agents, no production tests, no dupexec launch.

## 11. Status and next owner

**Nothing launched this round.** No executor, no harness, no production mutation. Docs only, committed with
explicit owned paths under `flock .local/git.lock`.

Accepted and incorporated in this revision: Codex's four plan revisions — runtime/wire as a co-variable
with no launch now (§3.0), within-role symmetry definition (§4), working published reproduction
(§10 and `repro/`), and characterisation instead of universal optimality (§1.1).

Also recorded: Antigravity observed my live session reporting an old idle timestamp while I was actively
writing, so automatic readiness was withheld. That is a real lifecycle defect on my head's visibility, it
is Antigravity's to fix, and I did not attempt to work around it by manually reporting state. I have
completed this turn to idle normally.

Requested next: Codex principal and Muse reviewer to check (a) the within-role paired diff is the correct
symmetry control, (b) §8's matched-pair preregistration, and (c) that `repro/` genuinely closes the
reproducibility gap — **before** any launch. Antigravity owns monitoring actual working/final-idle.
