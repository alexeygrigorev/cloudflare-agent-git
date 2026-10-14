#!/usr/bin/env python3
"""Offline contract tests for the additive Hub bindings in scripts/root/headless-root-run.sh.

Everything runs against a disposable HR_STATE and a fake HR_REPO (fake quota
gate, fake launch-codex.sh, fake root prompt). No canonical Root state, no
systemd, no service, no secret file, no principal file, no provider, no live
Root cycle is touched, and HR_DRY_RUN keeps the engine out of every default
case. These are source/offline results only: they prove nothing about runtime.

Covered:
- HR_RUN_ID strict path-safe validation, collision refusal, fail-closed (exit 78)
  before any lock/state mutation.
- HR_HUB_JOB_ID + HR_HUB_LEASE_EPOCH optional pair, strict validation, and the
  fail-closed behaviour of every half-specified / malformed variant.
- Structured bootstrap receipt after real lock+state with canonical JSON digest
  (recomputed host-side here), pid/pgid/pid_namespace/pid_start_ticks,
  state_sha256/script_sha256, native epoch distinct from the hub lease epoch.
- Stale hub_* cleared on every canonical run start and run end.
- Healthy-lock skip produces a distinguishable structured skipped outcome for the
  requested run id, never a started receipt, incumbent state unchanged and the
  incumbent process untouched.
- Identity-verified stale takeover, heartbeat/freeze, crash record, quota gate
  refusal and notes remain; legacy incumbents are held until their own timeout.
- First-action receipt is only advertised to the engine: never written,
  synthesized or PID-filled by the script.
- Hub start acknowledgement gate: missing / unreadable / mismatched / unbound
  (empty, unrelated or partial document) / symlinked ack all fail closed before
  any business execution or side effect. A matching private file proves only its
  binding; genuine issuer/manager authority remains held for business execution.
- headless-root-launch.sh forwards the hooks only when actually set.
"""

import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUN_SH = ROOT / "scripts" / "root" / "headless-root-run.sh"
LAUNCH_SH = ROOT / "scripts" / "root" / "headless-root-launch.sh"
CANON_STATE = pathlib.Path(os.path.expanduser("~/.local/state/headless-root"))

FAKE_GATE_ALLOW = """#!/usr/bin/env python3
import os, sys
sys.exit(int(os.environ.get("FAKE_GATE_RC", "0")))
"""
FAKE_GATE_REFUSE = """#!/usr/bin/env python3
import sys
sys.stderr.write("fake gate: weekly window below reserve\\n")
sys.exit(1)
"""
FAKE_LAUNCHER = """#!/usr/bin/env bash
printf 'launcher invoked\\n' >> "$FAKE_REPO/launcher-invocations.log"
printf 'args: %s\\n' "$*" >> "$FAKE_REPO/launcher-invocations.log"
cat > "$FAKE_REPO/last-prompt.md"
exit 0
"""


INV = "0123456789abcdef0123456789abcdef"   # caller service INVOCATION_ID (caller fixture, never manager evidence)
INV_B = "fedcba9876543210fedcba9876543210"


def canonical_digest(receipt):
    body = {k: v for k, v in receipt.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


class HubBindingBase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="cag-hub-test-"))
        self.repo = self.tmp / "repo"
        (self.repo / "scripts" / "root").mkdir(parents=True)
        (self.repo / ".local" / "metrics").mkdir(parents=True)
        (self.repo / "scripts" / "quota-gate.py").write_text(FAKE_GATE_ALLOW)
        (self.repo / "scripts" / "quota-gate.py").chmod(0o755)
        (self.repo / "scripts" / "launch-codex.sh").write_text(FAKE_LAUNCHER)
        (self.repo / "scripts" / "launch-codex.sh").chmod(0o755)
        (self.repo / "scripts" / "root" / "root-prompt.txt").write_text("fake root prompt\n")
        (self.repo / ".local" / "metrics" / "latest.json").write_text("{}")
        self.state = self.tmp / "state"
        (self.state / "runs").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ------------------------------------------------------------
    def base_env(self, **over):
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(self.tmp),
            "HR_REPO": str(self.repo),
            "HR_STATE": str(self.state),
            "HR_SKIP_METRICS_GUARD": "1",
            "HR_FREEZE_HEARTBEAT": "1",
            "HR_WINDOW_SEC": "60",
            "FAKE_REPO": str(self.repo),
        }
        env.update({k: v for k, v in over.items() if v is not None})
        return env

    def run_script(self, script=None, **over):
        proc = subprocess.run(
            ["bash", str(script or RUN_SH)],
            env=self.base_env(**over),
            stdin=subprocess.DEVNULL,  # fixture execution always receives finite EOF
            capture_output=True,
            text=True,
            timeout=30,  # each fixture is bounded independently of the suite budget
        )
        return proc

    def runs(self, name):
        return self.state / "runs" / name

    def read_json(self, path):
        return json.loads(pathlib.Path(path).read_text())

    def state_json(self):
        return self.read_json(self.state / "state.json")

    def launcher_invocations(self):
        log = self.repo / "launcher-invocations.log"
        return log.read_text() if log.exists() else ""

    def assert_digest_ok(self, receipt, path):
        self.assertEqual(receipt["digest_algo"], "sha256-canonical-json-v1")
        self.assertEqual(receipt["digest"], canonical_digest(receipt), "digest mismatch for %s" % path)

    def assert_receipt_private(self, path):
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600, "%s must be 0600, got %o" % (path, mode))
        self.assertFalse(os.path.islink(path))

    def bound(self, run_id, job="root-run:slot", lease="4", epoch=1, ack_edit=None, **over):
        """Hub-bound env + a fully bound ack file in the disposable state dir.

        Returns (ack_path, env). ack_edit: callable(dict) -> dict|str to damage the
        ack, or False to write none. Fixture only: it proves the script's gate, never
        that a real Hub issued anything.
        """
        ack = self.state / (run_id + ".ack.json")
        env = {
            "HR_RUN_ID": run_id,
            "HR_HUB_JOB_ID": job,
            "HR_HUB_LEASE_EPOCH": lease,
            "HR_HUB_START_ACK_FILE": str(ack),
            "HR_HUB_START_ACK_WAIT_SEC": "2",
            "INVOCATION_ID": INV,
        }
        env.update(over)
        doc = {"kind": "hub_start_ack", "launcher_invocation_id": "UNKNOWN", "run_id": run_id, "job_id": job, "hub_lease_epoch": int(lease), "native_epoch": epoch}
        for key, field in (("HR_HUB_HOST_ID", "host_id"), ("HR_HUB_LAUNCHER_TASK_ID", "launcher_task_id"),
                           ("HR_HUB_LAUNCHER_UNIT", "launcher_unit")):
            if env.get(key):
                doc[field] = env[key]
        if ack_edit is not False:
            out = ack_edit(doc) if ack_edit else doc
            ack.write_text(out if isinstance(out, str) else json.dumps(out))
            os.chmod(ack, 0o600)   # what a Hub must write: owner-only, never group/other-writable
        return ack, env

    def write_state(self, **fields):
        (self.state / "state.json").write_text(json.dumps(fields, indent=1))

    def hold_lock(self, seconds=30):
        """Hold root.lock from a separate process (never with a python flock probe)."""
        proc = subprocess.Popen(["flock", "--no-fork", str(self.state / "root.lock"), "sleep", str(seconds)])
        time.sleep(0.4)
        self.addCleanup(self._kill, proc)
        return proc

    def spawn_stale(self, seconds=30, hold_lock=False):
        cmd = ["setsid"] + (["flock", "--no-fork", str(self.state / "root.lock")] if hold_lock else []) + ["sleep", str(seconds)]
        proc = subprocess.Popen(cmd)
        # reap it as soon as it dies: an unreaped zombie keeps its group "alive" for kill -0
        threading.Thread(target=proc.wait, daemon=True).start()
        time.sleep(0.4)
        self.addCleanup(self._kill, proc)
        return proc

    @staticmethod
    def _kill(proc):
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


