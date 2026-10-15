"""Byte-boundary regression tests; every external operation is mocked."""
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ping/principal-ping.py"
SPEC = importlib.util.spec_from_file_location("principal_ping_utf8", SCRIPT)
ping = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ping)

STATUS = json.dumps({"phase": "running", "state": "running", "reported_state": "working",
                     "reported_state_at_ms": 1000, "worker_alive": True}).encode("utf-8")
LIMITS = SimpleNamespace(max_busy=3600, stuck_threshold=900)


def invalid_status_cases():
    for key in ("phase", "state", "reported_state"):
        for value in ([], {}, False, 0, None, "", "\ud800", "bad\0value"):
            yield key, value
    for value in ([], {}, 0, "false", "", None):
        yield "worker_alive", value
    for key in ("workload_pid", "reported_state_at_ms", "last_activity_ms"):
        for value in ([], {}, False, "", "123", -1, 1.5, float("nan")):
            yield key, value
    for value in ([], {}, [1], {"x": 1}, False, 0, "\ud800", "bad\0path"):
        yield "history_path", value


def invalid_log_cases():
    for value in ([], [1], "", 0, False, None):
        yield {"from": value, "body": "ping-test", "kind": "reply"}
    for key in ("body", "kind"):
        for value in ([], {}, 0, False, None, "\ud800", "bad\0value"):
            msg = {"from": {"tag": "principal-test"}, "body": "ping-test", "kind": "reply"}
            msg[key] = value
            yield msg
    for value in ([], {}, 0, False, None, "\ud800", "bad\0tag"):
        yield {"from": {"tag": value}, "body": "ping-test", "kind": "reply"}


