# Independent Peer Review: Audit of `grok-five-percent-admission` (15% Remaining Quota Reservation Gate for Codex & Grok)

**Date & Time**: 2026-10-06T00:35:00Z (2026-10-06 02:35:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Technical Auditor)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Audited Commit**: `50debcade71bffa2793fcdb822c4fc41aee91ef0` (`50debca`)  
**Audited Task**: `grok-five-percent-admission`  
**Task Executor Session**: `34d62314-9132-4f86-b1a9-0fdb8f8d0a13` (`gemini-3.1-pro-high`)  
**Task Log File**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/grok-five-percent-admission-stdout.log`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

An adversarial, rigorous technical audit was conducted on task `grok-five-percent-admission` implemented in `/home/alexey/git/agent-quota-launcher` at commit `50debca`.

The purpose of this change is to enforce the strict 15% remaining quota reservation gate across both **Codex** and **Grok** providers in the Agent Quota Launcher admission subsystem, replacing the previous legacy 5% cutoff for Grok while maintaining fail-closed boundary enforcement and route isolation.

### Audit Evaluation Matrix

| # | Acceptance Criterion / Inspection Item | Requirement | Observed Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | **Target Commit Identification** | Verify commit `50debca` in `/home/alexey/git/agent-quota-launcher` | Commit `50debcade71bffa2793fcdb822c4fc41aee91ef0` ("Update Grok minimum remaining quota threshold to 15%") modifies `launcher/admission.py` (+1/-1) and `tests/test_admission.py` (+8/-8) | **PASS** |
| **2** | **CODEX_MIN_REMAINING Threshold** | Value must be exactly `15.0` | `launcher/admission.py:21`: `CODEX_MIN_REMAINING = 15.0`. Evaluated in `codex_gate_reason()` | **PASS** |
| **3** | **GROK_MIN_REMAINING Threshold** | Value must be exactly `15.0` | `launcher/admission.py:22`: `GROK_MIN_REMAINING = 15.0`. Evaluated in `_validate_route()` | **PASS** |
| **4** | **Grok Boundary: Exactly 15.0%** | Exactly 15.0% remaining quota must be rejected | `tests/test_admission.py:190-195`: `test_grok_at_exactly_15_percent_rejected` asserts `len(valid) == 0` and rejection reason contains `"Grok window <= 15% remaining (cutoff policy)"` | **PASS** |
| **5** | **Grok Boundary: Below 15.0% (14.9%)** | Below 15.0% (e.g. 14.9%) quota must be rejected | `tests/test_admission.py:197-201`: `test_grok_below_15_percent_rejected` asserts `len(valid) == 0` and rejection reason contains `"Grok window <= 15% remaining (cutoff policy)"` | **PASS** |
| **6** | **Grok Boundary: Above 15.0% (15.1%)** | Above 15.0% (e.g. 15.1%) quota must be admitted | `tests/test_admission.py:202-207`: `test_grok_above_15_percent_admitted` asserts `len(valid) == 1` and `valid[0]["provider"] == "grok"` | **PASS** |
| **7** | **Codex Boundary & Fail-Closed Gate** | Codex `<= 15.0%`, unknown windows, stale resets blocked | `tests/test_admission.py:99-125`: `test_codex_at_15_remaining_rejected`, `test_codex_unknown_window_fail_closed`, `test_codex_gate_helper`, `test_codex_unsupported_even_when_ample` pass | **PASS** |
| **8** | **Fail-Closed on Missing / Unparseable Windows** | Missing windows, empty dicts, NaNs, Infs, non-numerics, naive datetimes fail closed | Tested across `test_missing_reset_at`, `test_nonnumeric_percent`, `test_nan_percent_rejected`, `test_inf_percent_rejected`, `test_naive_reset_at_no_crash_and_fail_closed`, `test_per_route_exception_isolation` | **PASS** |
| **9** | **Admission Test Suite Execution** | `python3 -m unittest tests/test_admission.py` | 28/28 tests passed cleanly in 0.027s with zero failures and zero errors | **PASS** |
| **10** | **Task Execution Integrity & Staged Commit** | Clean execution lifecycle, zero stderr, atomic commit | `grok-five-percent-admission-stderr.log` is 0 bytes; commit `50debca` serialized via `flock .local/git.lock` preserving unstaged work | **PASS** |

---

## 2. Commit & Source Inspection (`commit 50debca`)

Commit `50debca` represents a minimal, focused change targeting solely the admission threshold and its boundary tests:

```diff
commit 50debcade71bffa2793fcdb822c4fc41aee91ef0
Author: Alexey Grigorev <alexey.s.grigoriev@gmail.com>
Date:   Tue Oct 6 01:23:49 2026 +0200

    Update Grok minimum remaining quota threshold to 15%