class TestRunIdValidation(HubBindingBase):
    def test_unbound_run_gets_generated_path_safe_run_id(self):
        proc = self.run_script(HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        started = list((self.state / "runs").glob("*.started.json"))
        self.assertEqual(len(started), 1)
        run_id = started[0].name[: -len(".started.json")]
        self.assertRegex(run_id, r"^[0-9]{8}T[0-9]{6}-[0-9]+$")
        receipt = self.read_json(started[0])
        self.assertIsNone(receipt["job_id"])
        self.assertIsNone(receipt["hub_lease_epoch"])
        self.assertEqual(receipt["run_id"], run_id)

    def test_invalid_run_id_fails_closed_without_state_mutation(self):
        bad = ["../evil", "a/b", ".hidden", "-leading", "a b", "x" * 65, "id;rm", "..", "a\tb", "sub/dir.json"]
        for value in bad:
            with self.subTest(run_id=value):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                proc = self.run_script(HR_RUN_ID=value, HR_DRY_RUN="1")
                self.assertEqual(proc.returncode, 78, "expected fail-closed for %r" % value)
                self.assertIn("HR_RUN_ID", proc.stderr)
                self.assertFalse((self.state / "state.json").exists())
                self.assertEqual(list((self.state / "runs").iterdir()), [])

    def test_valid_run_id_variants_are_accepted(self):
        for value in ["hostrun-1", "root-run:2026-10-14T20:30:00Z".replace(":", ""), "A_9.z", "0"]:
            with self.subTest(run_id=value):
                proc = self.run_script(HR_RUN_ID=value, HR_DRY_RUN="1")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(self.runs(value + ".started.json").exists())
                (self.state / "runs" / (value + ".started.json")).unlink()

    def test_empty_run_id_is_treated_as_unset(self):
        proc = self.run_script(HR_RUN_ID="", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(list((self.state / "runs").glob("*.started.json"))), 1)

    def test_run_id_collision_refused_and_evidence_not_overwritten(self):
        first = self.run_script(HR_RUN_ID="dup-1", HR_DRY_RUN="1")
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = self.runs("dup-1.started.json")
        before = (sha256_file(receipt), receipt.stat().st_mtime_ns)
        second = self.run_script(HR_RUN_ID="dup-1", HR_DRY_RUN="1")
        self.assertEqual(second.returncode, 78)
        self.assertIn("collision", second.stderr)
        self.assertEqual((sha256_file(receipt), receipt.stat().st_mtime_ns), before)

    def test_symlinked_receipt_path_is_refused(self):
        target = self.tmp / "outside.json"
        target.write_text('{"outside": true}')
        link = self.runs("sym-1.started.json")
        os.symlink(target, link)
        proc = self.run_script(HR_RUN_ID="sym-1", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 78)
        self.assertIn("collision", proc.stderr)
        self.assertEqual(json.loads(target.read_text()), {"outside": True})
        self.assertFalse((self.state / "state.json").exists())


class TestHubBindingValidation(HubBindingBase):
    def test_half_specified_binding_fails_closed(self):
        cases = [
            {"HR_HUB_JOB_ID": "root-run:slot-1"},
            {"HR_HUB_LEASE_EPOCH": "3"},
            {"HR_HUB_HOST_ID": "hetzner-1"},
            {"HR_HUB_LAUNCHER_UNIT": "headless-root-x"},
            {"HR_HUB_LAUNCHER_TASK_ID": "hub-job-1"},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                proc = self.run_script(HR_DRY_RUN="1", **extra)
                self.assertEqual(proc.returncode, 78)
                self.assertIn("HR_HUB_JOB_ID", proc.stderr)
                self.assertFalse((self.state / "state.json").exists())
                self.assertEqual(list((self.state / "runs").iterdir()), [])

    def test_malformed_binding_values_fail_closed(self):
        cases = [
            {"HR_HUB_JOB_ID": "../evil", "HR_HUB_LEASE_EPOCH": "1"},
            {"HR_HUB_JOB_ID": "a b", "HR_HUB_LEASE_EPOCH": "1"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": "0"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": "-1"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": "abc"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": "1.0"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": " 1"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": "1", "HR_HUB_HOST_ID": "../h"},
            {"HR_HUB_JOB_ID": "job", "HR_HUB_LEASE_EPOCH": "1", "HR_HUB_LAUNCHER_UNIT": "bad unit"},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                proc = self.run_script(HR_DRY_RUN="1", **extra)
                self.assertEqual(proc.returncode, 78, proc.stderr)
                self.assertFalse((self.state / "state.json").exists())
                self.assertEqual(list((self.state / "runs").iterdir()), [])

    def test_binding_recorded_cleared_and_distinct_from_native_epoch(self):
        _, env = self.bound(
            "bound-1", job="root-run:2026-10-14T20:30:00Z", lease="9", HR_HUB_HOST_ID="hetzner-1",
            HR_HUB_LAUNCHER_TASK_ID="hub-task-1", HR_HUB_LAUNCHER_UNIT="headless-root-x1", INVOCATION_ID=INV,
        )
        first = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = self.read_json(self.runs("bound-1.started.json"))
        self.assertEqual(receipt["job_id"], "root-run:2026-10-14T20:30:00Z")
        self.assertEqual(receipt["hub_lease_epoch"], 9)
        self.assertEqual(receipt["native_epoch"], 1)
        self.assertEqual(receipt["host_id"], "hetzner-1")
        self.assertEqual(receipt["launcher_task_id"], "hub-task-1")
        self.assertEqual(receipt["launcher_unit"], "headless-root-x1")
        self.assertEqual(receipt["launcher_invocation_id"], "UNKNOWN")
        summary = self.read_json(self.runs("bound-1.json"))
        self.assertEqual(summary["hub_binding"]["hub_lease_epoch"], 9)
        self.assertNotEqual(summary["native_epoch"], summary["hub_binding"]["hub_lease_epoch"])
        state = self.state_json()
        for key in ("hub_job_id", "hub_lease_epoch", "hub_host_id", "launcher_task_id", "launcher_unit", "launcher_invocation_id"):
            self.assertNotIn(key, state, "stale %s survived the run end" % key)
        self.assertEqual(state["epoch"], 1)
        self.assertEqual(state["status"], "finished")

        _, env2 = self.bound("bound-2", job="root-run:b", lease="10", epoch=2)
        second = self.run_script(HR_DRY_RUN="1", **env2)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.read_json(self.runs("bound-2.started.json"))["native_epoch"], 2)
        self.assertEqual(self.read_json(self.runs("bound-2.started.json"))["hub_lease_epoch"], 10)

    def test_stale_hub_keys_cleared_at_start_even_without_new_binding(self):
        now = int(time.time())
        self.write_state(
            run_id="old-1", pid=os.getpid(), pgid=os.getpgid(0), start=now - 10000, heartbeat=now - 10000,
            epoch=41, status="finished", hub_job_id="root-run:old", hub_lease_epoch="3",
            launcher_unit="old-unit", launcher_invocation_id="old-inv", host="old-host",
        )
        proc = self.run_script(HR_RUN_ID="fresh-1", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = self.read_json(self.runs("fresh-1.started.json"))
        self.assertIsNone(receipt["job_id"])
        self.assertIsNone(receipt["hub_lease_epoch"])
        self.assertIsNone(receipt["launcher_unit"])
        self.assertEqual(receipt["native_epoch"], 42)
        state = self.state_json()
        for key in ("hub_job_id", "hub_lease_epoch", "launcher_unit", "launcher_invocation_id"):
            self.assertNotIn(key, state)
        self.assertIsNone(self.read_json(self.runs("fresh-1.json"))["hub_binding"])


class TestStartedReceipt(HubBindingBase):
    def test_bootstrap_receipt_binds_everything_and_digest_verifies(self):
        _, env = self.bound("proof-1", lease="2", HR_HUB_HOST_ID="hetzner-1")
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        path = self.runs("proof-1.started.json")
        receipt = self.read_json(path)
        self.assert_digest_ok(receipt, path)
        self.assert_receipt_private(path)
        self.assertEqual(receipt["kind"], "observed_root_bootstrap")
        self.assertEqual(receipt["outcome"], "started")
        self.assertFalse(receipt["is_native_first_tool"])
        self.assertEqual(receipt["evidence_class"], "bootstrap_only")
        self.assertEqual(receipt["script_sha256"], sha256_file(RUN_SH))
        self.assertRegex(receipt["state_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(receipt["pid_namespace"], r"^pid:\[[0-9]+\]$")
        self.assertGreater(receipt["pid"], 0)
        self.assertGreater(receipt["pgid"], 0)
        self.assertIsInstance(receipt["pid_start_ticks"], int)
        self.assertEqual(receipt["first_action_receipt"], str(self.runs("proof-1.first-action.json")))
        self.assertTrue(receipt["dry_run"])
        state = self.state_json()
        self.assertEqual(state["run_id"], receipt["run_id"])
        self.assertEqual(state["pid"], receipt["pid"])
        self.assertEqual(state["pgid"], receipt["pgid"])
        self.assertEqual(state["epoch"], receipt["native_epoch"])
        self.assertEqual(state["pid_namespace"], receipt["pid_namespace"])
        self.assertEqual(state["pid_start_ticks"], receipt["pid_start_ticks"])
        for key in ("hub_job_id", "hub_lease_epoch", "hub_host_id", "launcher_task_id", "launcher_unit", "launcher_invocation_id"):
            self.assertNotIn(key, state, "hub binding must be cleared when the run ends")
        self.assertEqual(state["epoch"], receipt["native_epoch"])

    def test_binding_is_live_in_state_while_running_and_cleared_at_end(self):
        import threading

        seen = {}

        def watch():
            deadline = time.time() + 20
            while time.time() < deadline and "state" not in seen:
                try:
                    st = self.read_json(self.state / "state.json")
                except Exception:
                    continue
                if st.get("run_id") == "live-1":
                    seen["state"] = st
                    return
                time.sleep(0.05)

        watcher = threading.Thread(target=watch)
        watcher.start()
        _, env = self.bound(
            "live-1", lease="12", HR_HUB_HOST_ID="hetzner-1", HR_HUB_LAUNCHER_TASK_ID="hub-task-9",
            HR_HUB_LAUNCHER_UNIT="headless-root-live", INVOCATION_ID=INV_B,
        )
        proc = self.run_script(HR_DRY_RUN="3", **env)
        watcher.join(timeout=25)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("state", seen, "never observed the running state")
        st = seen["state"]
        self.assertEqual(st["hub_job_id"], "root-run:slot")
        self.assertEqual(st["hub_lease_epoch"], 12)
        self.assertEqual(st["hub_host_id"], "hetzner-1")
        self.assertEqual(st["launcher_task_id"], "hub-task-9")
        self.assertEqual(st["launcher_unit"], "headless-root-live")
        self.assertEqual(st["launcher_invocation_id"], "UNKNOWN")
        self.assertEqual(st["caller_env_invocation_id"], INV_B)
        self.assertEqual(st["pid_namespace"], self.read_json(self.runs("live-1.started.json"))["pid_namespace"])
        self.assertEqual(st["status"], "running")
        final = self.state_json()
        for key in ("hub_job_id", "hub_lease_epoch", "hub_host_id", "launcher_task_id", "launcher_unit", "launcher_invocation_id"):
            self.assertNotIn(key, final)

    def test_digest_detects_tampering_and_binding_swap(self):
        _, env = self.bound("tam-1", job="root-run:a", lease="4")
        self.run_script(HR_DRY_RUN="1", **env)
        receipt = self.read_json(self.runs("tam-1.started.json"))
        self.assertEqual(receipt["digest"], canonical_digest(receipt))
        tampered = dict(receipt, job_id="root-run:b")
        self.assertNotEqual(tampered["digest"], canonical_digest(tampered))
        tampered = dict(receipt, hub_lease_epoch=5)
        self.assertNotEqual(tampered["digest"], canonical_digest(tampered))
        tampered = dict(receipt, run_id="tam-2")
        self.assertNotEqual(tampered["digest"], canonical_digest(tampered))

    def test_started_receipt_precedes_business_execution(self):
        (self.repo / "scripts" / "quota-gate.py").write_text(FAKE_GATE_REFUSE)
        (self.repo / "scripts" / "quota-gate.py").chmod(0o755)
        proc = self.run_script(HR_RUN_ID="pre-1", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.runs("pre-1.started.json").exists())
        summary = self.read_json(self.runs("pre-1.json"))
        self.assertEqual(summary["outcome"], "quota_held")
        self.assertEqual(summary["exit_code"], 75)
        self.assertEqual(self.launcher_invocations(), "")

    def test_pid_namespace_guard_fails_closed(self):
        proc = self.run_script(HR_RUN_ID="ns-1", HR_PID_NAMESPACE_EXPECTED="pid:[0]", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 78)
        self.assertIn("pid namespace mismatch", proc.stderr)
        self.assertFalse((self.state / "state.json").exists())


class TestSkipOutcome(HubBindingBase):
    def _state_with_incumbent(self, status="running", hb_age=5):
        holder = self.hold_lock()
        now = int(time.time())
        self.write_state(
            run_id="incumbent-1", pid=holder.pid, pgid=os.getpgid(holder.pid),
            start=now - 60, heartbeat=now - hb_age, epoch=7, status=status,
            hub_job_id="root-run:incumbent", hub_lease_epoch="5",
        )
        return holder

    def test_healthy_lock_skip_is_structured_and_never_a_started_cycle(self):
        holder = self._state_with_incumbent()
        before = sha256_file(self.state / "state.json")
        _, env = self.bound("skip-1", job="root-run:new", lease="6", epoch=8)
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        path = self.runs("skip-1.skipped.json")
        self.assertTrue(path.exists())
        receipt = self.read_json(path)
        self.assert_digest_ok(receipt, path)
        self.assert_receipt_private(path)
        self.assertEqual(receipt["outcome"], "skipped")
        self.assertEqual(receipt["reason"], "healthy_incumbent")
        self.assertEqual(receipt["requested_run_id"], "skip-1")
        self.assertFalse(receipt["is_root_cycle"])
        self.assertIsNone(receipt["native_epoch"])
        self.assertEqual(receipt["incumbent"]["run_id"], "incumbent-1")
        self.assertEqual(receipt["incumbent"]["status"], "running")
        self.assertEqual(receipt["incumbent_state_sha256"], before)
        self.assertEqual(receipt["job_id"], "root-run:new")
        self.assertEqual(receipt["hub_lease_epoch"], 6)
        self.assertEqual(receipt["launcher_invocation_id"], "UNKNOWN")
        self.assertFalse(self.runs("skip-1.started.json").exists())
        self.assertFalse(self.runs("skip-1.json").exists())
        self.assertFalse(self.runs("skip-1.first-action.json").exists())
        self.assertEqual(sha256_file(self.state / "state.json"), before, "incumbent state must be untouched")
        self.assertEqual(self.state_json()["hub_job_id"], "root-run:incumbent")
        self.assertIsNone(holder.poll(), "healthy incumbent must not be killed")
        inbox = self.runs("incumbent-1.inbox.md")
        self.assertTrue(inbox.exists())
        self.assertIn("skip-1", inbox.read_text())

    def test_starting_incumbent_skip_is_distinguishable(self):
        self.hold_lock()
        proc = self.run_script(HR_RUN_ID="skip-2", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = self.read_json(self.runs("skip-2.skipped.json"))
        self.assertEqual(receipt["reason"], "starting_incumbent")
        self.assertEqual(receipt["incumbent"]["run_id"], "starting")
        self.assertEqual(receipt["incumbent"]["status"], "starting")
        self.assertIsNone(receipt["incumbent_state_sha256"])
        self.assertFalse(self.runs("skip-2.started.json").exists())
        self.assertFalse((self.state / "state.json").exists())

    def test_stale_takeover_still_produces_a_started_receipt(self):
        stale = self.spawn_stale(30, hold_lock=True)
        now = int(time.time())
        self.write_state(
            run_id="stale-1", pid=stale.pid, pgid=os.getpgid(stale.pid), start=now - 10000,
            heartbeat=now - 9000, epoch=11, status="running",
            pid_namespace=os.readlink("/proc/self/ns/pid"),
            pid_start_ticks=pathlib.Path("/proc/%d/stat" % stale.pid).read_text().rsplit(")", 1)[1].split()[19],
        )
        proc = self.run_script(HR_RUN_ID="take-1", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.runs("take-1.started.json").exists())
        self.assert_digest_ok(self.read_json(self.runs("take-1.started.json")), "take-1")
        superseded = self.runs("stale-1.superseded.json")
        self.assertTrue(superseded.exists())
        self.assertEqual(json.loads(superseded.read_text())["superseded_by"], "take-1")
        self.assertEqual(self.read_json(self.runs("take-1.started.json"))["native_epoch"], 12)
        for _ in range(50):
            if stale.poll() is not None:
                break
            time.sleep(0.2)
        self.assertIsNotNone(stale.poll(), "stale incumbent process group must be terminated")


class TestTakeoverGuard(HubBindingBase):
    def _stale_state(self, proc, **extra):
        now = int(time.time())
        identity = {"pid_namespace": os.readlink("/proc/self/ns/pid"),
                    "pid_start_ticks": pathlib.Path("/proc/%d/stat" % proc.pid).read_text().rsplit(")", 1)[1].split()[19]}
        identity.update(extra)
        self.write_state(run_id="stale-g", pid=proc.pid, pgid=os.getpgid(proc.pid), start=now - 10000,
                         heartbeat=now - 9000, epoch=5, status="running", **identity)

    def test_foreign_pid_namespace_group_is_never_signalled(self):
        stale = self.spawn_stale(30, hold_lock=True)
        self._stale_state(stale, pid_namespace="pid:[1]")
        proc = self.run_script(HR_RUN_ID="take-ns", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 1)
        self.assertIsNone(stale.poll(), "foreign-namespace group must not be signalled")
        self.assertIn("takeover refused", (self.state / "root.log").read_text())
        self.assertFalse(self.runs("take-ns.started.json").exists())

    def test_reused_pid_start_ticks_mismatch_is_never_signalled(self):
        stale = self.spawn_stale(30, hold_lock=True)
        self._stale_state(stale, pid_start_ticks="1")
        proc = self.run_script(HR_RUN_ID="take-tk", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 1)
        self.assertIsNone(stale.poll(), "a reused pid must not be signalled")
        self.assertIn("reused", (self.state / "root.log").read_text())

    def test_missing_identity_and_wrong_group_are_never_signalled(self):
        for label in ("missing namespace", "missing ticks", "wrong group"):
            with self.subTest(label=label):
                stale = self.spawn_stale(30, hold_lock=True)
                extra = {"pid_namespace": ""} if label == "missing namespace" else {"pid_start_ticks": ""} if label == "missing ticks" else {}
                self._stale_state(stale, **extra)
                if label == "wrong group":
                    state = self.state_json()
                    state["pgid"] = os.getpgid(0)
                    self.write_state(**state)
                before = sha256_file(self.state / "state.json")
                proc = self.run_script(HR_RUN_ID="take-missing", HR_DRY_RUN="1")
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertIsNone(stale.poll())
                self.assertEqual(sha256_file(self.state / "state.json"), before)
                self.assertFalse(self.runs("take-missing.started.json").exists())
                self._kill(stale)

    def test_matching_namespace_and_ticks_still_take_over(self):
        stale = self.spawn_stale(30, hold_lock=True)
        ns = os.readlink("/proc/self/ns/pid")
        ticks = open("/proc/%d/stat" % stale.pid).read().rsplit(")", 1)[1].split()[19]
        self._stale_state(stale, pid_namespace=ns, pid_start_ticks=ticks)
        proc = self.run_script(HR_RUN_ID="take-ok", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.runs("take-ok.started.json").exists())
        for _ in range(50):
            if stale.poll() is not None:
                break
            time.sleep(0.2)
        self.assertIsNotNone(stale.poll())


class TestFirstActionHonesty(HubBindingBase):
    def test_first_action_receipt_is_never_written_by_the_script(self):
        proc = self.run_script(HR_RUN_ID="fa-1", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.runs("fa-1.first-action.json").exists())
        summary = self.read_json(self.runs("fa-1.json"))
        self.assertFalse(summary["first_action_observed"])
        self.assertIsNone(summary["first_action_receipt"])
        self.assertIsNone(summary["native_session"])
        self.assertFalse(summary["genuine_root_cycle"], "a dry run must never claim a genuine Root cycle")
        source = RUN_SH.read_text()
        self.assertNotIn('> "$FIRST_ACTION_FILE"', source)

    def test_prompt_declares_the_first_action_contract_and_binding(self):
        _, env = self.bound("fa-2", lease="5")
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("fa-2.json"))
        self.assertEqual(summary["outcome"], "ok", summary)
        self.assertEqual(summary["exit_code"], 0, summary)
        prompt = self.runs("fa-2.prompt.md").read_text()
        self.assertIn("first-action receipt", prompt)
        self.assertIn("observed_native_tool", prompt)
        self.assertIn("observed_root_bootstrap", prompt)
        self.assertIn("NOT a first tool call", prompt)
        self.assertIn(str(self.runs("fa-2.first-action.json")), prompt)
        self.assertIn("root-run:slot", prompt)
        self.assertIn("hub_lease_epoch: 5", prompt)
        self.assertIn("native_epoch: 1", prompt)
        self.assertIn("This script never writes it for you", prompt)

    def test_existing_receipt_does_not_prove_a_native_first_action(self):
        receipt = self.runs("fa-existing.first-action.json")
        receipt.write_text(json.dumps({"kind": "observed_native_tool", "native_session_id": "caller-claim"}))
        planted_digest = sha256_file(receipt)
        proc = self.run_script(HR_RUN_ID="fa-existing", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("fa-existing.json"))
        self.assertTrue(summary["first_action_receipt_present"])
        self.assertEqual(sha256_file(receipt), planted_digest)
        self.assertFalse(summary["first_action_observed"])
        self.assertIsNone(summary["native_session"])
        self.assertFalse(summary["genuine_root_cycle"])
        for suffix in (".json", ".prompt.md", ".started.json"):
            self.assert_receipt_private(self.runs("fa-existing" + suffix))

    def test_real_engine_path_runs_fake_launcher_without_inventing_evidence(self):
        proc = self.run_script(HR_RUN_ID="real-1", HR_WINDOW_SEC="60")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("launcher invoked", self.launcher_invocations())
        summary = self.read_json(self.runs("real-1.json"))
        self.assertEqual(summary["outcome"], "ok")
        self.assertFalse(summary["dry_run"])
        self.assertEqual(summary["genuine_root_cycle"], "UNKNOWN")
        self.assertFalse(summary["first_action_observed"])
        self.assertFalse(self.runs("real-1.first-action.json").exists())
        self.assertEqual((self.repo / "last-prompt.md").exists(), True)


class TestHubStartAckGate(HubBindingBase):
    def _ack_env(self, run_id="ack-1", **extra):
        ack_edit = extra.pop("ack_edit", None)
        return self.bound(run_id, ack_edit=ack_edit, **extra)

    def test_missing_ack_refuses_business_execution(self):
        ack, env = self._ack_env(ack_edit=False)
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("ack-1.json"))
        self.assertEqual(summary["outcome"], "hub_start_ack_missing")
        self.assertEqual(summary["exit_code"], 75)
        self.assertEqual(summary["hub_start_ack"]["state"], "missing")
        self.assertFalse(summary["hub_start_ack"]["verified"])
        self.assertTrue(self.runs("ack-1.started.json").exists())
        self.assertEqual(self.launcher_invocations(), "")
        self.assertIn("ack-1", (self.state / "NEEDS-ALEXEY.md").read_text())
        self.assertFalse(ack.exists())

    def test_matching_ack_proceeds(self):
        ack, env = self._ack_env(ack_edit=lambda d: dict(d, issued="hub"))
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("ack-1.json"))
        self.assertEqual(summary["outcome"], "ok")
        self.assertFalse(summary["hub_start_ack"]["verified"])
        self.assertTrue(summary["hub_start_ack"]["binding_matched"])
        self.assertEqual(summary["hub_start_ack"]["issuer_authority"], "UNKNOWN")
        self.assertEqual(summary["hub_start_ack"]["sha256"], sha256_file(ack))

    def test_caller_matching_ack_cannot_authorize_business_execution(self):
        # Bound IDs and a caller's verified flag are data, not issuer/manager proof.
        _, env = self.bound("ack-forged", ack_edit=lambda d: dict(d, verified=True, issued="hub"),
                            HR_HUB_HOST_ID="fixture-host", HR_HUB_LAUNCHER_TASK_ID="fixture-task",
                            HR_HUB_LAUNCHER_UNIT="fixture-unit")
        proc = self.run_script(**env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("ack-forged.json"))
        self.assertEqual(summary["outcome"], "hub_start_ack_authority_held")
        self.assertEqual(summary["exit_code"], 75)
        self.assertFalse(summary["hub_start_ack"]["verified"])
        self.assertEqual(self.launcher_invocations(), "")
        self.assertFalse(self.runs("ack-forged.prompt.md").exists())
        self.assertIsNone(summary["native_session"])

    def test_mismatched_and_unreadable_ack_fail_closed(self):
        ack, env = self._ack_env(run_id="ack-2", ack_edit=lambda d: dict(d, job_id="root-run:other"))
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_json(self.runs("ack-2.json"))["outcome"], "hub_start_ack_mismatch")
        shutil.rmtree(self.state)
        (self.state / "runs").mkdir(parents=True)
        ack2, env2 = self._ack_env(run_id="ack-3", ack_edit=lambda d: "{oops")
        proc = self.run_script(HR_DRY_RUN="1", **env2)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_json(self.runs("ack-3.json"))["outcome"], "hub_start_ack_unreadable")
        self.assertEqual(self.launcher_invocations(), "")

    def test_unbound_and_partial_ack_fail_closed(self):
        # A start ack is only genuine when EVERY bound field is present, of the
        # exact type and equal. An empty document, an unrelated document, a partial
        # ack or one missing the native epoch / launcher binding is bound to
        # nothing and must never be reported as verified.
        full = {"kind":"hub_start_ack", "run_id": "ack-p1", "job_id": "root-run:slot", "hub_lease_epoch": 4, "native_epoch": 1,
                "launcher_invocation_id": "UNKNOWN"}
        cases = [
            ("empty object", {}),
            ("unrelated fields only", {"hello": "world", "issued": "hub"}),
            ("partial: run_id only", {"run_id": "ack-p1"}),
            ("partial: job_id only", {"job_id": "root-run:slot"}),
            ("partial: lease epoch only", {"hub_lease_epoch": 4}),
            ("partial: no lease epoch", {k: v for k, v in full.items() if k != "hub_lease_epoch"}),
            ("partial: no native epoch", {k: v for k, v in full.items() if k != "native_epoch"}),
            ("partial: no invocation id", {k: v for k, v in full.items() if k != "launcher_invocation_id"}),
            ("stringy lease epoch", dict(full, hub_lease_epoch="4")),
            ("boolean native epoch", dict(full, native_epoch=True)),
            ("wrong native epoch", dict(full, native_epoch=2)),
            ("wrong invocation id", dict(full, launcher_invocation_id=INV_B)),
            ("json list not object", ["run_id", "ack-p1"]),
        ]
        for label, doc in cases:
            with self.subTest(label=label):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                ack, env = self._ack_env(run_id="ack-p1", ack_edit=lambda d, doc=doc: doc)
                proc = self.run_script(HR_DRY_RUN="1", **env)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                summary = self.read_json(self.runs("ack-p1.json"))
                self.assertNotEqual(summary["outcome"], "ok", "%s must not proceed" % label)
                self.assertEqual(summary["exit_code"], 75)
                self.assertFalse(summary["hub_start_ack"]["verified"], label)
                self.assertIn(summary["hub_start_ack"]["state"], ("unbound", "unreadable", "mismatch"), label)
                self.assertEqual(self.launcher_invocations(), "", label)
                # the bootstrap receipt exists but is never a Root cycle / first tool
                self.assertTrue(self.runs("ack-p1.started.json").exists())
                started = self.read_json(self.runs("ack-p1.started.json"))
                self.assertFalse(started["is_native_first_tool"])
                self.assertIsNone(summary["native_session"])

    def test_bound_launcher_fields_must_be_in_the_ack(self):
        # host/task/unit are bound only when configured, and then they are required.
        for field, env_key in (("host_id", "HR_HUB_HOST_ID"), ("launcher_task_id", "HR_HUB_LAUNCHER_TASK_ID"),
                               ("launcher_unit", "HR_HUB_LAUNCHER_UNIT")):
            with self.subTest(field=field):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                _, env = self.bound("ack-b1", ack_edit=lambda d, f=field: {k: v for k, v in d.items() if k != f},
                                    **{env_key: "bound-value-1"})
                proc = self.run_script(HR_DRY_RUN="1", **env)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                summary = self.read_json(self.runs("ack-b1.json"))
                self.assertEqual(summary["outcome"], "hub_start_ack_unbound")
                self.assertEqual(self.launcher_invocations(), "")

    def test_group_writable_or_foreign_mode_ack_is_unreadable(self):
        for mode in (0o666, 0o644, 0o640, 0o400):
            with self.subTest(mode=oct(mode)):
                ack, env = self._ack_env(run_id="ack-m%d" % mode)
                os.chmod(ack, mode)
                proc = self.run_script(HR_DRY_RUN="1", **env)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(self.read_json(self.runs("ack-m%d.json" % mode))["outcome"], "hub_start_ack_unreadable")

    def test_hub_bound_run_requires_ack_file_and_safe_caller_data(self):
        cases = {
            "no ack file": dict(HR_HUB_JOB_ID="root-run:slot", HR_HUB_LEASE_EPOCH="4", INVOCATION_ID=INV),
            "invocation id with quote": dict(HR_HUB_JOB_ID="root-run:slot", HR_HUB_LEASE_EPOCH="4", INVOCATION_ID="x'\"+__import__('os')",
                                             HR_HUB_START_ACK_FILE=str(self.state / "a.json")),
            "bad wait": dict(HR_HUB_JOB_ID="root-run:slot", HR_HUB_LEASE_EPOCH="4", INVOCATION_ID=INV,
                             HR_HUB_START_ACK_FILE=str(self.state / "a.json"), HR_HUB_START_ACK_WAIT_SEC="x"),
        }
        for label, env in cases.items():
            with self.subTest(label=label):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                proc = self.run_script(HR_DRY_RUN="1", **env)
                self.assertEqual(proc.returncode, 78, "%s: %s" % (label, proc.stderr))
                self.assertFalse((self.state / "state.json").exists(), "no state mutation before refusal")
                self.assertEqual(list((self.state / "runs").iterdir()), [])
                self.assertEqual(self.launcher_invocations(), "")

    def test_hostile_invocation_id_cannot_inject_into_skip_receipt(self):
        # Every python heredoc must be quoted so no env value is ever interpolated
        # into Python source (the previous skipped_receipt interpolated them).
        for line in RUN_SH.read_text().splitlines():
            if "<<" in line and "PY" in line:
                self.assertIn("<<'PY'", line, "unquoted python heredoc: %s" % line)
        self.hold_lock()
        now = int(time.time())
        self.write_state(run_id="inc-x", pid=os.getpid(), pgid=os.getpgid(0), start=now - 60, heartbeat=now - 5, epoch=2, status="running")
        marker = self.tmp / "pwned"
        hostile = "a'+__import__('os').system('touch %s')+'" % marker
        proc = self.run_script(HR_RUN_ID="skip-inj", HR_DRY_RUN="1", INVOCATION_ID=hostile)
        self.assertEqual(proc.returncode, 78, proc.stderr)
        self.assertFalse(marker.exists())
        # a well-formed id on the same skip path is recorded verbatim, as data
        proc = self.run_script(HR_RUN_ID="skip-ok", HR_DRY_RUN="1", INVOCATION_ID=INV)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_json(self.runs("skip-ok.skipped.json"))["caller_env_invocation_id"], INV)

    def test_symlinked_ack_is_refused(self):
        # The ack must be a regular file. A symlink planted in the state dir must
        # not be able to supply a forged acknowledgement from outside it.
        outside = self.tmp / "outside.json"
        ack, env = self._ack_env(run_id="ack-s1", ack_edit=False)
        outside.write_text(json.dumps({"run_id": "ack-s1", "job_id": "root-run:slot", "hub_lease_epoch": 4, "native_epoch": 1,
                                       "launcher_invocation_id": "UNKNOWN"}))
        os.symlink(str(outside), str(ack))
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("ack-s1.json"))
        self.assertEqual(summary["outcome"], "hub_start_ack_unreadable")
        self.assertFalse(summary["hub_start_ack"]["verified"])
        self.assertEqual(self.launcher_invocations(), "")

    def test_unsafe_ack_path_is_refused(self):
        for value in ["relative/ack.json", "/etc/passwd.json", str(self.state / ".." / "out.json")]:
            with self.subTest(value=value):
                shutil.rmtree(self.state)
                (self.state / "runs").mkdir(parents=True)
                proc = self.run_script(
                    HR_DRY_RUN="1", HR_HUB_JOB_ID="root-run:slot", HR_HUB_LEASE_EPOCH="4",
                    HR_HUB_START_ACK_FILE=value, INVOCATION_ID=INV,
                )
                self.assertEqual(proc.returncode, 78, proc.stderr)
                self.assertFalse((self.state / "state.json").exists())


