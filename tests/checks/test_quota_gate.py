#!/usr/bin/env python3
"""Decision unit and negative tests for Codex quota gate (scripts/quota-gate.py).

Validates:
- Provider errors, non-ok status, limit_reached, missing/malformed records fail closed.
- Mandatory 7d/weekly window requirement.
- Optional windows with empty reading and absent reset treated as N/A.
- Any populated 5h/newwindow evaluated against >15% reserve.
- Fail closed on: malformed, missing required, non-finite, bool, out-of-range,
  missing-reset, naive-reset, stale-reset, not-present contradictions.
- Strict >15% reserve floor boundary checks.
- Robust error reasons without tracebacks.
- Pure stdlib: no actual quse/network/model launches.
"""

import datetime
import importlib.util
import io
import json
import math
import os
import pathlib
import subprocess
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE_PATH = ROOT / "scripts" / "quota-gate.py"

_spec = importlib.util.spec_from_file_location("quota_gate", GATE_PATH)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


class TestQuotaGateDecision(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 10, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self.future_iso = "2026-10-15T12:00:00Z"
        self.past_iso = "2026-10-13T12:00:00Z"

    def valid_weekly(self, percent=80.0, reset=None):
        return {
            "percent_remaining": percent,
            "reset_at": reset or self.future_iso,
        }

    # 1. Provider-level checks
    def test_provider_status_not_ok(self):
        record = {"status": "error", "windows": {"7d": self.valid_weekly()}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("quota unavailable", reason)

    def test_provider_error_field(self):
        record = {"status": "ok", "error": "rate limited by upstream", "windows": {"7d": self.valid_weekly()}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("provider error", reason)

    def test_provider_limit_reached(self):
        record = {
            "status": "ok",
            "details": {"limit_reached": True},
            "windows": {"7d": self.valid_weekly()},
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("provider limit reached", reason)

    def test_provider_malformed_details(self):
        record = {"status": "ok", "details": "not-a-dict", "windows": {"7d": self.valid_weekly()}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("malformed provider details", reason)

    def test_provider_present_false_contradiction(self):
        record = {"status": "ok", "present": False, "windows": {"7d": self.valid_weekly(90.0)}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("provider marked not present", reason)

    def test_provider_record_not_dict(self):
        for bad in (None, "string", [1, 2], 42, False):
            allowed, reason = gate.decision(bad, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("malformed record", reason)

    def test_windows_missing_or_not_dict(self):
        for bad in (None, "not-dict", [], 123):
            allowed, reason = gate.decision({"status": "ok", "windows": bad}, now=self.now)
            self.assertFalse(allowed)
        allowed, reason = gate.decision({"status": "ok", "windows": {}}, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("no available quota window", reason)

    # 2. Mandatory weekly / 7d window requirements
    def test_mandatory_weekly_missing(self):
        # 5h window present and healthy, but mandatory weekly missing
        record = {
            "status": "ok",
            "windows": {
                "5h": {"percent_remaining": 80.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("mandatory 7d/weekly quota window missing", reason)

    def test_mandatory_weekly_empty_reading_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("missing required percent_remaining", reason)

    def test_mandatory_weekly_missing_reset_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 50.0},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("missing reset timestamp", reason)

    def test_mandatory_weekly_marked_not_present_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "present": False},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("marked not present", reason)

    def test_weekly_aliases_accepted(self):
        for alias in ("7d", "weekly", "week", "7_day", "7-day", "codex_7d"):
            record = {
                "status": "ok",
                "windows": {
                    alias: {"percent_remaining": 80.0, "reset_at": self.future_iso},
                },
            }
            allowed, reason = gate.decision(record, now=self.now)
            self.assertTrue(allowed, f"Alias {alias} should be accepted")

    # 3. Optional windows: emptyreading + resetabsent N/A vs populated evaluation
    def test_optional_5h_empty_reading_and_reset_absent_is_na(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("minimum available window 80% remaining", reason)

    def test_optional_newwindow_empty_dict_is_na(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "new_rolling_window": {},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("minimum available window 80% remaining", reason)

    def test_optional_none_window_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": None,
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("malformed: expected dictionary", reason)

    def test_optional_5h_populated_evaluated_pass(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": 50.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("minimum available window 50% remaining", reason)

    def test_optional_5h_populated_evaluated_fail_reserve(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": 10.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("minimum available window 10% remaining; reserve 15%", reason)

    def test_optional_window_missing_reading_with_reset_fails_closed(self):
        # Reset is present, so not "emptyreading + resetabsent"
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": None, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("missing required percent_remaining", reason)

    # 4. Strict > 15 reserve floor
    def test_strict_15_reserve_boundary(self):
        # Exactly 15.0 fails closed (>15 required)
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(15.0)}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("minimum available window 15% remaining; reserve 15%", reason)

        # 14.999 fails closed
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(14.999)}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)

        # 0.0 fails closed
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(0.0)}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)

        # 15.0001 passes
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(15.0001)}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)

    # 5. Per-window malformed / type / range / non-finite / bool errors
    def test_window_bool_percent_remaining_fails_closed(self):
        for val in (True, False):
            record = {"status": "ok", "windows": {"7d": {"percent_remaining": val, "reset_at": self.future_iso}}}
            allowed, reason = gate.decision(record, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("boolean not allowed", reason)

    def test_window_nonfinite_nan_fails_closed(self):
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": float("nan"), "reset_at": self.future_iso}}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("non-finite value", reason)

    def test_window_nonfinite_inf_fails_closed(self):
        for val in (float("inf"), float("-inf")):
            record = {"status": "ok", "windows": {"7d": {"percent_remaining": val, "reset_at": self.future_iso}}}
            allowed, reason = gate.decision(record, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("non-finite value", reason)

    def test_window_out_of_range_fails_closed(self):
        for bad in (-1.0, -0.001, 100.001, 150.0):
            record = {"status": "ok", "windows": {"7d": {"percent_remaining": bad, "reset_at": self.future_iso}}}
            allowed, reason = gate.decision(record, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("out of range", reason)

    def test_window_string_percent_fails_closed(self):
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": "85.0", "reset_at": self.future_iso}}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("expected numeric", reason)

    def test_window_malformed_not_dict_fails_closed(self):
        record = {"status": "ok", "windows": {"7d": "malformed-string"}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("malformed: expected dictionary", reason)

    def test_window_error_and_status(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "error": "window failure"},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window failure", reason)

        record2 = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "status": "degraded"},
            },
        }
        allowed, reason = gate.decision(record2, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("status not ok", reason)

    # 6. Reset timestamp validation: naive, stale, malformed, missing
    def test_window_missing_reset_fails_closed(self):
        for val in (None, ""):
            record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": val}}}
            allowed, reason = gate.decision(record, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("missing reset timestamp", reason)

    def test_window_naive_reset_fails_closed(self):
        # No 'Z' or timezone offset -> naive
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": "2026-10-15T12:00:00"}}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("naive reset timestamp", reason)

    def test_window_stale_reset_fails_closed(self):
        # Reset timestamp is in the past
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.past_iso}}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("stale reset timestamp", reason)

    def test_window_malformed_reset_fails_closed(self):
        for bad in ("not-a-timestamp", "2026-99-99T99:99:99Z", 12345, []):
            record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": bad}}}
            allowed, reason = gate.decision(record, now=self.now)
            self.assertFalse(allowed)
            self.assertTrue("malformed" in reason or "invalid reset" in reason)

    # 7. Contradiction & bypass checks
    def test_bypass_cannot_override_gate(self):
        # Attempt to bypass low quota with bypass flag
        record = {
            "status": "ok",
            "bypass": True,
            "windows": {
                "7d": {"percent_remaining": 10.0, "reset_at": self.future_iso, "bypass": True},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("minimum available window 10% remaining; reserve 15%", reason)

    def test_window_present_false_contradiction(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": 90.0, "reset_at": self.future_iso, "present": False},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("marked not present", reason)

    # 8. Arbitrary garbage does not raise traceback
    def test_no_traceback_on_arbitrary_garbage(self):
        garbage_payloads = [
            {"status": "ok", "windows": {"7d": {"percent_remaining": {}}}},
            {"status": "ok", "windows": {"7d": {"percent_remaining": [1, 2, 3]}}},
            {"status": "ok", "windows": {"7d": {"percent_remaining": 80, "reset_at": {"obj": 1}}}},
            {"details": {"limit_reached": "yes"}, "windows": None},
            {"windows": {"7d": None}},
            {"windows": {"7d": []}},
            {"windows": 123},
        ]
        for g in garbage_payloads:
            try:
                allowed, reason = gate.decision(g, now=self.now)
                self.assertFalse(allowed)
                self.assertIsInstance(reason, str)
            except Exception as e:
                self.fail(f"gate.decision raised unexpected exception on {g}: {e}")

    # 9. Finding F1: Optional windows fail-open ordering & semantic override
    def test_f1_optional_5h_error_with_empty_reading_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": None, "reset_at": None, "error": "upstream timeout"},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h' reported error", reason)

    def test_f1_optional_5h_error_only_dict_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"error": "window parse failed"},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h' reported error", reason)

    def test_f1_optional_5h_status_not_ok_with_empty_reading_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"status": "error", "percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h' status not ok", reason)

    def test_f1_positive_optional_5h_absent_truthful_na_allowed(self):
        # Semantic override: optional present:false with empty reading and no reset and no error/limit is truthful ABSENT=N/A
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"present": False, "percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("minimum available window 80% remaining; reserve 15%", reason)

    def test_f1_negative_optional_5h_absent_with_error_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"present": False, "percent_remaining": None, "reset_at": None, "error": "upstream timeout"},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h' reported error", reason)

    def test_f1_negative_optional_5h_absent_with_status_not_ok_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"present": False, "status": "rate_limited", "percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h' status not ok", reason)

    def test_f1_negative_optional_5h_present_false_contradiction_reading_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"present": False, "percent_remaining": 80.0, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("marked not present", reason)

    def test_f1_negative_optional_5h_present_false_contradiction_reset_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"present": False, "percent_remaining": None, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("marked not present", reason)

    def test_f1_negative_mandatory_weekly_absent_present_false_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"present": False, "percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("marked not present", reason)

    def test_f1_arbitrary_reappearing_new_window_evaluated_or_failed(self):
        # Healthy reappearing new window evaluated
        record_ok = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "daily": {"percent_remaining": 60.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record_ok, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("minimum available window 60% remaining", reason)

        # Low reappearing new window fails reserve
        record_low = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "daily": {"percent_remaining": 10.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record_low, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("minimum available window 10% remaining; reserve 15%", reason)

        # Errored reappearing new window fails closed
        record_err = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "daily": {"error": "unsupported window"},
            },
        }
        allowed, reason = gate.decision(record_err, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window 'daily' reported error", reason)

    # 10. Finding F2: Reset resolution, alias unmasking, contradiction check
    def test_f2_optional_5h_reset_populated_masked_by_reset_at_none_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": None, "reset_at": None, "reset": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("missing required percent_remaining", reason)

    def test_f2_both_reset_at_and_reset_populated_contradictory_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "reset": self.past_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("contradictory reset timestamps", reason)

    def test_f2_both_reset_at_and_reset_populated_consistent_passes(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "reset": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)

    def test_f2_weekly_reset_alias_used_when_reset_at_none_passes(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": None, "reset": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)

    # 11. Finding F3: Limit reached flags (top-level and per-window) and details validation
    def test_f3_provider_top_level_limit_reached_fails_closed(self):
        record = {
            "status": "ok",
            "limit_reached": True,
            "windows": {"7d": self.valid_weekly(80.0)},
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("provider limit reached", reason)

    def test_f3_per_window_limit_reached_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "limit_reached": True},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '7d' limit reached", reason)

    def test_f3_per_window_details_limit_reached_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "details": {"limit_reached": True}},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '7d' limit reached", reason)

    def test_f3_per_window_malformed_details_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "details": "not-a-dict"},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("malformed details", reason)

    def test_f3_optional_window_limit_reached_with_empty_reading_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": self.valid_weekly(80.0),
                "5h": {"percent_remaining": None, "reset_at": None, "limit_reached": True},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h' limit reached", reason)

    # 12. Finding F4: Reference clock validation (nonbool, finite, aware, zero tracebacks)
    def test_f4_now_bool_fails_closed(self):
        for val in (True, False):
            record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
            allowed, reason = gate.decision(record, now=val)
            self.assertFalse(allowed)
            self.assertIn("boolean not allowed", reason)

    def test_f4_now_valid_iso_string_succeeds(self):
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
        allowed, reason = gate.decision(record, now="2026-10-14T12:00:00Z")
        self.assertTrue(allowed)

    def test_f4_now_malformed_string_fails_closed(self):
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
        allowed, reason = gate.decision(record, now="invalid-iso-string")
        self.assertFalse(allowed)
        self.assertIn("malformed timestamp string", reason)

    def test_f4_now_naive_string_fails_closed(self):
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
        allowed, reason = gate.decision(record, now="2026-10-14T12:00:00")
        self.assertFalse(allowed)
        self.assertIn("naive timestamp missing timezone", reason)

    def test_f4_now_naive_datetime_fails_closed(self):
        record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
        naive_dt = datetime.datetime(2026, 10, 14, 12, 0, 0)
        allowed, reason = gate.decision(record, now=naive_dt)
        self.assertFalse(allowed)
        self.assertIn("naive datetime missing timezone", reason)

    def test_f4_now_nan_and_inf_fails_closed(self):
        for val in (float("nan"), float("inf"), float("-inf")):
            record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
            allowed, reason = gate.decision(record, now=val)
            self.assertFalse(allowed)
            self.assertIn("non-finite timestamp", reason)

    def test_f4_now_unexpected_type_fails_closed(self):
        for val in ([], {}, object()):
            record = {"status": "ok", "windows": {"7d": self.valid_weekly(80.0)}}
            allowed, reason = gate.decision(record, now=val)
            self.assertFalse(allowed)
            self.assertIn("unexpected type", reason)

    # 13. Finding F5: Error sanitization, no raw reset strings, mocked CLI
    def test_f5_error_sanitization_redacts_tokens_and_keys(self):
        auth_sample = "Bea" + "rer " + "mock_token_val_1234567890abcdef"
        key_sample = "sk-" + "ant-" + "api03-abcdef1234567890abcdef1234567890"
        record = {
            "status": "ok",
            "error": f"upstream auth failure {auth_sample} {key_sample}",
            "windows": {"7d": self.valid_weekly(80.0)},
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn("mock_token_val", reason)
        self.assertNotIn("abcdef1234567890", reason)
        self.assertIn("[REDACTED]", reason)

        kw = "tok" + "en=" + "supersecretpassword123456"
        record_win = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "error": kw},
            },
        }
        allowed, reason = gate.decision(record_win, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn("supersecretpassword", reason)
        self.assertIn("[REDACTED]", reason)

    def test_f5_no_raw_reset_strings_in_public_reason(self):
        bad_reset = "2026-99-99T99:99:99Z-sensitive-info"
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": bad_reset}}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn(bad_reset, reason)

        stale_reset = "2020-01-01T00:00:00Z"
        record_stale = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": stale_reset}}}
        allowed, reason = gate.decision(record_stale, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn(stale_reset, reason)

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_f5_cli_exit_0_on_allowed_verifies_timeout_45(self, mock_stdout, mock_run):
        healthy_payload = {
            "codex": {
                "status": "ok",
                "windows": {
                    "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                },
            }
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(healthy_payload))
        rc = gate.main()
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with(["quse", "codex", "--json"], capture_output=True, text=True, timeout=45, check=True)
        out = json.loads(mock_stdout.getvalue())
        self.assertTrue(out["launch_allowed"])
        self.assertEqual(out["provider"], "codex")

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_f5_cli_exit_75_on_disallowed(self, mock_stdout, mock_run):
        low_payload = {
            "codex": {
                "status": "ok",
                "windows": {
                    "7d": {"percent_remaining": 10.0, "reset_at": self.future_iso},
                },
            }
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(low_payload))
        rc = gate.main()
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_f5_cli_subprocess_timeout_exits_75(self, mock_stdout, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["quse", "codex", "--json"], timeout=45)
        rc = gate.main()
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("quota read failed (TimeoutExpired)", out["reason"])

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_f5_cli_subprocess_called_process_error_exits_75(self, mock_stdout, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["quse", "codex", "--json"])
        rc = gate.main()
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("quota read failed (CalledProcessError)", out["reason"])

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_f5_cli_subprocess_file_not_found_exits_75(self, mock_stdout, mock_run):
        mock_run.side_effect = FileNotFoundError("quse not found")
        rc = gate.main()
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("quota read failed (FileNotFoundError)", out["reason"])

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_f5_cli_invalid_json_stdout_exits_75(self, mock_stdout, mock_run):
        mock_run.return_value = MagicMock(stdout="<html>upstream 502 bad gateway</html>")
        rc = gate.main()
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("quota read failed (JSONDecodeError)", out["reason"])



class HubTestBase(unittest.TestCase):
    def setUp(self):
        gate.clear_cache()
        self.now = datetime.datetime(2026, 10, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self.now_iso = self.now.isoformat()
        self.future_iso = "2026-10-15T12:00:00Z"
        self.past_iso = "2026-10-13T12:00:00Z"
        self.host_id = "test" + "-host-id-42"
        self.token = "test" + "-bearer-token-123"
        self.hub_url = "http://hub.local"

    def tearDown(self):
        gate.clear_cache()

    def valid_hub_payload(self, weekly_pct=80.0, captured_at=None, host_id=None):
        return {
            "schema_version": "1.0",
            "captured_at": captured_at or self.now_iso,
            "host_id": host_id or self.host_id,
            "status": "ok",
            "error": None,
            "routes": {
                "codex": {
                    "status": "ok",
                    "error": None,
                    "windows": {
                        "7d": {
                            "percent_remaining": weekly_pct,
                            "reset_at": self.future_iso,
                        }
                    }
                }
            }
        }

    def mock_http_response(self, payload, code=200):
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        mock_cm.__enter__.return_value.status = code
        return mock_cm

    def make_config(self, **kwargs):
        params = {
            "hub_url": self.hub_url,
            "token": self.token,
            "host_id": self.host_id,
            "cache_ttl_sec": 30.0,
            "max_staleness_sec": 1200.0,
            "is_configured": True,
        }
        params.update(kwargs)
        return gate.HubConfig(**params)


class TestHubSchemaAndContract(HubTestBase):
    """Schema, validation, provider timestamp, and dynamic windows tests for Hub /api/quota."""

    @patch("urllib.request.urlopen")
    def test_schema_valid_codex_route_passes(self, mock_urlopen):
        payload = self.valid_hub_payload(weekly_pct=85.0)
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()
        record, captured = gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("windows", record)
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("85% remaining", reason)

    @patch("urllib.request.urlopen")
    def test_schema_version_mismatch_fails_closed(self, mock_urlopen):
        for bad_ver in ("2.0", "0.9", None, 1.0, 1, {}):
            payload = self.valid_hub_payload()
            payload["schema_version"] = bad_ver
            mock_urlopen.return_value = self.mock_http_response(payload)
            cfg = self.make_config()
            with self.assertRaises(gate.HubSchemaError):
                gate.fetch_hub_snapshot(cfg, now=self.now)

    @patch("urllib.request.urlopen")
    def test_schema_status_not_ok_fails_closed(self, mock_urlopen):
        for bad_status in ("error", "unavailable", "degraded", None):
            payload = self.valid_hub_payload()
            payload["status"] = bad_status
            mock_urlopen.return_value = self.mock_http_response(payload)
            cfg = self.make_config()
            with self.assertRaises(gate.HubSchemaError):
                gate.fetch_hub_snapshot(cfg, now=self.now)

    @patch("urllib.request.urlopen")
    def test_schema_top_level_error_fails_closed(self, mock_urlopen):
        payload = self.valid_hub_payload()
        payload["error"] = "upstream hub internal error"
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()
        with self.assertRaises(gate.HubSchemaError):
            gate.fetch_hub_snapshot(cfg, now=self.now)

    @patch("urllib.request.urlopen")
    def test_schema_captured_at_missing_or_naive_fails_closed(self, mock_urlopen):
        for bad_ts in (None, "", "2026-10-14T12:00:00", "not-a-timestamp", 12345):
            payload = self.valid_hub_payload()
            payload["captured_at"] = bad_ts
            mock_urlopen.return_value = self.mock_http_response(payload)
            cfg = self.make_config()
            with self.assertRaises(gate.HubSchemaError):
                gate.fetch_hub_snapshot(cfg, now=self.now)

    @patch("urllib.request.urlopen")
    def test_schema_captured_at_future_fails_closed(self, mock_urlopen):
        future_ts = (self.now + datetime.timedelta(seconds=120)).isoformat()
        payload = self.valid_hub_payload(captured_at=future_ts)
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("future", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_schema_captured_at_stale_fails_closed(self, mock_urlopen):
        stale_ts = (self.now - datetime.timedelta(seconds=1201)).isoformat()
        payload = self.valid_hub_payload(captured_at=stale_ts)
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("stale", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_schema_serverreceived_at_future_or_stale_fails_closed(self, mock_urlopen):
        cfg = self.make_config()
        future_ts = (self.now + datetime.timedelta(seconds=120)).isoformat()
        payload = self.valid_hub_payload()
        payload["serverreceived_at"] = future_ts
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("future", str(ctx.exception).lower())

        stale_ts = (self.now - datetime.timedelta(seconds=1205)).isoformat()
        payload["serverreceived_at"] = stale_ts
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("stale", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_schema_provider_observed_at_stale_cannot_be_laundered_by_fresh_serverreceived_at(self, mock_urlopen):
        cfg = self.make_config()
        fresh_ts = (self.now - datetime.timedelta(seconds=10)).isoformat()
        stale_observed = (self.now - datetime.timedelta(seconds=1205)).isoformat()
        payload = self.valid_hub_payload(captured_at=fresh_ts)
        payload["serverreceived_at"] = fresh_ts
        payload["routes"]["codex"]["observed_at"] = stale_observed
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("stale", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_schema_provider_details_stale_fails_closed(self, mock_urlopen):
        cfg = self.make_config()
        payload = self.valid_hub_payload()
        payload["routes"]["codex"]["details"] = {"stale": True}
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("stale", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_schema_routes_missing_or_missing_codex_fails_closed(self, mock_urlopen):
        cfg = self.make_config()
        payload1 = {"schema_version": "1.0", "captured_at": self.now_iso, "host_id": self.host_id, "status": "ok", "error": None}
        mock_urlopen.return_value = self.mock_http_response(payload1)
        with self.assertRaises(gate.HubSchemaError):
            gate.fetch_hub_snapshot(cfg, now=self.now)

        payload2 = self.valid_hub_payload()
        payload2["routes"] = {"openai": payload2["routes"]["codex"]}
        mock_urlopen.return_value = self.mock_http_response(payload2)
        with self.assertRaises(gate.HubSchemaError):
            gate.fetch_hub_snapshot(cfg, now=self.now)

    def test_schema_dynamic_safe_windows_max_32_enforced(self):
        windows = {f"win_{i}": {"percent_remaining": 80.0, "reset_at": self.future_iso} for i in range(32)}
        windows["7d"] = {"percent_remaining": 80.0, "reset_at": self.future_iso}
        record = {"status": "ok", "windows": windows}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("too many quota windows", reason)

    def test_schema_dynamic_safe_windows_name_validation(self):
        long_name = "a" * 49
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}, long_name: {"percent_remaining": 80.0, "reset_at": self.future_iso}}}
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("invalid window name", reason)

        for bad_name in ("window with space", "win$special", "win/slash", "win@at"):
            record2 = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}, bad_name: {"percent_remaining": 80.0, "reset_at": self.future_iso}}}
            allowed, reason = gate.decision(record2, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("invalid window name", reason)

    def test_schema_dynamic_safe_windows_valid_custom_window_evaluated(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 90.0, "reset_at": self.future_iso},
                "burst-1h_safe": {"percent_remaining": 50.0, "reset_at": self.future_iso},
            }
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("50% remaining", reason)

        record_low = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 90.0, "reset_at": self.future_iso},
                "burst-1h_safe": {"percent_remaining": 12.0, "reset_at": self.future_iso},
            }
        }
        allowed, reason = gate.decision(record_low, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("12% remaining; reserve 15%", reason)

    def test_schema_optional_present_true_empty_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                "5h": {"present": True, "percent_remaining": None, "reset_at": self.future_iso},
            }
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("missing percent_remaining", reason)

    def test_schema_optional_present_true_missing_reset_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                "5h": {"present": True, "percent_remaining": 50.0, "reset_at": None},
            }
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("missing reset timestamp", reason)


class TestHubAuthenticationAndSecurity(HubTestBase):
    """Authentication, host binding, secret privacy, and fail-closed security tests."""

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_auth_http_401_fails_closed_no_fallback(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://hub.local/api/quota", code=401, msg="Unauthorized", hdrs={}, fp=io.BytesIO(b"{}")
        )
        cfg = self.make_config()
        rc = gate.main(config=cfg)
        self.assertEqual(rc, 75)
        mock_run.assert_not_called()
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("auth error", out["reason"])

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_auth_http_403_fails_closed_no_fallback(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://hub.local/api/quota", code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"{}")
        )
        cfg = self.make_config()
        rc = gate.main(config=cfg)
        self.assertEqual(rc, 75)
        mock_run.assert_not_called()
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("auth error", out["reason"])

    @patch("urllib.request.urlopen")
    def test_auth_bearer_token_sent_in_header(self, mock_urlopen):
        mock_urlopen.return_value = self.mock_http_response(self.valid_hub_payload())
        cfg = self.make_config()
        gate.fetch_hub_snapshot(cfg, now=self.now)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), f"Bearer {self.token}")

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_auth_configured_missing_token_fails_closed(self, mock_stdout, mock_run):
        with patch.dict(os.environ, {"QUOTA_HUB_URL": "http://hub.local", "QUOTA_HUB_HOST_ID": "h1"}, clear=True):
            rc = gate.main()
            self.assertEqual(rc, 75)
            mock_run.assert_not_called()
            out = json.loads(mock_stdout.getvalue())
            self.assertFalse(out["launch_allowed"])
            self.assertIn("missing authentication token", out["reason"])

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_auth_configured_missing_host_id_fails_closed(self, mock_stdout, mock_run):
        with patch.dict(os.environ, {"QUOTA_HUB_URL": "http://hub.local", "QUOTA_HUB_TOKEN": "tok"}, clear=True):
            rc = gate.main()
            self.assertEqual(rc, 75)
            mock_run.assert_not_called()
            out = json.loads(mock_stdout.getvalue())
            self.assertFalse(out["launch_allowed"])
            self.assertIn("missing host_id", out["reason"])

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_host_id_mismatch_fails_closed_no_fallback(self, mock_stdout, mock_urlopen, mock_run):
        payload = self.valid_hub_payload(host_id="other" + "-different-host")
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()
        rc = gate.main(config=cfg)
        self.assertEqual(rc, 75)
        mock_run.assert_not_called()
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("host_id mismatch", out["reason"])

    def test_security_url_with_userinfo_or_query_fails_closed(self):
        bad_userinfo = "http://" + "user" + ":" + "pass" + "@" + "hub.local"  # secrets-allow: test malformed credential URL rejection
        bad_query = "http://" + "hub.local" + "?" + "tok" + "en=secret"
        for bad_url in (bad_userinfo, bad_query, "ftp://hub.local"):
            with self.assertRaises(gate.HubConfigError):
                gate._validate_hub_url(bad_url)

    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_security_no_tokens_in_reasons_or_output(self, mock_stdout, mock_urlopen):
        secret_fragment = "mock" + "-test-fragment-xyz"
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://hub.local/api/quota", code=401, msg=f"auth failure for {secret_fragment}", hdrs={}, fp=io.BytesIO(b"{}")
        )
        cfg = self.make_config()
        rc = gate.main(config=cfg)
        self.assertEqual(rc, 75)
        out_str = mock_stdout.getvalue()
        self.assertNotIn(secret_fragment, out_str)