diff --git a/launcher/admission.py b/launcher/admission.py
index 187e386..8386c2e 100644
--- a/launcher/admission.py
+++ b/launcher/admission.py
@@ -19,7 +19,7 @@ ADAPTER_MODELS = {
     "zai": "glm-5.3-flash",
 }
 CODEX_MIN_REMAINING = 15.0
-GROK_MIN_REMAINING = 5.0
+GROK_MIN_REMAINING = 15.0
 
 # Promotion stays disabled until a verified ZCode >=3.10 GLM-5.3-Flash
 # subscription route exists; even inside the campaign window the multiplier is
diff --git a/tests/test_admission.py b/tests/test_admission.py
index da77b83..a422d27 100644
--- a/tests/test_admission.py
+++ b/tests/test_admission.py
@@ -187,20 +187,20 @@ class TestAdmission(unittest.TestCase):
             data = fetch_quse()
         self.assertIn("grok", data)
 
-    def test_grok_at_exactly_5_percent_rejected(self):
-        data = {"grok": grok_route({"7d": {"percent_remaining": 5.0, "reset_at": self.future1}})}
+    def test_grok_at_exactly_15_percent_rejected(self):
+        data = {"grok": grok_route({"7d": {"percent_remaining": 15.0, "reset_at": self.future1}})}
         valid, rej = validate_quse(data)
         self.assertEqual(len(valid), 0)
-        self.assertIn("Grok window <= 5% remaining (cutoff policy)", rej.get("grok", ""))
+        self.assertIn("Grok window <= 15% remaining (cutoff policy)", rej.get("grok", ""))
 
-    def test_grok_below_5_percent_rejected(self):
-        data = {"grok": grok_route({"7d": {"percent_remaining": 4.9, "reset_at": self.future1}})}
+    def test_grok_below_15_percent_rejected(self):
+        data = {"grok": grok_route({"7d": {"percent_remaining": 14.9, "reset_at": self.future1}})}
         valid, rej = validate_quse(data)
         self.assertEqual(len(valid), 0)
-        self.assertIn("Grok window <= 5% remaining (cutoff policy)", rej.get("grok", ""))
+        self.assertIn("Grok window <= 15% remaining (cutoff policy)", rej.get("grok", ""))
 
-    def test_grok_above_5_percent_admitted(self):
-        data = {"grok": grok_route({"7d": {"percent_remaining": 5.1, "reset_at": self.future1}})}
+    def test_grok_above_15_percent_admitted(self):
+        data = {"grok": grok_route({"7d": {"percent_remaining": 15.1, "reset_at": self.future1}})}
         valid, rej = validate_quse(data)
         self.assertEqual(len(valid), 1)
         self.assertEqual(valid[0]["provider"], "grok")
```

---

## 3. Subsystem Architecture & Gate Evaluation

### 3.1 Codex Reservation Gate (`codex_gate_reason`)
In `launcher/admission.py:82-101`:
```python
def codex_gate_reason(route, now):
    """Codex fail-closed gate: any window <=15% remaining, unknown or stale
    blocks the route. Returns a rejection reason or None when all known."""
    windows = route.get("windows")
    if not isinstance(windows, dict) or not windows:
        return "codex fail-closed: no window evidence"
    for win_name, win in windows.items():
        if not isinstance(win, dict):
            return f"codex fail-closed: malformed window {win_name}"
        perc = _percent(win)
        if perc is None:
            return f"codex fail-closed: unknown window reading ({win_name})"
        reset_time = parse_iso(win.get("reset_at"))
        if reset_time is None:
            return f"codex fail-closed: unknown window timezone/reset ({win_name})"
        if reset_time < now:
            return f"codex fail-closed: stale window evidence ({win_name})"
        if perc <= CODEX_MIN_REMAINING:
            return f"codex window {win_name} <= {CODEX_MIN_REMAINING:g}% remaining"
    return None
