"""Exercise only fresh test-owned processes and temporary directories."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor


SOURCE = Path(__file__).resolve().parents[1] / "prototype/demo/pair-example.py"
spec = importlib.util.spec_from_file_location("pair_example_cleanup", SOURCE)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def alive(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        stat = Path(f"/proc/{pid}/stat")
        return not stat.exists() or stat.read_text().split()[2] != "Z"
    except ProcessLookupError:
        return False


class OwnedProcessTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows job handle lifecycle")
    def test_windows_job_kills_owned_child_when_owner_exits_without_finally(self):
        with tempfile.TemporaryDirectory(prefix="ab-owned-crash-test-") as directory:
            root = Path(directory)
            program = (
                "import importlib.util,os,pathlib,sys; "
                "spec=importlib.util.spec_from_file_location('demo',sys.argv[1]); "
                "demo=importlib.util.module_from_spec(spec); spec.loader.exec_module(demo); "
                "scope=demo.OwnedProcesses(pathlib.Path(sys.argv[2])); "
                "scope.start([sys.executable,'-c','import time; time.sleep(60)']); os._exit(0)"
            )
            result = subprocess.run([sys.executable, "-c", program, str(SOURCE), str(root)], timeout=10)
            self.assertEqual(result.returncode, 0)
            pid = json.loads((root / "processes.json").read_text())["processes"][0]["pid"]
            deadline = time.monotonic() + 5
            while alive(pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(alive(pid))

    @unittest.skipUnless((SOURCE.parent.parent / ".build/node/src/local/main.js").is_file(), "requires the local Node build")
    def test_helper_cancellation_after_servers_start_removes_owned_temp_and_processes(self):
        # Space starts the selected backend; the next presenter pause receives
        # Ctrl+C. All resources are created by this invocation, never discovered.
        result = subprocess.run(["uv", "run", "python", str(SOURCE), "--backend", "local", "--interactive"],
                                cwd=SOURCE.parent.parent, input=" \x03", capture_output=True,
                                # A parent managed Python may inject its own
                                # stdlib home; uv selects the project's runtime.
                                env={key: value for key, value in os.environ.items() if key.upper() not in (
                                    "PYTHONHOME", "PYTHONPATH", "UV_INTERNAL__PYTHONHOME", "VIRTUAL_ENV")},
                                text=True, encoding="utf-8", timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("The shared starting repository is ready", result.stdout)
        self.assertIn("Demo stopped.", result.stdout)
        match = re.search(r"^Workspace: (.+)$", result.stdout, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertFalse(Path(match.group(1).strip()).exists())

    def test_close_reaps_owned_server_and_descendant_preserving_other_scope(self):
        with tempfile.TemporaryDirectory(prefix="ab-owned-process-test-") as directory:
            root = Path(directory)
            own_dir, peer_dir = root / "own", root / "peer"
            own_dir.mkdir()
            peer_dir.mkdir()
            owned, peer = demo.OwnedProcesses(own_dir), demo.OwnedProcesses(peer_dir)
            child_file = own_dir / "child.json"
            program = (
                "import json,pathlib,subprocess,sys,time; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':child.pid})); time.sleep(60)"
            )
            try:
                decoy = peer.start([sys.executable, "-c", "import time; time.sleep(60)"])
                server = owned.start([sys.executable, "-c", program, str(child_file)])
                deadline = time.monotonic() + 10
                while not child_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(child_file.exists())
                descendant = json.loads(child_file.read_text())["pid"]
                manifest = json.loads((own_dir / "processes.json").read_text())
                self.assertEqual(manifest["ownerPid"], os.getpid())
                self.assertEqual([entry["pid"] for entry in manifest["processes"]], [server.pid])
                owned.close()
                deadline = time.monotonic() + 5
                while alive(descendant) and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertFalse(alive(descendant))
                self.assertIsNotNone(server.poll())
                self.assertIsNone(decoy.poll())
                self.assertEqual(json.loads((own_dir / "processes.json").read_text())["processes"], [])
            finally:
                owned.close()
                peer.close()

    def test_timeout_reaps_child_and_clears_owned_manifest(self):
        with tempfile.TemporaryDirectory(prefix="ab-owned-timeout-test-") as directory:
            scope = demo.OwnedProcesses(Path(directory))
            with self.assertRaises(subprocess.TimeoutExpired):
                scope.run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.05, capture_output=True)
            self.assertEqual(scope.entries, {})
            self.assertEqual(json.loads((Path(directory) / "processes.json").read_text())["processes"], [])

    def test_concurrent_commands_serialize_manifest_updates(self):
        with tempfile.TemporaryDirectory(prefix="ab-owned-concurrency-test-") as directory:
            scope = demo.OwnedProcesses(Path(directory))
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: scope.run([sys.executable, "-c", "print('ok')"], timeout=5, capture_output=True), range(8)))
                self.assertTrue(all(result.returncode == 0 for result in results))
                self.assertEqual(scope.entries, {})
            finally:
                scope.close()


if __name__ == "__main__":
    unittest.main()
