#!/usr/bin/env python3
"""Unit and integration test suite for sessionless model-worker-01 FileBus enrollment.

Validates:
1. Sessionless enrollment: session_id is None, rendered with '-' in namespaced ID.
2. Mode 0600 credential file security.
3. Zero inherited head or aplexer tokens.
4. Handshake message dispatch, inbox polling, and read ACK on FileBus store.
5. Verification receipt format and publication guard cleanliness.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AGENT_BUS_ROOT = Path("/home/alexey/git/agent-bus")
if AGENT_BUS_ROOT.is_dir() and str(AGENT_BUS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_BUS_ROOT))

from research.antigravity.recovery.run_sessionless_model_enrollment import (
    RECEIPT_FILE,
    run_sessionless_model_enrollment,
)


def test_sessionless_model_enrollment_lifecycle(tmp_path: Path) -> None:
    """Verifies end-to-end enrollment, handshake, polling/ACK, and receipt generation in isolated store."""
    isolated_store = tmp_path / "bus_store"
    isolated_receipt = tmp_path / "RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01.json"
    scratch_root = tmp_path / "scratch"

    receipt = run_sessionless_model_enrollment(
        store_path=isolated_store,
        head_cred_path=tmp_path / "nonexistent_head.json",
        receipt_output_path=isolated_receipt,
        scratch_root=scratch_root,
    )

    assert receipt["status"] == "PASS"
    assert receipt["all_checks_passed"] is True
    assert receipt["total_checks"] >= 10

    # 1. Verify worker identity and sessionless invariant
    worker_info = receipt["worker_enrollment"]
    assert worker_info["agent_name"] == "model-worker-01"
    assert worker_info["session_id"] is None
    assert "/-/" in worker_info["rendered_namespaced_id"]

    # 2. Verify credential file mode 0600
    cred_file = Path(worker_info["credential_file"])
    assert cred_file.is_file()
    assert stat.S_IMODE(cred_file.stat().st_mode) == 0o600

    # 3. Verify zero token inheritance
    token_proof = receipt["zero_token_inheritance_proof"]
    assert token_proof["tokens_are_distinct"] is True
    assert token_proof["ambient_aplexer_session_ignored"] is True
    assert token_proof["head_cred_inheritance_guard_verified"] is True
    assert token_proof["worker_token_sha256"] != token_proof["head_token_sha256"]

    # 4. Verify handshake message exchange and ACK
    exchange = receipt["message_exchange"]
    assert exchange["handshake_delivered_at"] is not None
    assert exchange["handshake_acked_at"] is not None
    assert exchange["reply_delivered_at"] is not None
    assert exchange["reply_to"] == exchange["handshake_message_id"]

    # 5. Verify publication guard passes cleanly on receipt
    guard_script = REPO_ROOT / "research" / "antigravity" / "tooling" / "publication_guard.py"
    proc = subprocess.run(
        [sys.executable, str(guard_script), str(isolated_receipt)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Publication guard failed:\n{proc.stdout}\n{proc.stderr}"


def test_production_receipt_file_exists_and_verified() -> None:
    """Verifies that the canonical receipt file exists at research/antigravity/recovery/RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01.json."""
    assert RECEIPT_FILE.is_file(), f"Expected receipt file at {RECEIPT_FILE}"
    data = json.loads(RECEIPT_FILE.read_text(encoding="utf-8"))

    assert data.get("status") == "PASS"
    assert data.get("all_checks_passed") is True
    assert data["worker_enrollment"]["session_id"] is None
    assert data["worker_enrollment"]["agent_name"] == "model-worker-01"
    assert data["worker_enrollment"]["credential_mode"] == "0o600"
    assert data["zero_token_inheritance_proof"]["tokens_are_distinct"] is True

    # Publication guard check
    guard_script = REPO_ROOT / "research" / "antigravity" / "tooling" / "publication_guard.py"
    proc = subprocess.run(
        [sys.executable, str(guard_script), str(RECEIPT_FILE)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
