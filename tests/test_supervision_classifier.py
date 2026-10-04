#!/usr/bin/env python3
"""
Test Suite for Supervision Classifier Candidate & Offline Repro
(Codex Principal C1444 / C1448 / C1454)

Verifies:
1. Codex Principal Footer False-Draft Repro:
   - Baseline fails: classifies status bar (GPT-*, Context %, weekly limit, warnings) as Draft.
   - Candidate succeeds: classifies composer prompt as Empty.
2. Dashboard Idle + Later Redraw Repro:
   - Baseline fails: pure PTY activity timestamp falsely contradicts idle resting state.
   - Candidate succeeds: verifies screen state (not busy, composer empty) and preserves Ready.
3. Real Non-Empty Draft Preservation:
   - Candidate fails closed on unsubmitted draft text (e.g., '› git reset --hard HEAD').
4. Active Work / Busy Screen Preservation:
   - Candidate fails closed on active working banners (e.g., '• Working (2m 15s • esc to interrupt)').
5. Heterogeneous TUI Engine Support:
   - OpenCode, Grok, Claude, Shell, and Dashboard coverage.
"""

import os
import sys
import unittest

# Ensure repo root is in python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from research.antigravity.tooling.classifier_candidate import (
    PromptState,
    ReadinessVerdict,
    classify_composer_prompt_baseline,
    classify_composer_prompt_candidate,
    idle_was_contradicted_baseline,
    idle_was_contradicted_candidate,
    evaluate_readiness_verdict_baseline,
    evaluate_readiness_verdict_candidate,
)


