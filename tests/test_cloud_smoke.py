"""Run ownership and truthful evidence for the smoke client."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("cloud_smoke", Path(__file__).parents[1] / "prototype/demo/cloud-smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class SmokeOwnershipTests(unittest.TestCase):
    def test_no_cleanup_on_preflight_failure(self):
        runner = smoke.CloudSmokeRunner("http://localhost", "admin", "runner")
        with patch.object(runner, "http_request") as request:
            self.assertEqual(runner.run_cleanup(), (0, None))
            request.assert_not_called()

    def test_failed_nonmock_report_is_not_live_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = smoke.CloudSmokeRunner("https://example.invalid", "admin", "runner", report_path=str(Path(directory) / "report.json"))
            self.assertFalse(runner.generate_report(1)["proof"]["real_cloudflare_proof"])
            self.assertNotIn("cwd", smoke.get_tool_versions())

    def test_partial_cleanup_count_and_recovery_id_survive_report(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = smoke.CloudSmokeRunner("https://example.invalid", "admin", "runner", report_path=str(Path(directory) / "report.json"))
            runner.setup_attempted = True
            with patch.object(runner, "http_request", side_effect=[
                (200, {"deleted": 2, "remaining": ["canonical"], "complete": False}, b""),
                (200, {"repoCount": 2}, b""),
            ]):
                with self.assertRaisesRegex(RuntimeError, "incomplete"):
                    runner.run_cleanup()
            report = runner.generate_report(2, runner.cleanup_deleted, runner.cleanup_remaining_count)
            self.assertEqual(report["metrics"]["cleanup_deleted"], 2)
            self.assertEqual(report["run_id"], runner.run_id)
            self.assertFalse(report["proof"]["real_cloudflare_proof"])

    def test_backend_without_owned_cleanup_refused_before_setup(self):
        runner = smoke.CloudSmokeRunner("http://localhost", "admin", "runner")
        with patch.object(runner, "http_request", side_effect=[(200, {"sanitizedSnapshot": True}, b""), (200, {"repoCount": 0}, b"")]) as request:
            with self.assertRaisesRegex(RuntimeError, "owned demo cleanup"):
                runner.run_preflight()
            self.assertFalse(runner.setup_attempted)
            self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))

    def test_cleanup_keeps_unrelated_repositories(self):
        server = smoke.MockServerManager()
        runner = smoke.CloudSmokeRunner(server.base_url, server.admin_token, server.runner_token, is_mock=True)
        try:
            runner.run_preflight()
            runner.run_setup()
            peer = Path(server.git_root) / "peer.git"
            peer.mkdir()
            (peer / "keep").write_text("peer data")
            server.server.state["repos"]["peer"] = {"name": "peer", "is_canonical": False}
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                runner.run_cleanup()
            self.assertEqual((peer / "keep").read_text(), "peer data")
            self.assertIn("peer", server.server.state["repos"])
            code, _, _ = runner.http_request("DELETE", "/cloud/demo-repos", headers={"Authorization": "Bearer " + server.admin_token}, body={})
            self.assertEqual(code, 400)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