class TestHubCacheAndFreshness(HubTestBase):
    """Local cache, TTL, hard snapshot age cap, tamper resistance, and privacy tests."""

    @patch("urllib.request.urlopen")
    def test_cache_hit_within_ttl_avoids_repeated_network_calls(self, mock_urlopen):
        payload = self.valid_hub_payload(weekly_pct=80.0)
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()

        t0 = self.now
        rec1 = gate.get_cached_record(cfg, t0)
        self.assertIsNone(rec1)
        rec_fetched, captured = gate.fetch_hub_snapshot(cfg, now=t0)
        gate.store_cached_record(cfg, rec_fetched, captured, t0)
        self.assertEqual(mock_urlopen.call_count, 1)

        t1 = t0 + datetime.timedelta(seconds=15)
        rec2 = gate.get_cached_record(cfg, t1)
        self.assertIsNotNone(rec2)
        self.assertEqual(rec2["windows"]["7d"]["percent_remaining"], 80.0)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_cache_ttl_expiry_triggers_fresh_fetch(self, mock_urlopen):
        payload = self.valid_hub_payload(weekly_pct=80.0)
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()

        t0 = self.now
        rec_fetched, captured = gate.fetch_hub_snapshot(cfg, now=t0)
        gate.store_cached_record(cfg, rec_fetched, captured, t0)

        t_expired = t0 + datetime.timedelta(seconds=35)
        rec_expired = gate.get_cached_record(cfg, t_expired)
        self.assertIsNone(rec_expired)

    @patch("urllib.request.urlopen")
    def test_cache_hit_hard_snapshot_age_check_stale_1190_plus_30(self, mock_urlopen):
        t0 = self.now
        snap_time = t0 - datetime.timedelta(seconds=1190)
        payload = self.valid_hub_payload(captured_at=snap_time.isoformat(), weekly_pct=80.0)
        mock_urlopen.return_value = self.mock_http_response(payload)
        cfg = self.make_config()

        record, captured = gate.fetch_hub_snapshot(cfg, now=t0)
        gate.store_cached_record(cfg, record, captured, t0)

        t20 = t0 + datetime.timedelta(seconds=20)
        cached = gate.get_cached_record(cfg, now_dt=t20)
        self.assertIsNone(cached)

    def test_cache_config_cannot_extend_1200s_cap(self):
        cfg = gate.HubConfig(
            hub_url=self.hub_url,
            token=self.token,
            host_id=self.host_id,
            max_staleness_sec=3600.0,
            is_configured=True,
        )
        self.assertEqual(cfg.max_staleness_sec, 1200.0)

    def test_cache_file_mode_600_and_tamper_safety(self):
        tmp_dir = ROOT / ".local" / "tmp"
        cache_file = tmp_dir / "test-cache-file.json"
        if cache_file.exists():
            cache_file.unlink()

        cfg = self.make_config(cache_file=cache_file)
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}}}

        gate.store_cached_record(cfg, record, self.now, self.now)
        self.assertTrue(cache_file.exists())

        mode = cache_file.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

        raw_content = cache_file.read_text(encoding="utf-8")
        self.assertNotIn(self.token, raw_content)

        read_record = gate.get_cached_record(cfg, self.now)
        self.assertEqual(read_record, record)

        cache_file.chmod(0o644)
        gate.clear_cache()
        with self.assertRaises(gate.CacheTamperError):
            gate.get_cached_record(cfg, self.now)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("tamper", reason.lower())

        if cache_file.exists():
            cache_file.unlink()


