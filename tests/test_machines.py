"""Availability selection and work routing over coordination/MACHINES.json."""
import importlib.machinery
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "machines.py"
loader = importlib.machinery.SourceFileLoader("machines", str(path))
spec = importlib.util.spec_from_loader("machines", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)

NOW = datetime(2026, 10, 11, 14, 0, 0, tzinfo=timezone.utc)


def ts(delta_seconds):
    return (NOW - timedelta(seconds=delta_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ssh_probe_for(answers, calls):
    def probe(alias):
        calls.append(alias)
        return answers.get(alias, False)
    return probe


class Registry(unittest.TestCase):
    def test_registry_records_how_each_machine_connects(self):
        reg = m.load_registry()
        self.assertIn("rule", reg)
        by_id = {x["id"]: x for x in reg["machines"]}
        self.assertEqual(set(by_id), {"hetzner", "win35", "founder-laptop"})
        for machine in reg["machines"]:
            for field in ("status", "online", "offline"):
                self.assertNotIn(field, machine)
                self.assertNotIn(field, machine["connect"])
        self.assertEqual(by_id["hetzner"]["connect"], {"mode": "inbound-ssh", "ssh": "hetzner"})
        for home in ("win35", "founder-laptop"):
            conn = by_id[home]["connect"]
            self.assertEqual(conn["mode"], "outbound-bus")
            self.assertIs(conn["inbound_ssh"], False)
            self.assertNotIn("ssh", conn)
            self.assertNotIn("ssh", by_id[home])
            self.assertTrue(conn["bus_device_ids"])
        self.assertIn("DESKTOP-FP4OP26", by_id["win35"]["connect"]["bus_device_ids"])
        self.assertEqual(reg["bus"]["hub"], "hetzner")
        self.assertGreater(m.checkin_window(reg), 0)

    def _write(self, td, machines):
        p = pathlib.Path(td) / "MACHINES.json"
        p.write_text(json.dumps({"machines": machines}))
        return p

    def test_load_registry_rejects_status_field(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, [{"id": "x", "connect": {"mode": "inbound-ssh", "ssh": "x"}, "status": "offline"}])
            with self.assertRaisesRegex(ValueError, "on/off status"):
                m.load_registry(p)

    def test_load_registry_rejects_ssh_route_for_home_machine(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, [{"id": "w", "connect": {"mode": "outbound-bus", "ssh": "win35",
                                                          "bus_device_ids": ["W"]}}])
            with self.assertRaisesRegex(ValueError, "must not carry an ssh route"):
                m.load_registry(p)

    def test_load_registry_requires_connect_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, [{"id": "x", "ssh": "x"}])
            with self.assertRaisesRegex(ValueError, "connect.mode"):
                m.load_registry(p)


class Selection(unittest.TestCase):
    def test_fresh_checkin_makes_home_machine_available_without_ssh(self):
        calls = []
        checkins = {"DESKTOP-FP4OP26": {"last_checkin": ts(60)}, "LAPTOP-PHA6TCNC": {"last_checkin": ts(120)}}
        got = m.select_available(probe=ssh_probe_for({"hetzner": True}, calls), checkins=checkins,
                                 now=NOW, window=900)
        self.assertEqual([x["id"] for x in got], ["hetzner", "win35", "founder-laptop"])
        self.assertEqual(calls, ["hetzner"])  # never ssh into home machines

    def test_stale_checkin_is_not_available(self):
        calls = []
        checkins = {"DESKTOP-FP4OP26": {"last_checkin": ts(3600)}, "LAPTOP-PHA6TCNC": {"last_checkin": ts(300)}}
        got = m.select_available(probe=ssh_probe_for({"hetzner": True}, calls), checkins=checkins,
                                 now=NOW, window=900)
        self.assertEqual([x["id"] for x in got], ["hetzner", "founder-laptop"])
        self.assertNotIn("win35", calls)
        self.assertNotIn("laptop", calls)

    def test_window_is_configurable(self):
        checkins = {"DESKTOP-FP4OP26": {"last_checkin": ts(3600)}}
        pool = m.list_machines(roles=["work"])
        self.assertEqual([x["id"] for x in m.select_available(pool, probe=lambda _a: False, checkins=checkins,
                                                                 now=NOW, window=7200)], ["win35"])
        self.assertEqual(m.select_available(pool, probe=lambda _a: False, checkins=checkins,
                                            now=NOW, window=600), [])

    def test_no_checkins_and_ssh_down_returns_empty(self):
        got = m.select_available(probe=lambda _a: False, checkins={}, now=NOW)
        self.assertEqual(got, [])

    def test_select_reachable_is_the_same_selection(self):
        self.assertIs(m.select_reachable, m.select_available)

    def test_outbound_machines_never_spawn_ssh(self):
        """Even with the default probe, home machines must not reach subprocess ssh."""
        seen = []
        real_probe = m.probe_ssh

        def recording_probe(alias, **kw):
            seen.append(alias)
            return False
        m.probe_ssh = recording_probe
        try:
            home = [x for x in m.list_machines() if x["connect"]["mode"] == "outbound-bus"]
            m.select_available(home, checkins={}, now=NOW)
        finally:
            m.probe_ssh = real_probe
        self.assertEqual(seen, [])


class CheckinSummary(unittest.TestCase):
    def test_registration_alone_is_not_a_checkin(self):
        ids = {"i1": {"device_id": "DESKTOP-FP4OP26", "created_at": ts(10), "project_id": "p"}}
        out = m.summarize_checkins(ids, {}, now=NOW)
        self.assertIsNone(out["DESKTOP-FP4OP26"]["last_checkin"])
        self.assertEqual(out["DESKTOP-FP4OP26"]["latest_identity"], "i1")

    def test_sends_acks_and_authority_presence_count(self):
        ids = {
            "w": {"device_id": "DESKTOP-FP4OP26", "created_at": ts(9000), "project_id": "p"},
            "l": {"device_id": "LAPTOP-PHA6TCNC", "created_at": ts(9000), "project_id": "p"},
            "h": {"device_id": "hetzner-role-authority", "created_at": ts(9000), "project_id": "p"},
        }
        msgs = {
            "1": {"sender_id": "l", "recipient_id": "h", "created_at": ts(500)},
            "2": {"sender_id": "h", "recipient_id": "w", "created_at": ts(50), "acked_at": ts(40)},
        }
        out = m.summarize_checkins(ids, msgs, now=NOW)
        self.assertEqual(out["LAPTOP-PHA6TCNC"]["last_checkin"], ts(500))
        self.assertEqual(out["DESKTOP-FP4OP26"]["last_checkin"], ts(40))
        authority = {"agents": [{"host": "DESKTOP-FP4OP26", "seen": (NOW - timedelta(seconds=5)).timestamp()}],
                     "leases": []}
        out = m.summarize_checkins(ids, msgs, authority, now=NOW)
        self.assertEqual(out["DESKTOP-FP4OP26"]["last_checkin"], ts(5))

    def test_live_role_lease_counts_as_current_checkin(self):
        authority = {"agents": [], "leases": [{"host": "DESKTOP-FP4OP26", "expires": NOW.timestamp() + 100}]}
        out = m.summarize_checkins({}, {}, authority, now=NOW)
        self.assertEqual(out["DESKTOP-FP4OP26"]["last_checkin"], ts(0))
        expired = {"agents": [], "leases": [{"host": "DESKTOP-FP4OP26", "expires": NOW.timestamp() - 1}]}
        self.assertEqual(m.summarize_checkins({}, {}, expired, now=NOW), {})

    def test_read_checkins_from_local_store(self):
        with tempfile.TemporaryDirectory() as td:
            store = pathlib.Path(td)
            (store / "identities.json").write_text(json.dumps(
                {"w": {"device_id": "DESKTOP-FP4OP26", "created_at": ts(100), "project_id": "p"}}))
            (store / "messages.json").write_text(json.dumps(
                {"1": {"sender_id": "w", "recipient_id": "w", "created_at": ts(30)}}))
            (store / "tokens.json").write_text(json.dumps({"w": "secret-token"}))
            out = m.read_checkins_from_store(store)
        self.assertEqual(out["DESKTOP-FP4OP26"]["last_checkin"], ts(30))
        self.assertNotIn("secret-token", json.dumps(out))

    def test_remote_read_goes_to_hub_only(self):
        reg = m.load_registry()
        reg = dict(reg, bus=dict(reg["bus"], store="/nonexistent/agent-bus-store"))
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            payload = {"identities": {"w": {"device_id": "DESKTOP-FP4OP26", "created_at": ts(5)}},
                       "messages": [{"sender_id": "w", "recipient_id": "w", "created_at": ts(5)}],
                       "authority": None}
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

        out = m.read_checkins(reg, runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "ssh")
        self.assertIn("hetzner", calls[0])
        self.assertNotIn("win35", calls[0])
        self.assertNotIn("laptop", calls[0])
        self.assertIn("DESKTOP-FP4OP26", out)

    def test_remote_failure_means_no_checkins(self):
        reg = m.load_registry()
        reg = dict(reg, bus=dict(reg["bus"], store="/nonexistent/agent-bus-store"))
        out = m.read_checkins(reg, runner=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 255, "", "x"))
        self.assertEqual(out, {})