class TestSupervisionClassifier(unittest.TestCase):
    """Offline unit & reproduction test suite for supervision classifier."""

    # -------------------------------------------------------------------------
    # Test 1: Codex Principal Footer False-Draft Repro
    # -------------------------------------------------------------------------
    def test_01_codex_footer_false_draft_repro(self):
        """
        Test 1: Exact captured screen from Codex Principal with placeholder prompt
        and status bar containing GPT-6.1-Sol, Context %, workspace path,
        weekly limit, and warning metrics.

        Proves:
        - Baseline failure: misclassifies status bar as unsubmitted draft (NOTREADY false-positive).
        - Candidate success: correctly ignores status bar, classifies prompt as Empty, evaluates to Ready.
        """
        captured_screen = (
            "• Working (10m 53s • esc to interrupt)\n"
            "  └ Tip: Use /export to save your conversation as Markdown.\n"
            "\n"
            "› Ask Codex to do anything\n"
            "\n"
            "  GPT-6.1-Sol medium · Context 14% left · ~/git/cloudflare-agent-git · Context 86% used · weekly limit (78% left)\n"
            "  ? for shortcuts                                                   ⚠ 1 warning · f2 to view"
        )

        record = {
            "engine": "codex",
            "reported_state": "idle",
            "reported_state_at_ms": 10000,
            "last_activity_ms": 10500,
            "has_lifecycle_hooks": True,
        }
        now_ms = 11000

        # --- Baseline verification: MUST reproduce failure ---
        baseline_state = classify_composer_prompt_baseline(captured_screen, "codex")
        self.assertTrue(
            baseline_state.is_draft,
            f"Expected baseline to falsely report Draft, got: {baseline_state}"
        )
        self.assertIn("GPT-6.1-Sol", baseline_state.detail)
        baseline_verdict = evaluate_readiness_verdict_baseline(baseline_state, record, now_ms)
        self.assertTrue(baseline_verdict.is_reject)
        self.assertIn("unsubmitted draft in progress", baseline_verdict.detail)
        self.assertIn("GPT-6.1-Sol", baseline_verdict.detail)

        # --- Candidate verification: MUST fix failure and succeed ---
        candidate_state = classify_composer_prompt_candidate(captured_screen, "codex")
        self.assertTrue(
            candidate_state.is_empty,
            f"Expected candidate to classify prompt as Empty, got: {candidate_state}"
        )
        self.assertEqual(candidate_state, "empty")
        self.assertEqual(candidate_state, PromptState.empty())

        candidate_verdict = evaluate_readiness_verdict_candidate(
            candidate_state, record, now_ms, screen_text=captured_screen
        )
        self.assertTrue(
            candidate_verdict.is_ready,
            f"Expected candidate verdict to be Ready, got: {candidate_verdict}"
        )
        self.assertEqual(candidate_verdict, "ready")

    # -------------------------------------------------------------------------
    # Test 2: Dashboard Idle + Later Redraw Repro
    # -------------------------------------------------------------------------
    def test_02_dashboard_idle_and_later_redraw_repro(self):
        """
        Test 2: Dashboard reports idle at timestamp T, and subsequent harmless
        PTY activity lands at T + 5000ms due to periodic TUI redraws / cursor refreshes.

        Proves:
        - Baseline failure: pure PTY activity timestamp check falsely contradicts idle.
        - Candidate success: verifies screen state (not busy, composer empty) and preserves Ready.
        """
        dashboard_screen_idle = (
            "============================= AGENT DASHBOARD =============================\n"
            " [Status: IDLE]   Active Workers: 0   Queued: 0   Completed: 12            \n"
            "---------------------------------------------------------------------------\n"
            " 14:55:01  worker-1  completed task T-101                                  \n"
            " 14:55:02  worker-2  completed task T-102                                  \n"
            " 14:55:05  dashboard status refresh (redraw)                               \n"
            "---------------------------------------------------------------------------\n"
            " [Tab: Overview]  [q: Quit]  [r: Refresh]  [?: Help]                       \n"
            "› \n"
        )

        t_ms = 10000
        t_redraw_ms = 15000  # T + 5000ms (well past 2000ms grace)
        now_ms = 16000

        record = {
            "engine": "dashboard",
            "reported_state": "idle",
            "reported_state_at_ms": t_ms,
            "last_activity_ms": t_redraw_ms,
            "has_lifecycle_hooks": True,
        }

        # --- Baseline verification: falsely contradicts idle ---
        baseline_contradicted = idle_was_contradicted_baseline(record, at=t_ms, has_lifecycle_hooks=True)
        self.assertTrue(
            baseline_contradicted,
            "Baseline must falsely contradict idle for non-antigravity engines"
        )

        p_state_baseline = classify_composer_prompt_baseline(dashboard_screen_idle, "dashboard")
        baseline_verdict = evaluate_readiness_verdict_baseline(p_state_baseline, record, now_ms)
        self.assertTrue(baseline_verdict.is_reject)
        self.assertIn("subsequent PTY activity contradicted resting state", baseline_verdict.detail)

        # --- Candidate verification: preserves idle readiness ---
        candidate_state = classify_composer_prompt_candidate(dashboard_screen_idle, "dashboard")
        self.assertTrue(candidate_state.is_empty)

        candidate_contradicted = idle_was_contradicted_candidate(
            record, screen_text=dashboard_screen_idle, at=t_ms, now=now_ms
        )
        self.assertFalse(
            candidate_contradicted,
            "Candidate must not contradict idle when screen is not busy and composer is empty"
        )

        candidate_verdict = evaluate_readiness_verdict_candidate(
            candidate_state, record, now_ms, screen_text=dashboard_screen_idle
        )
        self.assertTrue(
            candidate_verdict.is_ready,
            f"Expected candidate verdict to be Ready on harmless redraw, got: {candidate_verdict}"
        )

    # -------------------------------------------------------------------------
    # Test 3: Real Non-Empty Draft Preservation (Fail-Closed Safety)
    # -------------------------------------------------------------------------
    def test_03_real_draft_preservation(self):
        """
        Test 3: Typed user drafts must ALWAYS fail closed and be protected from
        message injection / overwriting.

        Checks:
        a) Codex screen with typed destructive command: '› git reset --hard HEAD'
        b) Codex screen with typed task: '› Fix rate limiter bug'
        c) Codex screen with multiline draft after prompt
        """
        # Case 3a: git reset draft
        screen_git_reset = (
            "• Worked for 5m 12s\n"
            "\n"
            "› git reset --hard HEAD\n"
            "\n"
            "  GPT-6.1-Sol medium · Context 14% left · ~/git/cloudflare-agent-git\n"
            "  ? for shortcuts"
        )
        state_3a = classify_composer_prompt_candidate(screen_git_reset, "codex")
        self.assertTrue(state_3a.is_draft)
        self.assertEqual(state_3a.detail, "git reset --hard HEAD")
        verdict_3a = evaluate_readiness_verdict_candidate(
            state_3a, {"engine": "codex", "reported_state": "idle", "reported_state_at_ms": 1000}, 2000
        )
        self.assertTrue(verdict_3a.is_reject)
        self.assertIn("git reset --hard HEAD", verdict_3a.detail)

        # Case 3b: bugfix draft
        screen_fix_bug = (
            "› Fix rate limiter bug\n"
            "  GPT-6.1-Sol · Context 20% left · weekly limit (78% left)"
        )
        state_3b = classify_composer_prompt_candidate(screen_fix_bug, "codex")
        self.assertTrue(state_3b.is_draft)
        self.assertEqual(state_3b.detail, "Fix rate limiter bug")
        verdict_3b = evaluate_readiness_verdict_candidate(
            state_3b, {"engine": "codex", "reported_state": "idle", "reported_state_at_ms": 1000}, 2000
        )
        self.assertTrue(verdict_3b.is_reject)
        self.assertIn("Fix rate limiter bug", verdict_3b.detail)

        # Case 3c: Multiline draft with placeholder on prompt line but draft line below
        screen_multiline = (
            "› Ask Codex to do anything\n"
            "  investigate connection pool timeout\n"
            "  GPT-6.1-Sol · Context 20% left · ? for shortcuts"
        )
        state_3c = classify_composer_prompt_candidate(screen_multiline, "codex")
        self.assertTrue(state_3c.is_draft)
        self.assertEqual(state_3c.detail, "investigate connection pool timeout")

    # -------------------------------------------------------------------------
    # Test 4: Active Work / Busy Screen Preservation (Fail-Closed Safety)
    # -------------------------------------------------------------------------
    def test_04_active_work_busy_screen_preservation(self):
        """
        Test 4: Screen containing active working indicators must fail closed as Busy
        and refuse delivery.

        Checks:
        a) Codex active execution: '• Working (2m 15s • esc to interrupt)'
        b) Claude active execution: 'Running command... (ctrl+c to cancel)'
        c) OpenCode active execution: 'Working (esc to interrupt)'
        """
        # Case 4a: Codex busy
        screen_codex_busy = (
            "› cargo test --package aplexer\n"
            "   Compiling aplexer v0.1.9\n"
            "• Working (2m 15s • esc to interrupt)\n"
        )
        state_4a = classify_composer_prompt_candidate(screen_codex_busy, "codex")
        self.assertTrue(
            state_4a.is_busy,
            f"Expected state to be Busy, got: {state_4a}"
        )
        self.assertEqual(state_4a, "busy")
        verdict_4a = evaluate_readiness_verdict_candidate(
            state_4a, {"engine": "codex", "reported_state": "idle", "reported_state_at_ms": 1000}, 2000
        )
        self.assertTrue(verdict_4a.is_reject)
        self.assertIn("actively busy", verdict_4a.detail)

        # Case 4b: Claude busy
        screen_claude_busy = (
            "❯ implement endpoint\n"
            "Reading file... src/api.rs\n"
            "Running command... cargo check\n"
        )
        state_4b = classify_composer_prompt_candidate(screen_claude_busy, "claude")
        self.assertTrue(state_4b.is_busy)
        verdict_4b = evaluate_readiness_verdict_candidate(
            state_4b, {"engine": "claude", "reported_state": "waiting", "reported_state_at_ms": 1000}, 2000
        )
        self.assertTrue(verdict_4b.is_reject)

        # Case 4c: OpenCode busy
        screen_opencode_busy = (
            "   /home/alexey/git/cloudflare-agent-git           83.5K (8%)  Working (esc to interrupt)\n"
        )
        state_4c = classify_composer_prompt_candidate(screen_opencode_busy, "opencode")
        self.assertTrue(state_4c.is_busy)

    # -------------------------------------------------------------------------
    # Test 5: OpenCode Bordered Composer Tests
    # -------------------------------------------------------------------------
    def test_05_opencode_bordered_composer(self):
        """Verify OpenCode empty, draft, and multiline draft classification."""
        empty_screen = (
            "   ▣  Build · Space Bunny Free\n"
            "┃\n"
            "┃  Ask a question...\n"
            "╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀\n"
            " /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands\n"
        )
        state_empty = classify_composer_prompt_candidate(empty_screen, "opencode")
        self.assertTrue(state_empty.is_empty)

        draft_screen = (
            "   ▣  Build · Space Bunny Free\n"
            "┃\n"
            "┃  deploy production worker candidate\n"
            "╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀\n"
            " /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands\n"
        )
        state_draft = classify_composer_prompt_candidate(draft_screen, "opencode")
        self.assertTrue(state_draft.is_draft)
        self.assertEqual(state_draft.detail, "deploy production worker candidate")

    # -------------------------------------------------------------------------
    # Test 6: Grok Bordered Box Tests
    # -------------------------------------------------------------------------
    def test_06_grok_composer(self):
        """Verify Grok empty vs draft box classification."""
        empty_grok = (
            "  ╭───────────────────────────────────────────────────────────────────────────────────────╮  \n"
            "  │ ❯                                                                                     │  \n"
            "  ╰────────────────────────────────────────────────── Grok 4.7 (medium) · always-approve ─╯  \n"
            "  Shift+Tab:mode  │  Ctrl+.:shortcuts                                                        "
        )
        state_empty = classify_composer_prompt_candidate(empty_grok, "grok")
        self.assertTrue(state_empty.is_empty)

        draft_grok = (
            "  ╭───────────────────────────────────────────────────────────────────────────────────────╮  \n"
            "  │ ❯ unsubmitted grok draft                                                              │  \n"
            "  ╰────────────────────────────────────────────────── Grok 4.7 (medium) · always-approve ─╯  \n"
            "  Shift+Tab:mode  │  Ctrl+.:shortcuts                                                        "
        )
        state_draft = classify_composer_prompt_candidate(draft_grok, "grok")
        self.assertTrue(state_draft.is_draft)
        self.assertEqual(state_draft.detail, "unsubmitted grok draft")

    # -------------------------------------------------------------------------
    # Test 7: Claude CLI Prompt & Menu Overlay Tests
    # -------------------------------------------------------------------------
    def test_07_claude_composer_and_menu(self):
        """Verify Claude empty prompt, draft, and menu dialog protection."""
        empty_claude = (
            "Task completed.\n"
            "❯ \n"
            "──────────────────────────────────────────\n"
            "? help · ctrl+c to cancel\n"
        )
        state_empty = classify_composer_prompt_candidate(empty_claude, "claude")
        self.assertTrue(state_empty.is_empty)

        draft_claude = (
            "Task completed.\n"
            "❯ git checkout -b feature/test\n"
            "──────────────────────────────────────────\n"
        )
        state_draft = classify_composer_prompt_candidate(draft_claude, "claude")
        self.assertTrue(state_draft.is_draft)
        self.assertEqual(state_draft.detail, "git checkout -b feature/test")

        menu_claude = (
            "How is Claude doing?\n"
            "1. Great\n"
            "2. Needs improvement\n"
        )
        state_menu = classify_composer_prompt_candidate(menu_claude, "claude")
        self.assertTrue(state_menu.is_draft)

    # -------------------------------------------------------------------------
    # Test 8: Shell Prompt Tests
    # -------------------------------------------------------------------------
    def test_08_shell_composer(self):
        """Verify Shell prompt empty vs typed draft."""
        empty_shell = "alexey@host:~/git$ ls -la\ntotal 0\nalexey@host:~/git$ "
        state_empty = classify_composer_prompt_candidate(empty_shell, "shell")
        self.assertTrue(state_empty.is_empty)

        draft_shell = "alexey@host:~/git$ ls -la\ntotal 0\nalexey@host:~/git$ rm -rf /tmp/data"
        state_draft = classify_composer_prompt_candidate(draft_shell, "shell")
        self.assertTrue(state_draft.is_draft)
        self.assertEqual(state_draft.detail, "rm -rf /tmp/data")

    # -------------------------------------------------------------------------
    # Test 9: Dashboard Active Task Contradiction
    # -------------------------------------------------------------------------
    def test_09_dashboard_active_task_contradicted(self):
        """
        Verify that if dashboard screen shows active task execution,
        later PTY activity is correctly treated as contradicting idle.
        """
        busy_dashboard = (
            "============================= AGENT DASHBOARD =============================\n"
            " [Status: RUNNING]   Active Workers: 2   Queued: 1   Completed: 12         \n"
            " • Working (executing task T-103: runbook synthesis)                      \n"
            "---------------------------------------------------------------------------\n"
        )
        record = {
            "engine": "dashboard",
            "reported_state": "idle",
            "reported_state_at_ms": 10000,
            "last_activity_ms": 15000,
            "has_lifecycle_hooks": True,
        }
        contradicted = idle_was_contradicted_candidate(
            record, screen_text=busy_dashboard, at=10000, now=16000
        )
        self.assertTrue(
            contradicted,
            "When dashboard screen is actively executing, idle must be contradicted"
        )

        verdict = evaluate_readiness_verdict_candidate(
            PromptState.busy("running task"), record, 16000, screen_text=busy_dashboard
        )
        self.assertTrue(verdict.is_reject)

    # -------------------------------------------------------------------------
    # Test 10: Garbled / Unknown Screen Fails Closed
    # -------------------------------------------------------------------------
    def test_10_unknown_screen_fails_closed(self):
        """Unrecognized screen content with no recognizable prompt markers must fail closed."""
        garbled_screen = "=== UNKNOWN CORRUPTED STREAM ===\n0x00 0x88 0xFF random data\n"
        state_unknown = classify_composer_prompt_candidate(garbled_screen, "codex")
        self.assertTrue(state_unknown.is_unknown)

        verdict = evaluate_readiness_verdict_candidate(
            state_unknown, {"engine": "codex", "reported_state": "idle", "reported_state_at_ms": 1000}, 2000
        )
        self.assertTrue(verdict.is_reject)
        self.assertIn("prompt state is unknown", verdict.detail)

    # -------------------------------------------------------------------------
    # Test 11: Codex Scrollback Working + Real User Draft
    # -------------------------------------------------------------------------
    def test_11_codex_scrollback_working_plus_real_draft(self):
        """
        If scrollback has '• Working (...)', but the current composer has a typed
        draft '› make test', the draft MUST be detected and protected (not Busy, not Empty).
        """
        screen = (
            "• Working (10m 53s • esc to interrupt)\n"
            "  └ Tip: Use /export to save your conversation as Markdown.\n"
            "\n"
            "› make test\n"
            "\n"
            "  GPT-6.1-Sol medium · Context 14% left · ~/git/cloudflare-agent-git\n"
            "  ? for shortcuts"
        )
        state = classify_composer_prompt_candidate(screen, "codex")
        self.assertTrue(state.is_draft)
        self.assertEqual(state.detail, "make test")

    # -------------------------------------------------------------------------
    # Test 12: Multiple Warning and Quota Metrics in Codex Footer
    # -------------------------------------------------------------------------
    def test_12_codex_multiple_warnings_and_quota_metrics(self):
        """
        Verify that multiple status lines with warnings, f2 shortcuts, high context usage,
        and weekly limits are all correctly filtered as footers.
        """
        screen = (
            "› Ask Codex to do anything\n"
            "  GPT-6.1-Sol max · Context 95% used · ~/git/cloudflare-agent-git · weekly limit (5% left)\n"
            "  ? for shortcuts                                                   ⚠ 2 warnings · f2 to view"
        )
        state = classify_composer_prompt_candidate(screen, "codex")
        self.assertTrue(state.is_empty)

    # -------------------------------------------------------------------------
    # Test 13: Dashboard Read-Only Monitoring View (Without Shell Prompt)
    # -------------------------------------------------------------------------
    def test_13_dashboard_readonly_monitoring_view(self):
        """
        Dashboard TUIs often have no shell prompt (read-only monitoring view).
        Baseline rejected as Unknown('generic prompt marker not found').
        Candidate correctly recognizes resting dashboard view as Empty.
        """
        screen = (
            "============================= AGENT DASHBOARD =============================\n"
            " [Status: IDLE]   Active Workers: 0   Queued: 0   Completed: 24            \n"
            "---------------------------------------------------------------------------\n"
            " [Tab: Workers]  [Tab: Tasks]  [Tab: Metrics]                              \n"
        )
        # Baseline fails with unknown
        state_base = classify_composer_prompt_baseline(screen, "dashboard")
        self.assertTrue(state_base.is_unknown)

        # Candidate succeeds with empty
        state_cand = classify_composer_prompt_candidate(screen, "dashboard")
        self.assertTrue(state_cand.is_empty)

    # -------------------------------------------------------------------------
    # Test 14: Lifecycle Hooks Missing Fails Closed
    # -------------------------------------------------------------------------
    def test_14_missing_lifecycle_hooks_fails_closed(self):
        """
        Without lifecycle hooks, PTY activity after grace period cannot be
        verified safely, so it MUST fail closed (idle_was_contradicted == True)
        even for dashboard or antigravity engines.
        """
        record = {
            "engine": "dashboard",
            "reported_state": "idle",
            "reported_state_at_ms": 10000,
            "last_activity_ms": 15000,
            "has_lifecycle_hooks": False,  # Missing hooks!
        }
        contradicted = idle_was_contradicted_candidate(
            record, screen_text=None, at=10000, now=16000
        )
        self.assertTrue(
            contradicted,
            "Missing lifecycle hooks must fail closed on subsequent PTY activity"
        )

    # -------------------------------------------------------------------------
    # Tests 15-18: Codex Principal C1500 Negative Regression Tests
    # -------------------------------------------------------------------------
    def test_15_c1500_user_draft_mentioning_agents(self):
        """
        Codex C1500 negative test: User draft mentions the word 'agents'.
        Arbitrary substring filtering for 'agents' falsely stripped this as a footer.
        The geometrically anchored candidate MUST preserve this as an active Draft.
        """
        screen = (
            "› Ask Codex to do anything\n"
            "  please review agents before pushing\n"
            "  GPT-6.1-Sol medium · Context 14% left · weekly limit (78% left)\n"
            "  ? for shortcuts                                                   ⚠ 1 warning · f2 to view"
        )
        state = classify_composer_prompt_candidate(screen, "codex")
        self.assertTrue(state.is_draft, f"Expected Draft, got: {state}")
        self.assertEqual(state.detail, "please review agents before pushing")

    def test_16_c1500_user_draft_mentioning_context(self):
        """
        Codex C1500 negative test: User draft mentions 'Context: do not submit this draft'.
        Arbitrary substring filtering for 'Context' falsely stripped this as a footer.
        The geometrically anchored candidate MUST preserve this as an active Draft.
        """
        screen = (
            "› Ask Codex to do anything\n"
            "  Context: do not submit this draft\n"
            "  GPT-6.1-Sol medium · Context 14% left · weekly limit (78% left)\n"
            "  ? for shortcuts                                                   ⚠ 1 warning · f2 to view"
        )
        state = classify_composer_prompt_candidate(screen, "codex")
        self.assertTrue(state.is_draft, f"Expected Draft, got: {state}")
        self.assertEqual(state.detail, "Context: do not submit this draft")

    def test_17_c1500_user_draft_mentioning_repo_path(self):
        """
        Codex C1500 negative test: User draft mentions '~/git/agent-bus needs a fix'.
        Arbitrary substring filtering for '~/git/' falsely stripped this as a footer.
        The geometrically anchored candidate MUST preserve this as an active Draft.
        """
        screen = (
            "› Ask Codex to do anything\n"
            "  ~/git/agent-bus needs a fix\n"
            "  GPT-6.1-Sol medium · Context 14% left · weekly limit (78% left)\n"
            "  ? for shortcuts                                                   ⚠ 1 warning · f2 to view"
        )
        state = classify_composer_prompt_candidate(screen, "codex")
        self.assertTrue(state.is_draft, f"Expected Draft, got: {state}")
        self.assertEqual(state.detail, "~/git/agent-bus needs a fix")

    def test_18_c1500_scrollback_select_keyword_does_not_false_positive_empty_prompt(self):
        """
        Codex C1500 negative test: Historical scrollback contains 'Earlier report: Select approach 6'.
        A full-screen regex search for 'Select' falsely tripped the choice modal classifier
        and marked an empty composer as a draft!
        The candidate scopes dialogue checks to the active bottom dialogue, correctly
        classifying this as Empty.
        """
        screen = (
            "• Working (10m 53s • esc to interrupt)\n"
            "  Earlier report: Select approach 6 for the architecture\n"
            "  Please proceed with implementation\n"
            "  └ Tip: Use /export to save your conversation as Markdown.\n"
            "\n"
            "› Ask Codex to do anything\n"
            "\n"
            "  GPT-6.1-Sol medium · Context 14% left · ~/git/cloudflare-agent-git · Context 86% used · weekly limit (78% left)\n"
            "  ? for shortcuts                                                   ⚠ 1 warning · f2 to view"
        )
        state = classify_composer_prompt_candidate(screen, "codex")
        self.assertTrue(state.is_empty, f"Expected Empty, got: {state}")


if __name__ == "__main__":
    unittest.main()