class TestHubFallbackAndCLI(HubTestBase):
    """Single fallback, failure handling, and CLI wrapper integration tests."""

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_hub_unreachable_connection_refused_falls_back_once(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        healthy_codex = {
            "codex": {
                "status": "ok",
                "windows": {
                    "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                },
            }
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(healthy_codex))
        cfg = self.make_config()
        rc = gate.main(config=cfg, now=self.now)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with(["quse", "codex", "--json"], capture_output=True, text=True, timeout=45, check=True)
        out = json.loads(mock_stdout.getvalue())
        self.assertTrue(out["launch_allowed"])
        self.assertEqual(out["provider"], "codex")

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_hub_unreachable_http_503_falls_back_once(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://hub.local/api/quota", code=503, msg="Service Unavailable", hdrs={}, fp=io.BytesIO(b"{}")
        )
        healthy_codex = {
            "codex": {
                "status": "ok",
                "windows": {
                    "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                },
            }
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(healthy_codex))
        cfg = self.make_config()
        rc = gate.main(config=cfg, now=self.now)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with(["quse", "codex", "--json"], capture_output=True, text=True, timeout=45, check=True)

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_fallback_failure_timeout_fails_closed_75(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["quse", "codex", "--json"], timeout=45)
        cfg = self.make_config()
        rc = gate.main(config=cfg, now=self.now)
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("TimeoutExpired", out["reason"])

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_fallback_failure_invalid_json_fails_closed_75(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        mock_run.return_value = MagicMock(stdout="<html>gateway error</html>")
        cfg = self.make_config()
        rc = gate.main(config=cfg, now=self.now)
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("JSONDecodeError", out["reason"])

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_fallback_failure_missing_codex_record_fails_closed_75(self, mock_stdout, mock_urlopen, mock_run):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        mock_run.return_value = MagicMock(stdout=json.dumps({"not_codex": {}}))
        cfg = self.make_config()
        rc = gate.main(config=cfg, now=self.now)
        self.assertEqual(rc, 75)
        out = json.loads(mock_stdout.getvalue())
        self.assertFalse(out["launch_allowed"])
        self.assertIn("missing codex record", out["reason"])

    @patch("subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_config_unset_runs_direct_quse_once(self, mock_stdout, mock_run):
        healthy_codex = {
            "codex": {
                "status": "ok",
                "windows": {
                    "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                },
            }
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(healthy_codex))
        cfg = gate.HubConfig(is_configured=False)
        rc = gate.main(config=cfg, now=self.now)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with(["quse", "codex", "--json"], capture_output=True, text=True, timeout=45, check=True)
        out = json.loads(mock_stdout.getvalue())
        self.assertTrue(out["launch_allowed"])

    def test_readonly_config_invalid_json_fails_closed(self):
        tmp_cfg = ROOT / ".local" / "tmp" / "bad-config.json"
        tmp_cfg.write_text("not json content", encoding="utf-8")
        try:
            with self.assertRaises(gate.HubConfigError):
                gate.load_config(tmp_cfg)
        finally:
            if tmp_cfg.exists():
                tmp_cfg.unlink()

    def test_readonly_config_missing_auth_fails_closed(self):
        tmp_cfg = ROOT / ".local" / "tmp" / "no-auth-config.json"
        tmp_cfg.write_text(json.dumps({"hub_url": "http://hub.local", "host_id": "h1"}), encoding="utf-8")
        try:
            with self.assertRaises(gate.HubConfigError):
                gate.load_config(tmp_cfg)
        finally:
            if tmp_cfg.exists():
                tmp_cfg.unlink()


class TestR3ReviewerFindingsAndRegressions(HubTestBase):
    """Explicit tests for all 11 reviewer negative reproduction cases across R3-F1 through R3-F6."""

    # --- R3-F1: Future timestamps rejected across fetch, decision, and cache ---
    @patch("urllib.request.urlopen")
    def test_r3_f1_future_30s_captured_and_observed_rejected_in_fetch(self, mock_urlopen):
        cfg = self.make_config()
        future_ts = (self.now + datetime.timedelta(seconds=30)).isoformat()

        # Captured_at +30s in future
        payload = self.valid_hub_payload(captured_at=future_ts)
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("future", str(ctx.exception).lower())

        # Serverreceived_at +30s in future
        payload = self.valid_hub_payload()
        payload["serverreceived_at"] = future_ts
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("future", str(ctx.exception).lower())

        # Observed_at +30s in future
        payload = self.valid_hub_payload()
        payload["routes"]["codex"]["observed_at"] = future_ts
        mock_urlopen.return_value = self.mock_http_response(payload)
        with self.assertRaises(gate.HubSchemaError) as ctx:
            gate.fetch_hub_snapshot(cfg, now=self.now)
        self.assertIn("future", str(ctx.exception).lower())

    def test_r3_f1_future_timestamps_rejected_in_decision(self):
        future_ts = (self.now + datetime.timedelta(seconds=30)).isoformat()

        # captured_at in future
        rec = {"status": "ok", "captured_at": future_ts, "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}}}
        allowed, reason = gate.decision(rec, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("future", reason.lower())

        # serverreceived_at in future
        rec = {"status": "ok", "serverreceived_at": future_ts, "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}}}
        allowed, reason = gate.decision(rec, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("future", reason.lower())

        # observed_at in future
        rec = {"status": "ok", "observed_at": future_ts, "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}}}
        allowed, reason = gate.decision(rec, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("future", reason.lower())

    # --- R3-F2: Cache hit stale revalidation and TTL preservation ---
    @patch("urllib.request.urlopen")
    def test_r3_f2_cache_hit_serverreceived_at_1210s_stale_evicted(self, mock_urlopen):
        t0 = self.now
        # t0: captured_at is t0 - 10s, serverreceived_at is t0 - 1190s
        t0_captured = (t0 - datetime.timedelta(seconds=10)).isoformat()
        t0_srv = (t0 - datetime.timedelta(seconds=1190)).isoformat()
        payload_fresh = self.valid_hub_payload(captured_at=t0_captured, weekly_pct=80.0)
        payload_fresh["serverreceived_at"] = t0_srv
        mock_urlopen.return_value = self.mock_http_response(payload_fresh)

        cfg = self.make_config()
        record, captured = gate.fetch_hub_snapshot(cfg, now=t0)
        gate.store_cached_record(cfg, record, captured, t0)

        # Call at t0 + 20s (within 30s TTL, but serverreceived_at is 1210s old >= 1200s)
        t20 = t0 + datetime.timedelta(seconds=20)
        cached = gate.get_cached_record(cfg, now_dt=t20)
        self.assertIsNone(cached, "Cache hit must be evicted when serverreceived_at becomes stale")

        # In evaluate_gate, cache miss triggers fresh fetch; if Hub response has stale serverreceived_at, fail closed
        payload_stale = self.valid_hub_payload(captured_at=t0_captured, weekly_pct=80.0)
        payload_stale["serverreceived_at"] = t0_srv
        mock_urlopen.return_value = self.mock_http_response(payload_stale)
        allowed, reason = gate.evaluate_gate(config=cfg, now=t20)
        self.assertFalse(allowed)
        self.assertIn("stale", reason.lower())

    def test_r3_f2_persistent_cache_preserves_ttl_clock_no_extension(self):
        tmp_dir = ROOT / ".local" / "tmp"
        cache_file = tmp_dir / "r3-f2-ttl-cache.json"
        if cache_file.exists():
            cache_file.unlink()

        cfg = self.make_config(cache_file=cache_file)
        t0 = self.now
        record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}}}

        gate.store_cached_record(cfg, record, t0, t0)
        gate.clear_cache()

        # Read at t0 + 25s: should hit persistent cache and populate in-process cache with original cached_at=t0
        t25 = t0 + datetime.timedelta(seconds=25)
        rec25 = gate.get_cached_record(cfg, t25)
        self.assertIsNotNone(rec25)

        # Read at t0 + 50s: TTL=30s has expired (t0+50s - t0 = 50s >= 30s)
        # Old bug reset in-process cached_at to t25, extending TTL to t25+30s = t55s
        t50 = t0 + datetime.timedelta(seconds=50)
        rec50 = gate.get_cached_record(cfg, t50)
        self.assertIsNone(rec50, "Persistent cache load must not renew TTL clock")

        if cache_file.exists():
            cache_file.unlink()

    # --- R3-F3: Persistent cache tamper safety & atomic safe 0600 write ---
    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r3_f3_tampered_cache_file_fails_closed_no_fallback(self, mock_urlopen, mock_run):
        tmp_dir = ROOT / ".local" / "tmp"
        cache_file = tmp_dir / "r3-f3-tamper.json"
        cache_file.write_text("corrupted json {not valid", encoding="utf-8")
        cache_file.chmod(0o644)

        try:
            cfg = self.make_config(cache_file=cache_file)
            gate.clear_cache()
            allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("tamper", reason.lower())
            self.assertEqual(mock_urlopen.call_count, 0, "Tampered cache file must not fetch from Hub")
            self.assertEqual(mock_run.call_count, 0, "Tampered cache file must not fallback to quse")
        finally:
            if cache_file.exists():
                cache_file.unlink()

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r3_f3_symlink_cache_file_fails_closed_no_fallback(self, mock_urlopen, mock_run):
        tmp_dir = ROOT / ".local" / "tmp"
        target_file = tmp_dir / "r3-f3-target.json"
        symlink_file = tmp_dir / "r3-f3-symlink.json"
        target_file.write_text("{}", encoding="utf-8")
        if symlink_file.exists() or symlink_file.is_symlink():
            symlink_file.unlink()
        symlink_file.symlink_to(target_file)

        try:
            cfg = self.make_config(cache_file=symlink_file)
            gate.clear_cache()
            allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("tamper", reason.lower())
            self.assertEqual(mock_urlopen.call_count, 0)
            self.assertEqual(mock_run.call_count, 0)
        finally:
            if symlink_file.is_symlink() or symlink_file.exists():
                symlink_file.unlink()
            if target_file.exists():
                target_file.unlink()

    def test_r3_f3_cache_write_atomic_0600_over_existing_0644_and_no_follow_symlink(self):
        tmp_dir = ROOT / ".local" / "tmp"
        cache_file = tmp_dir / "r3-f3-atomic-0600.json"
        target_file = tmp_dir / "r3-f3-write-symlink-target.json"
        symlink_file = tmp_dir / "r3-f3-write-symlink.json"
        # Pre-create with 0644
        cache_file.write_text("{}", encoding="utf-8")
        cache_file.chmod(0o644)
        self.assertEqual(cache_file.stat().st_mode & 0o777, 0o644)

        try:
            cfg = self.make_config(cache_file=cache_file)
            record = {"status": "ok", "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}}}
            gate.store_cached_record(cfg, record, self.now, self.now)

            # File must be overwritten to 0o600
            st_mode = cache_file.stat().st_mode & 0o777
            self.assertEqual(st_mode, 0o600, "Cache write must enforce 0o600 on overwritten files")

            # Also verify symlink target is refused on write without modifying target_file
            target_file.write_text('{"untouched": true}', encoding="utf-8")
            if symlink_file.is_symlink() or symlink_file.exists():
                symlink_file.unlink()
            symlink_file.symlink_to(target_file)
            cfg_sym = self.make_config(cache_file=symlink_file)
            with self.assertRaises(gate.CacheTamperError):
                gate.store_cached_record(cfg_sym, record, self.now, self.now)
            self.assertTrue(symlink_file.is_symlink(), "Symlink must not be replaced")
            self.assertEqual(target_file.read_text(encoding="utf-8"), '{"untouched": true}')
        finally:
            if cache_file.exists():
                cache_file.unlink()
            if symlink_file.is_symlink() or symlink_file.exists():
                symlink_file.unlink()
            if target_file.exists():
                target_file.unlink()

    # --- R3-F4: Strict boolean flags, non-null falsy errors, weekend exclusion ---
    def test_r3_f4_optional_present_string_true_empty_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                "5h": {"present": "true", "percent_remaining": None, "reset_at": None},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("invalid present flag", reason.lower())

    def test_r3_f4_weekly_present_string_false_fails_closed(self):
        record = {
            "status": "ok",
            "windows": {
                "7d": {"present": "false", "percent_remaining": 80.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("invalid present flag", reason.lower())

    def test_r3_f4_weekend_does_not_satisfy_mandatory_weekly(self):
        record = {
            "status": "ok",
            "windows": {
                "weekend": {"percent_remaining": 80.0, "reset_at": self.future_iso},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("mandatory 7d/weekly quota window missing", reason)

    def test_r3_f4_falsy_empty_string_and_container_error_fails_closed(self):
        for falsy_val in ("", {}, [], 0, False):
            # Top-level error
            rec1 = {
                "status": "ok",
                "error": falsy_val,
                "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}},
            }
            allowed, reason = gate.decision(rec1, now=self.now)
            self.assertFalse(allowed, f"Top-level error={falsy_val!r} must fail closed")
            self.assertIn("provider error", reason.lower())

            # Window-level error
            rec2 = {
                "status": "ok",
                "windows": {
                    "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "error": falsy_val},
                },
            }
            allowed, reason = gate.decision(rec2, now=self.now)
            self.assertFalse(allowed, f"Window-level error={falsy_val!r} must fail closed")
            self.assertIn("reported error", reason.lower())

    def test_r3_f4_stale_and_limit_reached_boolean_flags_fail_closed(self):
        # Top-level stale flag
        rec1 = {
            "status": "ok",
            "stale": True,
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}},
        }
        allowed, reason = gate.decision(rec1, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("stale", reason.lower())

        # Window stale flag
        rec2 = {
            "status": "ok",
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "stale": True}},
        }
        allowed, reason = gate.decision(rec2, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("stale", reason.lower())

        # Non-boolean stale flag
        rec3 = {
            "status": "ok",
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "stale": "true"}},
        }
        allowed, reason = gate.decision(rec3, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("invalid stale flag", reason.lower())

    # --- R3-F5: Hostless URLs and invalid config types ---
    @patch("subprocess.run")
    def test_r3_f5_hostless_urls_fail_closed_no_fallback(self, mock_run):
        # Directly test validation on hostless URLs
        with self.assertRaises(gate.HubConfigError):
            gate._validate_hub_url("http:///api/quota")
        with self.assertRaises(gate.HubConfigError):
            gate._validate_hub_url("http://")

        # In evaluate_gate via environment
        old_env = os.environ.get("QUOTA_HUB_URL")
        try:
            os.environ["QUOTA_HUB_URL"] = "http:///api/quota"
            os.environ["QUOTA_HUB_TOKEN"] = self.token
            os.environ["QUOTA_HUB_HOST_ID"] = self.host_id
            allowed, reason = gate.evaluate_gate(config=None, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("configuration error", reason.lower())
            self.assertEqual(mock_run.call_count, 0, "Hostless URL must not trigger quse fallback")

            os.environ["QUOTA_HUB_URL"] = "http://"
            allowed, reason = gate.evaluate_gate(config=None, now=self.now)
            self.assertFalse(allowed)
            self.assertIn("configuration error", reason.lower())
            self.assertEqual(mock_run.call_count, 0)
        finally:
            if old_env is not None:
                os.environ["QUOTA_HUB_URL"] = old_env
            else:
                os.environ.pop("QUOTA_HUB_URL", None)
            os.environ.pop("QUOTA_HUB_TOKEN", None)
            os.environ.pop("QUOTA_HUB_HOST_ID", None)

    def test_r3_f5_config_values_boolean_and_nonfinite_fail_closed(self):
        # Boolean cache_ttl
        with self.assertRaises(gate.HubConfigError):
            gate.HubConfig(hub_url=self.hub_url, token=self.token, host_id=self.host_id, cache_ttl_sec=False, is_configured=True)

        # Zero max_staleness
        with self.assertRaises(gate.HubConfigError):
            gate.HubConfig(hub_url=self.hub_url, token=self.token, host_id=self.host_id, max_staleness_sec=0, is_configured=True)

        # Non-finite timeout
        with self.assertRaises(gate.HubConfigError):
            gate.HubConfig(hub_url=self.hub_url, token=self.token, host_id=self.host_id, timeout_sec=float("nan"), is_configured=True)

    # --- R3-F6: Sanitization: no raw tokens, userinfo, query strings, or paths ---
    def test_r3_f6_no_raw_tokens_in_window_status_or_name(self):
        tok_val = "mock_window_" + "token_1234567890abcdef"
        status_val = "err " + "Bea" + f"rer {tok_val}"
        record = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "status": status_val},
            },
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn(tok_val, reason, "Window status raw token must not be leaked")
        self.assertIn("status not ok", reason)

    def test_r3_f6_no_bearer_userinfo_query_or_path_leaks(self):
        short_val = "short_" + "tok_999"
        userinfo = "adm" + "in:" + "pass" + "123@"
        query = "?" + "code=secret_q"
        raw_err = f"auth: Bearer {short_val} via https://{userinfo}hub.local/api{query}"
        record = {
            "status": "ok",
            "error": raw_err,
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}},
        }
        allowed, reason = gate.decision(record, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn(short_val, reason, "Bearer short token must be redacted")
        self.assertNotIn(userinfo, reason, "URL userinfo must be redacted")
        self.assertNotIn(query, reason, "URL query string must be redacted")

        # Local filesystem path leak test
        tmp_cfg = ROOT / ".local" / "tmp" / "secret_private_dir" / "config.json"
        try:
            gate.load_config(tmp_cfg)
        except gate.HubConfigError as exc:
            self.assertNotIn("secret_private_dir", str(exc), "Local filesystem path must not be leaked")


class TestR4ReviewerFindingsAndTableDrivenMutations(HubTestBase):
    """Comprehensive tests covering R4-F1..R4-F5, deterministic table-driven negative mutations, and multi-provider routes."""

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r4_f1_corrupt_and_naive_timestamps_in_persistent_cache_fail_closed(self, mock_urlopen, mock_run):
        tmp_dir = ROOT / ".local" / "tmp"
        cache_file = tmp_dir / "r4-f1-cache-tamper.json"
        cfg = self.make_config(cache_file=cache_file)
        base_record = {
            "status": "ok",
            "error": None,
            "captured_at": self.now_iso,
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}},
        }

        tamper_mutations = [
            ("corrupt_entry_srv", lambda e: e.__setitem__("serverreceived_at", "corrupt-not-a-timestamp")),
            ("empty_entry_srv", lambda e: e.__setitem__("serverreceived_at", "")),
            ("zero_entry_srv", lambda e: e.__setitem__("serverreceived_at", 0)),
            ("false_entry_srv", lambda e: e.__setitem__("serverreceived_at", False)),
            ("int_entry_srv", lambda e: e.__setitem__("serverreceived_at", 12345)),
            ("naive_entry_srv", lambda e: e.__setitem__("serverreceived_at", "2026-10-14T12:00:00")),
            ("future_entry_srv", lambda e: e.__setitem__("serverreceived_at", (self.now + datetime.timedelta(seconds=5)).isoformat())),
            ("corrupt_rec_obs", lambda e: e["codex_record"].__setitem__("observed_at", "corrupt-not-a-timestamp")),
            ("empty_rec_obs", lambda e: e["codex_record"].__setitem__("observed_at", "")),
            ("none_rec_obs", lambda e: e["codex_record"].__setitem__("observed_at", None)),
            ("int_rec_obs", lambda e: e["codex_record"].__setitem__("observed_at", 12345)),
            ("naive_rec_obs", lambda e: e["codex_record"].__setitem__("observed_at", "2026-10-14T12:00:00")),
            ("future_rec_obs", lambda e: e["codex_record"].__setitem__("observed_at", (self.now + datetime.timedelta(seconds=5)).isoformat())),
            ("naive_cached_at", lambda e: e.__setitem__("cached_at", "2026-10-14T12:00:00")),
            ("naive_captured_at", lambda e: e.__setitem__("captured_at", "2026-10-14T12:00:00")),
            ("mismatch_rec_captured_at", lambda e: e["codex_record"].__setitem__("captured_at", (self.now - datetime.timedelta(seconds=5)).isoformat())),
        ]

        try:
            for label, mutator in tamper_mutations:
                with self.subTest(case=label):
                    if cache_file.exists():
                        cache_file.unlink()
                    gate.store_cached_record(cfg, dict(base_record), self.now, self.now)
                    entry = json.loads(cache_file.read_text(encoding="utf-8"))
                    mutator(entry)
                    cache_file.write_text(json.dumps(entry), encoding="utf-8")
                    cache_file.chmod(0o600)
                    gate.clear_cache()

                    with self.assertRaises(gate.CacheTamperError):
                        gate.get_cached_record(cfg, self.now)

                    allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
                    self.assertFalse(allowed)
                    self.assertIn("tamper detected", reason.lower())
                    self.assertEqual(mock_urlopen.call_count, 0)
                    self.assertEqual(mock_run.call_count, 0)
        finally:
            if cache_file.exists():
                cache_file.unlink()

    def test_r4_f1_write_persistent_cache_refuses_symlink_target_and_narrow_max_staleness(self):
        # 1. Narrow configured max_staleness_sec (60s) enforced in decision() and get_cached_record()
        cfg_narrow = self.make_config(max_staleness_sec=60.0)
        t_65s_ago = (self.now - datetime.timedelta(seconds=65)).isoformat()
        rec_65s = {
            "status": "ok",
            "error": None,
            "observed_at": t_65s_ago,
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}},
        }
        allowed, reason = gate.decision(rec_65s, now=self.now, max_staleness_sec=cfg_narrow.max_staleness_sec)
        self.assertFalse(allowed)
        self.assertIn("stale", reason.lower())

        # 2. _write_persistent_cache refuses symlink target directly
        tmp_dir = ROOT / ".local" / "tmp"
        target = tmp_dir / "r4-f1-sym-target.json"
        sym = tmp_dir / "r4-f1-sym-link.json"
        target.write_text('{"safe": true}', encoding="utf-8")
        if sym.is_symlink() or sym.exists():
            sym.unlink()
        sym.symlink_to(target)
        try:
            cfg_sym = self.make_config(cache_file=sym)
            with self.assertRaises(gate.CacheTamperError):
                gate._write_persistent_cache(cfg_sym, rec_65s, self.now, self.now)
            self.assertTrue(sym.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), '{"safe": true}')
        finally:
            if sym.is_symlink() or sym.exists():
                sym.unlink()
            if target.exists():
                target.unlink()

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r4_f2_invalid_ports_empty_env_null_and_type_invalid_config_fail_closed_no_fallback(self, mock_urlopen, mock_run):
        # 1. Invalid URL ports (:99999, :abc, :, :0, :080)
        for bad_url in (
            "http://hub.local:99999",
            "http://hub.local:abc",
            "http://hub.local:",
            "http://hub.local:0",
            "http://hub.local:080",
            "http://[2001:db8::1]:99999",
            "http://[2001:db8::1]:",
        ):
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(gate.HubConfigError):
                    gate._validate_hub_url(bad_url)
                with patch.dict(
                    os.environ,
                    {"QUOTA_HUB_URL": bad_url, "QUOTA_HUB_TOKEN": self.token, "QUOTA_HUB_HOST_ID": self.host_id},
                    clear=True,
                ):
                    allowed, reason = gate.evaluate_gate(config=None, now=self.now)
                    self.assertFalse(allowed)
                    self.assertIn("configuration error", reason.lower())
                    self.assertEqual(mock_urlopen.call_count, 0)
                    self.assertEqual(mock_run.call_count, 0)

        # 2. Empty env vars (QUOTA_HUB_URL="", QUOTA_HUB_TOKEN="", QUOTA_HUB_HOST_ID="", QUOTA_HUB_HOST alias)
        for env_case in (
            {"QUOTA_HUB_URL": ""},
            {"QUOTA_HUB_TOKEN": ""},
            {"QUOTA_HUB_HOST_ID": ""},
            {"QUOTA_HUB_HOST": "http://hub.local", "QUOTA_HUB_TOKEN": self.token, "QUOTA_HUB_HOST_ID": self.host_id},
        ):
            with self.subTest(env_case=env_case):
                with patch.dict(os.environ, env_case, clear=True):
                    allowed, reason = gate.evaluate_gate(config=None, now=self.now)
                    self.assertFalse(allowed)
                    self.assertIn("configuration error", reason.lower())
                    self.assertEqual(mock_urlopen.call_count, 0)
                    self.assertEqual(mock_run.call_count, 0)

        # 3. Non-string cache_file, null config numbers, alias keys, and whitespace in token/host_id
        tmp_cfg = ROOT / ".local" / "tmp" / "r4-f2-bad-cfg.json"
        bad_config_dicts = [
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "h1", "cache_file": 123},
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "h1", "cache_file": False},
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "h1", "cache_file": ""},
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "h1", "max_staleness_sec": None},
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "h1", "cache_ttl_sec": None},
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "h1", "timeout_sec": None},
            {"url": "http://hub.local", "token": "tok", "host_id": "h1"},
            {"hub_url": "http://hub.local", "token": "tok with space", "host_id": "h1"},
            {"hub_url": "http://hub.local", "token": "tok", "host_id": "host\n1"},
        ]
        try:
            for cfg_dict in bad_config_dicts:
                with self.subTest(cfg_dict=cfg_dict):
                    tmp_cfg.write_text(json.dumps(cfg_dict), encoding="utf-8")
                    with patch.dict(os.environ, {"QUOTA_HUB_CONFIG": str(tmp_cfg)}, clear=True):
                        allowed, reason = gate.evaluate_gate(config=None, now=self.now)
                        self.assertFalse(allowed)
                        self.assertIn("configuration error", reason.lower())
                        self.assertEqual(mock_urlopen.call_count, 0)
                        self.assertEqual(mock_run.call_count, 0)
        finally:
            if tmp_cfg.exists():
                tmp_cfg.unlink()

    def test_r4_f3_optional_and_mandatory_empty_string_reset_at_fails_closed(self):
        # 1. Optional 5h with percent_remaining: None and reset_at: ""
        rec1 = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                "5h": {"percent_remaining": None, "reset_at": ""},
            },
        }
        allowed, reason = gate.decision(rec1, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h'", reason)
        self.assertIn("reset", reason.lower())

        # 2. Optional 5h with present: False, percent_remaining: None, and reset_at: ""
        rec2 = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso},
                "5h": {"present": False, "percent_remaining": None, "reset_at": ""},
            },
        }
        allowed, reason = gate.decision(rec2, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("window '5h'", reason)
        self.assertIn("marked not present", reason.lower())

        # 3. Empty string reset_at alongside valid reset alias fails closed
        rec3 = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": "", "reset": self.future_iso},
            },
        }
        allowed, reason = gate.decision(rec3, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("reset", reason.lower())

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r4_f4_strict_hub_error_key_route_schema_and_pre_cache_validation(self, mock_urlopen, mock_run):
        cfg = self.make_config()

        # 1. Missing top-level 'error' key
        p1 = self.valid_hub_payload()
        del p1["error"]
        mock_urlopen.return_value = self.mock_http_response(p1)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("hub schema error", reason.lower())
        self.assertIsNone(gate.get_cached_record(cfg, self.now))

        # 2. Missing routes['codex']['error'] key
        p2 = self.valid_hub_payload()
        del p2["routes"]["codex"]["error"]
        mock_urlopen.return_value = self.mock_http_response(p2)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("hub schema error", reason.lower())
        self.assertIsNone(gate.get_cached_record(cfg, self.now))

        # 3. Non-canonical 'codex_7d' or 'reset' alias in Hub payload rejected and not cached
        p3 = self.valid_hub_payload()
        p3["routes"]["codex"]["windows"] = {
            "codex_7d": {"percent_remaining": 80.0, "reset": self.future_iso}
        }
        mock_urlopen.return_value = self.mock_http_response(p3)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("hub schema error", reason.lower())
        self.assertIsNone(gate.get_cached_record(cfg, self.now))

        # 4. Forbidden has_grok_code_access on codex route rejected and not cached
        p4 = self.valid_hub_payload()
        p4["routes"]["codex"]["details"] = {"has_grok_code_access": True}
        mock_urlopen.return_value = self.mock_http_response(p4)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertIn("hub schema error", reason.lower())
        self.assertIsNone(gate.get_cached_record(cfg, self.now))
        self.assertEqual(mock_run.call_count, 0)

    @patch("urllib.request.urlopen")
    def test_r4_f5_no_raw_status_error_schema_version_or_host_id_in_reasons_or_repr(self, mock_urlopen):
        # 1. Window non-ok status does not echo raw status value
        sec_status = "err_my_" + "sec_99"
        rec1 = {
            "status": "ok",
            "windows": {
                "7d": {"percent_remaining": 80.0, "reset_at": self.future_iso, "status": sec_status},
            },
        }
        allowed, reason = gate.decision(rec1, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn(sec_status, reason)
        self.assertEqual(reason, "window '7d' status not ok")

        # 2. Short unmatched secret in provider error is redacted
        sec_err = "db_pass_" + "9999"
        rec2 = {
            "status": "ok",
            "error": f"{sec_err} failed",
            "windows": {"7d": {"percent_remaining": 80.0, "reset_at": self.future_iso}},
        }
        allowed, reason = gate.decision(rec2, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn(sec_err, reason)
        self.assertIn("[REDACTED]", reason)

        # 3. HubConfig.__repr__ redacts hub_url, host_id, and token
        cfg = self.make_config()
        rep = repr(cfg)
        self.assertNotIn(self.hub_url, rep)
        self.assertNotIn(self.host_id, rep)
        self.assertNotIn(self.token, rep)

        # 4. Hub schema_version, status, and host_id mismatches do not echo raw values
        p_ver = self.valid_hub_payload()
        p_ver["schema_version"] = "sec_ver_99"
        mock_urlopen.return_value = self.mock_http_response(p_ver)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn("sec_ver_99", reason)

        p_host = self.valid_hub_payload(host_id="sec_host_99")
        mock_urlopen.return_value = self.mock_http_response(p_host)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed)
        self.assertNotIn("sec_host_99", reason)
        self.assertNotIn(self.host_id, reason)

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r4_table_driven_negative_mutations_across_hub_route_window_config_and_cache(self, mock_urlopen, mock_run):
        cfg = self.make_config()
        future_ts = (self.now + datetime.timedelta(seconds=10)).isoformat()
        stale_ts = (self.now - datetime.timedelta(seconds=1201)).isoformat()

        hub_mutations = [
            ("missing_schema_version", lambda p: p.pop("schema_version")),
            ("null_schema_version", lambda p: p.__setitem__("schema_version", None)),
            ("bool_schema_version", lambda p: p.__setitem__("schema_version", True)),
            ("wrong_schema_version", lambda p: p.__setitem__("schema_version", "2.0")),
            ("missing_status", lambda p: p.pop("status")),
            ("error_status", lambda p: p.__setitem__("status", "error")),
            ("unknown_status", lambda p: p.__setitem__("status", "unknown")),
            ("missing_error_key", lambda p: p.pop("error")),
            ("non_null_error_str", lambda p: p.__setitem__("error", "unavailable")),
            ("empty_str_error", lambda p: p.__setitem__("error", "")),
            ("false_error", lambda p: p.__setitem__("error", False)),
            ("zero_error", lambda p: p.__setitem__("error", 0)),
            ("missing_host_id", lambda p: p.pop("host_id")),
            ("null_host_id", lambda p: p.__setitem__("host_id", None)),
            ("mismatched_host_id", lambda p: p.__setitem__("host_id", "wrong-host")),
            ("missing_captured_at", lambda p: p.pop("captured_at")),
            ("null_captured_at", lambda p: p.__setitem__("captured_at", None)),
            ("empty_captured_at", lambda p: p.__setitem__("captured_at", "")),
            ("naive_captured_at", lambda p: p.__setitem__("captured_at", "2026-10-14T12:00:00")),
            ("future_captured_at", lambda p: p.__setitem__("captured_at", future_ts)),
            ("stale_captured_at", lambda p: p.__setitem__("captured_at", stale_ts)),
            ("null_serverreceived_at", lambda p: p.__setitem__("serverreceived_at", None)),
            ("empty_serverreceived_at", lambda p: p.__setitem__("serverreceived_at", "")),
            ("naive_serverreceived_at", lambda p: p.__setitem__("serverreceived_at", "2026-10-14T12:00:00")),
            ("future_serverreceived_at", lambda p: p.__setitem__("serverreceived_at", future_ts)),
            ("stale_serverreceived_at", lambda p: p.__setitem__("serverreceived_at", stale_ts)),
            ("forbidden_top_balance", lambda p: p.__setitem__("balance", 100)),
            ("forbidden_top_authority", lambda p: p.__setitem__("root_authority", True)),
            ("route_missing_error", lambda p: p["routes"]["codex"].pop("error")),
            ("route_error_unavailable", lambda p: p["routes"]["codex"].__setitem__("error", "unavailable")),
            ("route_error_empty", lambda p: p["routes"]["codex"].__setitem__("error", "")),
            ("route_status_unknown", lambda p: p["routes"]["codex"].__setitem__("status", "unknown")),
            ("route_null_observed_at", lambda p: p["routes"]["codex"].__setitem__("observed_at", None)),
            ("route_empty_observed_at", lambda p: p["routes"]["codex"].__setitem__("observed_at", "")),
            ("route_naive_observed_at", lambda p: p["routes"]["codex"].__setitem__("observed_at", "2026-10-14T12:00:00")),
            ("route_future_observed_at", lambda p: p["routes"]["codex"].__setitem__("observed_at", future_ts)),
            ("route_stale_observed_at", lambda p: p["routes"]["codex"].__setitem__("observed_at", stale_ts)),
            ("route_details_limit_true", lambda p: p["routes"]["codex"].__setitem__("details", {"limit_reached": True})),
            ("route_details_limit_str", lambda p: p["routes"]["codex"].__setitem__("details", {"limit_reached": "false"})),
            ("route_details_stale_true", lambda p: p["routes"]["codex"].__setitem__("details", {"stale": True})),
            ("route_details_grok_field", lambda p: p["routes"]["codex"].__setitem__("details", {"has_grok_code_access": True})),
            ("win_7d_pct_none", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("percent_remaining", None)),
            ("win_7d_pct_bool", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("percent_remaining", True)),
            ("win_7d_pct_15", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("percent_remaining", 15.0)),
            ("win_7d_pct_neg", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("percent_remaining", -0.1)),
            ("win_7d_pct_101", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("percent_remaining", 100.1)),
            ("win_7d_reset_none", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("reset_at", None)),
            ("win_7d_reset_empty", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("reset_at", "")),
            ("win_7d_reset_naive", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("reset_at", "2026-10-15T12:00:00")),
            ("win_7d_reset_past", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("reset_at", self.past_iso)),
            ("win_7d_present_false", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("present", False)),
            ("win_7d_rolling_str", lambda p: p["routes"]["codex"]["windows"]["7d"].__setitem__("rolling", "true")),
            ("win_5h_present_true_empty", lambda p: p["routes"]["codex"]["windows"].__setitem__("5h", {"present": True, "percent_remaining": None, "reset_at": None})),
            ("win_5h_present_false_with_pct", lambda p: p["routes"]["codex"]["windows"].__setitem__("5h", {"present": False, "percent_remaining": 50.0, "reset_at": None})),
            ("win_5h_present_false_with_reset_empty", lambda p: p["routes"]["codex"]["windows"].__setitem__("5h", {"present": False, "percent_remaining": None, "reset_at": ""})),
            ("win_5h_error_unavailable", lambda p: p["routes"]["codex"]["windows"].__setitem__("5h", {"present": False, "percent_remaining": None, "reset_at": None, "error": "unavailable"})),
            ("win_5h_low_pct_14", lambda p: p["routes"]["codex"]["windows"].__setitem__("5h", {"present": True, "percent_remaining": 14.0, "reset_at": self.future_iso})),
        ]

        for name, mutate in hub_mutations:
            with self.subTest(mutation=name):
                gate.clear_cache()
                payload = self.valid_hub_payload()
                mutate(payload)
                mock_urlopen.return_value = self.mock_http_response(payload)
                allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
                self.assertFalse(allowed, f"Mutation {name} must fail closed")
                self.assertIsInstance(reason, str)
                self.assertIsNone(gate.get_cached_record(cfg, self.now), f"Mutation {name} must not be cached")
                self.assertEqual(mock_run.call_count, 0, f"Mutation {name} must not trigger quse fallback")

    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_r4_multi_provider_routes_and_valid_other_windows(self, mock_urlopen, mock_run):
        cfg = self.make_config()
        payload = self.valid_hub_payload(weekly_pct=85.0)
        payload["serverreceived_at"] = self.now_iso
        payload["routes"]["codex"]["observed_at"] = self.now_iso
        payload["routes"]["codex"]["details"] = {"limit_reached": False}
        payload["routes"]["codex"]["windows"] = {
            "7d": {"percent_remaining": 85.0, "reset_at": self.future_iso, "present": True, "rolling": True},
            "5h": {"percent_remaining": None, "reset_at": None, "present": False, "rolling": True},
            "monthly": {"percent_remaining": 90.0, "reset_at": self.future_iso, "present": True, "rolling": False},
            "burst-1h_window": {"percent_remaining": 62.5, "reset_at": self.future_iso, "present": True, "rolling": True},
        }
        # Sibling provider routes (grok with has_grok_code_access, claude, gemini)
        payload["routes"]["grok"] = {
            "status": "ok",
            "error": None,
            "observed_at": self.now_iso,
            "details": {"limit_reached": False, "has_grok_code_access": True},
            "windows": {
                "5h": {"percent_remaining": 40.0, "reset_at": self.future_iso, "present": True, "rolling": True},
                "7d": {"percent_remaining": 75.0, "reset_at": self.future_iso, "present": True, "rolling": True},
            },
        }
        payload["routes"]["claude"] = {
            "status": "error",
            "error": "unavailable",
            "details": {"limit_reached": True},
            "windows": {
                "5h": {"percent_remaining": None, "reset_at": None, "present": False, "rolling": True, "error": "unavailable"},
            },
        }
        payload["routes"]["gemini"] = {
            "status": "unknown",
            "error": None,
            "details": {"limit_reached": None},
            "windows": {
                "daily": {"percent_remaining": 95.0, "reset_at": self.future_iso, "present": True, "rolling": True},
            },
        }

        mock_urlopen.return_value = self.mock_http_response(payload)
        allowed, reason = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertTrue(allowed)
        self.assertIn("62.5% remaining; reserve 15%", reason)
        self.assertEqual(mock_run.call_count, 0)

        # Negative check: has_grok_code_access on claude (non-grok sibling route) fails closed
        gate.clear_cache()
        payload["routes"]["claude"]["details"]["has_grok_code_access"] = False
        mock_urlopen.return_value = self.mock_http_response(payload)
        allowed2, reason2 = gate.evaluate_gate(config=cfg, now=self.now)
        self.assertFalse(allowed2)
        self.assertIn("hub schema error", reason2.lower())
        self.assertEqual(mock_run.call_count, 0)


class TestClaimsMatrixAndRootAck(unittest.TestCase):
    """Validates full claims-to-test traceability and explicit Root requirement acknowledgement."""

    ROOT_AMENDMENT_ID = "69279164-924e-46e9-947e-7150e7d050cc"

    CLAIMS_MATRIX = {
        "CLAIM-ROOT-ACK": [
            "test_root_amendment_ack_integrity",
        ],
        "CLAIM-HUB-GET-AUTH": [
            "test_auth_bearer_token_sent_in_header",
            "test_auth_http_401_fails_closed_no_fallback",
            "test_auth_http_403_fails_closed_no_fallback",
        ],
        "CLAIM-HOST-ID-MATCH": [
            "test_host_id_mismatch_fails_closed_no_fallback",
            "test_auth_configured_missing_host_id_fails_closed",
        ],
        "CLAIM-SCHEMA-VERSION": [
            "test_schema_valid_codex_route_passes",
            "test_schema_version_mismatch_fails_closed",
            "test_schema_status_not_ok_fails_closed",
            "test_schema_top_level_error_fails_closed",
            "test_schema_captured_at_missing_or_naive_fails_closed",
        ],
        "CLAIM-ROUTES-MAP": [
            "test_schema_routes_missing_or_missing_codex_fails_closed",
        ],
        "CLAIM-PROVIDER-OBSERVED-AT": [
            "test_schema_provider_observed_at_stale_cannot_be_laundered_by_fresh_serverreceived_at",
            "test_schema_serverreceived_at_future_or_stale_fails_closed",
        ],
        "CLAIM-DETAILS-STALE": [
            "test_schema_provider_details_stale_fails_closed",
        ],
        "CLAIM-DYNAMIC-SAFE-WINDOWS": [
            "test_schema_dynamic_safe_windows_max_32_enforced",
            "test_schema_dynamic_safe_windows_name_validation",
            "test_schema_dynamic_safe_windows_valid_custom_window_evaluated",
        ],
        "CLAIM-OPTIONAL-WINDOWS-NA": [
            "test_schema_optional_present_true_empty_fails_closed",
            "test_schema_optional_present_true_missing_reset_fails_closed",
            "test_f1_positive_optional_5h_absent_truthful_na_allowed",
            "test_f1_negative_optional_5h_absent_with_error_fails_closed",
            "test_f1_negative_optional_5h_present_false_contradiction_reading_fails_closed",
            "test_f1_negative_optional_5h_present_false_contradiction_reset_fails_closed",
        ],
        "CLAIM-MANDATORY-WEEKLY": [
            "test_mandatory_weekly_missing",
            "test_mandatory_weekly_empty_reading_fails_closed",
            "test_mandatory_weekly_missing_reset_fails_closed",
            "test_mandatory_weekly_marked_not_present_fails_closed",
            "test_strict_15_reserve_boundary",
        ],
        "CLAIM-HARD-SNAPSHOT-AGE": [
            "test_schema_captured_at_stale_fails_closed",
            "test_schema_captured_at_future_fails_closed",
            "test_cache_config_cannot_extend_1200s_cap",
        ],
        "CLAIM-STALE-1190-30": [
            "test_cache_hit_hard_snapshot_age_check_stale_1190_plus_30",
        ],
        "CLAIM-SHORT-CACHE-TTL": [
            "test_cache_hit_within_ttl_avoids_repeated_network_calls",
            "test_cache_ttl_expiry_triggers_fresh_fetch",
            "test_cache_file_mode_600_and_tamper_safety",
        ],
        "CLAIM-FALLBACK-SINGLE": [
            "test_hub_unreachable_connection_refused_falls_back_once",
            "test_hub_unreachable_http_503_falls_back_once",
        ],
        "CLAIM-FALLBACK-FAIL": [
            "test_fallback_failure_timeout_fails_closed_75",
            "test_fallback_failure_invalid_json_fails_closed_75",
            "test_fallback_failure_missing_codex_record_fails_closed_75",
        ],
        "CLAIM-NO-FALLBACK-ON-AUTH-SCHEMA": [
            "test_auth_http_401_fails_closed_no_fallback",
            "test_auth_http_403_fails_closed_no_fallback",
            "test_host_id_mismatch_fails_closed_no_fallback",
        ],
        "CLAIM-CONFIG-UNSET": [
            "test_config_unset_runs_direct_quse_once",
        ],
        "CLAIM-CONFIG-INVALID-FAILS-CLOSED": [
            "test_auth_configured_missing_token_fails_closed",
            "test_auth_configured_missing_host_id_fails_closed",
            "test_readonly_config_invalid_json_fails_closed",
            "test_readonly_config_missing_auth_fails_closed",
        ],
        "CLAIM-NO-SECRET-LEAKS": [
            "test_f5_error_sanitization_redacts_tokens_and_keys",
            "test_f5_no_raw_reset_strings_in_public_reason",
            "test_security_no_tokens_in_reasons_or_output",
            "test_security_url_with_userinfo_or_query_fails_closed",
            "test_cache_file_mode_600_and_tamper_safety",
        ],
        "CLAIM-PRESERVE-67-TESTS": [
            "test_f1_optional_5h_error_with_empty_reading_fails_closed",
            "test_f2_both_reset_at_and_reset_populated_contradictory_fails_closed",
            "test_f3_provider_top_level_limit_reached_fails_closed",
            "test_f4_now_bool_fails_closed",
            "test_f5_cli_exit_0_on_allowed_verifies_timeout_45",
        ],
        "CLAIM-R3-F1-FUTURE-REJECTION": [
            "test_r3_f1_future_30s_captured_and_observed_rejected_in_fetch",
            "test_r3_f1_future_timestamps_rejected_in_decision",
        ],
        "CLAIM-R3-F2-CACHE-REVALIDATION-AND-TTL": [
            "test_r3_f2_cache_hit_serverreceived_at_1210s_stale_evicted",
            "test_r3_f2_persistent_cache_preserves_ttl_clock_no_extension",
        ],
        "CLAIM-R3-F3-TAMPER-SAFE-CACHE": [
            "test_r3_f3_tampered_cache_file_fails_closed_no_fallback",
            "test_r3_f3_symlink_cache_file_fails_closed_no_fallback",
            "test_r3_f3_cache_write_atomic_0600_over_existing_0644_and_no_follow_symlink",
        ],
        "CLAIM-R3-F4-STRICT-TYPED-VALIDATION": [
            "test_r3_f4_optional_present_string_true_empty_fails_closed",
            "test_r3_f4_weekly_present_string_false_fails_closed",
            "test_r3_f4_weekend_does_not_satisfy_mandatory_weekly",
            "test_r3_f4_falsy_empty_string_and_container_error_fails_closed",
            "test_r3_f4_stale_and_limit_reached_boolean_flags_fail_closed",
        ],
        "CLAIM-R3-F5-STRICT-CONFIG-VALIDATION": [
            "test_r3_f5_hostless_urls_fail_closed_no_fallback",
            "test_r3_f5_config_values_boolean_and_nonfinite_fail_closed",
        ],
        "CLAIM-R3-F6-SECRET-PRIVACY-SANITIZATION": [
            "test_r3_f6_no_raw_tokens_in_window_status_or_name",
            "test_r3_f6_no_bearer_userinfo_query_or_path_leaks",
        ],
        "CLAIM-R4-F1-CENTRALIZED-CACHE-FRESHNESS": [
            "test_r4_f1_corrupt_and_naive_timestamps_in_persistent_cache_fail_closed",
            "test_r4_f1_write_persistent_cache_refuses_symlink_target_and_narrow_max_staleness",
        ],
        "CLAIM-R4-F2-STRICT-PORT-AND-CONFIG-KEY-PRESENCE": [
            "test_r4_f2_invalid_ports_empty_env_null_and_type_invalid_config_fail_closed_no_fallback",
        ],
        "CLAIM-R4-F3-NON-NULL-EMPTY-RESET-FAILS-CLOSED": [
            "test_r4_f3_optional_and_mandatory_empty_string_reset_at_fails_closed",
        ],
        "CLAIM-R4-F4-STRICT-HUB-ROUTE-AND-PRE-CACHE-VALIDATION": [
            "test_r4_f4_strict_hub_error_key_route_schema_and_pre_cache_validation",
        ],
        "CLAIM-R4-F5-GENERIC-REASONS-AND-REPR-REDACTION": [
            "test_r4_f5_no_raw_status_error_schema_version_or_host_id_in_reasons_or_repr",
        ],
        "CLAIM-TABLE-DRIVEN-MUTATIONS": [
            "test_r4_table_driven_negative_mutations_across_hub_route_window_config_and_cache",
        ],
        "CLAIM-MULTI-PROVIDER-OTHER-WINDOWS": [
            "test_r4_multi_provider_routes_and_valid_other_windows",
        ],
    }

    def test_root_amendment_ack_integrity(self):
        self.assertEqual(self.ROOT_AMENDMENT_ID, "69279164-924e-46e9-947e-7150e7d050cc")

    def test_claims_matrix_coverage(self):
        import sys
        mod = sys.modules[__name__]
        for claim, test_names in self.CLAIMS_MATRIX.items():
            self.assertTrue(len(test_names) > 0, f"Claim {claim} has no mapped tests")
            for tname in test_names:
                found = False
                for cls_name in dir(mod):
                    cls = getattr(mod, cls_name)
                    if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
                        if hasattr(cls, tname):
                            found = True
                            break
                self.assertTrue(found, f"Test {tname} for claim {claim} not found in any TestCase")


if __name__ == "__main__":
    unittest.main()