class Routing(unittest.TestCase):
    def test_resolve_execution_target(self):
        self.assertEqual(m.resolve_execution_target(device_id="hetzner-rmthz"), "hetzner-rmthz")
        self.assertEqual(m.resolve_execution_target(device_id="DESKTOP-FP4OP26"), "win35-desktop-fp4op26")
        self.assertEqual(m.resolve_execution_target(device_id="win35-device-01"), "win35-desktop-fp4op26")
        self.assertEqual(m.resolve_execution_target(device_id="LAPTOP-PHA6TCNC"), "founder-laptop")
        self.assertEqual(m.resolve_execution_target(hostname="RMTHZ"), "hetzner-rmthz")
        self.assertEqual(m.resolve_execution_target(device_id="other-box"), "other-box")

    def test_hetzner_routes_over_ssh(self):
        r = m.work_route("hetzner")
        self.assertEqual((r["transport"], r["ssh"]), ("ssh", "hetzner"))

    def test_home_machines_route_as_bus_messages(self):
        checkins = {"DESKTOP-FP4OP26": {"last_checkin": ts(10), "latest_identity": "id-new", "project_id": "p"},
                    "win35-device-01": {"last_checkin": ts(9999), "latest_identity": "id-old", "project_id": "q"}}
        for key in ("win35", "DESKTOP-FP4OP26", "win35-desktop-fp4op26"):
            r = m.work_route(key, checkins=checkins)
            self.assertEqual(r["transport"], "bus")
            self.assertIsNone(r["ssh"])
            self.assertEqual(r["hub"], "hetzner")
            self.assertEqual(r["recipient"]["identity_id"], "id-new")
        r = m.work_route("founder-laptop")
        self.assertEqual(r["transport"], "bus")
        self.assertIsNone(r["recipient"])

    def test_unknown_machine_raises(self):
        with self.assertRaises(m.RouteError):
            m.work_route("nope")


class LaunchGatesHosts(unittest.TestCase):
    def setUp(self):
        lg_path = ROOT / "scripts" / "launch_gates.py"
        loader = importlib.machinery.SourceFileLoader("launch_gates", str(lg_path))
        spec = importlib.util.spec_from_loader("launch_gates", loader)
        self.g = importlib.util.module_from_spec(spec)
        loader.exec_module(self.g)

    def test_hetzner_by_probe_home_by_checkin(self):
        calls = []
        checkins = {"DESKTOP-FP4OP26": {"last_checkin": ts(30)}, "LAPTOP-PHA6TCNC": {"last_checkin": ts(99999)}}
        reached = self.g.reachable_work_hosts(probe=ssh_probe_for({"hetzner": True}, calls),
                                              checkins=checkins, now=NOW, window=900)
        self.assertEqual([x["id"] for x in reached], ["hetzner", "win35"])
        self.assertEqual(calls, ["hetzner"])

    def test_only_hetzner_when_no_checkins(self):
        reached = self.g.reachable_work_hosts(probe=lambda a: a == "hetzner", checkins={}, now=NOW)
        self.assertEqual([x["id"] for x in reached], ["hetzner"])


if __name__ == "__main__":
    unittest.main()