class TestPreservedSemantics(HubBindingBase):
    def test_heartbeat_descendant_streams_do_not_hold_caller_pipes(self):
        bindir = self.tmp / "bin"
        bindir.mkdir()
        # Record inherited streams and terminate the heartbeat's first sleep.
        # This uses no waiting descendant and cannot leave an orphaned fixture.
        fake_sleep = bindir / "sleep"
        fake_sleep.write_text(
            "#!/usr/bin/python3\n"
            "import json, os, pathlib, sys\n"
            "fds = {str(i): os.readlink('/proc/self/fd/%d' % i) for i in range(3)}\n"
            "pathlib.Path(os.environ['FAKE_REPO'], 'heartbeat-fds.json').write_text(json.dumps(fds))\n"
            "sys.exit(1)\n"
        )
        fake_sleep.chmod(0o755)
        proc = self.run_script(HR_RUN_ID="hb-streams", PATH=str(bindir) + ":" + self.base_env()["PATH"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        fds = self.read_json(self.repo / "heartbeat-fds.json")
        self.assertEqual(fds["0"], "/dev/null")
        self.assertEqual(fds["1"], str(self.state / "root.log"))
        self.assertEqual(fds["2"], str(self.state / "root.log"))
        self.assertIn("launcher invoked", self.launcher_invocations())

    def test_timer_path_without_hub_env_behaves_as_before(self):
        proc = self.run_script(HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summaries = [p for p in (self.state / "runs").glob("*.json") if not p.name.endswith((".started.json", ".skipped.json"))]
        self.assertEqual(len(summaries), 1)
        summary = self.read_json(summaries[0])
        self.assertEqual(summary["outcome"], "ok")
        self.assertIsNone(summary["hub_binding"])
        self.assertIsNone(summary["hub_start_ack"])
        self.assertEqual(self.launcher_invocations(), "")
        self.assertIn("quota gate: ", (self.state / "runs" / (summary["run_id"] + ".prompt.md")).read_text())
        state = self.state_json()
        self.assertEqual(state["status"], "finished")
        self.assertNotIn("hub_job_id", state)
        self.assertEqual(state["heartbeat"], state["start"], "HR_FREEZE_HEARTBEAT must still freeze the heartbeat")

    def test_crashed_previous_run_is_recorded(self):
        now = int(time.time())
        self.write_state(run_id="crash-1", pid=os.getpid(), pgid=os.getpgid(0), start=now - 10, heartbeat=now - 10, epoch=3, status="running")
        proc = self.run_script(HR_RUN_ID="after-crash", HR_DRY_RUN="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        record = self.runs("crash-1.superseded.json")
        self.assertTrue(record.exists())
        self.assertEqual(json.loads(record.read_text())["status"], "crashed")
        self.assertEqual(self.read_json(self.runs("after-crash.json"))["prev_run"], "crash-1")

    def test_quota_gate_refusal_keeps_rc75_and_notes(self):
        (self.repo / "scripts" / "quota-gate.py").write_text(FAKE_GATE_REFUSE)
        (self.repo / "scripts" / "quota-gate.py").chmod(0o755)
        _, env = self.bound("gate-1", lease="1")
        proc = self.run_script(HR_DRY_RUN="1", **env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.read_json(self.runs("gate-1.json"))
        self.assertEqual(summary["outcome"], "quota_held")
        self.assertEqual(summary["hub_binding"]["job_id"], "root-run:slot")
        self.assertIn("quota gate refused", (self.state / "root.log").read_text())

    def test_runs_stay_inside_the_disposable_state_and_never_read_canonical_state(self):
        # HOME points at the disposable tree, so a script that fell back to its
        # default STATE would create ~/.local/state/headless-root under it. The real
        # Root state is deliberately never read or hashed here.
        self.run_script(HR_RUN_ID="canon-1", HR_DRY_RUN="1")
        _, env = self.bound("canon-2", lease="1", epoch=2)
        self.run_script(HR_DRY_RUN="1", **env)
        self.assertFalse((self.tmp / ".local" / "state" / "headless-root").exists())
        self.assertTrue((self.state / "state.json").exists())
        source = RUN_SH.read_text()
        self.assertNotIn("/.local/state/headless-root/", source.replace("$HOME/.local/state/headless-root", ""))


class TestLaunchForwarding(HubBindingBase):
    def test_launch_forwards_only_set_hooks(self):
        bindir = self.tmp / "bin"
        bindir.mkdir()
        argv_file = self.tmp / "systemd-run-argv.txt"
        fake = bindir / "systemd-run"
        fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$ARGV_FILE"\n')
        fake.chmod(0o755)
        env = self.base_env(HR_RUN_ID="launch-1", HR_HUB_JOB_ID="root-run:slot", HR_HUB_LEASE_EPOCH="8")
        env["PATH"] = "%s:%s" % (bindir, env["PATH"])
        env["ARGV_FILE"] = str(argv_file)
        proc = subprocess.run(["bash", str(LAUNCH_SH)], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = argv_file.read_text().splitlines()
        self.assertIn("HR_RUN_ID=launch-1", argv)
        self.assertIn("HR_HUB_JOB_ID=root-run:slot", argv)
        self.assertIn("HR_HUB_LEASE_EPOCH=8", argv)
        self.assertNotIn("HR_HUB_HOST_ID=", argv)
        self.assertNotIn("HR_HUB_START_ACK_FILE=", argv)
        unit = [a for a in argv if a.startswith("--unit=headless-root-")][0]
        self.assertRegex(unit, r"^--unit=headless-root-[0-9]{14}-[0-9]+$")
        self.assertIn("--scope", argv)
        self.assertIn("-p", argv)

    def test_launch_uses_hub_unit_as_real_scope_name_and_never_forwards_secrets(self):
        bindir = self.tmp / "bin"
        bindir.mkdir()
        argv_file = self.tmp / "argv-unit.txt"
        fake = bindir / "systemd-run"
        fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$ARGV_FILE"\n')
        fake.chmod(0o755)
        env = self.base_env(HR_RUN_ID="launch-u", HR_HUB_JOB_ID="root-run:slot", HR_HUB_LEASE_EPOCH="8",
                            HR_HUB_LAUNCHER_UNIT="headless-root-hub-1")
        env["PATH"] = "%s:%s" % (bindir, env["PATH"])
        env["ARGV_FILE"] = str(argv_file)
        env["HUB_JOB_TOKEN"] = "super-secret-token-value"
        proc = subprocess.run(["bash", str(LAUNCH_SH)], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = argv_file.read_text()
        self.assertIn("--unit=headless-root-hub-1", argv.splitlines())
        self.assertNotIn("super-secret-token-value", argv)
        self.assertNotIn("HUB_JOB_TOKEN", argv)
        bad = self.base_env(HR_HUB_LAUNCHER_UNIT="bad unit;x")
        bad["PATH"] = env["PATH"]
        proc = subprocess.run(["bash", str(LAUNCH_SH)], env=bad, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 78)

    def test_launch_without_hooks_forwards_nothing(self):
        bindir = self.tmp / "bin"
        bindir.mkdir()
        argv_file = self.tmp / "argv.txt"
        fake = bindir / "systemd-run"
        fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$ARGV_FILE"\n')
        fake.chmod(0o755)
        env = self.base_env(HR_RUN_ID="")
        env["PATH"] = "%s:%s" % (bindir, env["PATH"])
        env["ARGV_FILE"] = str(argv_file)
        proc = subprocess.run(["bash", str(LAUNCH_SH)], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = argv_file.read_text()
        self.assertNotIn("HR_RUN_ID", argv)
        self.assertNotIn("HR_HUB_", argv)

    def test_both_scripts_parse(self):
        for script in (RUN_SH, LAUNCH_SH):
            proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, "%s: %s" % (script, proc.stderr))



class TestR8Corrections(HubBindingBase):
    def test_non_dry_hub_ack_never_reaches_gate_engine_or_metrics(self):
        bindir=self.tmp/'bin';bindir.mkdir()
        systemctl=bindir/'systemctl'
        systemctl.write_text('#!/usr/bin/env bash\nprintf called >> "$FAKE_REPO/metrics-called"\n')
        systemctl.chmod(0o755)
        (self.repo/'scripts'/'quota-gate.py').write_text(
            "import os,pathlib\npathlib.Path(os.environ['FAKE_REPO'],'gate-called').write_text('called')\n")
        edits=[False,lambda d:dict(d,kind='observed_root_bootstrap'),lambda d:dict(d,job_id='wrong-job'),None]
        for i,edit in enumerate(edits):
            rid='side-effects-%d'%i
            _,env=self.bound(rid,epoch=i+1,ack_edit=edit,HR_HUB_START_ACK_WAIT_SEC='0')
            proc=self.run_script(HR_SKIP_METRICS_GUARD='',PATH=str(bindir)+':'+self.base_env()['PATH'],**env)
            self.assertEqual(proc.returncode,0,proc.stderr)
            summary=self.read_json(self.runs(rid+'.json'))
            self.assertEqual(summary['exit_code'],75)
            self.assertFalse(summary['hub_start_ack']['verified'])
            self.assertFalse((self.repo/'metrics-called').exists())
            self.assertFalse((self.repo/'gate-called').exists())
            self.assertEqual(self.launcher_invocations(),'')

    def test_ack_cannot_alias_any_script_output_including_realpath(self):
        alias = self.state / 'alias'
        alias.symlink_to(self.state / 'runs', target_is_directory=True)
        for i, path in enumerate([self.state / 'state.json', self.runs('own.started.json'),
                                  self.runs('own.skipped.json'), self.runs('own.json'),
                                  self.runs('own.first-action.json'), alias / 'own.started.json',
                                  self.state / 'native-action.json']):
            with self.subTest(path=path):
                _, env = self.bound('reserved-%d' % i)
                env['HR_HUB_START_ACK_FILE'] = str(path)
                env['HR_HUB_FIRST_ACTION_FILE'] = str(self.state / 'native-action.json')
                proc = self.run_script(HR_DRY_RUN='0', **env)
                self.assertEqual(proc.returncode, 78, proc.stderr)
                self.assertIn('reserved output', proc.stderr)
                self.assertFalse((self.state / 'state.json').exists())
                self.assertEqual(self.launcher_invocations(), '')

    def test_bootstrap_kind_is_rejected_even_with_all_matching_metadata(self):
        for dry in ('0', None):
            rid = 'bootstrap-dry' if dry else 'bootstrap-held'
            _, env = self.bound(rid, ack_edit=lambda d: dict(d, kind='observed_root_bootstrap'))
            proc = self.run_script(HR_DRY_RUN=dry, **env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = self.read_json(self.runs(rid + '.json'))
            self.assertEqual(summary['outcome'], 'hub_start_ack_mismatch')
            self.assertFalse(summary['hub_start_ack']['binding_matched'])
            self.assertFalse(summary['hub_start_ack']['verified'])
            self.assertEqual(self.launcher_invocations(), '')

    def test_caller_invocation_is_unverified_and_optional(self):
        for i, caller in enumerate((INV_B, 'caller-service', None)):
            rid = 'caller-%d' % i
            _, env = self.bound(rid, epoch=i+1, INVOCATION_ID=caller)
            proc = self.run_script(HR_DRY_RUN='0', **env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = self.read_json(self.runs(rid + '.started.json'))
            self.assertEqual(receipt['launcher_invocation_id'], 'UNKNOWN')
            self.assertEqual(receipt['caller_env_invocation_id'], caller)
            self.assertEqual(receipt['caller_env_invocation_id_authority'], 'unverified')
            summary = self.read_json(self.runs(rid + '.json'))
            self.assertEqual(summary['launcher_invocation_id'], 'UNKNOWN')
            self.assertEqual(summary['hub_start_ack']['manager_authority'], 'UNKNOWN')

    def _capture_child_env(self, through_launch=False, mask='0022'):
        engine = self.repo / 'scripts' / 'launch-codex.sh'
        engine.write_text('''#!/usr/bin/env bash
cat > "$FAKE_REPO/last-prompt.md"
python3 - <<'PYENV'
import json,os,pathlib
p=pathlib.Path(os.environ['FAKE_REPO'])
m=os.umask(0); os.umask(m)
(p/'engine-env.json').write_text(json.dumps({'hub_keys':[k for k in os.environ if k.startswith('HUB_')],
 'invocation_present':'INVOCATION_ID' in os.environ, 'umask':m,
 'public_host':os.environ.get('HR_HUB_HOST_ID')}))
(p/'created-code.py').write_text('pass\\n'); (p/'created-dir').mkdir()
PYENV
''')
        bindir = self.tmp / 'bin'
        bindir.mkdir()
        fake = bindir / 'systemd-run'
        fake.write_text('''#!/usr/bin/python3
import json,os,pathlib,sys
pathlib.Path(os.environ['FAKE_REPO'],'scope-env.json').write_text(json.dumps({
 'hub_keys':[k for k in os.environ if k.startswith('HUB_')],
 'invocation_present':'INVOCATION_ID' in os.environ}))
a=sys.argv[1:]; cmd=a[a.index('env'):]; os.execvpe(cmd[0],cmd,os.environ)
''')
        fake.chmod(0o755)
        script = LAUNCH_SH if through_launch else RUN_SH
        env = self.base_env(HR_RUN_ID='child-env', HUB_JOB_TOKEN='fixture-token', HUB_URL='fixture-url',
                            HUB_NEW_SECRET='fixture-extra', INVOCATION_ID=INV_B,
                            PATH=str(bindir)+':'+self.base_env()['PATH'])
        proc = subprocess.run(['bash', '-c', 'umask "$1"; exec bash "$2"', 'fixture', mask, str(script)],
                              env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        capture = self.read_json(self.repo/'engine-env.json')
        self.assertEqual(capture['hub_keys'], [])
        self.assertFalse(capture['invocation_present'])
        self.assertEqual(capture['umask'], int(mask,8))
        if through_launch:
            scope = self.read_json(self.repo/'scope-env.json')
            self.assertEqual(scope['hub_keys'], [])
            self.assertFalse(scope['invocation_present'])
            self.assertIsNone(self.read_json(self.runs('child-env.started.json'))['caller_env_invocation_id'])
        self.assertEqual(stat.S_IMODE((self.repo/'created-code.py').stat().st_mode), 0o666 & ~int(mask,8))
        self.assertEqual(stat.S_IMODE((self.repo/'created-dir').stat().st_mode), 0o777 & ~int(mask,8))
        for suffix in ('.started.json','.json','.prompt.md','.codex.log','.last.txt'):
            self.assert_receipt_private(self.runs('child-env'+suffix))
        self.assert_receipt_private(self.state/'state.json')
        self.assertNotIn('fixture-token', self.runs('child-env.prompt.md').read_text())

    def test_direct_engine_environment_drops_hub_secrets_and_restores_umask(self):
        self._capture_child_env(mask='0027')

    def test_scope_inherited_child_environment_is_sanitized_and_umask_preserved(self):
        self._capture_child_env(through_launch=True)

    def test_public_hr_binding_survives_scope_without_raw_hub_environment(self):
        bindir=self.tmp/'bin';bindir.mkdir()
        fake=bindir/'systemd-run'
        fake.write_text('''#!/usr/bin/python3
import json,os,pathlib,sys
pathlib.Path(os.environ['FAKE_REPO'],'scope-binding.json').write_text(json.dumps({
 'hub_keys':[k for k in os.environ if k.startswith('HUB_')],
 'job':os.environ.get('HR_HUB_JOB_ID'),'host':os.environ.get('HR_HUB_HOST_ID'),
 'invocation_present':'INVOCATION_ID' in os.environ}))
a=sys.argv[1:]; cmd=a[a.index('env'):]; os.execvpe(cmd[0],cmd,os.environ)
''');fake.chmod(0o755)
        _,env=self.bound('public-binding',HR_HUB_HOST_ID='public-host')
        proc=self.run_script(script=LAUNCH_SH, HR_DRY_RUN='0', HUB_JOB_TOKEN='fixture-token',
                             HUB_URL='fixture-url',PATH=str(bindir)+':'+self.base_env()['PATH'],**env)
        self.assertEqual(proc.returncode,0,proc.stderr)
        scope=self.read_json(self.repo/'scope-binding.json')
        self.assertEqual(scope,{'hub_keys':[],'job':'root-run:slot','host':'public-host','invocation_present':False})
        receipt=self.read_json(self.runs('public-binding.started.json'))
        self.assertEqual(receipt['job_id'],'root-run:slot');self.assertEqual(receipt['host_id'],'public-host')
        self.assertEqual(receipt['launcher_invocation_id'],'UNKNOWN')
        self.assertIsNone(receipt['caller_env_invocation_id'])

    def test_cgroup_substring_is_not_unit_membership(self):
        _,env=self.bound('cgroup-u',HR_HUB_LAUNCHER_UNIT='u')
        proc=self.run_script(HR_DRY_RUN='0',**env)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertFalse(self.read_json(self.runs('cgroup-u.started.json'))['launcher_unit_in_cgroup'])

    def test_exact_cgroup_leaf_positive_and_negative(self):
        # Execute the production receipt writer with only its proc cgroup read mocked.
        # This is source evidence, never an actual manager qualification.
        from unittest.mock import patch
        source=RUN_SH.read_text().split('started_receipt() {',1)[1]
        code=source.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        sf=self.state/'state.json';sf.write_text('{}')
        real_open=open
        for i,cg in enumerate(('0::/user.slice/u.scope\n','0::/user.slice/not-u.scope\n','0::/u.scope/child\n')):
            output=self.runs('cg-%d.started.json'%i)
            args=['receipt',str(output),'cg-test','1','20','20','pid:[1]','1','','host','','','','','u','UNKNOWN','0','now','1','fa',str(sf),str(RUN_SH),'']
            def fake_open(path,*a,**kw):
                if path=='/proc/self/cgroup':
                    import io
                    return io.StringIO(cg)
                return real_open(path,*a,**kw)
            with patch.object(sys,'argv',args),patch('builtins.open',fake_open): exec(compile(code,'production-receipt','exec'),{})
            self.assertEqual(self.read_json(output)['launcher_unit_in_cgroup'], i==0)

    def test_skipped_id_collision_preserves_prior_evidence_and_incumbent(self):
        holder=self.hold_lock()
        first=self.run_script(HR_RUN_ID='skip-dup',HR_DRY_RUN='0')
        self.assertEqual(first.returncode,0,first.stderr)
        path=self.runs('skip-dup.skipped.json')
        before=(sha256_file(path),path.stat().st_mtime_ns)
        proc=self.run_script(HR_RUN_ID='skip-dup',HR_DRY_RUN='0')
        self.assertEqual(proc.returncode,78,proc.stderr)
        self.assertEqual((sha256_file(path),path.stat().st_mtime_ns),before)
        self.assertIsNone(holder.poll())
        self.assertFalse(self.runs('skip-dup.started.json').exists())

    def test_ack_wait_exceeding_window_plus_grace_refused_before_state(self):
        _,env=self.bound('wait-limit',ack_edit=False,HR_HUB_START_ACK_WAIT_SEC='181')
        start=time.monotonic();proc=self.run_script(HR_DRY_RUN='0',**env)
        self.assertEqual(proc.returncode,78,proc.stderr)
        self.assertIn('WINDOW+GRACE',proc.stderr)
        self.assertLess(time.monotonic()-start,5)
        self.assertFalse((self.state/'state.json').exists())

    def test_missing_ack_wait_is_bounded_and_never_calls_engine(self):
        _,env=self.bound('wait-bounded',ack_edit=False,HR_HUB_START_ACK_WAIT_SEC='1')
        start=time.monotonic();proc=self.run_script(**env)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertLess(time.monotonic()-start,12)
        summary=self.read_json(self.runs('wait-bounded.json'))
        self.assertEqual(summary['outcome'],'hub_start_ack_missing')
        self.assertEqual(self.launcher_invocations(),'')

    def test_legacy_incumbent_is_held_until_its_own_timeout_then_resume(self):
        holder=self.spawn_stale(6,hold_lock=True)
        now=int(time.time())
        self.write_state(run_id='legacy',pid=holder.pid,pgid=os.getpgid(holder.pid),
                         start=now-10000,heartbeat=now-10000,epoch=3,status='running')
        before=sha256_file(self.state/'state.json')
        proc=self.run_script(HR_RUN_ID='legacy-held',HR_DRY_RUN='0')
        self.assertEqual(proc.returncode,1,proc.stderr)
        self.assertIsNone(holder.poll())
        self.assertEqual(sha256_file(self.state/'state.json'),before)
        self.assertIn('legacy upgrade held until incumbent self-timeout',(self.state/'root.log').read_text())
        holder.wait(timeout=8)
        self.assertEqual(holder.returncode,0,'incumbent must end normally, never be signalled')
        proc=self.run_script(HR_RUN_ID='legacy-resumed',HR_DRY_RUN='0')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertTrue(self.runs('legacy-resumed.started.json').exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)