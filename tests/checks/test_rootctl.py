#!/usr/bin/env python3
"""Offline tests for scripts/root/rootctl.

Standalone by construction: the only inputs are scripts/root/rootctl and this
file. No test reads .local/, no credential file, no Hub, no real systemd unit.
Every Hub is a mock on 127.0.0.1 and every systemctl is a fake script that
reproduces real systemd exit codes (is-enabled disabled -> rc 1, is-active
inactive -> rc 3, both printing the state word on stdout).

Covered: stop=BOTH off and start=BOTH on against systemd-faithful codes, the
readonly status observation, the full verdict vocabulary from actual readbacks,
idempotence, 401/403, a total bounded HTTP budget (DNS, connect, slow drip),
redirect refusal with no credential forwarded, proxy-free credentialed calls,
URL userinfo/query/fragment refusal with sanitized errors, mandatory explicit
auth_mode, config permission warnings, redaction of a secret echoed by
systemctl, start compensation that restores the pre-check intent, a failing
compensating PUT reported as unknown, argparse refusal of --pause-session, the
shared readonly status lock and the mutation lock, and a source-only contract
check that needs no private file.
"""

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROOTCTL = ROOT / "scripts" / "root" / "rootctl"

_loader = importlib.machinery.SourceFileLoader("rootctl_module", str(ROOTCTL))
_spec = importlib.util.spec_from_loader("rootctl_module", _loader)
rootctl = importlib.util.module_from_spec(_spec)
_loader.exec_module(rootctl)

SENTINEL_TOKEN = "SENTINEL-HUB-TOKEN-9c1f2b7a-do-not-print"
SENTINEL_CSRF = "SENTINEL-CSRF-4e7a1d33-do-not-print"
SENTINEL_COOKIE = "SENTINEL-COOKIE-8b2c5e90-do-not-print"
SENTINEL_URL_SECRET = "SENTINEL-URL-SECRET-5d0a-do-not-print"

# systemd-faithful fake: the state word always goes to stdout, and the negative
# states exit non-zero exactly as man systemctl documents ("non-zero otherwise").
FAKE_SYSTEMCTL = '''#!/usr/bin/env python3
"""Fake systemctl --user. systemd-faithful exit codes; only its own state file."""
import json, os, sys

state_path = os.environ["FAKE_SYSTEMCTL_STATE"]
try:
    state = json.load(open(state_path))
except Exception:
    state = {"enabled": False, "active": False}

args = sys.argv[1:]
log_path = os.environ.get("FAKE_SYSTEMCTL_LOG")
if log_path:
    with open(log_path, "a") as fh:
        fh.write(json.dumps({"argv": args}) + chr(10))


def out(text, code=0):
    sys.stdout.write(text + chr(10))
    sys.exit(code)


if args[:2] == ["--user", "is-enabled"]:
    if state.get("fail_is_enabled"):
        sys.stderr.write((state.get("fail_text") or "fake: is-enabled refused") + chr(10))
        out("", 1)
    raw = state.get("is_enabled_raw")
    if raw is not None:
        out(raw, 1)
    out("enabled" if state.get("enabled") else "disabled",
        0 if state.get("enabled") else 1)

if args[:2] == ["--user", "is-active"]:
    if state.get("fail_is_active"):
        sys.stderr.write((state.get("fail_text") or "fake: is-active refused") + chr(10))
        out("", 1)
    raw = state.get("is_active_raw")
    if raw is not None:
        out(raw, 3)
    out("active" if state.get("active") else "inactive",
        0 if state.get("active") else 3)

if args[:1] == ["--user"] and "enable" in args:
    if state.get("fail_enable"):
        sys.stderr.write((state.get("fail_text") or "fake: enable refused") + chr(10))
        sys.exit(1)
    state["enabled"] = True
    # enable_no_active decouples the two flags: enable succeeds (rc 0) but
    # the unit never becomes active, so start must fail its readback.
    state["active"] = not bool(state.get("enable_no_active"))
elif args[:1] == ["--user"] and "disable" in args:
    if state.get("fail_disable"):
        sys.stderr.write((state.get("fail_text") or "fake: disable refused") + chr(10))
        sys.exit(1)
    state["enabled"] = False
    # disable_keeps_active decouples the two flags: disable succeeds (rc 0)
    # but the unit stays active, so stop must fail its readback.
    state["active"] = bool(state.get("disable_keeps_active"))
else:
    out("fake systemctl: unsupported verb")

json.dump(state, open(state_path, "w"))
out("")'''


class MockHub:
    """Local mock of GET/PUT /api/root/scheduling. Never talks to a real Hub."""

    def __init__(self):
        self.lock = threading.Lock()
        self.enabled = False
        self.updated_at = "2026-10-14T00:00:00Z"
        self.behaviour = "normal"
        self.requests = []
        self.strict_bool = True
        self.applied = None
        self.gets = 0
        self.echo_secret = False
        self.blind = False
        mock = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, code, payload=None, raw=None):
                body = b"" if (payload is None and raw is None) else (
                    raw if raw is not None else json.dumps(payload).encode())
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    try:
                        self.wfile.write(body)
                    except OSError:
                        pass

            def _record(self, method, body):
                with mock.lock:
                    mock.requests.append({
                        "method": method,
                        "path": self.path,
                        "auth": self.headers.get("Authorization"),
                        "cookie": self.headers.get("Cookie"),
                        "csrf": self.headers.get("X-CSRF-Token"),
                        "body": body,
                    })

            def _secret_echo(self, code):
                """A hostile/buggy Hub that reflects the credential it got."""
                if not mock.echo_secret:
                    return None
                with mock.lock:
                    secrets = [r["auth"] or "" for r in mock.requests]
                    secrets += [r["cookie"] or "" for r in mock.requests]
                    secrets += [r["csrf"] or "" for r in mock.requests]
                blob = " ".join(s for s in secrets if s) or "no-credential"
                return self._send(code, {"error": "upstream rejected %s" % blob,
                                         "enabled": "true",
                                         "updated_at": "2026-10-14T00:00:00Z"})

            def do_GET(self):
                self._record("GET", None)
                with mock.lock:
                    mock.gets += 1
                    gets = mock.gets
                echoed = self._secret_echo(502)
                if echoed is not None:
                    return echoed
                b = mock.behaviour
                if mock.blind:
                    return self._send(503, {"error": "hub is not answering"})
                if b == "unauthorized":
                    return self._send(401, {"error": "unauthorized"})
                if b == "forbidden":
                    return self._send(403, {"error": "forbidden"})
                if b == "server_error":
                    return self._send(500, {"error": "boom"})
                if b == "oversize":
                    big = "x" * 98304
                    return self._send(200, {"enabled": mock.enabled,
                                            "updated_at": mock.updated_at,
                                            "pad": big})
                if b == "timeout":
                    time.sleep(5.0)
                    return self._send(200, {"enabled": mock.enabled,
                                            "updated_at": mock.updated_at})
                if b == "malformed":
                    return self._send(200, raw=b"{not json")
                if b == "not_object":
                    return self._send(200, raw=b"[1,2,3]")
                if b == "enabled_string":
                    return self._send(200, {"enabled": "true",
                                            "updated_at": mock.updated_at})
                if b == "enabled_number":
                    return self._send(200, {"enabled": 1, "updated_at": mock.updated_at})
                if b == "bad_updated_at":
                    return self._send(200, {"enabled": mock.enabled,
                                            "updated_at": "2026-10-14 00:00:00"})
                if b == "naive_updated_at":
                    return self._send(200, {"enabled": mock.enabled,
                                            "updated_at": "2026-10-14T00:00:00"})
                if b == "missing_updated_at":
                    return self._send(200, {"enabled": mock.enabled})
                if b == "readback_mismatch":
                    return self._send(200, {"enabled": not mock.enabled,
                                            "updated_at": mock.updated_at})
                if b == "final_flip" and gets >= 3:
                    # The Hub only loses the flag on the very last readback.
                    return self._send(200, {"enabled": False,
                                            "updated_at": mock.updated_at})
                return self._send(200, {"enabled": mock.enabled,
                                        "updated_at": mock.updated_at})

            def do_PUT(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw.decode())
                except Exception:
                    body = {"__unparsable__": raw.decode("utf-8", "replace")}
                self._record("PUT", body)
                echoed = self._secret_echo(502)
                if echoed is not None:
                    return echoed
                b = mock.behaviour
                if b == "unauthorized":
                    return self._send(401, {"error": "unauthorized"})
                if b == "forbidden":
                    return self._send(403, {"error": "forbidden"})
                if b == "put_forbidden_only":
                    return self._send(403, {"error": "forbidden"})
                if b == "server_error":
                    return self._send(500, {"error": "boom"})
                if b == "put_malformed":
                    return self._send(200, raw=b"{oops")
                if b == "put_wrong_bool":
                    return self._send(200, {"enabled": not bool(body.get("enabled")),
                                            "updated_at": mock.updated_at})
                if b == "put_no_reply":
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if b == "compensate_fail" and body.get("enabled") is False:
                    # The compensating PUT fails, and the Hub then refuses to
                    # answer at all, so the state really is unknown.
                    mock.blind = True
                    return self._send(500, {"error": "compensating write refused"})
                if mock.strict_bool and not isinstance(body.get("enabled"), bool):
                    return self._send(422, {"error": "enabled must be a strict boolean"})
                with mock.lock:
                    mock.applied = body.get("enabled")
                    mock.enabled = bool(body.get("enabled"))
                    mock.updated_at = "2026-10-14T12:00:00Z"
                    state = mock.enabled
                return self._send(200, {"enabled": state, "updated_at": mock.updated_at})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def paths(self):
        with self.lock:
            return [r["path"] for r in self.requests]

    def methods(self):
        with self.lock:
            return [r["method"] for r in self.requests]


