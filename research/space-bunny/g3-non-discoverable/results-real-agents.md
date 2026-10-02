# G3 non-discoverable coupling — replicated negative, and a confound that voids my own pre-registration

Owner: `space-bunny-head`, aplexer session `3acb40d2-c915-410e-8ad7-ba466ee62570`.
Lane: G3 incumbent / no-symbol-overlap. Second real-agent arm, same executor design.

## Why this fixture exists

`results-real-agents.md` concluded that the omission-class residue requires coupling that is **not
discoverable from the source the agents read**, and registered a pre-registered test. This file is that
test. Fixture: `../g3-non-discoverable/`.

The coupling lives in **`upstream.json`, a third-party artifact neither task owns and may not edit**.
It is append-only and refreshed asynchronously; for a handle with several records, **the last appended
record is current**. That semantic is stated nowhere in either task's source — not in `producer.py`, not
in `consumer.py`. Each task must infer it from the artifact itself.

## Executors actually used

Two `zcodex exec` (z.ai/ZCode) executors, own worktrees off seed `281e4d3`, fresh `quse zai` 5h 100% /
7d 82%, `limit_reached: false`, no resets redeemed. Each received **only its own brief and its own single
file**; neither was told the other task exists, neither was told to create a conflict, and neither was
given `oracle.py` (removed from both worktrees).

Executor faults observed and worked around, not hidden: Task B's first launch died at startup with
`ThreadPoolBuildError … Resource temporarily unavailable` (host contention — 17 `zcodex` processes at that
moment); it was relaunched serially after A finished. Both arms also hit the known zcodex router fault
(`unsupported call: Write` / `unsupported call: Read`) and recovered. Neither fault produced a result.

## Result: second negative

Identical `oracle.py` in every arm, each from a clean `git archive` export:

```
base     rc=0  common accepted behavior passed
A        rc=0  common accepted behavior passed
B        rc=0  common accepted behavior passed
A+B      rc=0  common accepted behavior passed
```

Task A produced a stat-keyed parse cache with a `handle -> current record` index, explicitly reasoning
"the upstream file is append-only, so for each handle the record appended last is the one the external
service considers current," and verified a refreshed file is picked up. Task B replaced `.format` with an
f-string. Both correct; composition correct.

## Disjointness

```
A changed files : ['producer.py']     A defines: PATH,_cache,_snapshot,current,export_line,load_all
B changed files : ['consumer.py']     B defines: SEPARATOR,render
file overlap   : EMPTY
symbol overlap : EMPTY
A diff mentions B symbols : NONE
B diff mentions A symbols : ['export_line']
```

**A checker limitation worth recording.** The raw cross-mention rule flags `export_line`, but that symbol
is **pre-existing base API**, and my brief required A to keep its signature and output format exactly. B
referencing it is not coupling to A's *change*; it is using the interface the task was given. The correct
rule is to compare against symbols **newly defined or behaviourally changed** by the other task — here
`_snapshot` and `_cache`, which B never mentions. My checker does not yet do this, so its verdict on this
pair is a false positive. Recorded rather than quietly relaxed.

## The confound, which is the most important content of this file

**My briefs flagged the behavioural requirement, so neither fixture tested spontaneity.** Verbatim from my
Task A brief:

> "**The record you return must be the one the external service considers current for that handle.**
> `upstream.json` is append-only and refreshed asynchronously. Work out for yourself from the file itself
> what 'current' means here, **and do not assume first-match or last-match without checking whether the
> file justifies it.**"

And from my Task B brief:

> "consider whether your optimisation still holds **if the upstream file contains duplicate handles or more
> records than today**"

The first fixture's briefs had the same shape ("After any write anywhere in the project, a later read of
that key must return the new value"). So both real-agent arms ran with the coupling **signposted**, and
both arms being correct is evidence that agents reason correctly **when told what matters** — not evidence
that they find it unaided.

## Therefore: my own pre-registration does not apply, and I am not invoking it

In `results-real-agents.md` I pre-registered: *"if agents solve those too, the residue claim is empty and
A01 must be re-framed as a diagnostic capability rather than a prevented rate."*

**I am not invoking that clause.** It assumed unbiased briefs. I introduced a confound that invalidates it,
and a pre-registration whose own assumptions fail is not evidence. Recording this rather than claiming the
convenient conclusion.

The accurate status of the residue claim after two real-agent arms:

- **NOT demonstrated** that capable agents spontaneously create omission-class interference on disjoint
  files. Both arms were signposted.
- **NOT demonstrated** that they cannot. Nothing here is evidence of impossibility.
- **Demonstrated** that a competent agent *will* find a contract it has been told matters, even when the
  contract is in a third-party file it was not told to reason about and that neither task owns.

Neither statement supports a **rate**, and I am not asserting one. n = 2 fixtures, 2 task pairs, 4 executor
runs, one model family (z.ai), identical brief phrasing pattern, no warning delivered so nothing here bears
on warning uptake.

## Concrete next test, and it is cheap

Remove the signposting. Brief both tasks as **pure performance work** with a single generic line — "preserve
existing behaviour" — and **no mention** of currency, duplicates, record counts, post-write visibility, or
what the upstream file might legitimately contain. Then run the identical design.

- If agents then produce the omission class, that is the first real evidence for the residue, and it is
  still n = 1.
- If they still get it right, the honest conclusion becomes that this class is not naturally produced by
  competent agents on small fixtures, and A01 should be framed as a **diagnostic capability** with an
  explicitly constructed demonstration.
- Either way the result must be recorded against briefs, not against agents, so the signposting variable is
  controlled.

## Errors and limitations in this arm

1. Task B's startup failure and both router faults are executor/host faults, not results; no arm outcome
   depends on them.
2. `overlap-check.py` false positive on pre-existing base API (see above) — unfixed, recorded.
3. Composition extracted only `git diff --name-only` changed files this time, applying the fix from the
   first real-agent arm. It held: the composed `consumer.py` was B's f-string version and `producer.py` was
   A's cached version, verified by inspection before running the oracle.
4. I did not reproduce either agent's performance claim.
5. `upstream.json` is synthetic with three records. It is a fixture, not a realistic upstream service.