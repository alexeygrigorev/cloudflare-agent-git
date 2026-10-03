# A05 same-task baseline — requirement-coverage matrix (v1, read-only audit)

- Owner: zcode-independent (64049aa2), 2026-10-03, Europe/Berlin.
- Authorized by claude-principal 01a10046-9518 (OWNER-ME) and codex-principal
  01a1003e-3641 gates. READ-ONLY on copies; no Bunny-path files were edited.
- **No winner is claimed.** This is a requirement-coverage audit against the
  frozen task text; outcome ranking is reserved for the independent hidden
  suite design, not for my fixtures.

## Provenance pins (sha256, audited working-tree bytes)

| File | sha256 |
|---|---|
| TASK.md (= attempt-1/TASK.md = attempt-2/TASK.md, all identical) | 8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb |
| attempt-1/validate_tasks.py (worktree) | 3a58ebde980c428cbdfa2bc3b3d9307a95b362d6fb9ce37a3b30864c8253ae69 |
| attempt-2/validate_tasks.py | 7a4ee2563dc513284b7c8e4d65980ac64b165892fbaa1645cae3c10098b84b84 |
| attempt-1/tests/test_validate_tasks.py (worktree) | d61b369c48dd89cb3fd934852bbef5156adc08db00d3ad91e31e7b6e6428c905 |
| attempt-2/test_validate_tasks.py | 1f415c95af9e9712cf3c31c2396f4fdc5c5ed0add2de965b5a0e25e5ab0d1880 |
| attempt-1/README.md | 0a1105f844c69aae10847427a0bb8815dae43db8173df2eb0f37b7f4bc6724b9 |
| attempt-2/README.md | e9bf2d9115a10a80a7d38d4aa42395cd3e4f9d97bce85ef2339106d40fc8551e |
| attempt-1/input/TASKS.json = attempt-2/input/TASKS.json | 4065d99fb00f542092f0b6f2e31d7e65b8ecf9cd48e7cc3a9401ce84b6fc20e8 |
| attempt-1/input/TEAM-REGISTRY.json = attempt-2/input/TEAM-REGISTRY.json | 1734f132421d515a5c07ed49821aebe28615d18663c0f527d381558286a39f27 |

Provenance facts:

- Task text is byte-identical across both attempts (same-task baseline holds
  at task and input level).
- attempt-1 tool+tests were committed at 7ad05d7; the working tree carries
  uncommitted hardening deltas on top (clean non-UTF-8 error, global
  no-traceback wrapper, +matching test). Audited bytes = worktree bytes
  (pinned above).
- attempt-2, both TASK.md copies, input/ pairs and inputs.sha256 are
  untracked (never committed). Attempt-2 has no committed recovery point.

## Method

Static read of both implementations plus 11 differential fixtures run in
/tmp scratch (F1–F7, G1–G4; script preserved in session log, rerunnable).
Fixtures are probes for coverage evidence only — synthetic, not the hidden
suite, and not a verdict instrument.

## Requirement matrix

Legend: ✅ covered (fixture evidence) · ⚠️ covered with behavioral variance ·
❌ not covered · ❓ UNKNOWN (needs hidden-suite assumption).

| Requirement | attempt-1 | attempt-2 | Evidence / notes |
|---|---|---|---|
| R1 schema: exact key set, missing vs unexpected distinct, id/index naming | ✅ | ✅ | F2/G1: both report missing and unexpected keys distinctly; F5: numeric id falls back to `tasks[0]` label in both |
| R2 types: string vs number vs list vs missing distinct | ✅ | ✅ | F2/G2/G4: numeric owner_tag, numeric array element both flagged by both; phrasing differs (both name task+field). A2 folds unparseable updated_at into the type check; A1 reports it as a separate ISO8601 problem — same coverage |
| R3 fixed status vocabulary | ✅ | ✅ | F2/G3: `WIP` and numeric status flagged by both; identical project vocabulary (queued/ready/running/review/blocked/done/cancelled). A1 adds `--statuses` override (harmless extra) |
| R4 top-level updated_at ≥ all rows | ✅ | ✅ | F2: newer row flagged by both; naive timestamps treated as UTC in both |
| R5 owner_tag = head_tag for registry-known teams; unknown teams not errors | ✅ | ✅ | G1 mismatch flagged by both; F2 team-b (absent) not flagged by either — matches spec. Variance: A1 accepts 4 registry layouts, A2 only the live `{"teams":[...]}` layout (irrelevant for the specified input format) |
| R6 evidence paths exist; no directory restriction | ⚠️ | ⚠️ | F7 differential: A1 resolves relative paths against cwd + tasks-dir + parent (+`--base`); A2 against `--root` (default cwd) only. Both spec-defensible ("exist on disk" is ambiguous about base). ❓ which resolution the hidden suite assumes |
| B1 exit 0 clean / non-zero problems | ✅ | ✅ | F1: both exit 0; F2/G1–G4: both exit 1 |
| B2 all problems reported, not first | ✅ | ✅ | F2: 6 problem classes in one run all surfaced by both |
| B3 problems identify task + field | ✅ | ✅ | G2: both lines name task label and field (formats differ) |
| B4 malformed JSON = clean error, no traceback | ✅ | ⚠️ | F3: malformed JSON clean exit 2 both. **F4 differential: non-UTF-8 bytes → A2 crashes with uncaught UnicodeDecodeError traceback (exit 1); A1 clean exit 2.** Whether "invalid UTF-8" falls under B4 is ❓ (spec says "malformed JSON"); A2's `load_tasks_document` catches OSError+JSONDecodeError but not UnicodeDecodeError |
| D deliverable: tool + README + synthetic-only tests | ✅ | ✅ | Both READMEs explain run+checks; both test suites build fixtures in tempdirs, never touching the live registry (grep + harness read verified) |
| C stdlib only, no network | ✅ | ✅ | imports: argparse/json/sys/datetime/pathlib|os only |

## Implementation-quality notes (not spec violations)

- A1 flags `schema_version != 1` (spec doesn't ask; out-of-spec input only,
  ❓ no expected suite impact).
- A2 prints `PROBLEM`-prefixed lines and a count; A1 plain lines + count.
  Both satisfy B3.
- A1 exits 2 on unreadable tasks file; A2 likewise for OSError/JSONDecode,
  but non-UTF-8 lands at exit 1 + traceback (B4 differential above).

## Explicit UNKNOWNs

1. Whether the hidden suite feeds non-UTF-8 bytes (decides severity of the
   A2 F4 differential).
2. Which cwd/base the hidden suite uses for relative evidence paths (decides
   R6 resolution variance).
3. Hidden-suite pass/fail weighting is unknowable from here; no exit-code or
   message-format match is asserted beyond the spec text.

## Constraint compliance of this audit

Repo untouched: fixtures + scripts lived in /tmp; nothing under
research/space-bunny/ was modified; audited bytes pinned above. Fixture
scripts and raw outputs are reproducible from the pinned bytes.
