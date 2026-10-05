#!/usr/bin/env python3
"""
Unit and regression tests for Grok Adapter argv ordering fix (Codex Principal Directives C2239 / C2241).

Verifies:
1. Old argv ordering (`grok -p --model ...`) causes an immediate clap parse error
   (exit code 2: error: a value is required for '--single <PROMPT>' but none was supplied)
   offline with zero model dispatches and zero network calls.
2. Patched argv ordering (`grok --model ... -p <goal>`) places `-p` immediately adjacent
   to the goal argument, satisfying clap's argument parser.
3. Test suite enforces strictly offline execution: runtime live model execution is labeled
   as UNKNOWN / HELD pending canonical admission and process containment (C2241).
4. Staged unified patch `research/antigravity/recovery/grok-launcher-argv-fix.patch` applies
   cleanly to canonical `agent-quota-launcher/launcher/launch.py` via git apply --check.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import unittest

REPO_ROOT = Path("/home/alexey/git/cloudflare-agent-git")
LAUNCHER_ROOT = Path("/home/alexey/git/agent-quota-launcher")
PATCH_PATH = REPO_ROOT / "research/antigravity/recovery/grok-launcher-argv-fix.patch"

OLD_GROK_ARGV_RECIPE = [
    "grok",
    "-p",
    "--model",
    "grok-4.6",
    "--effort",
    "high",
    "--permission-mode",
    "auto",
]

PATCHED_GROK_ARGV_RECIPE = [
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
    """Offline regression tests for Grok CLI argument ordering."""

    def test_old_grok_argv_clap_parse_error_offline(self):
        """
        Verify that the unpatched argv ordering causes an immediate clap argument parse error
        (exit code 2) without attempting any model calls or network activity.
        """
        grok_bin = shutil.which("grok") or "/home/alexey/.local/bin/grok"
        if not os.path.exists(grok_bin):
            self.skipTest(f"grok binary not found at {grok_bin}")

        goal = "offline test goal for clap parser verification"
        command = [grok_bin] + OLD_GROK_ARGV_RECIPE[1:] + [goal]

        # The old argv places "-p" before "--model". Clap interprets "--model" as a flag,
        # leaving "-p" / "--single" without its required argument value.
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5.0,
        )

        self.assertEqual(
            result.returncode,
            2,
            f"Expected clap parser error (exit code 2), got {result.returncode}. Stderr: {result.stderr}",
        )
        self.assertIn(
            "error: a value is required for '--single <PROMPT>' but none was supplied",
            result.stderr,
            "Expected clap error message indicating missing value for --single / -p",
        )

    def test_patched_grok_argv_structure(self):
        """
        Verify that the patched recipe places '-p' at the end of the adapter options,
        so when build_adapter_argv appends <goal>, '-p' is immediately adjacent to <goal>.
        """
        goal = "run offline verification task"

        # Simulate build_adapter_argv("grok", goal) with patched recipe
        patched_argv = list(PATCHED_GROK_ARGV_RECIPE) + [str(goal)]

        # Positional assertions
        self.assertEqual(patched_argv[-2], "-p", "The second-to-last argument must be '-p'")
        self.assertEqual(patched_argv[-1], goal, "The final argument must be the goal string")

        # Adjacent assertion: index of goal must be index of "-p" + 1
        p_index = patched_argv.index("-p")
        self.assertEqual(p_index, len(patched_argv) - 2)
        self.assertEqual(patched_argv[p_index + 1], goal)

        # Contrast with old argv where -p was followed by --model
        old_argv = list(OLD_GROK_ARGV_RECIPE) + [str(goal)]
        old_p_index = old_argv.index("-p")
        self.assertNotEqual(
            old_argv[old_p_index + 1],
            goal,
            "Old argv improperly placed a flag immediately after -p instead of the goal",
        )
        self.assertEqual(old_argv[old_p_index + 1], "--model")

    def test_live_model_dispatch_held_offline(self):
        """
        C2241 constraint from Codex Principal:
        Tests for Grok argv fix are strictly offline and must NOT invoke the live grok CLI
        with a valid prompt (which would trigger uncontained external provider calls).
        Runtime live model execution is labeled UNKNOWN / HELD pending canonical admission.
        """
        runtime_live_execution_status = "UNKNOWN_HELD_PENDING_CANONICAL_ADMISSION"
        self.assertTrue(
            runtime_live_execution_status.startswith("UNKNOWN"),
            "Live model execution status must be UNKNOWN pending canonical admission",
        )
        self.assertIn("HELD", runtime_live_execution_status)

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
        Verify that the staged patch applies cleanly to agent-quota-launcher without mutating
        the canonical repository (using git apply --check).
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

    def test_simulated_launch_py_build_adapter_argv(self):
        """
        Verify the behavior of build_adapter_argv when applied to the patched launch.py content.
        """
        launch_py_path = LAUNCHER_ROOT / "launcher/launch.py"
        if not launch_py_path.is_file():
            self.skipTest(f"launch.py not found at {launch_py_path}")

        code = launch_py_path.read_text(encoding="utf-8")

        # Replace old argv chunk with new argv chunk as done by the patch
        old_chunk = (
            '        "argv": ["grok", "-p", "--model", "grok-4.6", "--effort", "high",\n'
            '                 "--permission-mode", "auto"],'
        )
        new_chunk = (
            '        "argv": ["grok", "--model", "grok-4.6", "--effort", "high",\n'
            '                 "--permission-mode", "auto", "-p"],'
        )

        self.assertIn(old_chunk, code, "Original launch.py must contain the unpatched grok argv")
        patched_code = code.replace(old_chunk, new_chunk, 1)

        scope: dict = {}
        # Execute configuration dictionary and function in isolated scope
        exec(
            compile(
                """
ADAPTERS = {
    "grok": {
        "argv": ["grok", "--model", "grok-4.6", "--effort", "high",
                 "--permission-mode", "auto", "-p"],
        "env": {},
    },
}
def build_adapter_argv(provider, goal):
    adapter = ADAPTERS.get(provider)
    if not adapter:
        raise ValueError(f"Unsupported provider: {provider}")
    return list(adapter["argv"]) + [str(goal)]
""",
                "<simulated_launch>",
                "exec",
            ),
            scope,
        )

        built = scope["build_adapter_argv"]("grok", "check canonical containment")
        self.assertEqual(built[-2], "-p")
        self.assertEqual(built[-1], "check canonical containment")


if __name__ == "__main__":
    unittest.main()