```
- **Strict inequality comparison**: `perc <= CODEX_MIN_REMAINING` ensures that 15.0% remaining is rejected.
- **Fail-closed on any missing/stale/unparseable window**: Unlike adapter-backed execution where non-applicable windows (like `monthly: null`) may be present in `quse` output, Codex fails closed on *any* unknown reading.
- **Defense in depth**: Even if `codex_gate_reason` passes, `_validate_route` verifies the presence of `scripts/launch-codex.sh`, rejecting Codex with `"codex explicitly unsupported in launcher v0.1"` if the protected wrapper is absent.

### 3.2 Grok Reservation Gate (`_validate_route`)
In `launcher/admission.py:135-176`:
```python
    windows = route.get("windows")
    if not isinstance(windows, dict) or not windows:
        return None, "Missing route evidence (no windows)"

    min_rem = 100.0
    min_hours = None
    exhausted = False
    valid_evidence = False
    stale_evidence = False

    for win_name, win in windows.items():
        if not isinstance(win, dict):
            continue
        perc = _percent(win)
        reset_time = parse_iso(win.get("reset_at"))
        if perc is None or reset_time is None:
            continue
        if reset_time < now:
            stale_evidence = True
            continue

        valid_evidence = True
        if perc <= 0:
            exhausted = True
        if perc < min_rem:
            min_rem = perc
        ...

    if stale_evidence and not valid_evidence:
        return None, "Stale route evidence"
    if not valid_evidence:
        return None, ("Missing valid route evidence (nonfinite percent, missing/naive "
                      "reset timezone, or stale reset_at)")
    if exhausted:
        return None, "Quota exhausted"
    if provider == "grok" and min_rem <= GROK_MIN_REMAINING:
        return None, f"Grok window <= {GROK_MIN_REMAINING:g}% remaining (cutoff policy)"
```
- **Threshold**: `GROK_MIN_REMAINING = 15.0`
- **Operator**: `min_rem <= GROK_MIN_REMAINING`
- **Minimum Window Aggregation**: If Grok has multiple active windows (e.g. `5h` and `7d`), `min_rem` tracks the lowest remaining percentage across all valid windows. Any window at or below 15.0% rejects the entire Grok route.
- **Handling of Unused / Absent Windows**: `quse` reports Grok with `"5h": {"percent_remaining": null}` and `"monthly": {"percent_remaining": null}`. The loop ignores windows where `perc is None or reset_time is None` without falsely treating them as 0%, while requiring at least one valid window (`valid_evidence == True`) to admit.

---

## 4. Test Suite Execution & Output

Running `python3 -m unittest tests/test_admission.py -v` produces:

```text
test_codex_at_15_remaining_rejected (tests.test_admission.TestAdmission.test_codex_at_15_remaining_rejected) ... ok
test_codex_gate_helper (tests.test_admission.TestAdmission.test_codex_gate_helper) ... ok
test_codex_unknown_window_fail_closed (tests.test_admission.TestAdmission.test_codex_unknown_window_fail_closed) ... ok
test_codex_unsupported_even_when_ample (tests.test_admission.TestAdmission.test_codex_unsupported_even_when_ample) ... ok
test_exhausted_window (tests.test_admission.TestAdmission.test_exhausted_window) ... ok
test_fetch_quse_rejects_truncated_json (tests.test_admission.TestAdmission.test_fetch_quse_rejects_truncated_json) ... ok
test_fetch_quse_salvages_trailing_garbage (tests.test_admission.TestAdmission.test_fetch_quse_salvages_trailing_garbage) ... ok
test_gemini_maps_to_antigravity (tests.test_admission.TestAdmission.test_gemini_maps_to_antigravity) ... ok
test_grok_above_15_percent_admitted (tests.test_admission.TestAdmission.test_grok_above_15_percent_admitted) ... ok
test_grok_absent_window_not_interpreted_as_zero (tests.test_admission.TestAdmission.test_grok_absent_window_not_interpreted_as_zero) ... ok
test_grok_at_exactly_15_percent_rejected (tests.test_admission.TestAdmission.test_grok_at_exactly_15_percent_rejected) ... ok
test_grok_below_15_percent_rejected (tests.test_admission.TestAdmission.test_grok_below_15_percent_rejected) ... ok
test_grok_entitlement_required (tests.test_admission.TestAdmission.test_grok_entitlement_required) ... ok
test_grok_exhausted_rejected (tests.test_admission.TestAdmission.test_grok_exhausted_rejected) ... ok
test_grok_failed_reading_rejected (tests.test_admission.TestAdmission.test_grok_failed_reading_rejected) ... ok
test_grok_limit_reached_rejected (tests.test_admission.TestAdmission.test_grok_limit_reached_rejected) ... ok
test_inf_percent_rejected (tests.test_admission.TestAdmission.test_inf_percent_rejected) ... ok
test_limit_reached (tests.test_admission.TestAdmission.test_limit_reached) ... ok
test_missing_reset_at (tests.test_admission.TestAdmission.test_missing_reset_at) ... ok
test_naive_reset_at_no_crash_and_fail_closed (tests.test_admission.TestAdmission.test_naive_reset_at_no_crash_and_fail_closed) ... ok
test_nan_percent_rejected (tests.test_admission.TestAdmission.test_nan_percent_rejected) ... ok
test_nonnumeric_percent (tests.test_admission.TestAdmission.test_nonnumeric_percent) ... ok
test_per_route_exception_isolation (tests.test_admission.TestAdmission.test_per_route_exception_isolation) ... ok
test_stale_evidence (tests.test_admission.TestAdmission.test_stale_evidence) ... ok
test_task_fit_known_against_requirements (tests.test_admission.TestAdmission.test_task_fit_known_against_requirements) ... ok
test_task_fit_unknown_without_requirements (tests.test_admission.TestAdmission.test_task_fit_unknown_without_requirements) ... ok
test_unsupported_routes_blocked (tests.test_admission.TestAdmission.test_unsupported_routes_blocked) ... ok
test_valid_route (tests.test_admission.TestAdmission.test_valid_route) ... ok

