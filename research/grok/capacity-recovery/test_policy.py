"""Offline tests for capacity-recovery policy. Not native success."""

from __future__ import annotations

import unittest

from policy import (
    BACKOFF_S,
    CAPACITY_PHRASE,
    ENGINE_EVENT_PROVENANCE,
    FIRST_RETRY_S,
    Identity,
    NativeReadiness,
    Observation,
    QuotaSample,
    ResourceSample,
    classify_capacity_signal,
    classify_composer,
    dump_decision,
    empty_twice,
    error_fingerprint,
    plan_recovery,
    reset_ledger_entry,
    resource_ok,
)

LIVE_CAPACITY = (
    "some prior assistant text\n"
    f"■ {CAPACITY_PHRASE}\n"
    "› Ask Codex to do anything\n"
    "  GPT-6.1-Sol medium  context 24%\n"
    "  ? for shortcuts\n"
)

HISTORICAL_QUOTE = (
    "peer capture said:\n"
    f"> {CAPACITY_PHRASE}\n"
    "› Ask Codex to do anything\n"
    "  GPT-6.1-Sol medium\n"
)

HISTORICAL_MENU = (
    "old tool output:\n"
    "> Select model\n"
    "> Esc to cancel\n"
    "› Ask Codex to do anything\n"
)

BUSY = "• Working (5m • esc to interrupt)\n› Ask Codex to do anything\n"
DRAFT = "› please deploy production now\n"
UNKNOWN = "no prompt marker at all, just a log\n"
EMPTY_TWICE = "› Ask Codex to do anything\n  GPT-6.1-Sol medium\n  ? for shortcuts\n"


def bottom_window_empty() -> str:
    return "› Ask Codex to do anything\n  GPT-6.1-Sol medium\n"

OK_RESOURCES = ResourceSample(root_free_gib=62.0, mem_available_gib=23.0, operation="recovery_scratch")
OK_QUOTA = QuotaSample(
    provider="codex",
    status="ok",
    windows={"weekly": 67.0, "5h": 90.0},
    limit_reached=False,
    required_windows=("weekly", "5h"),
)
IDENT = Identity(
    session_id="93cf28f2-2872-411c-a5da-179e1b83b59f",
    tag="codex-principal",
    workspace="/home/alexey/git/cloudflare-agent-git",
    engine="codex",
    expected_session_id="93cf28f2-2872-411c-a5da-179e1b83b59f",
    expected_tag="codex-principal",
    expected_workspace="/home/alexey/git/cloudflare-agent-git",
)


def _obs(**kwargs) -> Observation:
    base = dict(
        full_screen=LIVE_CAPACITY,
        bottom_screen=LIVE_CAPACITY,
        second_bottom_screen=EMPTY_TWICE,
        quoted_history="",
        now_s=1000.0,
        last_error_s=1000.0 - FIRST_RETRY_S,
        retry_count=0,
        identity=IDENT,
        quota=OK_QUOTA,
        resources=OK_RESOURCES,
        native=NativeReadiness(status="not-ready", reason="recipient reported working", reported_state="working", derived_state="running", source="reported"),
        conversation_id="conv-1",
        sender_owns_message=True,
        dry_run=True,
        deployed=False,
        capacity_provenance=ENGINE_EVENT_PROVENANCE,
    )
    base.update(kwargs)
    return Observation(**base)


class ClassifyTests(unittest.TestCase):
    def test_live_capacity_vs_historical_quoted(self):
        self.assertEqual(
            classify_capacity_signal(LIVE_CAPACITY, "", LIVE_CAPACITY, ENGINE_EVENT_PROVENANCE),
            "live_capacity",
        )
        self.assertEqual(
            classify_capacity_signal(LIVE_CAPACITY, "", LIVE_CAPACITY, "unknown"),
            "unproven_screen",
        )
        self.assertEqual(
            classify_capacity_signal(HISTORICAL_QUOTE, HISTORICAL_QUOTE, bottom_window_empty()),
            "historical_quoted",
        )
        quoted_full = "log\n> " + CAPACITY_PHRASE + "\n› Ask Codex to do anything\n"
        self.assertEqual(classify_capacity_signal(quoted_full, quoted_full), "historical_quoted")

    def test_supervision_select_false_positive_not_copied(self):
        # Whole-screen Select would fire on Selected model; bottom classifier does not.
        self.assertEqual(classify_composer(LIVE_CAPACITY, "codex-principal", LIVE_CAPACITY), "empty")
        self.assertEqual(classify_composer(HISTORICAL_MENU, "codex-principal", "› Ask Codex to do anything\n"), "empty")
        live_choose = "Choose a model\n›\n"
        self.assertEqual(classify_composer(live_choose, "claude-principal", live_choose), "menu-or-draft")

    def test_busy_tools_and_draft_and_unknown(self):
        self.assertEqual(classify_composer(BUSY, "codex-principal", BUSY), "busy")
        self.assertEqual(classify_composer(DRAFT, "codex-principal", DRAFT), "draft")
        self.assertEqual(classify_composer(UNKNOWN, "codex-principal", UNKNOWN), "unknown")


