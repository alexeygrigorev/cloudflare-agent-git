# TASKS.json validator

A command-line validator for this project's coordination task registry
(`coordination/TASKS.json`, cross-checked against
`coordination/TEAM-REGISTRY.json`). Python 3 standard library only; no
third-party packages, no network access.

## How to run

```sh
# Defaults: ./coordination/TASKS.json and ./coordination/TEAM-REGISTRY.json
python3 validate_tasks.py

# Explicit paths (positional or flags, both work)
python3 validate_tasks.py path/to/TASKS.json path/to/TEAM-REGISTRY.json
python3 validate_tasks.py --tasks path/to/TASKS.json --registry path/to/TEAM-REGISTRY.json

# A directory argument is treated as the repository root and the tool reads
# <dir>/coordination/TASKS.json and <dir>/coordination/TEAM-REGISTRY.json
python3 validate_tasks.py path/to/repo-root/
```

Extra options:

- `--base DIR` — additional directory for resolving relative evidence paths
  (repeatable). By default relative evidence paths are resolved against the
  current working directory, the directory holding `TASKS.json`, and that
  directory's parent (the repository root in the live layout).
- `--statuses CSV` — override the allowed status set (see below).

## What it checks

1. **Schema conformance** — every row in `tasks` must have exactly the key
   set `id, team_id, owner_tag, status, updated_at, evidence_paths,
   blocked_on, next_action, acceptance, assignment_ack`. Missing keys and
   unexpected keys are reported as distinct problems. Rows are identified by
   their `id` (e.g. `tasks[3] (id='fix-harness')`) or, when `id` is absent or
   not a string, by their zero-based row index (`tasks[3]`).
2. **Type conformance** — `id, team_id, owner_tag, status, updated_at,
   next_action, acceptance, assignment_ack` must be strings;
   `evidence_paths, blocked_on` must be arrays of strings. A string field
   given a number, an array field given a string, and a missing field are
   reported as three different problems. Array elements that are not strings
   are reported per element (`evidence_paths[1]`). Strings that should be
   ISO8601 timestamps but do not parse as such are reported too.
3. **Allowed statuses** — `status` must be one of the fixed project
   vocabulary from `coordination/OPERATING-MODEL.md`: `queued, ready,
   running, review, blocked, done, cancelled`. Anything else is an error.
4. **File-level timestamp consistency** — the top-level `updated_at` must be
   at least as new as every row's `updated_at`; rows newer than the file are
   flagged. Timestamps without a UTC offset are compared as if UTC. A row
   equal to the file timestamp is fine.
5. **Cross-file ownership** — for each row whose `team_id` appears in
   `TEAM-REGISTRY.json`, `owner_tag` must equal that team's `head_tag`.
   Teams absent from the registry are not an ownership error. The registry
   may be in any of these layouts: the live format
   `{"teams": [{"id": ..., "head_tag": ...}, ...]}`, a bare list of such
   team objects, a dict mapping team id to `{"head_tag": ...}`, or a dict
   mapping team id directly to the head-tag string.
6. **Evidence paths** — every string entry in `evidence_paths` must exist on
   disk (see resolution rules above). Paths may be absolute or relative and
   are not required to live inside any particular directory.

## Behaviour

- Exit code `0` — no problems found.
- Exit code `1` — at least one problem; every problem is printed on its own
  line to stdout (nothing is suppressed after the first), followed by a
  `N problem(s) found.` summary.
- Exit code `2` — operational error: missing/unreadable file or malformed
  JSON. Reported as a clean one-line `ERROR:` message on stderr, never a
  traceback.
- Each problem line names the task (`id='...'` or `tasks[i]`) and the field
  (or array element) involved, so a human can fix it without re-reading the
  file.
- If the registry file does not exist, ownership checks are skipped with a
  note on stderr and the exit code reflects only the other checks.

## Tests

The test suite builds synthetic fixtures in temporary directories and never
reads the live `coordination/TASKS.json` or `TEAM-REGISTRY.json` (the live
files change while agents work, so tests must not depend on them).

```sh
python3 tests/test_validate_tasks.py -v
# or, from this directory:
python3 -m unittest discover -s tests -v
```
