# A05 original-vs-hardened adjudication — VERDICT

## Identity

- I am **a05-adjudicator**, a bounded independent reviewer dispatched by head
  **zcode-independent** (aplexer session `64049aa2`) in
  `/home/alexey/git/cloudflare-agent-git`.
- I am NOT session `64049aa2` and not either principal; I am the distinct
  preferred-provider adjudicator required by codex-principal containment rule
  `01a1005e-74da`.
- First-tool evidence: `research/zcode/independent/a05-adjudication/WORKLOG.md`
  (`id` uid=1000(alexey), `date -u` Sat Oct 3 06:28:42 AM UTC 2026,
  `hostname` RMTHZ, `pwd` /home/alexey/git/cloudflare-agent-git).
- Scope: bounded original-vs-hardened adjudication of attempt-1 lineage ONLY:
  `frozen/7ad05d7/` (committed at git 7ad05d7, "original") vs `frozen/current/`
  (worktree with uncommitted hardening deltas, "hardened"). Static review only;
  no execution, no installs, no commits.

## Manifest verification

Verified 9 of 13 `MANIFEST.sha256` entries by recomputation (requirement: ≥3).
All recomputed hashes match the manifest exactly:

- `./TASK.md`: `84190454…863bb` — MATCH
- `./ACCEPTANCE-POLICY.md`: `63dc18b8…4769` — MATCH
- `./matrix-v1.md`: `90e79711…66f271` — MATCH
- `./matrix-v1.1.md`: `4d7559d2…11e95a1d6` — MATCH
- `./7ad05d7/README.md`: `0a1105f8…6724b9` — MATCH
- `./7ad05d7/validate_tasks.py`: `872a5713…03a5a5a` — MATCH
- `./7ad05d7/tests/test_validate_tasks.py`: `1cd23380…4d25fc` — MATCH
- `./current/README.md`: `0a1105f8…6724b9` — MATCH (identical to 7ad05d7 README)
- `./current/validate_tasks.py`: `3a58ebde…8253ae69` — MATCH
- `./current/tests/test_validate_tasks.py`: `d61b369c…6428c905` — MATCH
- `./current/TASKS.json`: `4065d99f…fc20e8` — MATCH
- `./current/TEAM-REGISTRY.json`: `1734f132…6a39f27` — MATCH
- `./current/TASK.md`: `84190454…863bb` — MATCH (identical to frozen TASK.md)

Comment: `diff -u 7ad05d7/README.md current/README.md` is empty; README is
unchanged. `current/TASK.md` is byte-identical to frozen `TASK.md`.

## Requirement-level deltas

`diff -u` of `7ad05d7/validate_tasks.py` vs `current/validate_tasks.py` shows
exactly two behavioral hunks; everything else (R1–R6, B1–B3 logic:
`EXPECTED_KEYS`, `row_label`, `validate_tasks_doc`, `build_registry_map`,
`path_exists`, `parse_iso8601`/`as_comparable`, status vocabulary, timestamp
comparison, ownership check, evidence-path resolution, exit-0/1 paths) is
byte-identical. Test diff shows exactly one added test. README diff is empty.

- **Delta H1 — `load_json`: `except UnicodeDecodeError` catch** (current lines
  321–322; absent in 7ad05d7 lines 309–322). Non-UTF-8 input files now return a
  clean `(None, "... not valid UTF-8 text: ...")` error surfaced as
  `ERROR: ...` on stderr with exit 2, instead of propagating. Maps to matrix
  label **F4 / B4-adjacent**. Static code-path basis confirms the matrix-v1.1
  §2 mechanism claim: 7ad05d7 catches only `JSONDecodeError` + `OSError`, so a
  `UnicodeDecodeError` raised by `open(..., encoding="utf-8")` is uncaught
  there (note: `UnicodeDecodeError` is a `ValueError` sibling of
  `JSONDecodeError`, not a subclass of it, so the `JSONDecodeError` handler
  does not catch it). Per **ACCEPTANCE-POLICY P3**, F4 is SPEC-SILENT (TASK.md
  line 56 proves only "malformed JSON"; the spec never names encodings), so H1
  is a **spec-silent posture difference, not a B4 requirement delta**.
- **Delta H2 — `__main__` global no-traceback wrapper** (current lines 467–473;
  7ad05d7 line 465 is bare `sys.exit(main())`). Any otherwise-uncaught
  `Exception` is now printed as `ERROR: unexpected failure: ...` with exit 2
  (`SystemExit` re-raised). No TASK.md requirement mandates this: B4 covers
  malformed JSON only, and P2 scopes out-of-spec behavior to a note. H2 is
  **defensive robustness, not a requirement-coverage delta**. No regression is
  visible: normal exit-0/1/2 paths and `SystemExit` propagation are preserved.
- **Delta H3 — test added** (`test_non_utf8_tasks_file_is_clean_error`,
  current test lines 435–442; writes `b"\xff\xfe\x00not json at all"`, asserts
  rc 2 + `ERROR` + no `Traceback`). Test-only; pins H1 behavior. No
  requirement-level delta beyond H1.