class TinyServer:
    """A single-purpose local HTTP server used by the redirect/proxy/drip tests."""

    def __init__(self, handler_factory):
        self.record = []
        factory = handler_factory

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                factory(self, server_self)

            def do_PUT(self):
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                factory(self, server_self)

        server_self = self
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class RootctlHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.hub = MockHub()
        self.addCleanup(self.hub.stop)
        self.addCleanup(self.tmp.cleanup)

        self.fake = self.dir / "fake-systemctl"
        self.fake.write_text(FAKE_SYSTEMCTL)
        self.fake.chmod(0o755)

        self.timer_state = self.dir / "timer-state.json"
        self.timer_state.write_text(json.dumps({"enabled": False, "active": False}))
        self.timer_log = self.dir / "systemctl.log"
        self.lock = self.dir / "rootctl.lock"
        self.config = self.dir / "hub.json"
        self.write_config()

    def write_config(self, **extra):
        config = {
            "hub_url": self.hub.url,
            "token": SENTINEL_TOKEN,
            "auth_mode": "bearer",
            "host_id": "hetzner",
            "timeout_sec": 2,
        }
        config.update(extra)
        self.config.write_text(json.dumps(config))
        try:
            self.config.chmod(0o600)
        except OSError:
            pass

    def env(self, **extra):
        env = dict(os.environ)
        env.update({
            "ROOTCTL_SYSTEMCTL": str(self.fake),
            "FAKE_SYSTEMCTL_STATE": str(self.timer_state),
            "FAKE_SYSTEMCTL_LOG": str(self.timer_log),
            "ROOTCTL_LOCK": str(self.lock),
            "ROOTCTL_TIMER_UNIT": "headless-root.timer",
        })
        env.pop("http_proxy", None)
        env.pop("HTTP_PROXY", None)
        env.pop("https_proxy", None)
        env.pop("HTTPS_PROXY", None)
        for key, value in extra.items():
            env[key] = str(value)
        return env

    def run_ctl(self, *args, **kwargs):
        env = kwargs.pop("env", None) or self.env(**kwargs)
        argv = [sys.executable, "-B", str(ROOTCTL)] + list(args)
        if "--config" not in args:
            argv += ["--config", str(self.config)]
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=120, env=env)

    def timer(self):
        return json.loads(self.timer_state.read_text())

    def timer_argv(self):
        if not self.timer_log.exists():
            return []
        return [json.loads(line)["argv"] for line in
                self.timer_log.read_text().splitlines() if line.strip()]

    def set_timer(self, **values):
        state = json.loads(self.timer_state.read_text())
        state.update(values)
        self.timer_state.write_text(json.dumps(state))

    def assertNoSentinel(self, proc):
        blob = (proc.stdout or "") + (proc.stderr or "")
        for secret in (SENTINEL_TOKEN, SENTINEL_CSRF, SENTINEL_COOKIE,
                       SENTINEL_URL_SECRET):
            self.assertNotIn(secret, blob, "credential leaked into output")


class TestBothDirectionsSystemdFaithful(RootctlHarness):
    """F1: real systemd exits 1 for disabled and 3 for inactive."""

    def test_stop_turns_both_off_against_real_exit_codes(self):
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["verdict"], "both_off")
        self.assertIs(report["hub"]["enabled"], False)
        self.assertIs(report["timer"]["enabled"], False)
        self.assertIs(report["timer"]["active"], False)
        self.assertTrue(report["timer"]["known"])
        # The negative readbacks really did return non-zero, and were still read.
        self.assertIn(1, [report["timer"]["is_enabled_rc"],
                          report["timer"]["is_active_rc"]])
        self.assertIs(self.hub.enabled, False)
        self.assertEqual(self.timer()["enabled"], False)

    def test_status_of_a_truly_off_system_is_both_off(self):
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        report = json.loads(proc.stdout)
        self.assertEqual(report["verdict"], "both_off")
        self.assertEqual(report["timer"]["is_enabled_rc"], 1)
        self.assertEqual(report["timer"]["is_active_rc"], 3)

    def test_start_turns_both_on(self):
        proc = self.run_ctl("start", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertIs(self.hub.enabled, True)
        self.assertEqual(self.timer(), {"enabled": True, "active": True})
        self.assertEqual(json.loads(proc.stdout)["verdict"], "both_on")

    def test_start_and_stop_are_not_inverted(self):
        self.assertEqual(self.run_ctl("start").returncode, rootctl.EXIT_OK)
        self.assertIs(self.hub.enabled, True)
        self.assertTrue(self.timer()["enabled"] and self.timer()["active"])
        self.assertEqual(self.run_ctl("stop").returncode, rootctl.EXIT_OK)
        self.assertIs(self.hub.enabled, False)
        self.assertFalse(self.timer()["enabled"] or self.timer()["active"])

    def test_status_is_readonly(self):
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stderr)
        self.assertEqual(self.hub.methods(), ["GET"])
        self.assertEqual(json.loads(proc.stdout)["verdict"], "both_on")

    def test_idempotent_start_and_stop(self):
        for _ in range(2):
            proc = self.run_ctl("start", "--json")
            self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
            self.assertIs(self.hub.enabled, True)
            self.assertEqual(json.loads(proc.stdout)["verdict"], "both_on")
        for _ in range(2):
            proc = self.run_ctl("stop", "--json")
            self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
            self.assertIs(self.hub.enabled, False)
            self.assertEqual(json.loads(proc.stdout)["verdict"], "both_off")

    def test_only_scheduling_endpoint_is_called(self):
        self.run_ctl("start")
        self.run_ctl("stop")
        self.run_ctl("status")
        self.assertTrue(self.hub.paths())
        for path in self.hub.paths():
            self.assertEqual(path, "/api/root/scheduling")

    def test_strict_boolean_put_body(self):
        self.assertEqual(self.run_ctl("start").returncode, rootctl.EXIT_OK)
        self.assertEqual(self.run_ctl("stop").returncode, rootctl.EXIT_OK)
        bodies = [r["body"] for r in self.hub.requests if r["method"] == "PUT"]
        self.assertTrue(bodies)
        for body in bodies:
            self.assertIsInstance(body["enabled"], bool)
            self.assertEqual(set(body.keys()), {"enabled"})


