#!/usr/bin/env python3
"""
test_hardened_runner_guards.py

Targeted Adversarial Negative Test Suite for Hardened FileBus Model Review Runner
(Codex Directives C2387 and C2392).

Verifies fail-closed behavior against mutants:
1. Unsteered Prompt: Verify absence of signposted outcomes ("VERDICT: ACCEPT").
2. Fail-Closed Verdict Extraction:
   - Mutant 2A: Missing verdict -> ValueError.
   - Mutant 2B: Invalid/unrecognized verdict -> ValueError.
   - Mutant 2C: Conflicting text verdicts -> ValueError.
   - Mutant 2D: Conflicting data vs text verdicts -> ValueError.
3. Exact Reply Correlation:
   - Mutant 3A: Mismatched reply_to -> ValueError.
   - Mutant 3B: Mismatched sender_id -> ValueError.
   - Mutant 3C: Substring trap in stdout/body -> ValueError.
4. Cryptographic Digest Verification:
   - Mutant 4A: Missing ARTIFACT_SHA256 -> ValueError.
   - Mutant 4B: Invalid hex format -> ValueError.
   - Mutant 4C: Hash mismatch against actual disk content -> ValueError.
   - Mutant 4D: Missing or empty deliverable -> ValueError.
5. Per-Run Exclusivity: Duplicate run_id collision deny -> RuntimeError.
6. Append-Only Ledger: Durability and append preservation in trial_receipts.jsonl.
7. Loaded Source Manifest: Verified SHA256 of loaded bus_cli.py and bus.py.
8. Accurate Terminology: Explicit symmetric_token_auth_per_identity verification.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

WORKSPACE = Path("/home/alexey/git/cloudflare-agent-git").resolve()
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

TOOLING_DIR = (WORKSPACE / "research" / "antigravity" / "tooling" / "self_org").resolve()
if str(TOOLING_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLING_DIR))

SCRATCH_DIR = WORKSPACE / ".local" / "scratch"
if str(SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(SCRATCH_DIR))

from run_hardened_filebus_model_review import (
    ALLOWED_VERDICTS,
    BUS_CLI,
    append_receipt_to_ledger,
    build_loaded_source_manifest,
    build_unsteered_worker_prompt,
    compute_sha256,
    correlate_reply,
    extract_artifact_sha256,
    init_run_environment,
    parse_verdict,
    run_hardened_filebus_review,
    verify_cryptographic_digest,
)


class TestHardenedRunnerGuards(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp(prefix="hardened_guard_test_", dir=str(SCRATCH_DIR))).resolve()
        self.tmp_dir = self.test_dir / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    # -----------------------------------------------------------------------
    # Invariant 1: Unsteered Prompt
    # -----------------------------------------------------------------------
    def test_unsteered_prompt_invariants(self) -> None:
        """Proves prompt does not hardcode or signpost any outcome."""
        prompt = build_unsteered_worker_prompt(
            bus_cli_path=Path("/fake/bus_cli.py"),
            bus_store_path=Path("/fake/store"),
            reviewer_cred_path=Path("/fake/reviewer_cred.json"),
            task_msg_id="task-msg-1234",
            target_patch_path=Path("/fake/patch.diff"),
            expected_patch_sha="abcd" * 16,
            target_commit="249d086a007ee3d5d0381334a27d56771b959d11",
            deliverable_path=Path("/fake/report.md"),
            scratch_testbed_path=Path("/fake/testbed"),
        )

        # Invariant 1: Strictly no hardcoded "VERDICT: ACCEPT"
        self.assertNotIn("VERDICT: ACCEPT", prompt)
        self.assertNotIn("VERDICT: ACCEPTED", prompt)
        self.assertNotIn("VERDICT: REJECT", prompt)
        self.assertNotIn("VERDICT: BOUNDED ACCEPTANCE", prompt)

        # Must instruct model to determine verdict independently
        self.assertIn("STRICTLY INDEPENDENTLY", prompt)
        self.assertIn("Allowed verdicts: ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT", prompt)
        self.assertIn("VERDICT: <YOUR_INDEPENDENT_VERDICT>", prompt)

    # -----------------------------------------------------------------------
    # Invariant 2: Fail-Closed Verdict Extraction
    # -----------------------------------------------------------------------
    def test_fail_closed_verdict_extraction_mutants(self) -> None:
        """Proves parser NEVER defaults missing/unparseable verdict to ACCEPT."""
        # Mutant 2A: Missing verdict
        missing_text = "The review was conducted. Unit tests ran. Patch was inspected."
        with self.assertRaises(ValueError) as ctx:
            parse_verdict(missing_text)
        self.assertIn("No valid independent verdict found", str(ctx.exception))

        # Mutant 2B: Unrecognized verdict
        invalid_verdicts = [
            "VERDICT: LOOKS_GOOD_TO_ME",
            "VERDICT: PASS",
            "VERDICT: APPROVED",
            "VERDICT: LGTM",
            "VERDICT: SUCCESS",
        ]
        for iv in invalid_verdicts:
            with self.assertRaises(ValueError) as ctx:
                parse_verdict(f"Review notes here.\n{iv}\nDone.")
            self.assertIn("No valid independent verdict found", str(ctx.exception))

        # Mutant 2C: Conflicting text verdicts
        conflict_text = "Earlier section: VERDICT: ACCEPT\nLater section: VERDICT: REJECT"
        with self.assertRaises(ValueError) as ctx:
            parse_verdict(conflict_text)
        self.assertIn("Conflicting verdicts found", str(ctx.exception))

        # Mutant 2D: Conflicting data vs text verdicts
        with self.assertRaises(ValueError) as ctx:
            parse_verdict("VERDICT: ACCEPT", data_dict={"verdict": "REQUEST_CHANGES"})
        self.assertIn("Contradictory verdicts across sources", str(ctx.exception))

        # Positive 2E: Valid verdicts parsed correctly
        for valid_v in ALLOWED_VERDICTS:
            parsed = parse_verdict(f"Summary...\nVERDICT: {valid_v}\nSignoff.")
            self.assertEqual(parsed, valid_v)

    # -----------------------------------------------------------------------
    # Invariant 3: Exact Reply Correlation
    # -----------------------------------------------------------------------
    def test_exact_reply_correlation_mutants(self) -> None:
        """Proves correlation requires exact match on reply_to AND sender_id."""
        task_id = "task-c2387-001"
        reviewer_id = "reviewer-uuid-1111"

        # Mutant 3A: Mismatched reply_to
        mutant_3a = [
            {"message_id": "msg-1", "reply_to": "wrong-task-id", "sender_id": reviewer_id, "body": "done"}
        ]
        with self.assertRaises(ValueError) as ctx:
            correlate_reply(mutant_3a, task_id, reviewer_id)
        self.assertIn("No reply found correlating to task_msg_id", str(ctx.exception))

        # Mutant 3B: Mismatched sender_id
        mutant_3b = [
            {"message_id": "msg-2", "reply_to": task_id, "sender_id": "imposter-uuid-9999", "body": "done"}
        ]
        with self.assertRaises(ValueError) as ctx:
            correlate_reply(mutant_3b, task_id, reviewer_id)
        self.assertIn("No reply found correlating to task_msg_id", str(ctx.exception))

        # Mutant 3C: Substring trap in body (reply_to is wrong, but body mentions task_id)
        mutant_3c = [
            {
                "message_id": "msg-3",
                "reply_to": "other-task",
                "sender_id": reviewer_id,
                "body": f"In reference to {task_id}, review complete.",
            }
        ]
        with self.assertRaises(ValueError) as ctx:
            correlate_reply(mutant_3c, task_id, reviewer_id)
        self.assertIn("No reply found correlating to task_msg_id", str(ctx.exception))

        # Mutant 3D: Empty inbox
        with self.assertRaises(ValueError) as ctx:
            correlate_reply([], task_id, reviewer_id)
        self.assertIn("Inbox is empty", str(ctx.exception))

        # Positive 3E: Exact correlation
        valid_messages = [
            {"message_id": "noise-1", "reply_to": "other", "sender_id": "other", "body": "noise"},
            {"message_id": "reply-correct", "reply_to": task_id, "sender_id": reviewer_id, "body": "valid"},
        ]
        matched = correlate_reply(valid_messages, task_id, reviewer_id)
        self.assertEqual(matched["message_id"], "reply-correct")

    # -----------------------------------------------------------------------
    # Invariant 4: Cryptographic Digest Verification
    # -----------------------------------------------------------------------
    def test_cryptographic_digest_verification_mutants(self) -> None:
        """Proves extraction and strict digest comparison fail closed on mutants."""
        # Deliverable setup
        deliv_path = self.test_dir / "deliverable.md"
        deliv_content = b"# Valid Review Report Content\nVerdict: ACCEPT\n"
        deliv_path.write_bytes(deliv_content)
        actual_sha = hashlib.sha256(deliv_content).hexdigest()

        # Mutant 4A: Missing ARTIFACT_SHA256 in reply
        reply_no_sha = {"body": "VERDICT: ACCEPT\nNOTES: All tests pass."}
        with self.assertRaises(ValueError) as ctx:
            extract_artifact_sha256(reply_no_sha)
        self.assertIn("Missing or invalid 64-character hex ARTIFACT_SHA256", str(ctx.exception))

        # Mutant 4B: Invalid hex format (truncated or illegal chars)
        reply_bad_hex = {"body": "VERDICT: ACCEPT\nARTIFACT_SHA256: 1234nothex5678"}
        with self.assertRaises(ValueError) as ctx:
            extract_artifact_sha256(reply_bad_hex)
        self.assertIn("Missing or invalid 64-character hex ARTIFACT_SHA256", str(ctx.exception))

        # Mutant 4C: Hash mismatch against actual disk content
        wrong_sha = "0" * 64
        with self.assertRaises(ValueError) as ctx:
            verify_cryptographic_digest(deliv_path, wrong_sha)
        self.assertIn("Cryptographic digest mismatch", str(ctx.exception))

        # Mutant 4D: File missing
        missing_file = self.test_dir / "missing.md"
        with self.assertRaises(ValueError) as ctx:
            verify_cryptographic_digest(missing_file, actual_sha)
        self.assertIn("Deliverable file does not exist", str(ctx.exception))

        # Mutant 4E: Empty file (0 bytes)
        empty_file = self.test_dir / "empty.md"
        empty_file.touch()
        with self.assertRaises(ValueError) as ctx:
            verify_cryptographic_digest(empty_file, actual_sha)
        self.assertIn("Deliverable file is empty", str(ctx.exception))

        # Positive 4F: Matching digest from body
        reply_valid_body = {"body": f"VERDICT: ACCEPT\nARTIFACT_SHA256: {actual_sha}\n"}
        extracted = extract_artifact_sha256(reply_valid_body)
        self.assertEqual(extracted, actual_sha)
        verified = verify_cryptographic_digest(deliv_path, extracted)
        self.assertEqual(verified, actual_sha)

        # Positive 4G: Matching digest from structured data
        reply_valid_data = {
            "body": "Done",
            "data": {"artifact_sha256": actual_sha},
        }
        extracted_data = extract_artifact_sha256(reply_valid_data)
        self.assertEqual(extracted_data, actual_sha)

    # -----------------------------------------------------------------------
    # Invariant 5: Per-Run Exclusivity & Append-Only Ledger
    # -----------------------------------------------------------------------
    def test_per_run_exclusivity_collision_deny(self) -> None:
        """Proves collision denial on duplicate run_id."""
        run_id = "test-run-unique-001"
        env1 = init_run_environment(self.test_dir / "scratch", self.tmp_dir, run_id)
        self.assertTrue(env1["run_dir"].exists())

        # Duplicate run_id must raise RuntimeError (collision deny)
        with self.assertRaises(RuntimeError) as ctx:
            init_run_environment(self.test_dir / "scratch", self.tmp_dir, run_id)
        self.assertIn("Exclusive create collision deny", str(ctx.exception))

    def test_append_only_ledger(self) -> None:
        """Proves receipts are durably appended to trial_receipts.jsonl."""
        ledger_file = self.test_dir / "trial_receipts.jsonl"
        receipt1 = {"run_id": "run-1", "verdict": "ACCEPT", "sha256": "aaaa" * 16}
        receipt2 = {"run_id": "run-2", "verdict": "REQUEST_CHANGES", "sha256": "bbbb" * 16}

        append_receipt_to_ledger(ledger_file, receipt1)
        append_receipt_to_ledger(ledger_file, receipt2)

        lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        parsed1 = json.loads(lines[0])
        parsed2 = json.loads(lines[1])
        self.assertEqual(parsed1["run_id"], "run-1")
        self.assertEqual(parsed2["run_id"], "run-2")

        # Verify permissions (mode 0600)
        self.assertEqual(ledger_file.stat().st_mode & 0o777, 0o600)

    # -----------------------------------------------------------------------
    # Invariant 6: Loaded Source Manifest
    # -----------------------------------------------------------------------
    def test_loaded_source_manifest(self) -> None:
        """Proves source manifest computes SHA256 of loaded bus_cli and bus.py."""
        manifest = build_loaded_source_manifest()
        self.assertIn("bus_cli", manifest)
        self.assertIn("bus_py", manifest)
        self.assertEqual(len(manifest["bus_cli"]["sha256"]), 64)
        self.assertEqual(len(manifest["bus_py"]["sha256"]), 64)

    # -----------------------------------------------------------------------
    # Invariant 7: Accurate Terminology
    # -----------------------------------------------------------------------
    def test_accurate_terminology_invariant(self) -> None:
        """Proves runner code and receipts do not claim asymmetric signatures."""
        runner_file = (TOOLING_DIR / "run_hardened_filebus_model_review.py") if (TOOLING_DIR / "run_hardened_filebus_model_review.py").exists() else (SCRATCH_DIR / "run_hardened_filebus_model_review.py")
        runner_source = runner_file.read_text(encoding="utf-8")
        # Ensure symmetric token auth is explicitly stated
        self.assertIn("symmetric_token_auth_per_identity", runner_source)
        # Ensure no claims of 'signed reply' or 'asymmetric signature'
        self.assertNotIn("signed reply", runner_source.lower())
        self.assertNotIn("asymmetric signature", runner_source.lower())
    # -----------------------------------------------------------------------
    # Directive C2396: Defect 1 - Reply Body vs Deliverable Verdict Mismatch
    # -----------------------------------------------------------------------
    def test_reply_body_vs_deliverable_verdict_mismatch_fails_closed(self) -> None:
        """
        Codex Directive C2396 (Defect 1):
        Verifies that when deliv_text has one verdict (e.g. ACCEPT) and reply_body
        has a conflicting verdict (e.g. REJECT) with data_dict=None, parse_verdict
        strictly fails closed by raising ValueError.
        """
        deliv_text = "# Technical Review Report\nVerdict: ACCEPT\nAll tests passed.\n"
        reply_body = "VERDICT: REJECT\nARTIFACT_SHA256: " + ("0" * 64) + "\nNOTES: Tests failed."

        # Must fail closed with ValueError when deliverable and reply_body contradict
        with self.assertRaises(ValueError) as ctx:
            parse_verdict(deliv_text=deliv_text, reply_body=reply_body, data_dict=None)
        self.assertIn("Contradictory verdicts across sources", str(ctx.exception))
        self.assertIn("deliverable='ACCEPT'", str(ctx.exception))
        self.assertIn("reply_body='REJECT'", str(ctx.exception))

        # When deliverable and reply_body agree, it succeeds
        agree_body = "VERDICT: ACCEPT\nARTIFACT_SHA256: " + ("0" * 64)
        verdict = parse_verdict(deliv_text=deliv_text, reply_body=agree_body, data_dict=None)
        self.assertEqual(verdict, "ACCEPT")

        # When structured data_dict contradicts deliverable or reply_body, strictly fail closed
        with self.assertRaises(ValueError) as ctx:
            parse_verdict(deliv_text=deliv_text, reply_body=agree_body, data_dict={"verdict": "REQUEST_CHANGES"})
        self.assertIn("Contradictory verdicts across sources", str(ctx.exception))

    # -----------------------------------------------------------------------
    # Directive C2396: Defect 2 - Multiple Conflicting Replies Fencing
    # -----------------------------------------------------------------------
    def test_multiple_conflicting_replies_fails_closed(self) -> None:
        """
        Codex Directive C2396 (Defect 2):
        Verifies that when multiple replies exist for the same task_msg_id and reviewer,
        if their verdicts, artifact hashes, or payloads conflict, correlate_reply
        strictly fails closed by raising ValueError.
        """
        task_id = "task-c2396-001"
        reviewer_id = "reviewer-uuid-1111"

        # Case 1: Conflicting verdicts in multiple replies
        conflicting_replies_verdict = [
            {
                "message_id": "reply-1",
                "reply_to": task_id,
                "sender_id": reviewer_id,
                "body": "VERDICT: ACCEPT\nARTIFACT_SHA256: " + ("a" * 64),
            },
            {
                "message_id": "reply-2",
                "reply_to": task_id,
                "sender_id": reviewer_id,
                "body": "VERDICT: REJECT\nARTIFACT_SHA256: " + ("a" * 64),
            },
        ]
        with self.assertRaises(ValueError) as ctx:
            correlate_reply(conflicting_replies_verdict, task_id, reviewer_id)
        self.assertIn("Multiple conflicting replies detected", str(ctx.exception))

        # Case 2: Conflicting artifact hashes in multiple replies
        conflicting_replies_sha = [
            {
                "message_id": "reply-3",
                "reply_to": task_id,
                "sender_id": reviewer_id,
                "body": "VERDICT: ACCEPT\nARTIFACT_SHA256: " + ("a" * 64),
            },
            {
                "message_id": "reply-4",
                "reply_to": task_id,
                "sender_id": reviewer_id,
                "body": "VERDICT: ACCEPT\nARTIFACT_SHA256: " + ("b" * 64),
            },
        ]
        with self.assertRaises(ValueError) as ctx:
            correlate_reply(conflicting_replies_sha, task_id, reviewer_id)
        self.assertIn("Multiple conflicting replies detected", str(ctx.exception))

        # Case 3: Identical idempotent duplicate replies succeed
        identical_replies = [
            {
                "message_id": "reply-5",
                "reply_to": task_id,
                "sender_id": reviewer_id,
                "body": "VERDICT: ACCEPT\nARTIFACT_SHA256: " + ("a" * 64),
                "data": None,
            },
            {
                "message_id": "reply-5",
                "reply_to": task_id,
                "sender_id": reviewer_id,
                "body": "VERDICT: ACCEPT\nARTIFACT_SHA256: " + ("a" * 64),
                "data": None,
            },
        ]
        matched = correlate_reply(identical_replies, task_id, reviewer_id)
        self.assertEqual(matched["message_id"], "reply-5")

    # -----------------------------------------------------------------------
    # Directive C2396: Defect 3 - Real Head ACK in Main
    # -----------------------------------------------------------------------
    def test_head_ack_emitted_on_completion(self) -> None:
        """
        Codex Directive C2396 (Defect 3):
        Verifies that run_hardened_filebus_review emits a real FileBus ACK
        for the worker's reply and records head_ack in the execution receipt.
        """
        scratch_root = self.test_dir / "scratch_head_ack"
        tmp_root = self.test_dir / "tmp_head_ack"
        deliv_path = self.test_dir / "test_deliv.md"
        deliv_path.write_text("# Review Report\nVerdict: ACCEPT\n", encoding="utf-8")

        receipt = run_hardened_filebus_review(
            scratch_root=scratch_root,
            tmp_root=tmp_root,
            deliverable_path=deliv_path,
            dry_run=True,
        )

        # 1. Receipt records head_ack
        self.assertIn("head_ack", receipt)
        head_ack = receipt["head_ack"]
        self.assertTrue(head_ack.get("acked"))
        self.assertEqual(head_ack.get("reply_msg_id"), receipt["reply_message_id"])

        # 2. Check FileBus store to confirm the reply message was acknowledged
        bus_store = scratch_root / f"run_{receipt['run_id']}" / "bus_store"
        dispatcher_cred = scratch_root / f"run_{receipt['run_id']}" / "creds" / "dispatcher_cred.json"

        # Query the message via bus_cli.py show
        res = subprocess.run(
            [
                sys.executable,
                str(BUS_CLI),
                "--store",
                str(bus_store),
                "show",
                "--cred",
                str(dispatcher_cred),
                "--message-id",
                receipt["reply_message_id"],
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        msg_obj = json.loads(res.stdout)
        self.assertIsNotNone(msg_obj.get("acked_at"), "Reply message was not marked acked in FileBus store")


if __name__ == "__main__":
    unittest.main()
