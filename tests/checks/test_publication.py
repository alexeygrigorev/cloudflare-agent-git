import hashlib, json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/checks/publication.sh"
GOOD = "# A quiet day\n\n## Setup\n\nPlain text. See [the review](https://github.com/x/y/blob/d4a0456/r.md).\n"

class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.d)
        (self.d / "website/content/daily").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.d, check=True)
    def run_check(self, text, sha=True, local=None, env=None):
        page = self.d / "website/content/daily/2026-01-01.md"; page.write_text(text)
        meta = {"published": True}
        if sha: meta["article_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        page.with_suffix(".json").write_text(json.dumps(meta))
        if local is not None:
            c = self.d / ".local/journal/2026-01-01"; c.mkdir(parents=True, exist_ok=True)
            if local: (c / "check.json").write_text(json.dumps(local))
        e = dict(os.environ, PUBLICATION_ROOT=str(self.d)); e.pop("PRINCIPAL_OVERRIDE", None); e.update(env or {})
        return subprocess.run([str(SCRIPT), str(page.relative_to(self.d))], cwd=self.d, env=e, capture_output=True, text=True)
    def test_good(self): self.assertEqual(self.run_check(GOOD).returncode, 0)
    def test_good_with_check_json(self): self.assertEqual(self.run_check(GOOD, local={"verdict": "pass"}).returncode, 0)
    def test_missing_check_json(self): self.assertNotEqual(self.run_check(GOOD, local=False).returncode, 0)
    def test_failed_check_json(self): self.assertNotEqual(self.run_check(GOOD, local={"verdict": "fail"}).returncode, 0)
    def test_ci_sha_mismatch(self): self.assertNotEqual(self.run_check(GOOD, sha=False).returncode, 0)
    def test_hash(self): self.assertNotEqual(self.run_check(GOOD + "\nFixed in commit d4a0456b.\n").returncode, 0)
    def test_path(self): self.assertNotEqual(self.run_check(GOOD + "\nSee /home/alexey/x\n").returncode, 0)
    def test_secret(self): self.assertNotEqual(self.run_check(GOOD + "\nghp_" + "a1" * 12 + "\n").returncode, 0)
    def test_caps(self): self.assertNotEqual(self.run_check(GOOD + "\n## WHAT HAPPENED\n").returncode, 0)
    def test_forbidden(self): self.assertNotEqual(self.run_check(GOOD + "\n## Corrections\n").returncode, 0)
    def test_override(self):
        r = self.run_check(GOOD + "\n/home/alexey/x\n", env={"PRINCIPAL_OVERRIDE": "founder ok"})
        self.assertEqual(r.returncode, 0); self.assertIn("founder ok", r.stderr)
        self.assertIn("founder ok", (self.d / ".local/overrides.log").read_text())
if __name__ == "__main__": unittest.main()