class GateTests(unittest.TestCase):
    def test_live_capacity_waits_180s(self):
        d = plan_recovery(_obs(now_s=10.0, last_error_s=0.0, retry_count=0, second_bottom_screen=None))
        self.assertEqual(d.action, "wait_capacity")
        self.assertEqual(d.wait_s, FIRST_RETRY_S - 10)
        self.assertFalse(d.would_inject)
        self.assertFalse(d.would_switch_model)
        self.assertFalse(d.deployed)

    def test_backoff_and_cap(self):
        d1 = plan_recovery(_obs(retry_count=1, now_s=100.0, last_error_s=0.0))
        self.assertEqual(d1.action, "wait_capacity")
        self.assertEqual(BACKOFF_S[1], 360)
        d2 = plan_recovery(_obs(retry_count=3, now_s=10_000.0, last_error_s=0.0))
        self.assertEqual(d2.action, "cap_retries")

    def test_stale_working_needs_native_event_not_timer(self):
        d = plan_recovery(_obs())
        self.assertEqual(d.action, "need_native_error_event")
        self.assertTrue(d.native_fix_required)
        self.assertIn("working", d.reason)

    def test_historical_quoted_not_live_retry(self):
        d = plan_recovery(
            _obs(
                full_screen=HISTORICAL_QUOTE,
                bottom_screen=bottom_window_empty(),
                quoted_history=HISTORICAL_QUOTE,
            )
        )
        self.assertEqual(d.action, "ignore_quoted_history")

    def test_busy_draft_unknown(self):
        self.assertEqual(plan_recovery(_obs(full_screen=BUSY, bottom_screen=BUSY)).action, "block_busy")
        self.assertEqual(plan_recovery(_obs(full_screen=DRAFT, bottom_screen=DRAFT)).action, "block_draft")
        self.assertEqual(plan_recovery(_obs(full_screen=UNKNOWN, bottom_screen=UNKNOWN)).action, "block_unknown")

    def test_quota_unknown_and_denied(self):
        unknown = QuotaSample(
            provider="codex",
            status="error",
            windows={},
            limit_reached=False,
            error="read-failed",
        )
        self.assertEqual(plan_recovery(_obs(quota=unknown)).action, "block_quota_unknown")
        missing_5h = QuotaSample(
            provider="codex",
            status="ok",
            windows={"weekly": 80.0, "5h": None},
            limit_reached=False,
            required_windows=("weekly", "5h"),
        )
        self.assertEqual(plan_recovery(_obs(quota=missing_5h)).action, "block_quota_unknown")
        denied = QuotaSample(
            provider="codex",
            status="ok",
            windows={"weekly": 12.0, "5h": 90.0},
            limit_reached=False,
            required_windows=("weekly", "5h"),
        )
        self.assertEqual(plan_recovery(_obs(quota=denied)).action, "block_quota")
        limited = QuotaSample(
            provider="codex",
            status="ok",
            windows={"weekly": 80.0, "5h": 90.0},
            limit_reached=True,
            required_windows=("weekly", "5h"),
        )
        self.assertEqual(plan_recovery(_obs(quota=limited)).action, "block_quota")

    def test_stale_identity(self):
        bad = Identity(
            session_id="dead-session",
            tag="codex-principal",
            workspace="/home/alexey/git/cloudflare-agent-git",
            engine="codex",
            expected_session_id="93cf28f2-2872-411c-a5da-179e1b83b59f",
            expected_tag="codex-principal",
            expected_workspace="/home/alexey/git/cloudflare-agent-git",
        )
        self.assertEqual(plan_recovery(_obs(identity=bad)).action, "block_stale_identity")

    def test_foreign_sender(self):
        self.assertEqual(plan_recovery(_obs(sender_owns_message=False)).action, "block_foreign_sender")

    def test_dedup_and_reset(self):
        ledger = {}
        fp = error_fingerprint(IDENT.session_id, "conv-1")
        first = plan_recovery(_obs(retry_count=3, now_s=10_000.0), ledger)
        self.assertEqual(first.action, "cap_retries")
        second = plan_recovery(_obs(retry_count=0, now_s=20_000.0), ledger)
        self.assertEqual(second.action, "dedup_hold")
        reset_ledger_entry(ledger, fp)
        third = plan_recovery(_obs(now_s=20_000.0, last_error_s=20_000.0 - 10), ledger)
        self.assertEqual(third.action, "wait_capacity")

    def test_repeated_live_errors_share_fingerprint(self):
        a = error_fingerprint(IDENT.session_id, "conv-1")
        b = error_fingerprint(IDENT.session_id, "conv-1")
        c = error_fingerprint(IDENT.session_id, "conv-2")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_native_ready_still_uninstalled(self):
        d = plan_recovery(
            _obs(
                native=NativeReadiness(status="ready", reason="idle", reported_state="idle", derived_state="idle", source="reported"),
            )
        )
        self.assertEqual(d.action, "dry_run_same_conversation_retry")
        self.assertFalse(d.deployed)
        self.assertFalse(d.would_inject)
        self.assertNotIn("native success", dump_decision(d).lower())
        self.assertNotIn("native_success", dump_decision(d))

    def test_empty_twice_required(self):
        self.assertFalse(empty_twice(_obs(second_bottom_screen=None)))
        d = plan_recovery(
            _obs(
                native=NativeReadiness(status="ready", reported_state="idle", derived_state="idle", source="reported"),
                second_bottom_screen=None,
            )
        )
        self.assertEqual(d.action, "hold_empty_snapshots")

    def test_never_labels_seeded_native_success(self):
        d = plan_recovery(
            _obs(
                native=NativeReadiness(status="ready", reported_state="idle", derived_state="idle", source="reported"),
            )
        )
        text = dump_decision(d)
        self.assertNotRegex(text, r"native[_ ]success")
        self.assertTrue(d.extras.get("dry_run"))

    def test_unprefixed_bottom_phrase_is_unproven(self):
        tool_dump = f"tool output recap\n{CAPACITY_PHRASE}\n› Ask Codex to do anything\n"
        self.assertEqual(classify_capacity_signal(tool_dump, "", tool_dump, "unknown"), "unproven_screen")
        d = plan_recovery(_obs(full_screen=tool_dump, bottom_screen=tool_dump, capacity_provenance="unknown"))
        self.assertEqual(d.action, "hold_unproven_provenance")

    def test_multiline_draft_and_error_text_in_composer(self):
        multiline = "›\nplease deploy production now\n"
        self.assertEqual(classify_composer(multiline, "codex-principal", multiline), "draft")
        err_draft = f"›\n{CAPACITY_PHRASE}\n"
        self.assertEqual(classify_composer(err_draft, "codex-principal", err_draft), "draft")
        self.assertEqual(plan_recovery(_obs(full_screen=multiline, bottom_screen=multiline)).action, "block_draft")

    def test_historical_transport_not_live_transport(self):
        hist = "old log: mailbox is busy\n› Ask Codex to do anything\n"
        d = plan_recovery(_obs(full_screen=hist, bottom_screen="› Ask Codex to do anything\n", capacity_provenance="unknown"))
        self.assertNotEqual(d.action, "block_transport")

    def test_resource_floors_do_not_weaken_worker_gate(self):
        scratch_ok = ResourceSample(root_free_gib=12.0, mem_available_gib=23.0, operation="recovery_scratch")
        worker_low = ResourceSample(root_free_gib=12.0, mem_available_gib=23.0, operation="new_worker")
        self.assertTrue(resource_ok(scratch_ok))
        self.assertFalse(resource_ok(worker_low))
        d = plan_recovery(_obs(resources=worker_low))
        self.assertEqual(d.action, "block_resources")


if __name__ == "__main__":
    unittest.main()
