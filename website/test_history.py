#!/usr/bin/env python3
"""website/test_history.py

Tests for website/history.py: data validity, privacy guarantees,
epistemic labeling, and HTML generation for the telemetry & task tracker page.
"""

import json
import re
import unittest
from pathlib import Path

from website.history import (
    load_telemetry_data,
    render_hourly_chart_svg,
    history_page,
    EXPORT_PATH,
)


class TestHourlyHistory(unittest.TestCase):
    def setUp(self):
        self.data = load_telemetry_data()

    def test_export_file_exists_and_valid(self):
        self.assertTrue(EXPORT_PATH.exists(), f"Missing export file at {EXPORT_PATH}")
        raw = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
        self.assertIn("hourly_history", raw)
        self.assertIn("window", raw)
        self.assertIn("epistemic_policy", raw)
        self.assertIn("products", raw)

    def test_twenty_four_hourly_buckets(self):
        buckets = self.data.get("hourly_history", [])
        self.assertEqual(len(buckets), 24, "Must contain exactly 24 hourly buckets")

        indices = [b.get("bucket_index") for b in buckets]
        self.assertEqual(indices, list(range(24)), "Bucket indices must be sequential 0..23")

        # First 4 buckets should be unobserved (pre-collector launch)
        for i in range(4):
            b = buckets[i]
            is_unobs = b.get("observation_state") == "unobserved"
            self.assertTrue(is_unobs, f"Bucket {i} must be unobserved")

        # Buckets 4..23 should have observation coverage
        observed_count = 0
        for i in range(4, 24):
            b = buckets[i]
            if b.get("observation_state") == "observed" or any(
                p.get("observation_status") in ("observed", "partial")
                for p in b.get("products", {}).values()
            ):
                observed_count += 1
        self.assertEqual(observed_count, 20, "Must have exactly 20 observed buckets")

    def test_four_products_present(self):
        products = self.data.get("products", [])
        prod_ids = {p.get("id") for p in products}
        expected = {"agent-branches", "agent-dashboard", "quota-launcher", "agent-coordination"}
        self.assertTrue(expected.issubset(prod_ids), f"Missing products from {prod_ids}")

    def test_token_numbers_match_verified_audit(self):
        token_sum = self.data.get("product_token_summary", {})
        ad_tok = token_sum.get("agent-dashboard", {}).get("total_tokens", 0)
        ac_tok = token_sum.get("agent-coordination", {}).get("total_tokens", 0)
        self.assertEqual(ad_tok, 680764, "Agent Dashboard token total must match audit (680,764)")
        self.assertEqual(ac_tok, 406080, "Agent Coordination token total must match audit (406,080)")
        self.assertEqual(ad_tok + ac_tok, 1086844, "Total tokens must match 1,086,844")

    def test_privacy_no_leaks_in_html(self):
        html_content = history_page()

        # Check for absolute user paths
        self.assertNotIn("/home/alexey", html_content, "Leaked /home/alexey path into public HTML")
        self.assertNotIn("/Users/", html_content, "Leaked user path into public HTML")
        self.assertNotIn("/tmp/", html_content, "Leaked /tmp path into public HTML")

        # Check for private session UUID patterns (36-char lowercase hex with hyphens)
        # Note: standard SVG ids or hashes like commit shas are fine, but raw session UUIDs should not leak
        uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        matches = uuid_pattern.findall(html_content)
        self.assertEqual(matches, [], f"Found raw UUIDs in public history HTML: {matches}")

        # Check for credentials or secrets
        self.assertNotIn("Bearer ", html_content)
        self.assertNotIn("token=", html_content)

    def test_chart_svg_generation(self):
        buckets = self.data.get("hourly_history", [])
        svg = render_hourly_chart_svg(buckets)
        self.assertTrue(svg.startswith("<svg"), "Chart must start with <svg tag")
        self.assertTrue(svg.endswith("</svg>"), "Chart must end with </svg> tag")
        self.assertIn("Sampled Working Hours", svg)
        self.assertIn("Pre-collector (Unobserved)", svg)

    def test_html_page_structure(self):
        html_content = history_page()
        self.assertIn("Telemetry &amp; Task Tracker", html_content)
        self.assertIn("EPISTEMIC BOUNDARIES", html_content)
        self.assertIn("1,086,844", html_content)
        self.assertIn("Active Delivery &amp; Task Tracker", html_content)
        self.assertIn("Agent Branches", html_content)
        self.assertIn("Agent Dashboard", html_content)
        self.assertIn("Quota Launcher", html_content)
        self.assertIn("Cross-computer Coordination", html_content)


if __name__ == "__main__":
    unittest.main()
