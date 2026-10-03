# Reproducing the G3 real-agent arms from published artefacts

Owner: `space-bunny-head`, aplexer session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`.

## Why this directory exists

Codex principal's plan review (`01a0ff08-5b09`) checked my reproduction claims and found them broken:

> "public repro currently fails: root `git cat-file` cannot find full `685f3f88`/`91d1b752` objects, and agent
> worktrees had `oracle` removed, so `git archive` arm→`python oracle.py` is not reproducible from clone."

**That is correct and I verified it before answering.** All six executor commits
(`685f3f88…`, `91d1b75…`, `4432c51…`, `f616255…`, and both seeds `2cf59e1…`, `281e4d3…`) return
`fatal: git cat-file: could not get object info` from this repository. They live in throwaway scratch repos
under `/tmp/opencode/…`, which is outside this repository and is not published. My earlier
"reproducibility" section pointed at `git archive <arm-sha>` and would have failed for any reviewer.

The fixed instruction is: **publish sanitised actual-source snapshots plus full source/tree/oracle hashes,
copy the protected oracle separately.** This directory is that fix. It contains no private env, no
`aplexer whoami` output, no session IDs, no executor logs, and nothing from a `.local` path.

## Layout

| Path | What it is |
|---|---|
| `seed-arm1/` | Agent-visible seed of fixture 1 (`2cf59e1`). **`oracle.py` deliberately excluded.** |
| `seed-arm2/` | Agent-visible seed of fixture 2 (`281e4d3`). **`oracle.py` deliberately excluded.** |
| `arm1-signposted/A/`, `.../B/` | The **actual** sources each executor produced, fixture 1. `.head` records the executor's commit SHA. |
| `arm2-signposted/A/`, `.../B/` | Same for fixture 2. |
| `protected-oracle/oracle-arm1.py` | Fixture 1 oracle, kept **separate** because executors never saw it. |
| `protected-oracle/oracle-arm2.py` | Fixture 2 oracle, same. |
| `MANIFEST.sha256` | sha256 of every other file here, paths relative to this directory. |

The A/B split is preserved because it is the whole point: these are two different agents' outputs, and
composing them is the experiment.

## Verified reproduction, run from these files only

I re-derived every arm from this directory alone, in a scratch directory outside the repo, with no access
to any executor repo. All eight arms reproduce:

```
arm1-signposted  armA  rc=0 common accepted behavior passed
arm1-signposted  armB  rc=0 common accepted behavior passed
arm1-signposted  AB    rc=0 common accepted behavior passed
arm2-signposted  armA  rc=0 common accepted behavior passed
arm2-signposted  armB  rc=0 common accepted behavior passed
arm2-signposted  AB    rc=0 common accepted behavior passed
arm1  base       rc=0 common accepted behavior passed
arm2  base       rc=0 common accepted behavior passed
```

This matches the outcomes recorded in `../g3-no-symbol-overlap/results-real-agents.md` and
`../g3-non-discoverable/results-real-agents.md`. **The negative results stand, and they are now
reproducible from a clone** rather than from my scratch directories.

## How to reproduce

```bash
cd research/space-bunny/repro
sha256sum -c MANIFEST.sha256          # integrity of every published file

# one arm: seed + that agent's actual sources + the protected oracle
mkdir -p /tmp/armA && cp seed-arm1/* arm1-signposted/A/* /tmp/armA/
cp protected-oracle/oracle-arm1.py /tmp/armA/oracle.py
( cd /tmp/armA && python3 -B oracle.py )        # rc=0

# the composition, which is the actual finding: start from A, copy ONLY B's paths
mkdir -p /tmp/AB && cp seed-arm1/* arm1-signposted/A/* /tmp/AB/
for f in bulk.py bulk-notes.md; do cp arm1-signposted/B/$f /tmp/AB/; done
cp protected-oracle/oracle-arm1.py /tmp/AB/oracle.py
( cd /tmp/AB && python3 -B oracle.py )           # rc=0 — A+B PASSES
```

The composition step is written out explicitly because getting it wrong is exactly the error that produced
a false result in round 3: **copying B's whole tree over A's overwrites A's work.** Here A's files and B's
files are disjoint, so the outcome of that mistake would be visible, but the correct procedure is
start-at-A, copy-only-B's-changed-paths.

### Record of the composed arms actually run in round 3

For completeness, and because the executor SHAs are not resolvable from this clone, the compositions
executed at the time were: fixture 1 A `685f3f8…` + B `91d1b75…` → composed `8a1b06c…`; fixture 2
A `4432c51…` + B `f616255…` → composed `2a21c15…`. Both composed trees were verified by inspection before
the oracle ran, and both `rc=0`. The snapshots above are the file-level equivalent.

## What this directory does NOT contain, deliberately

- No executor prompt logs, no private `.local` paths, no `aplexer whoami` or session identifiers.
- No network fixtures, no credentials, nothing from a real user project. All fixtures are synthetic and
  were written for this experiment.
- No claim that the executor SHAs are recoverable here. They are recorded in `.head` as provenance labels
  only; **they are not resolvable in this repository and this document does not imply they are.**

## Relationship to the plan

`../g3-signposting-comparison-plan.md` §10 previously asserted a `git archive`-based reproduction path that
did not work. **This directory replaces that section.** The plan's other revisions are in the same commit.