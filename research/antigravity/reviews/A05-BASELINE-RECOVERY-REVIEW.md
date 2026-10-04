# REV-A05-BASELINE-RECOVERY — Independent Review of A05 Same-Task Baseline, Frozen Pins, and Gate Integrity

- **Reviewer Tag:** `a05-baseline-reviewer`
- **Session ID:** `55e1a893-fcb1-4683-ba6d-89f3058b581c`
- **Parent Session:** `antigravity-head` (`46fdb644`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives:** Codex Principal C1660 (`01a1051f-57c2-7352-856a-e245123b4657`) / C1661 (`01a1051f-57fe-78a1-b7b5-0d10b6e454c5`)
- **Review Date / As-of:** 2026-10-04, Europe/Berlin
- **Repository HEAD:** `8e4d4605ed9795e7e35b40931170a6feae56bafc`
- **Target Lineage under Review:** `research/space-bunny/a05-same-task-baseline/`
- **Bounded Verdict:** **MAINTAIN_PROVISIONAL_PARK — ATTEMPT-1 SUPERIORITY WITH DIRTY BYTE QUARANTINE**
  - **Ownership Invariant:** Original ownership belongs to `space-bunny-head` (`ses_f01ef9c54ffe86f5DrG7n8GCsY`). All existing dirty files and untracked artifacts in `research/space-bunny/` have remained strictly **read-only and untouched** (zero working tree changes, zero reverts).
  - **Input Integrity:** Frozen inputs (`TASK.md` SHA256 content digest `84190454...`, `input/TASKS.json` SHA256 content digest `4065d99f...`, `input/TEAM-REGISTRY.json` SHA256 content digest `1734f132...`) are 100% byte-identical across both attempt directories and `inputs.sha256`. The same-task baseline specification holds cleanly, though identical input bytes alone do not establish matched actor/control/provider conditions or product superiority.
  - **Committed vs Uncommitted Bytes:**
    - **Attempt-1 (Committed `7ad05d7`):** 3 files, 1060 lines, 38 passing synthetic tests. Covers requirements R1–R6 and B1–B3. Exhibits an unhandled `UnicodeDecodeError` traceback crash on non-UTF-8 inputs (exit code 1).
    - **Attempt-1 (Uncommitted Worktree):** +9 lines in `validate_tasks.py` (H1 `UnicodeDecodeError` catch, H2 global `Exception` guard) and +10 lines in `tests/test_validate_tasks.py` (H3 `test_non_utf8_tasks_file_is_clean_error`). 39 passing tests. Cleanly fixes the non-UTF-8 crash to exit code 2.
    - **Attempt-2 (Untracked Worktree):** Entirely uncommitted (0 commits). 37 passing tests. Crashes with `UnicodeDecodeError` traceback on non-UTF-8 input, conflates exit codes 1 and 2, and returns exit 1 for top-level non-object inputs (violating its own README).
  - **Gate Resolution (`ignore-return2` & Missing Cases):**
    - The historical Space Bunny replay harness defect (`replay.sh` ignoring returncode 2 and exiting 0 on missing cases) was resolved at `4937506` in `research/space-bunny/repro/`, where replay callers capture return codes and test exit 3 on missing/duplicate cases.
    - In A05, **Attempt-1 strictly implements and tests exit code 2** for all input/operational failures (`assertEqual(returncode, 2)`).
    - In contrast, **Attempt-2 exhibits an evasive false-pass gate**: its test suite uses `assertNotEqual(proc.returncode, 0)` for malformed JSON and missing files, concealing that it returns exit 1 for malformed registry JSON and non-object tasks, and crashes with exit 1 on non-UTF-8 bytes.
  - **Action Rate & Telemetry Truth:**
    - Measured from preserved logs (`attempt-1.log` and `attempt-2.log`):
      - Attempt 1: 144,629 log-reported tokens (not billed usage), 9.75 min, 13 bash `exec` tool commands (1.33 cmd/min tool activity rate, not user adoption or repair rate), 13 tool router errors (~50% error rate). Model suffered a self-confusion hallucination, misidentifying its own committed git commit (`Alexey Grigorev`) as a "concurrent teammate" and triggering uncommitted hardening.
      - Attempt 2: 145,776 log-reported tokens (not billed usage), 11.5 min, 13 bash `exec` tool commands (1.13 cmd/min tool activity rate), 12 tool router errors (~48% error rate). Omitted git commit entirely.
  - **Disposition:** A05 remains **PROVISIONALLY PARKED** per standing portfolio decisions (`01a10064-382f` / `01a10064-776a`). If reopened, Attempt-1 lineage with its hardening deltas is the recommended base. Original head ownership is preserved without declaring experimental superiority causal.

---

## 1. Context & Directive Scope

Under Codex Principal directive C1660 (`01a1051f-57c2-7352-856a-e245123b4657`), this review was commissioned as a healthy preferred-worker independent audit of the A05 same-task baseline challenge.

### 1.1. Core Mandates
1. **Committed Frozen Inputs vs Uncommitted Bytes:**
   - Audit `git diff research/space-bunny/a05-same-task-baseline/` to identify all uncommitted changes.
   - Contrast committed baseline results with uncommitted edits, labeling each clearly.
2. **Ignore-Return2 & Missing Cases Gate Audit:**
   - Investigate whether the validator ignores return code 2 or suppresses missing case failures.
   - Determine if the validation gate was actually corrected or if evasion/false-pass modes exist.
3. **Baseline Validity & Action Rate Analysis:**
   - Evaluate actual task execution, tool action rates, and measured outcomes vs unmeasured claims.
   - Assess comparative evidence quality between attempt-1 and attempt-2.
4. **Exact Pins, Commands, and Next Action:**
   - Record exact git commit SHAs, tree SHAs, reproduction commands (`python3 -m unittest ...`), and owner handoff.
5. **Operating Invariants:**
   - Strictly zero modifications or reverts in `research/space-bunny/`.
   - Preserve original head ownership (`space-bunny-head`).
   - Scratch usage <= 512 MB (`.local/scratch/a05-baseline-review/`, mode `0700`), zero `/tmp` growth, cooperative memory limit <= 1500 MB.

---

## 2. Committed Frozen Inputs vs Uncommitted Bytes

### 2.1. Frozen Input Integrity Verification
Every input file referenced in `research/space-bunny/a05-same-task-baseline/inputs.sha256` was verified by direct SHA-256 recomputation:

| File Path | Recorded SHA-256 | Actual Computed SHA-256 | Integrity Status |
|---|---|---|---|
| `TASK.md` (root) | `8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb` | `8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb` | **EXACT MATCH** |
| `attempt-1/TASK.md` | `8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb` | `8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb` | **EXACT MATCH** |
| `attempt-2/TASK.md` | `8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb` | `8419045491c3f8007c215906fa3f29fecf7cfab587c4a205d3f57828c78663bb` | **EXACT MATCH** |
| `attempt-1/input/TASKS.json` | `4065d99fb00f542092f0b6f2e31d7e65b8ecf9cd48e7cc3a9401ce84b6fc20e8` | `4065d99fb00f542092f0b6f2e31d7e65b8ecf9cd48e7cc3a9401ce84b6fc20e8` | **EXACT MATCH** |
| `attempt-2/input/TASKS.json` | `4065d99fb00f542092f0b6f2e31d7e65b8ecf9cd48e7cc3a9401ce84b6fc20e8` | `4065d99fb00f542092f0b6f2e31d7e65b8ecf9cd48e7cc3a9401ce84b6fc20e8` | **EXACT MATCH** |
| `attempt-1/input/TEAM-REGISTRY.json` | `1734f132421d515a5c07ed49821aebe28615d18663c0f527d381558286a39f27` | `1734f132421d515a5c07ed49821aebe28615d18663c0f527d381558286a39f27` | **EXACT MATCH** |
| `attempt-2/input/TEAM-REGISTRY.json` | `1734f132421d515a5c07ed49821aebe28615d18663c0f527d381558286a39f27` | `1734f132421d515a5c07ed49821aebe28615d18663c0f527d381558286a39f27` | **EXACT MATCH** |

**Conclusion on Inputs:** Both attempt arms operated against identical specifications and identical mock input registries. The premise of the same-task baseline was uncompromised by fixture skew.

---

### 2.2. Git Audit of Uncommitted vs Committed Bytes

Running `git status --porcelain research/space-bunny/a05-same-task-baseline/` reveals:
```
 M research/space-bunny/a05-same-task-baseline/attempt-1/tests/test_validate_tasks.py
 M research/space-bunny/a05-same-task-baseline/attempt-1/validate_tasks.py
?? research/space-bunny/a05-same-task-baseline/TASK.md
?? research/space-bunny/a05-same-task-baseline/attempt-1/TASK.md
?? research/space-bunny/a05-same-task-baseline/attempt-1/input/
?? research/space-bunny/a05-same-task-baseline/attempt-1/tests/__pycache__/
?? research/space-bunny/a05-same-task-baseline/attempt-2/
?? research/space-bunny/a05-same-task-baseline/inputs.sha256
```
(Directory `logs/` is ignored by `.gitignore`).

#### The Unified Diff of Working Tree Changes
Running `git diff research/space-bunny/a05-same-task-baseline/` isolates the uncommitted changes in Attempt-1:

```diff
diff --git a/research/space-bunny/a05-same-task-baseline/attempt-1/tests/test_validate_tasks.py b/research/space-bunny/a05-same-task-baseline/attempt-1/tests/test_validate_tasks.py
index 706a9c9..e4aaa04 100644
--- a/research/space-bunny/a05-same-task-baseline/attempt-1/tests/test_validate_tasks.py
+++ b/research/space-bunny/a05-same-task-baseline/attempt-1/tests/test_validate_tasks.py
@@ -432,6 +432,15 @@ class CliBehaviourTests(FixtureBase):
         self.assertIn("not found", result.stderr)
         self.assertNotIn("Traceback", result.stderr)
 
+    def test_non_utf8_tasks_file_is_clean_error(self):
+        path = self.root / "binary.json"
+        path.write_bytes(b"\xff\xfe\x00not json at all")
+        result = self.run_tool(path)
+        self.assertEqual(result.returncode, 2)
+        self.assertIn("ERROR", result.stderr)
+        self.assertNotIn("Traceback", result.stderr)
+        self.assertNotIn("Traceback", result.stdout)
+
     def test_all_problems_reported_not_just_first(self):
         row = valid_row(status="WIP", owner_tag=5)
         del row["acceptance"]
diff --git a/research/space-bunny/a05-same-task-baseline/attempt-1/validate_tasks.py b/research/space-bunny/a05-same-task-baseline/attempt-1/validate_tasks.py
index 4d38716..710cd7a 100755
--- a/research/space-bunny/a05-same-task-baseline/attempt-1/validate_tasks.py
+++ b/research/space-bunny/a05-same-task-baseline/attempt-1/validate_tasks.py
@@ -318,6 +318,8 @@ def load_json(path):
             exc.lineno,
             exc.colno,
         )
+    except UnicodeDecodeError as exc:
+        return None, "%s is not valid UTF-8 text: %s" % (path, exc)
     except OSError as exc:
         return None, "cannot read %s: %s" % (path, exc.strerror or exc)
 
@@ -462,4 +464,10 @@ def main(argv=None):
 
 
 if __name__ == "__main__":
-    sys.exit(main())
+    try:
+        sys.exit(main())
+    except SystemExit:
+        raise
+    except Exception as exc:  # a broken run must not end in a traceback
+        print("ERROR: unexpected failure: %s" % exc, file=sys.stderr)
+        sys.exit(EXIT_INPUT_ERROR)
```

### 2.3. Characterization of the Three Code States

| Lineage / State | Tracking Status | Code Sha256 (`validate_tasks.py`) | Tests Sha256 (`test_validate_tasks.py`) | Test Count & Result | Behavior on Non-UTF-8 Input |
|---|---|---|---|---|---|
| **Attempt-1 (Committed)** | Committed in `7ad05d7` | `872a57131792...` | `1cd2338017c5...` | 38 tests, **PASS** | Crashes with unhandled `UnicodeDecodeError` traceback (`exit 1`) |
| **Attempt-1 (Current Worktree)** | Dirty working tree | `3a58ebde980c...` | `d61b369c48dd...` | 39 tests, **PASS** | Clean error on stderr, `exit 2`, no traceback |
| **Attempt-2 (Current Worktree)** | Untracked (0 commits) | `7a4ee2563dc5...` | `1f415c95af9e...` | 37 tests, **PASS** | Crashes with unhandled `UnicodeDecodeError` traceback (`exit 1`) |

---

## 3. Ignore-Return2 & Missing Cases Gate Audit

### 3.1. Background of the Defect Class
In earlier Space Bunny development (round 1–9, `research/space-bunny/repro/replay.sh` and `negative-tests.sh`), the test execution harness suffered from two critical vulnerabilities:
1. **`if ! out=...; then rc=$?; fi` defect (D1):** The bash negation `!` forced `$?` to always evaluate to 0 in the failure branch, rendering timeout (`rc=124`) and oracle failure branches unreachable and reporting broken runs as `rc=0`.
2. **Caller Ignored Return Code 2:** When a test case aborted or a manifest verification failed (`rc=2`), replay runners continued and evaluated partial test summaries (e.g. "7 of 8 passed, exit 0"), silently omitting aborted cases.
These defects were verified and structurally pinned in commit `4937506` (`A14-FOLD-OR-REOPEN-REPORT.md`), where all dispatches capture `rc=0; run_case ... || rc=$?`, nonzero exits set `setup_err=1`, and post-run checks mandate exactly 8 unique passing rows.

### 3.2. Evaluation of A05 Attempt-1
Attempt-1 explicitly implements a three-way exit contract:
- `EXIT_OK = 0` (no problems found)
- `EXIT_PROBLEMS = 1` (registry data validation issues detected)
- `EXIT_INPUT_ERROR = 2` (file not found, unreadable, or malformed JSON)

**Audit Findings:**
- In `validate_tasks.py`: Missing `TASKS.json` exits with `EXIT_INPUT_ERROR` (2). Malformed JSON exits with 2. Malformed `TEAM-REGISTRY.json` exits with 2. Missing `TEAM-REGISTRY.json` prints a warning note to stderr and cleanly degrades to skipping ownership checks without error, exactly as required by `TASK.md` lines 44–45.
- In `test_validate_tasks.py`: Attempt-1 explicitly checks exact return codes:
  ```python
  self.assertEqual(result.returncode, 2)
  self.assertIn("not valid JSON", result.stderr)
  self.assertNotIn("Traceback", result.stderr)
  ```
- **Conclusion:** Attempt-1 **does not ignore return code 2** and does not suppress missing cases. The uncommitted hardening adds an explicit test (`test_non_utf8_tasks_file_is_clean_error`) asserting `self.assertEqual(result.returncode, 2)`.

### 3.3. Evaluation of A05 Attempt-2 (The Evasive Gate)
Attempt-2 documents in its `README.md` (lines 61–64):
> "Exit codes: `0` = no problems; `1` = at least one problem; `2` = the input could not be read/parsed at all (missing file, malformed JSON, top-level value not an object) — reported as a clean error message, never a traceback."

However, deep static and dynamic audit of `attempt-2/validate_tasks.py` uncovers three distinct flaws:
1. **Malformed `TEAM-REGISTRY.json` Exits 1 Instead of 2:**
   In `load_registry_map` (line 267), malformed registry JSON returns `({}, "%s: malformed JSON...", None)` as `fatal_problem`. In `main()` (lines 342–352), `fatal_problem` is added to `validator.problems`, and the tool exits with `EXIT_PROBLEMS` (1), not `EXIT_INPUT_ERROR` (2).
2. **Top-Level Non-Object JSON Exits 1 Instead of 2:**
   If `TASKS.json` contains a JSON array (`["just", "a", "list"]`), `json.loads` succeeds. In `validator.validate()` (line 211), it records a problem: `top-level JSON value must be an object`. The tool exits with `EXIT_PROBLEMS` (1), directly contradicting README line 62.
3. **Non-UTF-8 Input Crashes with Unhandled Traceback:**
   In `load_tasks_document()` (lines 285–298), file reading catches `OSError` and `json.JSONDecodeError`, but **omits `UnicodeDecodeError`**. Feeding invalid UTF-8 bytes crashes python with an unhandled traceback and exit code 1.
4. **Test Suite Assertion Evasion:**
   In `attempt-2/test_validate_tasks.py` (lines 410, 418, 433):
   ```python
   def test_malformed_tasks_json_is_error_without_traceback(self):
       self.fixture.write_tasks(None, raw="{oops")
       self.fixture.write_registry()
       proc = self.fixture.run()
       self.assertNotEqual(proc.returncode, 0) # <--- EVASION!
   ```
   The test asserts only `assertNotEqual(proc.returncode, 0)` rather than asserting `assertEqual(proc.returncode, 2)`. Consequently, if the tool crashes with a traceback or returns exit code 1, the test suite still marks the case as `OK`.

**Verdict on Gate Integrity:**
- In Attempt-1: The validation gate is **structurally sound and actually corrected** in the uncommitted worktree.
- In Attempt-2: The validation gate **was never corrected and relies on evasive test assertions** that hide specification and exit-code defects.

---

## 4. Baseline Validity & Action Rate Analysis

### 4.1. Comparative Execution Telemetry

From direct analysis of the raw execution logs (`research/space-bunny/a05-same-task-baseline/logs/`):

| Telemetry Metric | Attempt-1 (`attempt-1.log`) | Attempt-2 (`attempt-2.log`) | Comparative Analysis |
|---|---|---|---|
| **Session ID** | `01a0fff5-4511-7b10-8176-3bb4dd535dd1` | `01a0fff0-f9c7-7ba3-b2ce-bedff4df5d79` | Distinct autonomous worker sessions |
| **Model & Engine** | `glm-5.3-flash` via `zcode` / `zcodex` | `glm-5.3-flash` via `zcode` / `zcodex` | Identical LLM & adapter environment |
| **Start Timestamp** | `2026-10-03T04:11:12Z` | `2026-10-03T04:06:25Z` | Executed concurrently |
| **End Timestamp** | `2026-10-03T04:20:57Z` | `2026-10-03T04:17:55Z` | Wall-clock: 9.75 min vs 11.50 min |
| **Total Tokens Reported** | 144,629 tokens | 145,776 tokens | Variance < 0.8% |
| **Token Burn Rate** | ~14,833 tokens / min | ~12,676 tokens / min | Consistent throughput |
| **Successful Bash Commands (`exec`)** | 13 commands | 13 commands | Exact parity in command count |
| **Successful Action Rate** | 1.33 commands / min | 1.13 commands / min | ~1.2 commands/min baseline rate |
| **Tool Router Rejections (`error=...`)** | 13 errors (50.0% of attempts) | 12 errors (48.0% of attempts) | Massive router impedance on both arms |
| **Breakdown of Rejected Tool Calls** | 6 `Edit`, 3 `Write`, 1 `Read`, 2 `rm -f` rejected, 1 goal error | 7 `Edit`, 3 `Write`, 1 `Read`, 1 goal error | Model attempted standard file tools not supported by `codex_core` |
| **Git Commit Execution** | Executed commit `7ad05d7` | **None** (Omitted entirely) | Attempt-1 preserved; Attempt-2 volatile |

### 4.2. Analysis of the Attempt-1 "Teammate Agent" Hallucination
Lines 284–351 of `attempt-1.log` explain how the uncommitted working tree changes were created:
1. At line 234, the Attempt-1 agent ran `flock .local/git.lock git commit -m "space-bunny a05 attempt-1: TASKS.json validator (tool, README, 38 synthetic-fixture tests)"`, creating commit `7ad05d7`.
2. At line 273, the agent ran `git show 7ad05d7` and saw:
   `7ad05d7 Alexey Grigorev Sat Oct 3 06:18:03 2026 +0200`
3. Seeing the human author name "Alexey Grigorev" rather than its own session identity, the agent suffered context confusion:
   > "The teammate's implementation covers all six requirements and the test suite is thorough. Let me run their tests to establish a baseline, then review for gaps." (line 293)
   > "Note: another team agent was writing to this shared directory concurrently; rather than duplicating the work, I verified their implementation against the spec line by line and hardened it (added UnicodeDecodeError handling...)" (line 351)
4. The agent then modified `validate_tasks.py` and `tests/test_validate_tasks.py` to add `UnicodeDecodeError` handling and the 39th test, confirmed that all 39 tests passed, and finished the turn **without committing the changes**.

**Finding on Process Rigor:** The uncommitted hardening was not an external tamper event or cross-session contamination; it was the same model session continuing to iterate after confusing its own git commit author with a human peer.

---

## 5. Requirement Coverage & Adjudication Reconciliation

### 5.1. Static Requirement Coverage Comparison

| Requirement ID | Specification (`TASK.md`) | Attempt-1 (Committed `7ad05d7`) | Attempt-1 (Current Worktree) | Attempt-2 (Untracked) |
|---|---|---|---|---|
| **R1: Schema** | Missing and unexpected keys distinct; task ID or index | **COVERED** | **COVERED** | **COVERED** |
| **R2: Types** | String, list, timestamp type distinctions | **COVERED** | **COVERED** | **COVERED** |
| **R3: Status** | Fixed set (`queued, ready, running, review, blocked, done, cancelled`) | **COVERED** | **COVERED** | **COVERED** |
| **R4: Timestamps** | Row `updated_at` <= file `updated_at` | **COVERED** | **COVERED** | **COVERED** |
| **R5: Ownership** | `owner_tag` == `head_tag` for registered teams | **COVERED** | **COVERED** | **COVERED** |
| **R6: Evidence** | Paths exist on disk; flexible directories | **COVERED** (cwd, task-dir, parent, `--base`) | **COVERED** | **COVERED** (cwd, `--root`) |
| **B1: Exit Codes** | 0 = clean, nonzero = problems | **COVERED** (0, 1, 2) | **COVERED** (0, 1, 2) | **PARTIAL** (blurs 1 & 2) |
| **B2: No Fail-Fast** | Every problem reported | **COVERED** | **COVERED** | **COVERED** |
| **B3: Task & Field** | Problems identify task & field | **COVERED** | **COVERED** | **COVERED** |
| **B4: Clean Errors** | Malformed JSON is clean error, not traceback | **FAIL (non-UTF-8)** | **COVERED** (exit 2) | **FAIL (non-UTF-8)** |

### 5.2. Reconciliation with Prior Reviews
1. **Matrix v1 (`69edde7`):** Claimed "read-only audit on frozen bytes", which was subsequently withdrawn by matrix v1.1.
2. **Matrix v1.1:** Proved that committed Attempt-1 (`7ad05d7`) and Attempt-2 both crash on non-UTF-8 inputs, and that Attempt-1's clean exit 2 comes solely from uncommitted bytes. Classified F4 (non-UTF-8) as a failure of B4.
3. **Adjudication Verdict (`VERDICT.md` by `a05-adjudicator`):** Ruled **TIE** between `7ad05d7` and current worktree under ACCEPTANCE-POLICY P3, holding that because `TASK.md` line 56 does not explicitly mention character encodings, F4 is a spec-silent posture/robustness difference rather than a requirement delta.
4. **Current Review Finding:** While ACCEPTANCE-POLICY P3 strictly governed the static review, on pure engineering merits Attempt-1 is superior. Attempt-1 properly separates exit 1 and exit 2, tests return codes rigorously, supports hierarchical evidence resolution, and cleanly handles binary files in its uncommitted state. Attempt-2 remains uncommitted, omits git hygiene, and masks its exit-code bugs behind loose test assertions.

---

## 6. Exact Pins, Commands, and Reproduction

### 6.1. Exact Git Object Pins

| Target Item | Type | Git SHA / Hash |
|---|---|---|
| Repository HEAD | Commit | `8e4d4605ed9795e7e35b40931170a6feae56bafc` |
| Attempt-1 Committed Checkpoint | Commit | `7ad05d70eb12809a353b12b3c0484de1b9e0e465` |
| `7ad05d7:attempt-1/validate_tasks.py` | Blob | `872a57131792172cda4f41d008a7803162f0ef9b61660ec4948475c9203a5a5a` |
| `7ad05d7:attempt-1/tests/test_validate_tasks.py` | Blob | `1cd2338017c57125a4c51936912ba70398836a44dbd208904e54794a0b4d25fc` |
| `7ad05d7:attempt-1/README.md` | Blob | `0a1105f844c69aae10847427a0bb8815dae43db8173df2eb0f37b7f4bc6724b9` |
| Worktree `attempt-1/validate_tasks.py` | SHA-256 | `3a58ebde980c428cbdfa2bc3b3d9307a95b362d6fb9ce37a3b30864c8253ae69` |
| Worktree `attempt-1/tests/test_validate_tasks.py` | SHA-256 | `d61b369c48dd89cb3fd934852bbef5156adc08db00d3ad91e31e7b6e6428c905` |
| Worktree `attempt-2/validate_tasks.py` | SHA-256 | `7a4ee2563dc513284b7c8e4d65980ac64b165892fbaa1645cae3c10098b84b84` |
| Worktree `attempt-2/test_validate_tasks.py` | SHA-256 | `1f415c95af9e9712cf3c31c2396f4fdc5c5ed0add2de965b5a0e25e5ab0d1880` |
| Worktree `attempt-2/README.md` | SHA-256 | `e9bf2d9115a10a80a7d38d4aa42395cd3e4f9d97bce85ef2339106d40fc8551e` |

### 6.2. Exact Reproduction Commands

All test suites were executed independently during this review with `-B` to prevent `.pyc` creation and zero working tree contamination:

1. **Attempt-1 Committed Baseline (`7ad05d7`):**
   ```bash
   # From scratch checkout or git archive:
   python3 -B -m unittest discover -s tests -v
   # Result: Ran 38 tests in 1.405s — OK (Exit code: 0)
   ```

2. **Attempt-1 Current Worktree (with hardening deltas):**
   ```bash
   cd /home/alexey/git/cloudflare-agent-git/research/space-bunny/a05-same-task-baseline/attempt-1
   python3 -B tests/test_validate_tasks.py -v
   # Result: Ran 39 tests in 1.495s — OK (Exit code: 0)
   ```

3. **Attempt-2 Current Worktree:**
   ```bash
   cd /home/alexey/git/cloudflare-agent-git/research/space-bunny/a05-same-task-baseline/attempt-2
   python3 -B test_validate_tasks.py -v
   # Result: Ran 37 tests in 1.157s — OK (Exit code: 0)
   ```

---

## 7. Owner Handoff & Next Actions

1. **Preserve Ownership:** Original ownership of `research/space-bunny/` remains with `space-bunny-head`. No files have been deleted, reverted, or committed by this reviewer.
2. **Quarantine Dirty State:** When `space-bunny-head` resumes, it should formalize the uncommitted bytes in `attempt-1/`:
   - Either commit the hardening deltas (H1–H3) under an explicit commit message (`docs(a05): commit attempt-1 hardening deltas and 39th non-UTF8 regression test`).
   - Or stage/commit `attempt-2/` and `TASK.md` so that the directory is fully tracked and clean.
3. **Portfolio Decision:** A05 remains **PROVISIONALLY PARKED** per `01a10064-382f`. This review does not trigger reopening of A05 or change its shortlist standing. If A05 is reopened at a future milestone, Attempt-1 is the validated foundation.
4. **Handoff Target:** Notify parent agent (`antigravity-head`, `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) and record completion in supervisory logs.
