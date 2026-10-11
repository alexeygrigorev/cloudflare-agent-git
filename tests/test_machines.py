"""Reachability selection over coordination/MACHINES.json."""
import importlib.machinery
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "machines.py"
loader = importlib.machinery.SourceFileLoader("machines", str(path))
spec = importlib.util.spec_from_loader("machines", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class Machines(unittest.TestCase):
    def test_registry_has_no_status_fields(self):
        reg = m.load_registry()
        self.assertIn("rule", reg)
        self.assertIn("machines", reg)
        for machine in reg["machines"]:
            self.assertNotIn("status", machine)
            self.assertNotIn("online", machine)
            self.assertNotIn("offline", machine)
            self.assertTrue(machine.get("ssh"))
            self.assertTrue(machine.get("id"))
        ids = {x["id"] for x in reg["machines"]}
        self.assertIn("hetzner", ids)
        self.assertIn("win35", ids)
        self.assertIn("founder-laptop", ids)

    def test_select_reachable_keeps_only_answering_hosts(self):
        pool = m.list_machines(roles=["work"])
        answers = {"hetzner": True, "win35": False, "laptop": True}

        def probe(alias):
            return answers.get(alias, False)

        reached = m.select_reachable(pool, probe=probe)
        self.assertEqual([x["id"] for x in reached], ["hetzner", "founder-laptop"])

    def test_select_reachable_all_down_returns_empty(self):
        reached = m.select_reachable(m.list_machines(), probe=lambda _a: False)
        self.assertEqual(reached, [])

    def test_resolve_execution_target_from_device_id(self):
        self.assertEqual(m.resolve_execution_target(device_id="hetzner-rmthz"), "hetzner-rmthz")
        self.assertEqual(
            m.resolve_execution_target(device_id="DESKTOP-FP4OP26"),
            "win35-desktop-fp4op26",
        )
        self.assertEqual(m.resolve_execution_target(hostname="RMTHZ"), "hetzner-rmthz")

    def test_load_registry_rejects_status_field(self):
        bad = {"machines": [{"id": "x", "ssh": "x", "status": "offline"}]}
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "MACHINES.json"
            p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, "on/off status"):
                m.load_registry(p)



class LaunchGatesHosts(unittest.TestCase):
    def setUp(self):
        lg_path = ROOT / "scripts" / "launch_gates.py"
        loader = importlib.machinery.SourceFileLoader("launch_gates", str(lg_path))
        spec = importlib.util.spec_from_loader("launch_gates", loader)
        self.g = importlib.util.module_from_spec(spec)
        loader.exec_module(self.g)

    def test_reachable_work_hosts_uses_probe(self):
        answers = {"hetzner": True, "win35": False, "laptop": False}
        reached = self.g.reachable_work_hosts(probe=lambda a: answers.get(a, False))
        self.assertEqual([x["id"] for x in reached], ["hetzner"])


if __name__ == "__main__":
    unittest.main()