class TestFaithfulTimerStates(RootctlHarness):
    """F1/F4: every recognised systemd state is a known state; unknown is fail-closed."""

    def test_every_faithful_state_word_is_known(self):
        cases = [
            ({"enabled": True, "active": True}, True, True, "on", True),
            ({"enabled": False, "active": False}, False, False, "off", True),
            ({"is_enabled_raw": "static", "is_active_raw": "inactive"}, False, False, "off", True),
            ({"is_enabled_raw": "masked", "is_active_raw": "failed"}, False, False, "off", True),
            ({"is_enabled_raw": "indirect", "is_active_raw": "active"}, False, True, "unknown", True),
            ({"is_enabled_raw": "enabled", "is_active_raw": "reloading"}, True, True, "on", True),
            ({"is_enabled_raw": "transient", "is_active_raw": "inactive"}, False, False, "off", True),
        ]
        for state, enabled, active, label, known in cases:
            with self.subTest(state=state):
                self.set_timer(**state)
                proc = self.run_ctl("status", "--json")
                report = json.loads(proc.stdout)
                self.assertTrue(report["timer"]["known"])
                self.assertIs(report["timer"]["enabled"], enabled)
                self.assertIs(report["timer"]["active"], active)
                word, _basis = rootctl.timer_label(report["timer"])
                self.assertEqual(word, label)
                expected = ("both_off" if label == "off"
                            else "hub_off_timer_%s" % label)
                self.assertEqual(report["verdict"], expected)

    def test_transitional_activating_deactivating_are_unknown_never_off(self):
        # activating/deactivating are transitional: unknown, fail-closed, and
        # never a clean off. stop must not claim both_off with exit 0.
        for raw in ("activating", "deactivating"):
            with self.subTest(raw=raw):
                self.set_timer(is_enabled_raw="disabled",
                               is_active_raw=raw)
                proc = self.run_ctl("status", "--json")
                report = json.loads(proc.stdout)
                self.assertFalse(report["timer"]["known"])
                self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
                self.assertEqual(report["verdict"], "hub_off_timer_unknown")
                proc = self.run_ctl("stop", "--json")
                report = json.loads(proc.stdout)
                self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
                self.assertNotEqual(report["verdict"], "both_off")

    def test_no_user_bus_is_unknown_and_fail_closed(self):
        self.set_timer(fail_is_enabled=True,
                       fail_text="Failed to connect to bus: No such file or directory")
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
        report = json.loads(proc.stdout)
        self.assertFalse(report["timer"]["known"])
        self.assertEqual(report["verdict"], "hub_off_timer_unknown")
        self.assertEqual(report["timer"]["verdict_basis"], "unreadable")

    def test_unrecognised_state_word_is_unknown(self):
        self.set_timer(is_enabled_raw="banana", is_active_raw="banana")
        proc = self.run_ctl("stop", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
        report = json.loads(proc.stdout)
        self.assertEqual(report["verdict"], "hub_off_timer_unknown")
        self.assertIn("recognised state", json.dumps(report["timer"]))

    def test_stop_on_an_off_timer_reports_both_off_not_mixed(self):
        proc = self.run_ctl("stop", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "both_off")


class TestVerdictsFromReadbacks(RootctlHarness):
    """F4: nine verdicts, each from an actual Hub x timer readback."""

    def test_status_vocabulary(self):
        cases = [
            (True, {"enabled": True, "active": True}, "both_on", rootctl.EXIT_OK),
            (False, {"enabled": False, "active": False}, "both_off", rootctl.EXIT_OK),
            (True, {"enabled": False, "active": False}, "hub_on_timer_off", rootctl.EXIT_FAILED),
            (False, {"enabled": True, "active": True}, "hub_off_timer_on", rootctl.EXIT_FAILED),
            (True, {"fail_is_enabled": True}, "hub_on_timer_unknown", rootctl.EXIT_UNKNOWN),
            (False, {"fail_is_enabled": True}, "hub_off_timer_unknown", rootctl.EXIT_UNKNOWN),
        ]
        for hub_enabled, timer_state, verdict, code in cases:
            with self.subTest(verdict=verdict):
                self.hub.enabled = hub_enabled
                self.set_timer(**timer_state)
                proc = self.run_ctl("status", "--json")
                self.assertEqual(proc.returncode, code, proc.stdout)
                self.assertEqual(json.loads(proc.stdout)["verdict"], verdict)

    def test_hub_unknown_combinations(self):
        self.set_timer(enabled=True, active=True)
        self.hub.stop()
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "hub_unknown_timer_on")

    def test_both_unknown(self):
        self.set_timer(fail_is_enabled=True, fail_text="Failed to connect to bus")
        self.hub.stop()
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
        self.assertEqual(json.loads(proc.stdout)["verdict"],
                         "hub_unknown_timer_unknown")

    def test_stop_verdict_names_the_actual_timer_state(self):
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True, fail_disable=True)
        proc = self.run_ctl("stop", "--json")
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "hub_off_timer_on")

    def test_failed_stop_never_reenables_the_hub(self):
        # Mutant I: stop re-enables the Hub after a timer-disable failure.
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True, fail_disable=True)
        proc = self.run_ctl("stop", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertIs(self.hub.enabled, False,
                      "stop must leave the Hub off even when the timer step fails")
        puts = [r["body"] for r in self.hub.requests if r["method"] == "PUT"]
        self.assertTrue(puts)
        for body in puts:
            self.assertIs(body.get("enabled"), False,
                          "stop must never PUT enabled=true")
        self.assertIs(report["hub"]["enabled"], False)

    def test_stop_readback_mismatch_is_a_verified_failure(self):
        # Mutant U: stop ignores a Hub readback that still says enabled=true.
        self.hub.enabled = True
        self.hub.behaviour = "readback_mismatch"
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertEqual(report["exit_code"], proc.returncode)
        self.assertNotEqual(report["verdict"], "both_off")
        self.assertTrue(report["verdict"].startswith("hub_on_timer_"))

    def test_stop_disable_keeps_active_is_a_verified_failure(self):
        # Mutant C: stop no longer fails a divergent timer readback.
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True, disable_keeps_active=True)
        proc = self.run_ctl("stop", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_FAILED, proc.stdout)
        self.assertNotEqual(report["verdict"], "both_off")
        self.assertEqual(report["verdict"], "hub_off_timer_unknown")
        self.assertIs(self.hub.enabled, False)

    def test_stop_with_hub_refusal_is_not_called_partial_unknown(self):
        self.hub.enabled = True
        self.hub.behaviour = "unauthorized"
        proc = self.run_ctl("stop", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH)
        self.assertEqual(report["verdict"], "hub_unknown_timer_off")
        self.assertNoSentinel(proc)


class TestStartFailureCompensation(RootctlHarness):
    """F5: compensation restores the pre-check intent and is always truthful."""

    def test_transient_timer_read_failure_does_not_disable_a_healthy_hub(self):
        # G9 fail-closed: an unknown timer pre-check refuses start before
        # any Hub change, so a healthy Hub is never touched.
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True, fail_is_active=True)
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertIs(self.hub.enabled, True,
                      "a transient timer read must not disable scheduling rootctl "
                      "did not enable")
        self.assertEqual(report["verdict"], "hub_on_timer_unknown")
        self.assertIsNotNone(report["verdict"])
        self.assertEqual([r for r in self.hub.requests if r["method"] == "PUT"],
                         [], "an unknown timer pre-check must send no Hub PUT")
        blob = json.dumps(report)
        self.assertIn("timer pre-check is unknown", blob)

    def test_failed_start_disables_hub_that_start_had_enabled(self):
        proc = self.run_ctl("start", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.hub.behaviour = "readback_mismatch"
        proc = self.run_ctl("start", "--json")
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertIs(self.hub.applied, False,
                      "a failed start must leave a Hub it had switched on disabled")
        report = json.loads(proc.stdout)
        # The verdict is the last ACTUAL readback; the errors say the
        # compensation itself did not confirm, so the exit stays non-zero.
        self.assertIs(report["hub"]["enabled"], True)
        self.assertEqual(report["verdict"], "both_on")
        self.assertTrue(any("could not be restored" in e for e in report["errors"]))

    def test_failing_compensating_put_reports_unknown_never_safe(self):
        # compensate_fail with a timer whose enable step fails: the start
        # reaches the Hub PUT, then the timer enable fails, then the
        # compensating PUT fails and the Hub goes blind: truly unknown.
        self.hub.behaviour = "compensate_fail"
        self.set_timer(fail_enable=True)
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertIs(report["hub"]["known"], False)
        self.assertTrue(report["verdict"].startswith("hub_unknown_timer_"))
        blob = proc.stdout + proc.stderr
        self.assertIn("unknown", blob)
        self.assertNotIn("safe", blob.lower())
        self.assertNotIn("restored: true", blob)

    def test_unknown_timer_precheck_with_failing_hub_stays_unknown(self):
        # Unknown timer pre-check plus a blind Hub: start refuses before any
        # change and the report stays unknown, never safe/off/restored.
        self.hub.behaviour = "compensate_fail"
        self.set_timer(fail_is_active=True)
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertEqual([r for r in self.hub.requests if r["method"] == "PUT"],
                         [])
        self.assertTrue(report["verdict"].endswith("_unknown"))
        blob = proc.stdout + proc.stderr
        self.assertIn("unknown", blob)
        self.assertNotIn("safe", blob.lower())

    def test_start_enable_leaves_inactive_is_a_verified_failure(self):
        # Mutant B: start no longer requires the timer to be active.
        self.set_timer(enabled=False, active=False, enable_no_active=True)
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertNotEqual(report["verdict"], "both_on")
        self.assertIs(self.hub.enabled, False,
                      "a failed start must leave a Hub it had switched on disabled")
        self.assertFalse(self.timer()["active"])

    def test_start_put_refused_sends_no_compensation_and_keeps_auth_exit(self):
        # G2: GET ok but PUT 401/403 must not send a pointless compensating
        # PUT, and the auth exit 4 must survive instead of exit 3 unknown.
        self.hub.behaviour = "forbidden"
        # Pre-check GET is forbidden too in this mock; use a Hub that is off
        # and refuses only the PUT: emulate by starting from off with the
        # forbidden behaviour (GET 403 -> pre-check auth). For the GET-ok /
        # PUT-403 path use two phases: first prove pre-check auth is exit 4,
        # then prove a PUT-time refusal keeps exit 4 with no second PUT.
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH, proc.stdout)
        puts = [r for r in self.hub.requests if r["method"] == "PUT"]
        self.assertEqual(puts, [],
                         "a pre-check refusal must send no PUT at all")

    def test_start_put_time_auth_refusal_sends_no_compensating_put(self):
        # G2: GET ok but PUT 403 must send exactly one PUT (the attempt),
        # never a compensating second PUT, and must keep exit 4 with the
        # Hub still off.
        self.hub.enabled = False
        self.hub.behaviour = "put_forbidden_only"
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH, proc.stdout)
        puts = [r for r in self.hub.requests if r["method"] == "PUT"]
        self.assertEqual(len(puts), 1,
                         "a refused PUT must not be followed by compensation")
        self.assertIs(self.hub.enabled, False)
        self.assertFalse(any("could not be restored" in e
                             for e in report["errors"]),
                         "a definite refusal is not an unknown-restore case")
        self.assertNoSentinel(proc)

    def test_divergent_timer_precheck_is_reported_truthfully(self):
        # G3: a divergent pre-check (enabled xor active) must never be
        # recorded as "already enabled+active".
        self.set_timer(enabled=True, active=False)
        self.hub.behaviour = "final_flip"
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        blob = json.dumps(report)
        self.assertNotIn("already enabled+active", blob)
        self.assertIn("divergent", blob)

    def test_compensation_restores_a_timer_that_start_enabled(self):
        self.hub.behaviour = "final_flip"
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertEqual(report["verdict"], "both_off",
                         "the timer start had enabled must be turned off again")
        self.assertEqual(self.timer()["enabled"], False)
        self.assertIs(self.hub.enabled, False)

    def test_precheck_failure_leaves_everything_untouched_and_verdicts(self):
        self.hub.behaviour = "forbidden"
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH)
        self.assertIsNotNone(report["verdict"])
        self.assertEqual(report["verdict"], "hub_unknown_timer_off")
        self.assertEqual(self.timer()["enabled"], False)
        self.assertEqual(self.hub.applied, None)

    def test_final_readback_flip_is_caught(self):
        self.hub.behaviour = "final_flip"
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertNotEqual(report["verdict"], "both_on")
        self.assertEqual(report["verdict"], "both_off")
        failing = " ".join(s["step"] for s in report["steps"] if not s["ok"])
        self.assertIn("final GET hub scheduling readback", failing)

    def test_every_start_failure_path_carries_a_verdict(self):
        for behaviour in ("unauthorized", "forbidden", "server_error", "malformed",
                          "not_object", "enabled_string", "bad_updated_at",
                          "readback_mismatch", "put_wrong_bool", "put_no_reply"):
            with self.subTest(behaviour=behaviour):
                self.hub.behaviour = behaviour
                proc = self.run_ctl("start", "--json")
                report = json.loads(proc.stdout)
                self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
                self.assertIsNotNone(report["verdict"], behaviour)
                self.assertEqual(report["exit_code"], proc.returncode)
                self.assertNoSentinel(proc)


