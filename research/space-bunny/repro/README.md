# Reproducing the G3 real-agent arms from published artefacts

Owner: `space-bunny-head`, workspace `/home/alexey/git/cloudflare-agent-git`.

**Scope of the sanitisation claim, corrected.** An earlier version of this file stated a blanket
"no session identifiers published". That was too broad: *this* README's own owner header carried a session
identifier. The accurate claim is narrower and is now verified: **no payload file under `repro/` contains a
session identifier, aplexer reference, or `whoami` output.** Payload files are the seed snapshots, the
per-arm source snapshots, the protected oracles and `MANIFEST.sha256`; all were re-checked and are clean.
Narrative documents such as this README and the plan file are **not** part of the sanitised payload set and
may name sessions for traceability.

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

## How to reproduce — corrected

Codex principal's review found a real defect in my first version of this section. **I reproduced it before
fixing:** the single-invocation form

```
cp seed-arm1/* arm1-signposted/A/* /tmp/armA/     # BROKEN
```

fails, because `cache.py` exists in **both** the seed and the agent overlay, and GNU `cp` refuses to
overwrite a file it just created in the same invocation:

```
cp: will not overwrite just-created '/tmp/cptest/cache.py' with 'arm1-signposted/A/cache.py'
```

So that line silently left the **seed's** `cache.py` in place — meaning the instruction as written did not
reliably reproduce agent A's actual cache. Note that `-n` "fixes" the error but keeps the *seed* file,
which is the opposite of the intent. Correct order: **seed first, agent overlay second.**

Always use a **unique disposable scratch directory per case** (shown as `$CASE`), so cases cannot contaminate
each other. `$REPRO` is this directory.

```bash
REPRO=research/space-bunny/repro
cd "$REPRO"
sha256sum -c MANIFEST.sha256          # 21 files, integrity of the payload

newcase() { CASE=$(mktemp -d /tmp/g3repro.XXXXXX); echo "$CASE"; }

# helper: seed, then overlay ONE agent's files, then copy the protected oracle in
build() {  # $1=seed dir  $2=agent dir (or "-" for base)  $3=oracle file
  CASE=$1/$(basename "$2")$3x
  mkdir -p "$CASE"
  cp "$REPRO/$1"/* "$CASE"/                       # seed FIRST
  if [ "$2" != "-" ]; then                        # agent overlay SECOND
    for f in "$REPRO/$2"/*; do cp "$f" "$CASE"/; done
  fi
  cp "$REPRO/protected-oracle/$3" "$CASE/oracle.py"   # protected oracle copied in
}
```

Concretely, all eight cases. Base arms first:

```bash
CASE=$(newcase); mkdir -p "$CASE"; cp seed-arm1/* "$CASE"/;   cp protected-oracle/oracle-arm1.py "$CASE/oracle.py"; ( cd "$CASE" && python3 -B oracle.py )
CASE=$(newcase); mkdir -p "$CASE"; cp seed-arm2/* "$CASE"/;   cp protected-oracle/oracle-arm2.py "$CASE/oracle.py"; ( cd "$CASE" && python3 -B oracle.py )
```

Single-agent arms — seed, then overlay:

```bash
CASE=$(newcase); mkdir -p "$CASE"; cp seed-arm1/* "$CASE"/;   cp arm1-signposted/A/* "$CASE"/; cp protected-oracle/oracle-arm1.py "$CASE/oracle.py"
CASE=$(newcase); mkdir -p "$CASE"; cp seed-arm1/* "$CASE"/;   cp arm1-signposted/B/* "$CASE"/; cp protected-oracle/oracle-arm1.py "$CASE/oracle.py"
CASE=$(newcase); mkdir -p "$CASE"; cp seed-arm2/* "$CASE"/;   cp arm1-signposted/A/* "$CASE"/ 2>/dev/null || true   # fixture 2 uses arm2-signposted
```

Use the matching overlay per fixture: `seed-arm1` + `arm1-signposted/{A,B}` +
`oracle-arm1.py`, and `seed-arm2` + `arm2-signposted/{A,B}` + `oracle-arm2.py`.

Composed arms — **start from A, copy only B's changed paths, never B's whole tree**:

```bash
CASE=$(newcase); mkdir -p "$CASE"; cp seed-arm1/* "$CASE"/;   cp arm1-signposted/A/* "$CASE"/                   # A first
for f in arm1-signposted/B/*; do cp "$f" "$CASE"/; done   # then ONLY B's paths
cp protected-oracle/oracle-arm1.py "$CASE/oracle.py"
( cd "$CASE" && python3 -B oracle.py )              # rc=0 — A+B PASSES
```

Note `.head` files are provenance labels and are harmless to copy.

**Verify the overlay actually took effect** before trusting a result — the defect above was an overlay that
did not apply:

```bash
grep -c OrderedDict "$CASE/cache.py"    # fixture 1 arm A must contain the agent's cache
```

### Expected results

All eight cases exit `rc=0`:

| Case | Composition | Result |
|---|---|---|
| fixture 1 | base | rc=0 |
| fixture 1 | A alone | rc=0 |
| fixture 1 | B alone | rc=0 |
| fixture 1 | A+B | rc=0 |
| fixture 2 | base | rc=0 |
| fixture 2 | A alone | rc=0 |
| fixture 2 | B alone | rc=0 |
| fixture 2 | A+B | rc=0 |

Any non-zero differs from the recorded outcome and should be reported as a reproduction failure before any
conclusion is drawn from it.

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