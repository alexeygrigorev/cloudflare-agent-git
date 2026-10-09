"""Native containment verification using only a new short-lived cmd child."""
import os
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/"scripts"/"recovery"))
from win35_root_job import WindowsJob, MEMORY_LIMIT, PROCESS_LIMIT

@unittest.skipUnless(os.name == "nt", "native Windows proof only")
class NativeJobTests(unittest.TestCase):
    def test_kernel_limits_and_owned_process(self):
        job = WindowsJob()
        try:
            self.assertEqual(job.query()["job_memory_limit_bytes"], MEMORY_LIMIT)
            self.assertEqual(job.query()["active_process_limit"], PROCESS_LIMIT)
            child = job.start([str(pathlib.Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"), "/d", "/c", "exit", "0"], str(pathlib.Path.cwd()))
            self.assertGreater(child.creation_filetime, 0)
            self.assertEqual(child.wait(10), 0)
        finally:
            job.close()

    def test_owned_job_kill_drains_new_descendants(self):
        job = WindowsJob()
        try:
            child = job.start([str(pathlib.Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"), "/d", "/c", "ping -n 30 127.0.0.1 >nul"], str(pathlib.Path.cwd()))
            self.assertIsNone(child.poll())
            job.kill()
            self.assertEqual(job.wait_empty(10)["active_processes"], 0)
            self.assertIsNotNone(child.wait(5))
        finally:
            job.close()

if __name__ == "__main__":
    unittest.main()