class TestHttpsafety(RootctlHarness):
    """F2/F3/F7: URL hygiene, no redirect/proxy credential forwarding, total bound."""

    def test_url_with_userinfo_is_refused_without_echoing_it(self):
        self.write_config(hub_url="http://admin:%s@127.0.0.1:9" % SENTINEL_URL_SECRET)
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertIn("userinfo", proc.stdout + proc.stderr)
        self.assertNotIn(SENTINEL_URL_SECRET, proc.stdout + proc.stderr)
        self.assertNoSentinel(proc)
        self.assertEqual(self.hub.requests, [])

    def test_url_with_query_is_refused_without_echoing_it(self):
        self.write_config(hub_url=self.hub.url + "/?apikey=%s" % SENTINEL_URL_SECRET)
        for args in (("status",), ("status", "--json"), ("start",), ("stop",)):
            proc = self.run_ctl(*args)
            self.assertEqual(proc.returncode, rootctl.EXIT_USAGE, proc.stdout)
            self.assertIn("query", proc.stdout + proc.stderr)
            self.assertNoSentinel(proc)
        self.assertEqual(self.hub.requests, [])

    def test_url_with_fragment_is_refused(self):
        self.write_config(hub_url=self.hub.url + "/#%s" % SENTINEL_URL_SECRET)
        proc = self.run_ctl("status")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertIn("fragment", proc.stdout + proc.stderr)
        self.assertNoSentinel(proc)

    def test_env_url_secret_is_redacted_too(self):
        proc = self.run_ctl("status", "--json", ROOTCTL_HUB_URL="http://x/?k=%s"
                            % SENTINEL_URL_SECRET)
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertNoSentinel(proc)

    def test_redirect_is_refused_and_no_credential_is_forwarded(self):
        seen = []

        def sink_handler(handler, server):
            seen.append({"auth": handler.headers.get("Authorization"),
                         "cookie": handler.headers.get("Cookie"),
                         "csrf": handler.headers.get("X-CSRF-Token")})
            body = json.dumps({"enabled": True,
                               "updated_at": "2026-10-14T12:00:00Z"}).encode()
            handler.send_response(200)
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

        sink = TinyServer(sink_handler)
        self.addCleanup(sink.stop)

        def redir_handler(handler, server):
            handler.send_response(302)
            handler.send_header("Location", sink.url + "/api/root/scheduling")
            handler.send_header("Content-Length", "0")
            handler.end_headers()

        red = TinyServer(redir_handler)
        self.addCleanup(red.stop)
        self.write_config(hub_url=red.url)

        proc = self.run_ctl("status", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertIn("redirect", json.dumps(report).lower())
        self.assertFalse(report["hub"]["known"],
                         "a redirect target body must never be trusted as the Hub")
        self.assertEqual(seen, [], "the admin credential was forwarded to a second host")
        self.assertNoSentinel(proc)

    def test_environment_proxy_is_not_used_for_the_credentialed_call(self):
        def sink_handler(handler, server):
            server.record.append({"auth": handler.headers.get("Authorization")})
            body = json.dumps({"enabled": True,
                               "updated_at": "2026-10-14T12:00:00Z"}).encode()
            handler.send_response(200)
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

        sink = TinyServer(sink_handler)
        self.addCleanup(sink.stop)
        env = self.env(http_proxy=sink.url, HTTP_PROXY=sink.url)
        proc = self.run_ctl("status", "--json", env=env)
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertEqual(sink.record, [], "the proxy must not see the admin call")
        self.assertTrue(self.hub.requests)

    def test_total_http_budget_includes_a_slow_drip_body(self):
        def drip_handler(handler, server):
            handler.send_response(200)
            handler.send_header("Content-Length", "400")
            handler.end_headers()
            try:
                for _ in range(400):
                    handler.wfile.write(b" ")
                    handler.wfile.flush()
                    time.sleep(0.4)
            except OSError:
                pass

        drip = TinyServer(drip_handler)
        self.addCleanup(drip.stop)
        self.write_config(hub_url=drip.url, timeout_sec=1)
        before = threading.active_count()
        started = time.time()
        proc = self.run_ctl("status", "--json")
        elapsed = time.time() - started
        self.assertLess(elapsed, 20, "slow drip defeated the total budget")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertIn("budget", (proc.stdout + proc.stderr).lower())
        drip.stop()
        deadline = time.time() + 10
        while threading.active_count() > before and time.time() < deadline:
            time.sleep(0.2)
        self.assertLessEqual(threading.active_count(), before + 1,
                             "an orphaned handler thread was left behind")

    def test_timeout_is_bounded(self):
        self.hub.behaviour = "timeout"
        started = time.time()
        proc = self.run_ctl("start", "--json", timeout_sec=1)
        self.assertLess(time.time() - started, 25)
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
        self.assertEqual(self.timer()["enabled"], False)


class TestRedaction(RootctlHarness):
    """F9: a secret echoed by a dependency must not reach the output."""

    def test_systemctl_stderr_echoing_the_token_is_redacted(self):
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True, fail_disable=True,
                       fail_text="unit rejected credential %s" % SENTINEL_TOKEN)
        proc = self.run_ctl("stop", "--json")
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertNoSentinel(proc)
        self.assertIn("***redacted***", proc.stdout + proc.stderr)

    def test_hub_reflecting_the_credential_does_not_leak_it(self):
        self.hub.echo_secret = True
        for command in ("status", "start", "stop"):
            proc = self.run_ctl(command, "--json")
            self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
            self.assertNoSentinel(proc)
            self.assertNotIn("upstream rejected", proc.stdout + proc.stderr)

    def test_error_paths_are_redacted(self):
        for behaviour in ("unauthorized", "server_error", "malformed"):
            self.hub.behaviour = behaviour
            for command in ("status", "start", "stop"):
                self.assertNoSentinel(self.run_ctl(command, "--json"))
                self.assertNoSentinel(self.run_ctl(command))
        self.assertNoSentinel(self.run_ctl("status", "--json"))

    def test_session_credentials_are_sent_but_never_printed(self):
        self.config.unlink()
        self.config.write_text(json.dumps({
            "hub_url": self.hub.url, "auth_mode": "session",
            "csrf_token": SENTINEL_CSRF, "cookie": SENTINEL_COOKIE}))
        self.config.chmod(0o600)
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stderr)
        self.assertNoSentinel(proc)
        request = [r for r in self.hub.requests if r["method"] == "GET"][0]
        self.assertEqual(request["csrf"], SENTINEL_CSRF)
        self.assertEqual(request["cookie"], SENTINEL_COOKIE)
        self.assertIsNone(request["auth"])