- **R1–R6 / B1–B3: no delta.** Schema keys, type checks (string-vs-number vs
  list-vs-string vs missing), fixed status set, file-vs-row timestamp rule,
  ownership rule (known-team equality / unknown-team skip), evidence-path
  multi-base resolution, exit-0/1 behavior, all-problems reporting, and
  task+field identification are unchanged bytes.

## Verdict

**TIE** — hardened and original satisfy an equal set of frozen-TASK
requirements with no requirement-level delta between them: the only
implementation deltas (UnicodeDecodeError catch + global no-traceback wrapper
+ pinning test) map to spec-silent posture/robustness per ACCEPTANCE-POLICY P2/P3,
not to strictly more R1–R6/B1–B4 coverage, and no requirement regression is
visible in either direction, so P4 permits no WINNER; no requirement-level gap
in either state is established from the frozen bytes, so NEITHER is not
warranted either.

## Matrix discrepancies

1. **Scope mismatch (v1 attempt-2 column out of scope).** Matrix-v1 audits
   attempt-1 vs attempt-2; this adjudication covers 7ad05d7-original vs
   current-hardened (both attempt-1 lineage). All v1 attempt-2 claims (hashes
   `7a4ee256…`, `1f415c95…`, `e9bf2d91…`, `--root` resolution, `PROBLEM`
   prefixes, A2 type-check folding) have no corresponding frozen bytes and are
   out of scope here — neither confirmed nor denied.
2. **F4 classification conflicts with the binding policy.** Matrix-v1.1 §3
   reclassifies F4 as "requirement failure of B4 in attempt-2 (and committed
   attempt-1)". ACCEPTANCE-POLICY P3 explicitly rules the opposite: F4 is NOT a
   clean B4 failure given the UTF-8 ambiguity and must be treated as a
   spec-silent posture difference "unless the frozen TASK.md text proves
   otherwise to you". I find TASK.md line 56 ("Malformed JSON is an error, not
   a crash with a traceback") does not name encodings, so it does not prove
   otherwise; policy P3 controls, and I treat F4 as spec-silent. The matrix's
   plain-reading argument (RFC 8259 UTF-8 default) is noted but does not
   override the frozen policy I must apply exactly.
3. **v1 "read-only audit on frozen bytes" framing already withdrawn by v1.1
   §1** — acknowledged; I relied solely on the frozen copies plus manifest
   recomputation, with no live-tree reads and no execution.
4. **v1.1 §4 "two attempts tie" is about attempt-1 vs attempt-2**, not about
   my original-vs-hardened scope; I independently reach TIE for my scope under
   P4, which must not be quoted as agreement with the v1.1 cross-attempt tie.
5. **No other matrix claim contradicts the frozen bytes.** R1–R5/B1–B3/D/C
   coverage statements concerning attempt-1 lineage are consistent with the
   static code read (identical logic in both frozen states); the F7
   spec-silent reclassification (v1.1 §3) agrees with P3 and with the frozen
   TASK.md line 46, which names no resolution base (both states' resolution
   code is byte-identical in any case, so F7 has no original-vs-hardened
   delta).

## UNVERIFIED-BY-FROZEN

Static review only — no implementation was executed and no test suite was run.
The following matrix claims could NOT be verified from the frozen bytes alone:

- Dynamic F4 behavior: that committed 7ad05d7 actually exits rc=1 with a
  `Traceback` on non-UTF-8 input, or that current actually exits rc=2 cleanly
  (the handlers' presence/absence is verified statically; the runtime outcome,
  exit codes, and stderr text are not).
- All fixture-probe outcomes (F1–F7, G1–G4 outputs, counts, exit codes) and
  the probe scripts/session logs — not present in the frozen set.
- Hidden-suite assumptions: whether it feeds non-UTF-8 bytes, which cwd/base
  it uses for relative evidence paths, and any pass/fail weighting.
- Attempt-2 bytes, hashes, and behaviors (out of scope, no frozen copies).
- During-probe worktree stability and live-registry behavior (concurrent
  writers, realistic flux data) — inherently unobservable from frozen bytes.
- That the added `test_non_utf8...` test passes as written (asserted exit
  code/message assume runtime behavior).

## Usage

UNKNOWN — no token/cost/usage numbers are surfaced anywhere in the frozen
inputs, and none was measured (static review performs no metered execution).
Per policy P6, UNKNOWN is reported; zero is not claimed.

## Park context

Per ACCEPTANCE-POLICY P5 and the task brief: A05 is provisionally parked
(codex `01a10064-382f`, claude `01a10064-776a`) as a portfolio/resource
decision. This TIE verdict informs keep-or-drop of the hardening deltas IF A05
reopens — the deltas are small, behavior-preserving, spec-silent hardening
worth keeping on cost grounds, but they confer no requirement-coverage win. It
does NOT reopen A05, select a build direction, or imply any 20-to-6 shortlist
approval.
