#!/usr/bin/env python3
"""website/test_history.py

Tests for website/history.py: data validity, privacy guarantees,
epistemic labeling, HTML generation, and the accepted product/hour filter contract.
"""

import json
import re
import unittest
from pathlib import Path

from website.history import (
    CANONICAL_IDS,
    CHIP_LABELS,
    EXPORT_PATH,
    bucket_in_range,
    compute_kpis,
    default_filter_state,
    embed_json,
    history_page,
    hour_bound_options,
    load_telemetry_data,
    parse_filter_params,
    parse_utc,
    public_filter_payload,
    render_hourly_chart_svg,
    serialize_filter_query,
    snap_from,
    snap_to,
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

        for i in range(4):
            b = buckets[i]
            is_unobs = b.get("observation_state") == "unobserved"
            self.assertTrue(is_unobs, f"Bucket {i} must be unobserved")

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

        self.assertNotIn("/home/alexey", html_content, "Leaked /home/alexey path into public HTML")
        self.assertNotIn("/Users/", html_content, "Leaked user path into public HTML")
        self.assertNotIn("/tmp/", html_content, "Leaked /tmp path into public HTML")

        uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        matches = uuid_pattern.findall(html_content)
        self.assertEqual(matches, [], f"Found raw UUIDs in public history HTML: {matches}")

        self.assertNotIn("Bearer ", html_content)
        self.assertNotIn("token=", html_content)
        self.assertNotIn("unattributed", html_content)

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
        self.assertIn("history-filter.js", html_content)
        self.assertIn('id="history-telemetry-data"', html_content)


class TestHistoryFilterContract(unittest.TestCase):
    def setUp(self):
        self.data = load_telemetry_data()
        self.hourly = self.data["hourly_history"]
        self.window = self.data["window"]

    def test_canonical_chips_are_four_public_labels(self):
        self.assertEqual(
            list(CANONICAL_IDS),
            ["agent-branches", "agent-dashboard", "quota-launcher", "agent-coordination"],
        )
        self.assertEqual(
            [CHIP_LABELS[i] for i in CANONICAL_IDS],
            ["Branches", "Dashboard", "Launcher", "Coordination"],
        )
        html_content = history_page()
        for label in ("Branches", "Dashboard", "Launcher", "Coordination"):
            self.assertIn(f">{label}</button>", html_content)
        self.assertEqual(html_content.count('class="history-chip"'), 4)
        self.assertNotIn("unattributed", html_content)
        self.assertNotIn("Unattributed", html_content)

    def test_half_open_bucket_inclusion(self):
        start = parse_utc("2026-10-04T11:00:00Z")
        end = parse_utc("2026-10-04T12:00:00Z")
        included = [b["bucket_index"] for b in self.hourly if bucket_in_range(b, start, end)]
        self.assertEqual(included, [4], "Bucket 4 start is in [11:00, 12:00); bucket 5 is not")

        end_eq_start = parse_utc("2026-10-04T11:00:00Z")
        none = [b["bucket_index"] for b in self.hourly if bucket_in_range(b, start, end_eq_start)]
        self.assertEqual(none, [], "Inverted/empty half-open range includes no buckets")

        full_start = parse_utc(self.window["start_utc"])
        full_end = parse_utc(self.window["end_utc"])
        all_idx = [b["bucket_index"] for b in self.hourly if bucket_in_range(b, full_start, full_end)]
        self.assertEqual(all_idx, list(range(24)))

        last_start = parse_utc(self.hourly[23]["bucket_start_utc"])
        last_end = parse_utc(self.hourly[23]["bucket_end_utc"])
        self.assertTrue(bucket_in_range(self.hourly[23], last_start, last_end))
        self.assertFalse(bucket_in_range(self.hourly[23], last_end, parse_utc("2026-10-06T00:00:00Z")))

    def test_empty_product_selection_is_empty_state_not_all(self):
        state = parse_filter_params({"product": ""}, self.data)
        self.assertEqual(state.product_ids, tuple())
        kpis = compute_kpis(self.data, state)
        self.assertEqual(kpis["empty_reason"], "products")
        self.assertEqual(kpis["tokens"], 0)
        self.assertEqual(kpis["observed_hours"], 0)
        self.assertEqual(kpis["sampled_work"], 0.0)
        self.assertFalse(kpis["show_tokens"])

    def test_missing_product_param_defaults_to_all(self):
        state = parse_filter_params({}, self.data)
        self.assertEqual(state.product_ids, CANONICAL_IDS)
        kpis = compute_kpis(self.data, state)
        self.assertIsNone(kpis["empty_reason"])
        self.assertEqual(kpis["tokens"], 1086844)
        self.assertEqual(kpis["observed_hours"], 20)
        self.assertEqual(kpis["in_range_count"], 24)
        self.assertAlmostEqual(kpis["sampled_work"], 12.6254, places=4)

    def test_invalid_query_falls_back_to_full_window_and_all_products(self):
        bad_product = parse_filter_params({"product": "agent-branches,not-a-product"}, self.data)
        self.assertEqual(bad_product.product_ids, CANONICAL_IDS)

        bad_from = parse_filter_params({"from": "yesterday", "product": "quota-launcher"}, self.data)
        fallback = default_filter_state(self.data)
        self.assertEqual(bad_from.start_utc, fallback.start_utc)
        self.assertEqual(bad_from.end_utc, fallback.end_utc)

        naive = parse_filter_params({"from": "2026-10-04T13:00:00", "to": "2026-10-05T07:00:00Z"}, self.data)
        self.assertEqual(naive.start_utc, fallback.start_utc)
        self.assertEqual(naive.end_utc, fallback.end_utc)

    def test_query_string_roundtrip_subset_and_bounds(self):
        state = parse_filter_params(
            {
                "product": "quota-launcher,agent-branches",
                "from": "2026-10-04T13:00:00Z",
                "to": "2026-10-05T07:00:00Z",
            },
            self.data,
        )
        self.assertEqual(state.product_ids, ("agent-branches", "quota-launcher"))
        self.assertEqual(state.start_utc, "2026-10-04T13:00:00Z")
        self.assertEqual(state.end_utc, "2026-10-05T07:00:00Z")
        query = serialize_filter_query(state, self.data)
        self.assertEqual(
            query,
            "product=agent-branches,quota-launcher&from=2026-10-04T13:00:00Z",
        )
        again = parse_filter_params(dict(part.split("=", 1) for part in query.split("&")), self.data)
        self.assertEqual(again, state)

        default_q = serialize_filter_query(default_filter_state(self.data), self.data)
        self.assertEqual(default_q, "")

    def test_kpi_tokens_require_selected_product_and_in_range_bucket(self):
        dash_only = parse_filter_params({"product": "agent-dashboard"}, self.data)
        kpis = compute_kpis(self.data, dash_only)
        self.assertEqual(kpis["tokens"], 680764)
        self.assertTrue(kpis["show_tokens"])

        after_dash = parse_filter_params(
            {
                "product": "agent-dashboard",
                "from": "2026-10-04T12:00:00Z",
                "to": "2026-10-05T07:00:00Z",
            },
            self.data,
        )
        kpis_after = compute_kpis(self.data, after_dash)
        self.assertEqual(kpis_after["tokens"], 0)
        self.assertFalse(kpis_after["show_tokens"])

        coord_slice = parse_filter_params(
            {
                "product": "agent-coordination",
                "from": "2026-10-04T12:00:00Z",
                "to": "2026-10-04T13:00:00Z",
            },
            self.data,
        )
        kpis_coord = compute_kpis(self.data, coord_slice)
        self.assertEqual(kpis_coord["tokens"], 406080)
        self.assertEqual(kpis_coord["observed_hours"], 1)
        self.assertEqual(kpis_coord["in_range_count"], 1)

        branches = parse_filter_params({"product": "agent-branches"}, self.data)
        kpis_br = compute_kpis(self.data, branches)
        self.assertEqual(kpis_br["tokens"], 0)
        self.assertFalse(kpis_br["show_tokens"])
        self.assertAlmostEqual(kpis_br["sampled_work"], 12.5577, places=4)

    def test_inverted_bounds_zero_kpis_and_empty_range(self):
        state = parse_filter_params(
            {"from": "2026-10-05T07:00:00Z", "to": "2026-10-04T07:00:00Z"},
            self.data,
        )
        kpis = compute_kpis(self.data, state)
        self.assertEqual(kpis["empty_reason"], "range")
        self.assertEqual(kpis["tokens"], 0)
        self.assertEqual(kpis["observed_hours"], 0)
        self.assertEqual(kpis["in_range_count"], 0)
        self.assertEqual(kpis["sampled_work"], 0.0)

    def test_snap_mid_hour_to_bucket_edges(self):
        mid = parse_utc("2026-10-04T11:30:00Z")
        self.assertEqual(snap_from(mid, self.data).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-10-04T11:00:00Z")
        self.assertEqual(snap_to(mid, self.data).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-10-04T12:00:00Z")

        snapped = parse_filter_params(
            {"from": "2026-10-04T11:30:00Z", "to": "2026-10-04T11:45:00Z"},
            self.data,
        )
        self.assertEqual(snapped.start_utc, "2026-10-04T11:00:00Z")
        self.assertEqual(snapped.end_utc, "2026-10-04T12:00:00Z")
        kpis = compute_kpis(self.data, snapped)
        self.assertEqual(kpis["in_range_count"], 1)
        self.assertEqual(kpis["tokens"], 680764)

    def test_berlin_hour_options_match_bucket_edges(self):
        opts = hour_bound_options(self.data)
        self.assertEqual(len(opts["from"]), 24)
        self.assertEqual(len(opts["to"]), 24)
        self.assertEqual(opts["from"][0]["value"], "2026-10-04T07:00:00Z")
        self.assertEqual(opts["to"][-1]["value"], "2026-10-05T07:00:00Z")
        self.assertIn("CEST", opts["from"][0]["berlin"])
        self.assertIn("09:00", opts["from"][0]["berlin"])
        self.assertIn("UTC", opts["from"][0]["utc"])
        html_content = history_page()
        self.assertIn("From (Berlin)", html_content)
        self.assertIn("To (Berlin)", html_content)
        self.assertIn("4 Oct 09:00 CEST", html_content)
        self.assertIn("5 Oct 09:00 CEST", html_content)

    def test_inlined_payload_excludes_private_and_unattributed(self):
        payload = public_filter_payload(self.data)
        blob = json.dumps(payload)
        self.assertNotIn("unattributed", blob)
        self.assertNotIn("/home/", blob)
        self.assertNotIn("session", blob.lower())
        self.assertEqual([p["id"] for p in payload["products"]], list(CANONICAL_IDS))
        self.assertEqual(len(payload["hourly"]), 24)
        html_content = history_page()
        start = html_content.index('id="history-telemetry-data">') + len('id="history-telemetry-data">')
        end = html_content.index("</script>", start)
        inlined = json.loads(html_content[start:end])
        self.assertEqual(inlined["products"], payload["products"])
        self.assertNotIn("unattributed", html_content[start:end])

    def test_html_marks_rows_cells_and_cards_for_filters(self):
        html_content = history_page()
        self.assertIn('data-product="agent-branches"', html_content)
        self.assertIn('data-product="agent-dashboard"', html_content)
        self.assertIn('data-product="quota-launcher"', html_content)
        self.assertIn('data-product="agent-coordination"', html_content)
        self.assertIn('data-start="2026-10-04T07:00:00Z"', html_content)
        self.assertIn('data-end="2026-10-04T08:00:00Z"', html_content)
        self.assertEqual(html_content.count('class="tracker-card"'), 4)
        self.assertIn('data-product="agent-branches"', html_content)
        self.assertIn("Export generated", html_content)
        self.assertIn("id=\"history-export-json\"", html_content)
        self.assertIn("id=\"history-export-csv\"", html_content)
        self.assertIn("id=\"history-export-md\"", html_content)
        self.assertIn("does not refresh the collector", html_content)

    def test_date_range_does_not_drop_task_cards_from_markup(self):
        html_content = history_page()
        for pid in CANONICAL_IDS:
            self.assertIn(f'<div class="tracker-card" data-product="{pid}">', html_content)

    def test_unobserved_rows_remain_in_range(self):
        state = parse_filter_params(
            {"from": "2026-10-04T07:00:00Z", "to": "2026-10-04T11:00:00Z"},
            self.data,
        )
        kpis = compute_kpis(self.data, state)
        self.assertEqual(kpis["in_range_count"], 4)
        self.assertEqual(kpis["observed_hours"], 0)
        self.assertEqual(kpis["empty_reason"], None)
        self.assertEqual(len(kpis["in_range_buckets"]), 4)

    def test_embed_json_escapes_script_breakers(self):
        encoded = embed_json({"x": "</script><b>"})
        self.assertNotIn("</script>", encoded)
        self.assertIn("\\u003c", encoded)

    def test_history_filter_js_contract_surface(self):
        js_path = Path(__file__).resolve().parent / "assets" / "history-filter.js"
        self.assertTrue(js_path.exists())
        js = js_path.read_text(encoding="utf-8")
        self.assertIn("product", js)
        self.assertIn("from", js)
        self.assertIn("to", js)
        self.assertIn("replaceState", js)
        self.assertIn("history-telemetry-data", js)
        self.assertIn("history-export-json", js)
        self.assertIn("history-export-csv", js)
        self.assertIn("history-export-md", js)
        self.assertNotIn("/home/alexey", js)
        self.assertNotIn("unattributed", js)
        html_content = history_page()
        for pid in CANONICAL_IDS:
            self.assertIn(f'data-product="{pid}"', html_content)

    def test_css_mobile_overflow_guards(self):
        css = (Path(__file__).resolve().parent / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertIn(".history-page{min-width:0;max-width:100%;overflow-x:clip}", css)
        self.assertIn(".telemetry-chart-svg{width:100%;height:auto;min-width:0;display:block;max-width:100%}", css)
        self.assertNotIn("min-width:600px", css)


if __name__ == "__main__":
    unittest.main()