class TestConfigHygiene(RootctlHarness):
    """F10/F11: explicit credential declaration, 0600 config, sanitized errors."""

    def test_auth_mode_must_be_declared(self):
        self.config.unlink()
        self.config.write_text(json.dumps({"hub_url": self.hub.url,
                                           "token": SENTINEL_TOKEN}))
        self.config.chmod(0o600)
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertIn("auth_mode", proc.stdout + proc.stderr)
        self.assertNoSentinel(proc)
        self.assertEqual(self.hub.requests, [])

    def test_session_pause_config_key_is_refused(self):
        self.write_config(session_pause=True,
                          session_pause_path="/api/root/session/pause")
        proc = self.run_ctl("start", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertIn("session_pause", proc.stdout + proc.stderr)
        self.assertEqual(self.hub.requests, [])
        self.assertEqual(self.timer()["enabled"], False)

    def test_pause_session_flag_does_not_exist_on_any_subcommand(self):
        for command in ("start", "stop", "status"):
            for extra in ((), ("--json",)):
                proc = self.run_ctl(command, *(extra + ("--pause-session",)))
                self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
                self.assertIn("pause-session", proc.stdout + proc.stderr)
                self.assertNoSentinel(proc)
        self.assertEqual(self.hub.requests, [], "a refused flag must send nothing")
        self.assertEqual(self.timer(), {"enabled": False, "active": False})

    def test_config_permission_0600_is_quiet_and_loose_modes_warn(self):
        proc = self.run_ctl("status", "--json")
        self.assertEqual(json.loads(proc.stdout)["warnings"], [])
        self.config.chmod(0o644)
        proc = self.run_ctl("status", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("0600", report["warnings"][0])
        self.assertNoSentinel(proc)
        self.config.chmod(0o666)
        proc = self.run_ctl("status", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("writable", report["warnings"][0])
        self.assertNoSentinel(proc)

    def test_malformed_config_is_a_sanitised_usage_error(self):
        self.config.write_text('{"token": "%s", broken' % SENTINEL_TOKEN)
        proc = self.run_ctl("start")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertNoSentinel(proc)
        self.assertNotIn(str(self.dir), proc.stdout + proc.stderr,
                         "the config path must not be echoed back")

    def test_missing_config_is_usage_error_and_makes_no_request(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOTCTL), "start", "--config",
             str(self.dir / "absent.json")],
            capture_output=True, text=True, timeout=60, env=self.env())
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertEqual(self.hub.requests, [])
        self.assertEqual(self.timer(), {"enabled": False, "active": False})

    def test_bad_hub_url_is_rejected(self):
        self.write_config(hub_url="ftp://x")
        proc = self.run_ctl("status")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertNoSentinel(proc)

    def test_env_overrides_are_honoured(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOTCTL), "status", "--json",
             "--config", str(self.config)],
            capture_output=True, text=True, timeout=60,
            env=self.env(ROOTCTL_HUB_URL=self.hub.url,
                         ROOTCTL_HUB_TOKEN=SENTINEL_TOKEN,
                         QUOTA_HUB_CONFIG=""))
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["hub_url"], self.hub.url)
        self.assertNoSentinel(proc)

    def test_host_quota_env_never_overrides_admin_config(self):
        # G6: a host QUOTA_HUB_TOKEN/URL must not silently replace the admin
        # config or receive the admin credential.
        other = "http://127.0.0.1:9"
        env = self.env(QUOTA_HUB_URL=other, QUOTA_HUB_TOKEN="HOSTQUOTA",
                       QUOTA_HUB_HOST_ID="other-host",
                       QUOTA_HUB_TIMEOUT="60")
        proc = self.run_ctl("status", "--json", env=env)
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        report = json.loads(proc.stdout)
        self.assertEqual(report["hub_url"], self.hub.url)
        self.assertTrue(self.hub.requests)
        auths = [r["auth"] for r in self.hub.requests if r["method"] == "GET"]
        self.assertTrue(auths)
        for auth in auths:
            self.assertNotIn("HOSTQUOTA", auth or "")
        self.assertNoSentinel(proc)

    def test_json_report_is_strict_and_redacted(self):
        proc = self.run_ctl("status", "--json")
        report = json.loads(proc.stdout)
        for key in ("command", "at_utc", "exit_code", "verdict", "hub", "timer",
                    "steps", "errors", "warnings", "lock", "linearizable"):
            self.assertIn(key, report)
        self.assertIsInstance(report["hub"]["enabled"], bool)
        self.assertRegex(report["at_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(report["hub_url"], self.hub.url)


class TestLocksAndReadonly(RootctlHarness):
    """F11: status is a shared-lock observation that creates no lock file."""

    def test_status_creates_no_lock_file(self):
        lock = self.dir / "state" / "rootctl.lock"
        proc = self.run_ctl("status", "--json", ROOTCTL_LOCK=str(lock))
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertFalse(lock.exists(), "a readonly status must not create a lock file")
        self.assertFalse(lock.parent.exists())
        report = json.loads(proc.stdout)
        self.assertEqual(report["lock"]["mode"], "shared")
        self.assertFalse(report["lock"]["created"])

    def test_status_does_not_write_the_lock_it_observes(self):
        handle, _info = rootctl.acquire_lock(str(self.lock), 0, exclusive=True)
        try:
            before = self.lock.stat().st_mtime_ns, self.lock.stat().st_size
            proc = self.run_ctl("status", "--json")
            after = self.lock.stat().st_mtime_ns, self.lock.stat().st_size
            self.assertEqual(before, after, "status must not write the lock file")
        finally:
            handle.close()

    def test_status_beside_a_mutating_rootctl_is_truthful_not_busy(self):
        handle, _info = rootctl.acquire_lock(str(self.lock), 0, exclusive=True)
        try:
            proc = self.run_ctl("status", "--json")
            self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
            report = json.loads(proc.stdout)
            self.assertFalse(report["linearizable"],
                             "an observation beside a mutator must not claim "
                             "linearizability")
            self.assertTrue(report["lock"]["contended"])
        finally:
            handle.close()

    def test_mutations_still_refuse_each_other(self):
        handle, _info = rootctl.acquire_lock(str(self.lock), 0, exclusive=True)
        try:
            proc = self.run_ctl("stop", "--json")
            self.assertEqual(proc.returncode, rootctl.EXIT_BUSY)
            self.assertEqual(self.timer(), {"enabled": False, "active": False})
        finally:
            handle.close()

    def test_concurrent_invocations_do_not_interleave(self):
        results = []

        def worker():
            results.append(self.run_ctl("start", "--json"))

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        codes = sorted(r.returncode for r in results)
        self.assertEqual(codes.count(rootctl.EXIT_BUSY), 2)
        self.assertEqual(codes.count(rootctl.EXIT_OK), 1)
        self.assertIs(self.hub.enabled, True)
        self.assertEqual(self.timer(), {"enabled": True, "active": True})


class TestSafetyBoundaries(RootctlHarness):
    def test_no_inflight_root_state_is_touched(self):
        state_dir = self.dir / "state"
        state_dir.mkdir()
        (state_dir / "root.lock").write_text("held")
        (state_dir / "state.json").write_text('{"run_id": "live", "status": "running"}')
        (state_dir / "root.log").write_text("log")
        self.assertEqual(self.run_ctl("stop").returncode, rootctl.EXIT_OK)
        self.assertEqual(self.run_ctl("start").returncode, rootctl.EXIT_OK)
        self.assertEqual((state_dir / "root.lock").read_text(), "held")
        self.assertIn('"status": "running"', (state_dir / "state.json").read_text())
        self.assertEqual((state_dir / "root.log").read_text(), "log")

    def test_never_stops_the_root_service_or_any_scope(self):
        self.run_ctl("stop")
        self.run_ctl("start")
        for argv in self.timer_argv():
            joined = " ".join(argv)
            self.assertNotIn(".service", joined)
            self.assertNotIn("scope", joined)
            for verb in ("kill", "stop", "restart", "daemon-reload", "mask", "isolate"):
                self.assertNotIn(verb, argv)

    def test_helper_contract_constants(self):
        self.assertEqual(rootctl.SCHEDULING_PATH, "/api/root/scheduling")
        self.assertEqual(rootctl.DEFAULT_TIMER_UNIT, "headless-root.timer")
        for a, b in ((rootctl.EXIT_OK, rootctl.EXIT_USAGE),
                     (rootctl.EXIT_USAGE, rootctl.EXIT_FAILED),
                     (rootctl.EXIT_FAILED, rootctl.EXIT_UNKNOWN),
                     (rootctl.EXIT_UNKNOWN, rootctl.EXIT_AUTH),
                     (rootctl.EXIT_AUTH, rootctl.EXIT_BUSY)):
            self.assertNotEqual(a, b)


class TestCorrectiveFindings(RootctlHarness):
    """G1/G7/G8/G9 + AK: timeouts, timer knob, final GET, origin display."""

    def test_bad_timeout_values_are_usage_errors_without_side_effects(self):
        # Non-numeric/non-finite timeouts are sanitized usage errors (exit 1,
        # no traceback, no Hub request, no timer change) on every config/env
        # path. Finite numerics clamp to 1..60 and proceed.
        for bad in ("abc", "nan", "inf", "-inf", [1], {"a": 1}):
            with self.subTest(path="config", bad=str(bad)):
                cfg = {"hub_url": self.hub.url, "token": SENTINEL_TOKEN,
                       "auth_mode": "bearer", "host_id": "hetzner",
                       "timeout_sec": bad}
                self.config.write_text(json.dumps(cfg))
                try:
                    self.config.chmod(0o600)
                except OSError:
                    pass
                before_reqs = len(self.hub.requests)
                before_timer = self.timer()
                proc = self.run_ctl("stop", "--json")
                self.assertEqual(proc.returncode, rootctl.EXIT_USAGE,
                                 proc.stdout + proc.stderr)
                self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
                self.assertEqual(len(self.hub.requests), before_reqs)
                self.assertEqual(self.timer(), before_timer)
                self.assertNoSentinel(proc)
            with self.subTest(path="env", bad=str(bad)):
                self.write_config()
                env = self.env(ROOTCTL_HUB_TIMEOUT=json.dumps(bad)
                               if isinstance(bad, (list, dict)) else str(bad))
                proc = self.run_ctl("stop", "--json", env=env)
                self.assertEqual(proc.returncode, rootctl.EXIT_USAGE,
                                 proc.stdout + proc.stderr)
                self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
                self.assertNoSentinel(proc)
        # Finite numerics clamp and the command proceeds without a traceback.
        for value, expected in ((-5, 1.0), ("-5", 1.0), (100000, 60.0),
                                ("100000", 60.0), ("0.2", 1.0)):
            with self.subTest(clamp=str(value)):
                self.assertEqual(
                    rootctl._coerce_timeout(value, "timeout_sec"), expected)
        self.write_config()
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True)
        cfg = json.loads(self.config.read_text())
        cfg["timeout_sec"] = 100000
        self.config.write_text(json.dumps(cfg))
        proc = self.run_ctl("stop", "--json")
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.write_config()

    def test_numeric_timeout_clamps_to_1_to_60(self):
        self.assertEqual(rootctl._coerce_timeout(100000, "timeout_sec"), 60.0)
        self.assertEqual(rootctl._coerce_timeout(-5, "timeout_sec"), 1.0)
        self.assertEqual(rootctl._coerce_timeout("0.2", "timeout_sec"), 1.0)
        for bad in ("abc", "nan", "inf", "-inf", [1], {"a": 1}):
            with self.subTest(bad=str(bad)):
                with self.assertRaises(rootctl.ConfigError):
                    rootctl._coerce_timeout(bad, "timeout_sec")

    def test_timer_unit_refuses_a_service(self):
        # G7: the knob can never target a .service unit or scope.
        env = self.env(ROOTCTL_TIMER_UNIT="headless-root.service")
        for command in ("start", "stop", "status"):
            proc = self.run_ctl(command, "--json", env=env)
            self.assertEqual(proc.returncode, rootctl.EXIT_USAGE, proc.stdout)
            self.assertIn(".timer", proc.stdout + proc.stderr)
        for argv in self.timer_argv():
            self.assertNotIn("headless-root.service", " ".join(argv))

    def test_start_with_unknown_timer_precheck_sends_no_put(self):
        # G9: no transient start enable when the timer pre-check is unknown.
        self.set_timer(fail_is_enabled=True,
                       fail_text="Failed to connect to bus: no user bus")
        proc = self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK)
        self.assertEqual([r for r in self.hub.requests if r["method"] == "PUT"],
                         [],
                         "an unknown timer pre-check must send no Hub PUT")
        self.assertIs(self.hub.enabled, False)
        self.assertIs(self.hub.applied, None)

    def test_hub_url_with_path_prints_origin_only(self):
        # G9: path segments (which may carry a secret) are never printed.
        self.write_config(hub_url=self.hub.url + "/tenant/%s" % SENTINEL_URL_SECRET)
        proc = self.run_ctl("status", "--json")
        blob = proc.stdout + proc.stderr
        self.assertNotIn(SENTINEL_URL_SECRET, blob)
        self.assertNotIn("/tenant/", blob)
        report = json.loads(proc.stdout)
        self.assertNotIn("/tenant/", report["hub_url"])
        self.assertTrue(report["hub_url"].startswith("http://127.0.0.1:"))
        self.assertNoSentinel(proc)

    def test_stop_uses_a_final_get_after_the_timer_step(self):
        # G8: stop re-reads the Hub after the timer step. A transient
        # pre-check failure still exits 3 (unverified-before) while the
        # verified final state is both_off.
        self.hub.behaviour = "server_error"
        proc = self.run_ctl("stop", "--json")
        first = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
        self.hub.behaviour = "normal"
        self.hub.enabled = True
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertEqual(report["verdict"], "both_off")
        gets = [r for r in self.hub.requests if r["method"] == "GET"]
        # pre-check GET + readback GET + final GET.
        self.assertGreaterEqual(len(gets), 3,
                                "stop must take a final GET after the timer step")

    def test_oversize_hub_response_is_bounded(self):
        # AK: removing the response size cap must be caught: an oversized
        # reply is never read unboundedly and never trusted blindly.
        self.hub.behaviour = "oversize"
        started = __import__("time").time()
        proc = self.run_ctl("status", "--json")
        elapsed = __import__("time").time() - started
        self.assertLess(elapsed, 60, "an oversized body defeated the bound")
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertNoSentinel(proc)