class Utf8EvidenceTests(unittest.TestCase):
    def collect(self, status=(0, STATUS, b""), capture=(0, b"screen", b""),
                transcript=(0, b"log", b"")):
        replies = {"status": status, "capture": capture, "transcript": transcript}

        def run(args, **kwargs):
            self.assertEqual(args[0], "aplexer")
            self.assertTrue(kwargs["capture_output"])
            self.assertFalse(kwargs.get("text", False))
            self.assertEqual(kwargs["timeout"], 30)
            reply = replies[args[1]]
            if isinstance(reply, Exception):
                raise reply
            return subprocess.CompletedProcess(args, *reply)

        with patch.object(ping.subprocess, "run", side_effect=run) as external, \
                patch.object(ping.time, "time", return_value=2000):
            ev = ping.collect("principal-test")
        return ev, external.call_count

    def test_invalid_capture_and_transcript_boundaries_hash_exact_bytes(self):
        for raw in (b"\x80screen", b"\x82\xac continuation", b"tail\xe2\x82", b"tail\xf0\x9f\x92"):
            with self.subTest(raw=raw):
                ev, calls = self.collect(capture=(0, raw, b""), transcript=(0, raw, b""))
                expected = hashlib.sha256(raw).hexdigest()[:16]
                self.assertEqual(ev["capture_hash"], expected)
                self.assertEqual(ev["transcript_hash"], expected)
                self.assertEqual(ev["transcript_size"], len(raw))
                self.assertNotIn("unknown", ev)
                self.assertEqual(calls, 3)
                self.assertNotIn(raw.decode("utf-8", "replace"), json.dumps(ev))

    def test_valid_unicode_byte_size_and_distinct_raw_hashes(self):
        raw = "Grüße € 🐈".encode("utf-8")
        ev, _ = self.collect(capture=(0, raw, b""), transcript=(0, raw, b""))
        self.assertEqual(ev["capture_hash"], hashlib.sha256(raw).hexdigest()[:16])
        self.assertEqual(ev["transcript_size"], len(raw))
        self.assertGreater(len(raw), len(raw.decode("utf-8")))
        # A lossy replacement would collapse these distinct observations.
        self.assertEqual(b"\x80".decode("utf-8", "replace"), b"\x81".decode("utf-8", "replace"))
        self.assertNotEqual(ping.digest(b"\x80"), ping.digest(b"\x81"))

    def test_valid_unicode_status_remains_structured(self):
        doc = json.loads(STATUS)
        doc["unused_label"] = "Grüße 🐈"
        ev, _ = self.collect(status=(0, json.dumps(doc, ensure_ascii=False).encode("utf-8"), b""))
        self.assertEqual(ev["reported_state"], "working")
        self.assertNotIn("unknown", ev)

    def test_invalid_status_utf8_is_unknown_before_absence_or_death(self):
        for rc, out, err in ((0, b"\x80" + STATUS, b""), (0, STATUS, b"\xe2\x82"),
                             (1, b"\x80", b"no session"), (1, b"no session", b"\x80")):
            with self.subTest(rc=rc, out=out, err=err):
                ev, calls = self.collect(status=(rc, out, err))
                self.assertIn("invalid UTF-8", ev["unknown"])
                self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], ping.UNKNOWN)
                self.assertNotIn("absent", ev)
                self.assertNotIn("gone", ev)
                self.assertEqual(calls, 1)

    def test_malformed_or_nonobject_status_json_is_unknown(self):
        for raw in (b"{bad", b"[]", b"null", b'"working"', b"true", b"123"):
            with self.subTest(raw=raw):
                ev, calls = self.collect(status=(0, raw, b""))
                self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], ping.UNKNOWN)
                self.assertNotIn("reported_state", ev)
                self.assertEqual(calls, 1)

    def test_status_exit_semantics_preserved(self):
        for reply, expected in (((127, b"", b""), ping.UNKNOWN),
                                ((1, b"", b"no session tagged principal-test"), ping.ABSENT),
                                ((2, b"", b"status failed"), ping.DEAD)):
            with self.subTest(reply=reply):
                ev, calls = self.collect(status=reply)
                self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], expected)
                self.assertEqual(calls, 1)

    def test_status_launch_failure_or_timeout_stays_unknown(self):
        for exc in (OSError("missing executable"), subprocess.TimeoutExpired("aplexer", 30)):
            with self.subTest(exc=exc):
                ev, _ = self.collect(status=exc)
                self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], ping.UNKNOWN)
                self.assertEqual(ev["unknown"], "aplexer cannot be run")

    def test_opaque_command_exit_code_preserved(self):
        result = subprocess.CompletedProcess(["aplexer"], 42, b"\x80", b"\x81")
        with patch.object(ping.subprocess, "run", return_value=result):
            self.assertEqual(ping.aplexer_full(["capture", "principal-test"]),
                             (42, b"\x80", b"\x81"))

    def test_capture_or_transcript_failure_cannot_fabricate_progress(self):
        prev, _ = self.collect()
        for command in ("capture", "transcript"):
            for failure in ((1, b"different output", b"error"), (127, b"", b""),
                            OSError("failed"), subprocess.TimeoutExpired("aplexer", 30)):
                with self.subTest(command=command, failure=failure):
                    ev, _ = self.collect(**{command: failure})
                    st = {"evidence": prev, "last_change_ts": 1, "busy_since": 1}
                    cls, _ = ping.classify(ev, prev, st, LIMITS, now=2000)
                    self.assertEqual(cls, ping.UNKNOWN)
                    ping.commit_evidence(st, ev, cls)
                    self.assertEqual(st["last_change_ts"], 1)
                    self.assertEqual(st["evidence"], prev)

    def test_raw_evidence_change_and_stuck_threshold_still_work(self):
        prev, _ = self.collect(capture=(0, b"\x80", b""))
        ev, _ = self.collect(capture=(0, b"\x81", b""))
        st = {"last_change_ts": 1, "busy_since": 1500}
        self.assertEqual(ping.classify(ev, prev, st, LIMITS, now=2000)[0], ping.PROGRESSING)
        self.assertEqual(ping.classify(prev, prev, st, LIMITS, now=2000)[0], ping.STUCK)
        st["busy_since"] = 1
        self.assertEqual(ping.classify(ev, prev, st, LIMITS, now=4000)[0], ping.STUCK)

    def test_invalid_status_never_selects_recovery_in_main(self):
        for status in ((0, b"\x80", b""), (0, b"{bad", b""), (0, b"[]", b"")):
            ev, _ = self.collect(status=status)
            with self.subTest(status=status), \
                    patch.object(ping, "collect", return_value=ev), \
                    patch.object(ping, "load_state", return_value={"misses": 100}), \
                    patch.object(ping, "recover") as recovery, \
                    patch.object(ping, "aplexer") as external, \
                    patch.object(ping, "save_state") as write, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(ping.main(["--tag", "principal-test"]), 0)
                recovery.assert_not_called()
                external.assert_not_called()
                write.assert_not_called()
                self.assertIn("UNKNOWN", output.getvalue())
                self.assertIn("never recover", output.getvalue())

    def test_invalid_log_cannot_acknowledge_a_ping(self):
        for raw in (b"\x80", b"{bad", b"null", b"{}", b"[1]",
                    b'[{"from": 123}]', b'[{"body": ["ping-test"]}]'):
            with self.subTest(raw=raw), patch.object(ping.subprocess, "run", return_value=
                    subprocess.CompletedProcess(["aplexer"], 0, raw, b"")):
                self.assertIsNone(ping.acked("principal-test", "ping-test"))

    def test_readable_log_retains_ack_and_empty_log_semantics(self):
        ack = {"from": {"tag": "principal-test"}, "kind": "reply", "body": "Grüße ping-test"}
        for msgs, expected in (([], False), ([ack], True), ([ack, {"from": 123}], None)):
            raw = json.dumps(msgs, ensure_ascii=False).encode("utf-8")
            with self.subTest(msgs=msgs), patch.object(ping.subprocess, "run", return_value=
                    subprocess.CompletedProcess(["aplexer"], 0, raw, b"")):
                self.assertIs(ping.acked("principal-test", "ping-test"), expected)

    def test_failed_log_is_unavailable_not_a_confirmed_missed_ack(self):
        for result in (subprocess.CompletedProcess(["aplexer"], 1, b"[]", b"failed"),
                       subprocess.TimeoutExpired("aplexer", 30), OSError("missing")):
            kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
            with self.subTest(result=result), patch.object(ping.subprocess, "run", **kwargs):
                self.assertIsNone(ping.acked("principal-test", "ping-test"))

    def test_wait_ack_preserves_unavailable_and_real_ack(self):
        a = SimpleNamespace(tag="principal-test", poll=1)
        for answer in (True, None, False):
            with self.subTest(answer=answer), patch.object(ping, "acked", return_value=answer), \
                    patch.object(ping.time, "time", return_value=2000):
                self.assertIs(ping.wait_ack(a, "ping-test", 0), answer)

    def test_unreadable_log_never_selects_recovery_even_at_idle_threshold(self):
        idle = json.loads(STATUS)
        idle["reported_state"] = "idle"
        ev, _ = self.collect(status=(0, json.dumps(idle).encode(), b""))
        for waits in ([None], [False, None]):
            st = {"misses": 100, "attempts": 0, "last_recovery": 0}
            with self.subTest(waits=waits), patch.object(ping, "collect", return_value=ev), \
                    patch.object(ping, "load_state", return_value=st), \
                    patch.object(ping, "wait_ack", side_effect=waits), \
                    patch.object(ping, "recover") as recovery, \
                    patch.object(ping, "alert") as alert, \
                    patch.object(ping, "aplexer") as sends, \
                    patch.object(ping, "save_state") as write, \
                    contextlib.redirect_stdout(io.StringIO()):
                # Only the decision function runs: process, sends, state and recovery are mocks.
                self.assertEqual(ping.main(["--live", "--threshold", "1"]), 1)
                recovery.assert_not_called()
                self.assertEqual(st["last_class"], ping.UNKNOWN)
                self.assertEqual(st["misses"], 100)
                self.assertEqual(alert.call_args.args[3], ping.UNKNOWN)
                self.assertTrue(write.called)
                self.assertTrue(sends.called)

    def decision_from_json(self, status, log):
        """Exercise the real status/log parsers and decision path with every I/O mocked."""
        raw_status, raw_log = json.dumps(status).encode(), json.dumps(log).encode()

        def run(args, **kwargs):
            if args[1] == "status":
                raw = raw_status
            elif args[1:3] == ["message", "log"]:
                raw = raw_log
            else:
                raw = b"synthetic output"
            return subprocess.CompletedProcess(args, 0, raw, b"")

        st = {"misses": 100, "attempts": 0, "last_recovery": 0}
        with patch.object(ping.subprocess, "run", side_effect=run), \
                patch.object(ping.os.path, "exists", return_value=True), \
                patch.object(ping.os, "stat", return_value=SimpleNamespace(st_size=123, st_mtime=1000)), \
                patch.object(ping, "load_state", return_value=st), \
                patch.object(ping, "save_state"), patch.object(ping, "alert"), \
                patch.object(ping, "recover") as recovery, patch.object(ping, "got_ack") as got_ack, \
                patch.object(ping.time, "time", return_value=2000), \
                patch.object(ping.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            ping.main(["--live", "--tag", "principal-test", "--timeout", "0", "--threshold", "1"])
        return st, recovery.called, got_ack.called

    def test_all_consumed_status_fields_reject_malformed_metadata_before_io(self):
        for key, value in invalid_status_cases():
            status = json.loads(STATUS)
            status[key] = value
            with self.subTest(key=key, value=value), patch.object(ping.os, "stat") as stat, \
                    patch.object(ping.os.path, "exists") as exists:
                ev, calls = self.collect(status=(0, json.dumps(status).encode(), b""))
                self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], ping.UNKNOWN)
                self.assertIn("malformed metadata", ev["unknown"])
                stat.assert_not_called()
                exists.assert_not_called()
                self.assertEqual(calls, 1)

    def test_malformed_status_metadata_never_increments_miss_or_recovers(self):
        for key, value in invalid_status_cases():
            status = json.loads(STATUS)
            status["reported_state"] = "idle"
            status[key] = value
            with self.subTest(key=key, value=value):
                st, recovery, acknowledged = self.decision_from_json(status, [])
                self.assertEqual(st["last_class"], ping.UNKNOWN)
                self.assertEqual(st["misses"], 100)
                self.assertFalse(recovery)
                self.assertFalse(acknowledged)

    def test_all_consumed_log_fields_reject_falsy_wrong_types_before_defaults(self):
        status = json.loads(STATUS)
        status["reported_state"] = "idle"
        for msg in invalid_log_cases():
            raw = json.dumps([msg]).encode()
            with self.subTest(msg=msg), patch.object(ping.subprocess, "run", return_value=
                    subprocess.CompletedProcess(["aplexer"], 0, raw, b"")):
                self.assertIsNone(ping.acked("principal-test", "ping-test"))
            with self.subTest(decision_msg=msg):
                st, recovery, acknowledged = self.decision_from_json(status, [msg])
                self.assertEqual(st["last_class"], ping.UNKNOWN)
                self.assertEqual(st["misses"], 100)
                self.assertFalse(recovery)
                self.assertFalse(acknowledged)

    def test_valid_status_metadata_and_known_liveness_proofs_remain(self):
        status = json.loads(STATUS)
        for key in ("workload_pid", "history_path", "reported_state_at_ms", "last_activity_ms"):
            status[key] = None
        ev, _ = self.collect(status=(0, json.dumps(status).encode(), b""))
        self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], ping.PROGRESSING)
        status.update(workload_pid=0, history_path="", reported_state_at_ms=0, last_activity_ms=0)
        with patch.object(ping.os.path, "exists") as exists, patch.object(ping.os, "stat") as stat:
            ev, _ = self.collect(status=(0, json.dumps(status).encode(), b""))
            self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], ping.PROGRESSING)
            exists.assert_not_called()
            stat.assert_not_called()
        status.update(workload_pid=123, history_path="synthetic/Grüße", reported_state_at_ms=0,
                      last_activity_ms=1000)
        for update, pid_exists, expected in (({}, True, ping.PROGRESSING),
                                            ({"reported_state": "idle"}, True, ping.IDLE),
                                            ({"worker_alive": False}, True, ping.DEAD),
                                            ({}, False, ping.DEAD),
                                            ({"phase": "failed"}, True, ping.DEAD),
                                            ({"state": "exited"}, True, ping.DEAD)):
            doc = {**status, **update}
            with self.subTest(update=update, pid_exists=pid_exists), \
                    patch.object(ping.os.path, "exists", return_value=pid_exists), \
                    patch.object(ping.os, "stat", return_value=SimpleNamespace(st_size=123, st_mtime=1000)):
                ev, _ = self.collect(status=(0, json.dumps(doc).encode(), b""))
                self.assertEqual(ping.classify(ev, None, {}, LIMITS)[0], expected)
                self.assertEqual(ev["history_size"], 123)

    def test_valid_empty_log_still_confirms_idle_miss(self):
        status = json.loads(STATUS)
        status["reported_state"] = "idle"
        st, recovery, acknowledged = self.decision_from_json(status, [])
        self.assertEqual(st["last_class"], ping.IDLE)
        self.assertEqual(st["misses"], 101)
        self.assertTrue(recovery)  # only the recovery mock is selected
        self.assertFalse(acknowledged)


if __name__ == "__main__":
    unittest.main()
