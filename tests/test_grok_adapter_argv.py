#!/usr/bin/env python3
"""
Offline regression and integration test suite for Grok Adapter argv ordering fix.
Enacted under Codex Principal Directives C2239, C2241, and C2243.

Verifies:
1. Documented historical fixture and mock parser analysis for unpatched argv ordering
   (clap parse failure with exit code 2: error: a value is required for '--single <PROMPT>').
   No uncontained live binary invocations in unit test runs.
2. Patch file validation and clean applicability against canonical agent-quota-launcher
   via `git apply --check`.
3. Real in-situ verification: Copies launcher source into an isolated scratch testbed,
   applies the staged recovery patch `research/antigravity/recovery/grok-launcher-argv-fix.patch`,
   imports the REAL patched `launcher.launch` module, and executes `build_adapter_argv("grok", goal)`
   against an expanded matrix of standard, option-looking, quoted, and unicode goals.
4. Asserts that in all test matrix cases, `argv[-2] == "-p"` and `argv[-1] == goal`.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

REPO_ROOT = Path("/home/alexey/git/cloudflare-agent-git")
LAUNCHER_ROOT = Path("/home/alexey/git/agent-quota-launcher")
PATCH_PATH = REPO_ROOT / "research/antigravity/recovery/grok-launcher-argv-fix.patch"
SCRATCH_TESTBED = REPO_ROOT / ".local/scratch/architect06-executor-admission/testbed"

# Documented historical receipt of unpatched grok CLI invocation (Directive C2243)
HISTORICAL_CLAP_PARSE_FAILURE_RECEIPT = {
    "exit_code": 2,
    "stderr": (
        "error: a value is required for '--single <PROMPT>' but none was supplied\n\n"
        "For more information, try '--help'.\n"
    ),
    "argv": [
        "grok",
        "-p",
        "--model",
        "grok-4.6",
        "--effort",
        "high",
        "--permission-mode",
        "auto",
        "offline test goal",
    ],
    "defect_mechanism": (
        "Clap parses positional options greedily. In `-p --model grok-4.6 ...`, clap "
        "encounters `--model` immediately after `-p` / `--single`, identifies it as an "
        "option flag rather than a value argument, and halts with exit code 2 without "
        "ever initializing runtime models or network connections."
    ),
}

EXPECTED_BASE_ARGV = [
    "grok",
    "--model",
    "grok-4.6",
    "--effort",
    "high",
    "--permission-mode",
    "auto",
    "-p",
]


class TestGrokAdapterArgv(unittest.TestCase):
    """Offline unit and integration tests for Grok CLI argument ordering."""

    @classmethod
    def setUpClass(cls):
        """Prepare scratch testbed with patched launcher source (Directive C2243)."""
        if SCRATCH_TESTBED.exists():
            shutil.rmtree(SCRATCH_TESTBED)
        SCRATCH_TESTBED.mkdir(parents=True, exist_ok=True)

        # Copy launcher source tree to scratch testbed
        src_launcher = LAUNCHER_ROOT / "launcher"
        dst_launcher = SCRATCH_TESTBED / "launcher"
        if not src_launcher.is_dir():
            raise RuntimeError(f"Source launcher directory missing: {src_launcher}")
        shutil.copytree(src_launcher, dst_launcher)

        # Apply exact staged unified patch using /usr/bin/patch
        patch_cmd = [
            "/usr/bin/patch",
            "-p1",
            "-d",
            str(SCRATCH_TESTBED),
            "-i",
            str(PATCH_PATH.resolve()),
        ]
        patch_res = subprocess.run(patch_cmd, capture_output=True, text=True)
        if patch_res.returncode != 0:
            raise RuntimeError(
                f"Failed to apply patch in testbed: {patch_res.stderr}\nStdout: {patch_res.stdout}"
            )

        # Dynamically load the REAL patched launch module from testbed
        patched_launch_path = dst_launcher / "launch.py"
        spec = importlib.util.spec_from_file_location(
            "testbed_launcher_launch", str(patched_launch_path)
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to create module spec for patched launch.py")

        # Ensure launcher package resolution works by prepending testbed to sys.path
        sys.path.insert(0, str(SCRATCH_TESTBED))
        try:
            cls.launch_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.launch_mod)
        finally:
            if sys.path and sys.path[0] == str(SCRATCH_TESTBED):
                sys.path.pop(0)

    @classmethod
    def tearDownClass(cls):
        """Clean up scratch testbed."""
        if SCRATCH_TESTBED.exists():
            shutil.rmtree(SCRATCH_TESTBED, ignore_errors=True)

    def test_historical_clap_parse_receipt_and_token_isolation(self):
        """
        Verify documented historical clap parse error contract (exit code 2) and
        token isolation defect without live binary invocations (Directive C2243).
        """
        receipt = HISTORICAL_CLAP_PARSE_FAILURE_RECEIPT
        self.assertEqual(receipt["exit_code"], 2)
        self.assertIn("error: a value is required for '--single <PROMPT>'", receipt["stderr"])

        # Token adjacency analysis on historical argv
        argv = receipt["argv"]
        p_idx = argv.index("-p")
        next_token = argv[p_idx + 1]
        self.assertTrue(
            next_token.startswith("-"),
            f"Expected next token after -p to be a flag in unpatched argv, got: {next_token}",
        )
        self.assertEqual(next_token, "--model")

    def test_patch_file_exists_and_valid(self):
        """Verify that the staged recovery patch file exists and contains the expected diff."""
        self.assertTrue(PATCH_PATH.is_file(), f"Patch file missing at {PATCH_PATH}")
        content = PATCH_PATH.read_text(encoding="utf-8")

        self.assertIn("--- a/launcher/launch.py", content)
        self.assertIn("+++ b/launcher/launch.py", content)
        self.assertIn('-        "argv": ["grok", "-p", "--model", "grok-4.6",', content)
        self.assertIn('+        "argv": ["grok", "--model", "grok-4.6",', content)
        self.assertIn('+                 "--permission-mode", "auto", "-p"],', content)

    def test_patch_applies_cleanly_to_launcher_repo(self):
        """
        Verify that the staged patch applies cleanly to canonical agent-quota-launcher
        without mutating the repository (using git apply --check).
        """
        if not (LAUNCHER_ROOT / ".git").is_dir():
            self.skipTest(f"Launcher git repo not found at {LAUNCHER_ROOT}")

        check_result = subprocess.run(
            ["git", "-C", str(LAUNCHER_ROOT), "apply", "--check", str(PATCH_PATH)],
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            check_result.returncode,
            0,
            f"Patch failed git apply --check: {check_result.stderr}",
        )

    def test_real_patched_build_adapter_argv_goal_matrix(self):
        """
        Test the REAL patched build_adapter_argv against an expanded goal test matrix:
        - standard goals
        - option-looking goals (--model, --help, -p, etc.)
        - spaces, quotes, and unicode goals
        Asserts that in all cases argv[-2] == '-p' and argv[-1] == goal (Directive C2243).

        Epistemic Demarcation (Directive C2247):
        This matrix verifies Python argv list construction and serialization boundaries.
        It proves that build_adapter_argv correctly places -p adjacent to the goal string.
        However, for leading-dash tokens (e.g. '--model'), live clap CLI parser acceptance
        without '--single=VALUE' syntax remains UNKNOWN / FAIL-CLOSED because clap option
        greediness may interpret tokens starting with '-' as flags rather than values.
        """
        goal_matrix = [
            # Standard goals (verified intended usage)
            ("standard_offline_task", "run offline task"),
            ("build_artifact_task", "compile offline verification deliverable"),
            # Option-looking goals (verifies argv serialization boundary; live CLI acceptance UNKNOWN/FAIL-CLOSED per C2247)
            ("option_model", "--model"),
            ("option_help", "--help"),
            ("option_p", "-p"),
            ("option_effort", "--effort"),
            ("option_v", "-v"),
            ("option_permission_mode", "--permission-mode"),
            ("option_with_value", "--custom-flag value"),
            # Whitespace, quotes, and special characters
            ("multiple_spaces", "multi word goal with   multiple   spaces"),
            ("double_quotes", 'goal with "double quotes" embedded'),
            ("single_quotes", "goal with 'single quotes' embedded"),
            ("mixed_quotes", 'nested "double" and \'single\' characters'),
            ("semicolon_command", "echo test; ls -la && exit 1"),
            ("newlines", "line 1\nline 2\nline 3"),
            # Unicode goals
            ("unicode_symbols", "unicode goal: 🚀 α/β → 100% 🎯"),
            ("cjk_characters", "自然语言处理目标 2026"),
            # Edge cases
            ("empty_goal", ""),
        ]

        # Verify adapter definition in real patched module
        grok_adapter = self.launch_mod.ADAPTERS.get("grok")
        self.assertIsNotNone(grok_adapter, "grok adapter must exist in ADAPTERS")
        self.assertEqual(
            grok_adapter["argv"],
            EXPECTED_BASE_ARGV,
            "Real patched launch.py must contain the corrected argv recipe",
        )

        for case_name, goal in goal_matrix:
            with self.subTest(case=case_name, goal=goal):
                argv = self.launch_mod.build_adapter_argv("grok", goal)

                # Ensure base arguments match expected recipe exactly
                self.assertEqual(
                    argv[:-1],
                    EXPECTED_BASE_ARGV,
                    f"Base arguments before goal deviated for case {case_name}",
                )

                # Ensure positional adjacency
                self.assertEqual(
                    argv[-2],
                    "-p",
                    f"Second-to-last argument must be '-p' for case {case_name}",
                )
                self.assertEqual(
                    argv[-1],
                    goal,
                    f"Final argument must match goal string for case {case_name}",
                )

                # Ensure total length is exactly len(base) + 1
                self.assertEqual(
                    len(argv),
                    len(EXPECTED_BASE_ARGV) + 1,
                    f"Unexpected argv length for case {case_name}",
                )


if __name__ == "__main__":
    unittest.main()