class TestSourceOnlyContract(unittest.TestCase):
    """F8: the contract is checked from the tracked source, never from .local/."""

    @classmethod
    def setUpClass(cls):
        raw = ROOTCTL.read_text(encoding="utf-8")
        cls.source = raw
        # Prose may name a .local file; code may not depend on one.
        end = raw.index('"""', raw.index('"""') + 3)
        cls.code = raw[end + 3:]
        cls.tests = pathlib.Path(__file__).read_text(encoding="utf-8")

    def test_no_tracked_code_reads_a_gitignored_fixture(self):
        # The documented default config path is fine; a private fixture is not.
        private = ".local/" + "author"
        fixture = "hub-" + "contract.json"
        for name, text in (("rootctl", self.code), ("test_rootctl.py", self.tests)):
            for forbidden in (private, fixture):
                self.assertNotIn(forbidden, text,
                                 "%s depends on a gitignored fixture" % name)
        reads = re.findall(r"read_text\([^)]*\)|open\([^)]*\)", self.code)
        self.assertTrue(reads)
        for hit in reads:
            if ".local" in hit:
                self.assertIn("quota-hub.json", hit,
                              "rootctl may only read the documented config: %s" % hit)

    def test_scheduling_path_is_the_only_hub_endpoint(self):
        endpoints = set(re.findall(r"[\"'](/api/[^\"']*)[\"']", self.source))
        self.assertEqual(endpoints, {"/api/root/scheduling"})

    def test_put_body_is_exactly_enabled(self):
        puts = re.findall(r"http_json\(config, \"PUT\", SCHEDULING_PATH, ([^)]*)\)",
                          self.source)
        self.assertTrue(puts)
        for payload in puts:
            self.assertEqual(payload.strip(), '{"enabled": enabled}')

    def test_no_pause_flag_and_no_invented_endpoint(self):
        self.assertNotIn("--pause-session", self.code)
        self.assertNotIn("pause_session", self.code)
        self.assertNotIn("/api/root/session", self.code)
        self.assertNotIn('"pause"', self.code)

    def test_systemd_faithful_state_sets_are_used(self):
        for state in ("disabled", "inactive", "enabled", "active", "masked",
                      "static", "failed", "activating"):
            self.assertIn(state, self.source)
        self.assertIn("ENABLED_KNOWN_STATES", self.source)
        self.assertIn("ACTIVE_KNOWN_STATES", self.source)

    def test_tests_reference_no_gitignored_fixture(self):
        for token in ("hub-" + "contract.json", ".local/" + "author"):
            self.assertNotIn(token, self.tests)