----------------------------------------------------------------------
Ran 28 tests in 0.027s

OK
```

All 28 admission unit tests pass cleanly.

---

## 5. Adversarial Probe Battery

To rigorously challenge the implementation beyond the checked-in unit test suite, an independent adversarial probe battery was executed across boundary edge cases:

1. **Multi-Window Interaction**:
   - `5h = 100.0%`, `7d = 15.0%`: **REJECTED** (`Grok window <= 15% remaining (cutoff policy)`).
   - `5h = 15.0%`, `7d = 100.0%`: **REJECTED** (`Grok window <= 15% remaining (cutoff policy)`).
   - `5h = 15.1%`, `7d = 15.1%`: **ADMITTED** (`valid[0]["provider"] == "grok"`).
2. **Type Confusion & NaN Attacks**:
   - `percent_remaining: True` (Python `bool` subclass of `int`): Caught by `isinstance(perc, bool)` in `_percent()`, evaluates to `None`, rejects route (**PASS**).
   - `percent_remaining: float("nan")`: `math.isfinite(perc)` is False, evaluates to `None`, rejects route (**PASS**).
   - `percent_remaining: float("inf")`: `math.isfinite(perc)` is False, evaluates to `None`, rejects route (**PASS**).
3. **Missing & Naive Timezones**:
   - `reset_at: None`: Rejected with `"Missing valid route evidence"` (**PASS**).
   - `reset_at: "2026-10-07T12:00:00"` (offset-naive): Ignored by aware datetime comparison, rejected if sole window (**PASS**).
   - Empty windows dict `{}`: Rejected with `"Missing route evidence (no windows)"` (**PASS**).
4. **Codex Fail-Closed Completeness**:
   - Exactly 15.0%: Returns rejection reason `codex window 7d <= 15% remaining` (**PASS**).
   - Below 15.0% (14.9%): Returns rejection reason `codex window 7d <= 15% remaining` (**PASS**).
   - Above 15.0% (15.1%): `codex_gate_reason` returns `None` (**PASS**).
   - Unknown window reading: Returns `codex fail-closed: unknown window reading (5h)` (**PASS**).

---

## 6. Execution Lifecycle & Task Provenance

Inspection of task logs in `/home/alexey/git/agent-quota-launcher/.local/launcher-config/`:
- **Stdout Log**: `grok-five-percent-admission-stdout.log` (73,984 bytes) confirms initial model prompt:
  `Update Grok minimum remaining quota threshold to 15%: verify launcher/admission.py CODEX_MIN_REMAINING is 15.0, set GROK_MIN_REMAINING to 15.0, and update tests/test_admission.py to verify 15.0% rejected, 14.9% rejected, 15.1% admitted.`
- **First Model Tool Execution**: Step index 2 executed `run_command` with non-trivial discovery command (`find . -type f ...`), followed by reading files, modifying code via `replace_file_content`, executing unit tests (`python3 -m unittest tests.test_admission`), verifying discovery tests, and committing using `flock .local/git.lock git commit ...`.
- **Stderr Log**: `grok-five-percent-admission-stderr.log` is **0 bytes**.
- **Exit Status**: `SUCCESS`, exit code 0.
- **Git Hygiene**: Committed only the intended files (`launcher/admission.py` and `tests/test_admission.py`), preserving unstaged work in `launcher/launch.py` and `launcher/store.py` intact.

---

## 7. Audit Findings & Final Verdict

1. **Threshold Alignment**: Both `CODEX_MIN_REMAINING` and `GROK_MIN_REMAINING` are strictly configured to `15.0`.
2. **Boundary Logic**: Rejections occur at both `< 15.0` and `== 15.0` using `<=` comparisons; admission occurs strictly at `> 15.0%`.
3. **Fail-Closed Robustness**: Unparseable, missing, NaN, Inf, boolean, and naive timestamp windows fail closed and do not fabricate headroom.
4. **Isolation**: Per-route exceptions are caught and reported in `rejections` without aborting other candidate routes.
5. **Clean Test Pass**: All 28 tests in `tests/test_admission.py` pass cleanly.

**Final Verdict**: **ACCEPTED**
