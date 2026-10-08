"""
Negative boundary and resting-state contradiction test suite for Dashboard Head readiness.
Verifies the exact protocol conditions of Principal Challenge C-0313.
"""

import unittest
import pytest
from scripts.supervision.service import check_resting_state_contradicted


class TestDashboardReadinessNegative(unittest.TestCase):
    """
    Rigorously tests negative boundaries and fail-closed properties of
    resting-state contradiction checks.
    """

    def test_c0313_production_timestamps_contradiction(self):
        """
        Production timestamps from C-0313 incident:
        reported_state_at_ms: 1791426597022 (04:29:57 CEST)
        last_activity_ms:     1791429152171 (05:12:32 CEST)
        Divergence: 2,555,149 ms (~42.5 minutes) >> 1,000 / 2,000 ms grace.
        Must evaluate to True (contradicted).
        """
        c0313_session = {
            "id": "6ef7413b-7bfe-4127-b58e-69d775e286e2",
            "tag": "agent-dashboard-head",
            "engine": "zcodex",
            "reported_state": "idle",
            "reported_state_at_ms": 1791426597022,
            "last_activity_ms": 1791429152171,
        }
        self.assertTrue(
            check_resting_state_contradicted(c0313_session, idle_grace_ms=1000),
            "C-0313 production session must be identified as contradicted"
        )
        self.assertTrue(
            check_resting_state_contradicted(c0313_session, idle_grace_ms=2000),
            "C-0313 production session must be identified as contradicted under 2000ms grace"
        )

    def test_negative_boundary_exact_grace_limits(self):
        """
        Verify exact millisecond boundary conditions:
        - at + grace: Not contradicted
        - at + grace + 1: Contradicted
        """
        reported_at = 1000000
        grace = 2000

        # Exact boundary: activity == reported_at + grace -> NOT contradicted
        boundary_session = {
            "reported_state_at_ms": reported_at,
            "last_activity_ms": reported_at + grace,
        }
        self.assertFalse(
            check_resting_state_contradicted(boundary_session, idle_grace_ms=grace),
            "Activity exactly at grace boundary must not be contradicted"
        )

        # 1ms over boundary: activity == reported_at + grace + 1 -> CONTRADICTED
        over_boundary_session = {
            "reported_state_at_ms": reported_at,
            "last_activity_ms": reported_at + grace + 1,
        }
        self.assertTrue(
            check_resting_state_contradicted(over_boundary_session, idle_grace_ms=grace),
            "Activity 1ms past grace boundary must be contradicted"
        )

    def test_missing_or_corrupt_timestamps_fail_safe(self):
        """
        Verify that missing, None, or unparseable timestamps do not crash
        and safely return False (requiring full downstream native checks).
        """
        self.assertFalse(check_resting_state_contradicted({}))
        self.assertFalse(check_resting_state_contradicted({"reported_state_at_ms": None}))
        self.assertFalse(check_resting_state_contradicted({"last_activity_ms": None}))
        self.assertFalse(check_resting_state_contradicted({
            "reported_state_at_ms": "invalid",
            "last_activity_ms": 1000
        }))
        self.assertFalse(check_resting_state_contradicted(None))

    def test_fresh_idle_report_precedes_activity(self):
        """
        When idle report was emitted AFTER or concurrently with last activity,
        contradiction must be False.
        """
        fresh_session = {
            "reported_state_at_ms": 2000000,
            "last_activity_ms": 1999500,
        }
        self.assertFalse(
            check_resting_state_contradicted(fresh_session),
            "Fresh idle report after PTY activity must not be contradicted"
        )


if __name__ == "__main__":
    unittest.main()