class TestCorrectiveR1R10(RootctlHarness):
    """R1-R10 corrective findings: sanitized errors, mapped transport failures,
    overflow/lock-wait, untouched-timer, truthful divergence, stale final GET,
    auth exit, transitional states, linearizable signal, docs/link."""

    def test_r1_credential_control_rejected_without_echo(self):
        self.config.write_text(json.dumps({
            "hub_url": self.hub.url, "auth_mode": "bearer",
            "token": SENTINEL_TOKEN + "\n", "host_id": "h", "timeout_sec": 2}))
        try:
            self.config.chmod(0o600)
        except OSError:
            pass
        before_reqs = len(self.hub.requests)
        before_timer = self.timer()
        for cmd in ("stop", "status"):
            proc = self.run_ctl(cmd, "--json")
            self.assertEqual(proc.returncode, rootctl.EXIT_USAGE, proc.stdout + proc.stderr)
            self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
            self.assertNoSentinel(proc)
        self.assertEqual(len(self.hub.requests), before_reqs)
        self.assertEqual(self.timer(), before_timer)
        self.write_config()
        # csrf/cookie variants (session mode)
        self.config.write_text(json.dumps({
            "hub_url": self.hub.url, "auth_mode": "session",
            "csrf_token": "BAD\x00", "cookie": SENTINEL_COOKIE}))
        try:
            self.config.chmod(0o600)
        except OSError:
            pass
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.assertNoSentinel(proc)
        self.write_config()

    def test_r1_catchall_never_tracebacks(self):
        proc = self.run_ctl("stop", "--json", ROOTCTL_LOCK_WAIT="abc")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.assertNoSentinel(proc)

    def _raw_server(self, payload):
        import socket
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        port = srv.getsockname()[1]
        stop = threading.Event()

        def serve():
            srv.settimeout(0.5)
            while not stop.is_set():
                try:
                    conn, _ = srv.accept()
                except OSError:
                    break
                try:
                    conn.settimeout(5)
                    conn.recv(65536)
                    conn.sendall(payload)
                except OSError:
                    pass
                finally:
                    try:
                        conn.close()
                    except OSError:
                        pass
        th = threading.Thread(target=serve, daemon=True)
        th.start()
        self.addCleanup(lambda: (stop.set(), srv.close()))
        return "http://127.0.0.1:%d" % port

    def test_r2_garbage_status_line_still_disables_timer(self):
        url = self._raw_server(b"GARBAGE-NOT-HTTP\r\n\r\n")
        self.write_config(hub_url=url)
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout + proc.stderr)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.assertNoSentinel(proc)
        self.assertEqual(self.timer()["enabled"], False)
        report = json.loads(proc.stdout)
        self.assertFalse(report["hub"]["known"])

    def test_r2_truncated_body_still_disables_timer(self):
        body = b'{"enabled": false}'
        hdr = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\nConnection: close\r\n\r\n"
        url = self._raw_server(hdr + body)
        self.write_config(hub_url=url)
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.assertEqual(self.timer()["enabled"], False)

    def test_r2_bad_url_mapped_to_unknown(self):
        self.write_config(hub_url="http://127.0.0.1:notaport")
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.write_config(hub_url="http://a..b.example/")
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.write_config()

    def test_r3_overflow_and_lockwait_inside_try(self):
        with self.assertRaises(rootctl.ConfigError):
            rootctl._coerce_timeout(10 ** 400, "timeout_sec")
        cfg = {"hub_url": self.hub.url, "token": SENTINEL_TOKEN,
               "auth_mode": "bearer", "timeout_sec": 10 ** 400}
        self.config.write_text(json.dumps(cfg))
        proc = self.run_ctl("stop", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_USAGE)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        self.assertEqual(self.hub.requests, [])
        self.write_config()

    def test_r4_hub_stage_failure_sends_no_timer_disable(self):
        self.hub.enabled = False
        self.hub.behaviour = "put_forbidden_only"
        proc = self.run_ctl("start", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH, proc.stdout)
        argv = self.timer_argv()
        disables = [a for a in argv if "disable" in a]
        self.assertEqual(disables, [], "a Hub-stage 403 must not touch the timer")

    def test_r5_divergent_reports_changed_not_untouched(self):
        self.set_timer(enabled=True, active=False)
        self.hub.behaviour = "final_flip"
        proc = self.run_fnc("start") if False else self.run_ctl("start", "--json")
        report = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        blob = json.dumps(report)
        self.assertIn("divergent", blob)
        self.assertNotIn("left untouched, divergence preserved", blob)

    def test_r6_failed_final_get_is_unknown_not_verified(self):
        calls = {"n": 0}

        def handler(handler_obj, server):
            calls["n"] += 1
            n = calls["n"]
            if handler_obj.command == "PUT":
                length = int(handler_obj.headers.get("Content-Length") or 0)
                if length:
                    handler_obj.rfile.read(length)
                body = json.dumps({"enabled": False,
                                   "updated_at": "2026-10-14T12:00:00Z"}).encode()
                handler_obj.send_response(200)
                handler_obj.send_header("Content-Length", str(len(body)))
                handler_obj.end_headers()
                handler_obj.wfile.write(body)
                return
            if n == 1:
                payload = {"enabled": True, "updated_at": "2026-10-14T00:00:00Z"}
                code = 200
            elif n == 2:
                payload = {"enabled": False, "updated_at": "2026-10-14T12:00:00Z"}
                code = 200
            else:
                payload = {"error": "gone"}
                code = 500
            body = json.dumps(payload).encode()
            handler_obj.send_response(code)
            handler_obj.send_header("Content-Length", str(len(body)))
            handler_obj.end_headers()
            handler_obj.wfile.write(body)
        srv = TinyServer(handler)
        self.addCleanup(srv.stop)
        self.write_config(hub_url=srv.url)
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertTrue(report["errors"], "a stale final GET must carry an error")
        self.assertIn("stale", json.dumps(report).lower())

    def test_r7_status_preserves_auth_exit(self):
        self.hub.behaviour = "forbidden"
        proc = self.run_ctl("status", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH, proc.stdout)
        self.assertNoSentinel(proc)
        self.hub.behaviour = "normal"

    def test_r8_maintenance_and_refreshing_are_unknown(self):
        for raw in ("maintenance", "refreshing"):
            with self.subTest(raw=raw):
                self.set_timer(is_enabled_raw="disabled", is_active_raw=raw)
                proc = self.run_ctl("status", "--json")
                report = json.loads(proc.stdout)
                self.assertFalse(report["timer"]["known"])
                self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN)
                self.assertNotEqual(report["verdict"], "both_off")

    def test_r9_linearizable_matches_contention(self):
        # Create the lock file with a mutation so the shared observation holds it.
        self.assertEqual(self.run_ctl("stop", "--json").returncode, rootctl.EXIT_OK)
        proc = self.run_ctl("status", "--json")
        report = json.loads(proc.stdout)
        self.assertTrue(report["linearizable"])
        self.assertFalse(report["lock"]["contended"])
        handle, _info = rootctl.acquire_lock(str(self.lock), 0, exclusive=True)
        try:
            proc = self.run_ctl("status", "--json")
            report = json.loads(proc.stdout)
            self.assertFalse(report["linearizable"])
            self.assertTrue(report["lock"]["contended"])
        finally:
            handle.close()

    def test_r10_docs_link_and_env(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("ROOTCTL_HUB_CSRF_TOKEN", readme)
        self.assertIn("ROOTCTL_HUB_COOKIE", readme)
        doc = (ROOT / "_docs" / "team" / "02-root.md").read_text(encoding="utf-8")
        self.assertIn("../../README.md#root-scheduling-switch", doc)
        self.assertNotIn("](../README.md#root-scheduling-switch", doc)


class TestCorrectiveN1N4(RootctlHarness):
    """N1-N4: deep-JSON boundary, PUT-ack vs readback-auth, urlsplit, budget."""

    DEEP_RAW = b"[" * 60000

    def _send_raw(self, handler_obj, code, raw):
        handler_obj.send_response(code)
        handler_obj.send_header("Content-Type", "application/json")
        handler_obj.send_header("Content-Length", str(len(raw)))
        handler_obj.end_headers()
        try:
            handler_obj.wfile.write(raw)
        except OSError:
            pass

    def _send_json(self, handler_obj, code, payload):
        self._send_raw(handler_obj, code, json.dumps(payload).encode())

    def _read_put_body(self, handler_obj):
        length = int(handler_obj.headers.get("Content-Length") or 0)
        if length:
            try:
                return handler_obj.rfile.read(length)
            except OSError:
                return b""
        return b""

    def test_n1_stop_get_deep_still_disables_timer(self):
        # N1 GET path: every GET returns deeply nested JSON (valid HTTP,
        # within 64 KiB, json.loads raises RecursionError). stop must still
        # disable the timer, exit unknown, never traceback or leak.
        # NOTE: TinyServer already consumes the PUT body before the factory
        # runs, so the factory must not re-read rfile (it would block).
        deep = self.DEEP_RAW
        calls = {"puts": 0}

        def handler(h, srv):
            if h.command == "GET":
                return self._send_raw(h, 200, deep)
            calls["puts"] += 1
            return self._send_json(h, 200, {"enabled": False,
                                            "updated_at": "2026-10-14T12:00:00Z"})

        srv = TinyServer(handler)
        self.addCleanup(srv.stop)
        self.write_config(hub_url=srv.url)
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        blob = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertNotIn("traceback", blob.lower())
        self.assertNotIn("RecursionError", blob)
        self.assertNoSentinel(proc)
        self.assertEqual(self.timer()["enabled"], False,
                         "stop with deep GET must still disable the timer")
        self.assertTrue(proc.stdout.strip(), "stop must still emit a report")
        report = json.loads(proc.stdout)
        self.assertFalse(report["hub"]["known"] and
                         report["verdict"] == "both_on")

    def test_n1_stop_put_deep_still_disables_timer(self):
        # N1 PUT path: GET is normal, PUT returns deeply nested JSON. stop
        # must still disable the timer with a sanitized unknown, no abort.
        deep = self.DEEP_RAW

        def handler(h, srv):
            if h.command == "GET":
                return self._send_json(h, 200, {"enabled": True,
                                                "updated_at": "2026-10-14T00:00:00Z"})
            return self._send_raw(h, 200, deep)

        srv = TinyServer(handler)
        self.addCleanup(srv.stop)
        self.write_config(hub_url=srv.url)
        self.set_timer(enabled=True, active=True)
        proc = self.run_ctl("stop", "--json")
        blob = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertNotIn("traceback", blob.lower())
        self.assertNotIn("RecursionError", blob)
        self.assertNoSentinel(proc)
        self.assertEqual(self.timer()["enabled"], False)
        report = json.loads(proc.stdout)
        self.assertTrue(report["errors"], "a deep PUT must carry an error")

    def test_n1_start_precheck_deep_sends_no_put(self):
        # N1 start pre-check: deep GET refuses start before any change.
        deep = self.DEEP_RAW
        seen = {"put": 0}

        def handler(h, srv):
            if h.command == "GET":
                return self._send_raw(h, 200, deep)
            seen["put"] += 1
            return self._send_json(h, 200, {"enabled": True,
                                            "updated_at": "2026-10-14T12:00:00Z"})

        srv = TinyServer(handler)
        self.addCleanup(srv.stop)
        self.write_config(hub_url=srv.url)
        self.set_timer(enabled=False, active=False)
        before = self.timer()
        proc = self.run_ctl("start", "--json")
        blob = (proc.stdout or "") + (proc.stderr or "")
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertNotIn("traceback", blob.lower())
        self.assertNotIn("RecursionError", blob)
        self.assertNoSentinel(proc)
        self.assertEqual(seen["put"], 0,
                         "a deep pre-check must send no Hub PUT")
        self.assertEqual(self.timer(), before)

    def test_n1_start_put_then_readback_deep_compensates(self):
        # N1 start compensation: PUT applies (Hub True) but the readback GET
        # is deep. start must compensate back to False, never leave True.
        # TinyServer consumes the PUT body, so intent is tracked by order:
        # first PUT is start's enabled=true, second is compensation false.
        deep = self.DEEP_RAW
        state = {"enabled": False, "gets": 0, "puts": []}

        def handler(h, srv):
            if h.command == "GET":
                state["gets"] += 1
                if state["gets"] == 1:
                    return self._send_json(h, 200, {"enabled": False,
                                                    "updated_at": "2026-10-14T00:00:00Z"})
                if state["gets"] == 2:
                    return self._send_raw(h, 200, deep)
                return self._send_json(h, 200, {"enabled": state["enabled"],
                                                "updated_at": "2026-10-14T12:00:00Z"})
            if not state["puts"]:
                state["puts"].append(True)
                state["enabled"] = True
            else:
                state["puts"].append(False)
                state["enabled"] = False
            return self._send_json(h, 200, {"enabled": state["enabled"],
                                            "updated_at": "2026-10-14T12:00:00Z"})

        srv = TinyServer(handler)
        self.addCleanup(srv.stop)
        self.write_config(hub_url=srv.url)
        self.set_timer(enabled=False, active=False)
        proc = self.run_ctl("start", "--json")
        blob = (proc.stdout or "") + (proc.stderr or "")
        self.assertNotEqual(proc.returncode, rootctl.EXIT_OK, proc.stdout)
        self.assertNotIn("traceback", blob.lower())
        self.assertNotIn("RecursionError", blob)
        self.assertNoSentinel(proc)
        self.assertEqual(state["enabled"], False,
                         "an applied PUT followed by deep readback must be compensated")
        self.assertIn(False, state["puts"],
                      "compensation PUT enabled=false must have been sent")
        report = json.loads(proc.stdout)
        self.assertTrue(report["errors"])

    def test_n2_acknowledged_put_then_auth_readback_attempts_restore(self):
        # N2: PUT acknowledged (Hub True) then GET 403. Only a definite PUT
        # refusal skips compensation; here compensation must be attempted and
        # the step must never claim nothing was changed. Exact method order
        # and Hub state are asserted.
        state = {"enabled": False, "gets": 0}
        methods = []

        def handler(h, srv):
            # TinyServer consumes the PUT body, so PUT intent is by order:
            # first PUT is start's enabled=true, second is compensation.
            if h.command == "GET":
                methods.append("GET")
                state["gets"] += 1
                if state["gets"] == 1:
                    return self._send_json(h, 200, {"enabled": False,
                                                    "updated_at": "2026-10-14T00:00:00Z"})
                if state["gets"] == 2:
                    return self._send_json(h, 403, {"error": "forbidden"})
                return self._send_json(h, 200, {"enabled": state["enabled"],
                                                "updated_at": "2026-10-14T12:00:00Z"})
            methods.append("PUT")
            if len([m for m in methods if m == "PUT"]) == 1:
                state["enabled"] = True
                return self._send_json(h, 200, {"enabled": True,
                                                "updated_at": "2026-10-14T12:00:00Z"})
            state["enabled"] = False
            return self._send_json(h, 200, {"enabled": state["enabled"],
                                            "updated_at": "2026-10-14T12:00:00Z"})

        srv = TinyServer(handler)
        self.addCleanup(srv.stop)
        self.write_config(hub_url=srv.url)
        self.set_timer(enabled=False, active=False)
        proc = self.run_ctl("start", "--json")
        self.assertEqual(proc.returncode, rootctl.EXIT_AUTH, proc.stdout)
        self.assertNoSentinel(proc)
        self.assertNotIn("traceback", (proc.stdout + proc.stderr).lower())
        # Exact sequence: pre-check GET, PUT true, readback GET 403,
        # compensation PUT false, compensation verify GET.
        self.assertEqual(methods, ["GET", "PUT", "GET", "PUT", "GET"],
                         "acknowledged PUT then 403 must attempt restore, methods=%r" % (methods,))
        self.assertEqual(state["enabled"], False,
                         "Hub must be restored to the pre-check intent")
        blob = proc.stdout
        self.assertNotIn("nothing was changed", blob,
                         "an acknowledged PUT then auth readback must never claim nothing changed")
        self.assertIn("compensation PUT hub scheduling enabled=false", blob)

    def test_n3_malformed_urlsplit_is_usage(self):
        # N3: http://[::1 raises ValueError in urlsplit -> sanitized exit 1.
        self.write_config(hub_url="http://[::1")
        before_timer = self.timer()
        before_reqs = len(self.hub.requests)
        for cmd in ("status", "stop"):
            proc = self.run_ctl(cmd, "--json")
            blob = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, rootctl.EXIT_USAGE, proc.stdout)
            self.assertNotIn("traceback", blob.lower())
            self.assertNoSentinel(proc)
        self.assertEqual(len(self.hub.requests), before_reqs)
        self.assertEqual(self.timer(), before_timer)
        self.assertEqual(self.timer_argv(), [],
                         "a malformed URL must send no systemctl call")
        self.write_config()

    def test_n4_http_error_body_timeout_preserved(self):
        # N4 unit: HubTimeoutError during an HTTPError body read must
        # propagate, not be swallowed into a 500 unknown.
        import urllib.error as urlerror

        class BadBody:
            code = 500
            headers = {}

            def read(self, *a, **k):
                raise rootctl.HubTimeoutError("budget fired during error body")

            def close(self):
                pass

            def getcode(self):
                return 500

        real_opener = rootctl._opener

        class FakeOpener:
            def open(self, *a, **k):
                raise urlerror.HTTPError("http://127.0.0.1/", 500, "boom", {}, BadBody())

        rootctl._OPENER = FakeOpener()
        try:
            cfg = {"hub_url": self.hub.url, "auth_mode": "bearer",
                   "token": SENTINEL_TOKEN, "timeout": 2}
            with self.assertRaises(rootctl.HubTimeoutError):
                rootctl.http_json(cfg, "GET", "/api/root/scheduling")
        finally:
            rootctl._OPENER = None
            rootctl._opener()

    def test_n4_slow_drip_500_is_bounded(self):
        # N4 integration (bounded): a slow-drip HTTP 500 body must still
        # honor the total budget instead of running past it by a socket
        # timeout per call.
        def drip_500(handler, server):
            if handler.command == "PUT":
                length = int(handler.headers.get("Content-Length") or 0)
                if length:
                    handler.rfile.read(length)
            handler.send_response(500)
            handler.send_header("Content-Length", "400")
            handler.end_headers()
            try:
                for _ in range(400):
                    handler.wfile.write(b" ")
                    handler.wfile.flush()
                    time.sleep(0.05)
            except OSError:
                pass

        drip = TinyServer(drip_500)
        self.addCleanup(drip.stop)
        self.write_config(hub_url=drip.url, timeout_sec=1)
        started = time.time()
        proc = self.run_ctl("status", "--json")
        elapsed = time.time() - started
        self.assertLess(elapsed, 20, "slow-drip 500 defeated the total budget")
        self.assertEqual(proc.returncode, rootctl.EXIT_UNKNOWN, proc.stdout)
        self.assertIn("budget", (proc.stdout + proc.stderr).lower())
        drip.stop()


if __name__ == "__main__":
    unittest.main()