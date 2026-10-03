#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
import tempfile

DETECTOR_PATH = Path(__file__).parent / "contract_drift_detector.py"


def test_positive_drift():
    """Producer migrates to timestamp_us, consumer reads timestamp -> MUST DETECT DRIFT (exit code 1)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        prod = tmp / "producer.py"
        cons = tmp / "consumer.py"

        prod.write_text("""
def emit_telemetry(msg_id, val):
    return {
        "id": msg_id,
        "val": val,
        "timestamp_us": 1727930000000000,
    }
""")

        cons.write_text("""
def handle_event(record):
    event_id = record["id"]
    t = record["timestamp"]
    return (event_id, t)
""")

        proc = subprocess.run([
            sys.executable, str(DETECTOR_PATH),
            "--producers", str(prod),
            "--consumers", str(cons),
            "--json"
        ], capture_output=True, text=True)

        assert proc.returncode == 1, f"Expected returncode 1, got {proc.returncode}"
        report = json.loads(proc.stdout)
        assert report["has_drift"] is True
        assert report["findings_count"] == 1
        finding = report["findings"][0]
        assert finding["retired_field"] == "timestamp"
        assert finding["replacement_field"] == "timestamp_us"
        assert finding["line"] == 4
        print("✅ test_positive_drift passed")


def test_negative_aligned():
    """Both producer and consumer migrated to timestamp_us -> NO DRIFT (exit code 0)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        prod = tmp / "producer.py"
        cons = tmp / "consumer.py"

        prod.write_text("""
def emit_telemetry(msg_id, val):
    return {
        "id": msg_id,
        "val": val,
        "timestamp_us": 1727930000000000,
    }
""")

        cons.write_text("""
def handle_event(record):
    event_id = record["id"]
    t_us = record["timestamp_us"]
    return (event_id, t_us)
""")

        proc = subprocess.run([
            sys.executable, str(DETECTOR_PATH),
            "--producers", str(prod),
            "--consumers", str(cons),
            "--json"
        ], capture_output=True, text=True)

        assert proc.returncode == 0, f"Expected returncode 0, got {proc.returncode}"
        report = json.loads(proc.stdout)
        assert report["has_drift"] is False
        assert report["findings_count"] == 0
        print("✅ test_negative_aligned passed")


def test_backward_compatible_property():
    """Producer provides backward-compatible property/alias -> NO DRIFT (exit code 0)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        prod = tmp / "producer.py"
        cons = tmp / "consumer.py"

        prod.write_text("""
class Event:
    def __init__(self, val, timestamp_us):
        self.val = val
        self.timestamp_us = timestamp_us

    @property
    def timestamp(self):
        return self.timestamp_us / 1e6
""")

        cons.write_text("""
def handle_event(event: Event):
    return event.timestamp
""")

        proc = subprocess.run([
            sys.executable, str(DETECTOR_PATH),
            "--producers", str(prod),
            "--consumers", str(cons),
            "--json"
        ], capture_output=True, text=True)

        assert proc.returncode == 0, f"Expected returncode 0, got {proc.returncode}"
        report = json.loads(proc.stdout)
        assert report["has_drift"] is False
        print("✅ test_backward_compatible_property passed")


def test_false_positive_resistance():
    """Unrelated dictionary keys or functions do not trigger false positive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        prod = tmp / "producer.py"
        cons = tmp / "consumer.py"

        prod.write_text("""
def emit_telemetry(msg_id, val):
    return {
        "id": msg_id,
        "val": val,
        "status": "ok"
    }
""")

        cons.write_text("""
def handle_event(record):
    # record does not read timestamp, unrelated local var
    timestamp = "unrelated"
    return record["id"]
""")

        proc = subprocess.run([
            sys.executable, str(DETECTOR_PATH),
            "--producers", str(prod),
            "--consumers", str(cons),
            "--json"
        ], capture_output=True, text=True)

        assert proc.returncode == 0, f"Expected returncode 0, got {proc.returncode}"
        report = json.loads(proc.stdout)
        assert report["has_drift"] is False
        print("✅ test_false_positive_resistance passed")


if __name__ == "__main__":
    test_positive_drift()
    test_negative_aligned()
    test_backward_compatible_property()
    test_false_positive_resistance()
    print("ALL DETECTOR TESTS PASSED.")
