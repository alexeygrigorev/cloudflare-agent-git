import os, subprocess, sys, tempfile, time, unittest, json
from pathlib import Path
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "scripts" / "guards"))
import claims_check as C, review_gate as G

def ctx(own, peers):
    return {"workspace": "/w", "you": {"declaration": {"scopes": own}},
            "peers": [{"session": {"tag": t, "state": s}, "declarations": [{"workspace": "/w", "scopes": sc, "stale": st}] } for t, s, sc, st in peers]}

class Claims(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(C.evaluate(["a/x.md"], ctx(["a/**"], [("p", "running", ["b/**"], False)]))[0], [])
    def test_outside_own(self):
        self.assertTrue(C.evaluate(["b/x"], ctx(["a/**"], []))[0])
    def test_peer_conflict(self):
        self.assertTrue(C.evaluate(["b/x"], ctx(["**"], [("p", "running", ["b/**"], False)]))[0] == [])  # shared: warn only
        self.assertTrue(C.evaluate(["b/x"], ctx(["b/x"], []))[0] == [])
        self.assertTrue(C.evaluate(["b/x"], ctx([], [("p", "running", ["b/**"], False)]))[0])
    def test_stale_and_dead_ignored(self):
        self.assertEqual(C.evaluate(["b/x"], ctx(["b/**"], [("p", "running", ["b/**"], True), ("q", "failed", ["b/**"], False)]))[1], [])
    def test_expiry(self):
        now = 10_000_000_000
        def c(own_age, peer_age, peer_mode="edit"):
            return {"workspace": "/w",
                    "you": {"declaration": {"scopes": ["a/**"], "updated_at_ms": now - own_age * 60000}},
                    "peers": [{"session": {"tag": "p", "state": "running"},
                               "declarations": [{"workspace": "/w", "scopes": ["a/**"], "stale": False, "mode": peer_mode,
                                                 "updated_at_ms": now - peer_age * 60000}]}]}
        ev = lambda x: C.evaluate(["a/x"], x, now_ms=now, ttl=30)
        self.assertEqual(ev(c(5, 100))[0], [])                      # inside own fresh claim: warning only
        w = ev(c(5, 100))[1]
        self.assertTrue(any("claim by p expired 100 min ago: owner unconfirmed; ask the owner or the principal "
                            "before editing; age never releases a claim" in x for x in w))
        self.assertFalse(any(k in x.lower() for x in w for k in ("released", "free", "available")))
        # expired peer does not authorize the committer: outside own claim still fails
        outside = {**c(5, 100), "you": {"declaration": {"scopes": ["z/**"], "updated_at_ms": now - 5 * 60000}}}
        self.assertEqual(C.evaluate(["a/x"], outside, now_ms=now, ttl=30)[0], ["a/x: outside own claim"])
        unclaimed = {**c(5, 100), "you": {"declaration": {}}}
        self.assertTrue(any("expired" in x for x in C.evaluate(["a/x"], unclaimed, now_ms=now, ttl=30)[1]))
        self.assertTrue(ev(c(5, 5))[1])                              # live peer, shared: warning
        e = ev(c(45, 5))[0]                                          # own expired: no authority
        self.assertTrue(e and "claim expired 45 min ago: re-run aplexer work join to reclaim" in e[0])
        self.assertEqual(ev(c(29, 5))[0], [])                        # within TTL
        self.assertEqual(ev(c(5, 5, "read"))[1], [])                 # read-mode declarations do not block
        no_ts = {"workspace": "/w", "you": {"declaration": {"scopes": ["a/**"]}}, "peers": []}
        self.assertEqual(ev(no_ts)[0], [])                           # no timestamp: not expired

    def test_override(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(ctx(["a/**"], []), f); f.close()
        env = dict(os.environ)
        env.pop("PRINCIPAL_OVERRIDE", None)
        r = subprocess.run([sys.executable, str(R/"scripts/guards/claims_check.py"), "--context", f.name, "--files", "z"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        env["PRINCIPAL_OVERRIDE"] = "because"
        r = subprocess.run([sys.executable, str(R/"scripts/guards/claims_check.py"), "--context", f.name, "--files", "z"], env=env, capture_output=True, text=True)
        self.assertEqual((r.returncode, "because" in r.stderr), (0, True))
        os.unlink(f.name)
    def test_script_skips_in_ci(self):
        r = subprocess.run(["bash", str(R/"scripts/checks/claims.sh")], env={**os.environ, "CI": "1"}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)

class ClaimsRange(unittest.TestCase):
    """Pre-push range mode: only paths in the pushed commit range are checked (C-0506)."""
    NOW = 10_000_000_000

    def run_range(self, own, peers, pushed, staged, own_age=5):
        c = ctx(own, peers)
        c["you"]["declaration"]["updated_at_ms"] = int(time.time() * 1000) - own_age * 60000
        with tempfile.TemporaryDirectory() as t:
            git = lambda *a: subprocess.run(["git", "-C", t, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                            check=True, capture_output=True, text=True)
            git("init", "-q")
            Path(t, "base.txt").write_text("b")
            git("add", "base.txt"); git("commit", "-q", "-m", "base")
            for p in pushed:
                Path(t, p).parent.mkdir(parents=True, exist_ok=True); Path(t, p).write_text("x")
                git("add", p)
            git("commit", "-q", "-m", "pushed")
            for p in staged:
                Path(t, p).parent.mkdir(parents=True, exist_ok=True); Path(t, p).write_text("y")
                git("add", p)
            Path(t, "ctx.json").write_text(json.dumps(c))
            env = {k: v for k, v in os.environ.items() if k != "PRINCIPAL_OVERRIDE"}
            env.update(CHECK_MODE="range", CHECK_RANGE="HEAD~1..HEAD")
            return subprocess.run([sys.executable, str(R / "scripts/guards/claims_check.py"), "--context",
                                   str(Path(t, "ctx.json"))], cwd=t, env=env, capture_output=True, text=True)

    def test_sibling_staged_path_outside_range_ignored(self):
        r = self.run_range(["README.md"], [], ["README.md"], ["recovery/principal.md"])
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_pushed_path_outside_own_claim_still_fails(self):
        r = self.run_range(["README.md"], [], ["README.md", "other/x.md"], [])
        self.assertEqual(r.returncode, 1)
        self.assertIn("other/x.md: outside own claim", r.stderr)

    def test_pushed_path_with_peer_claim_fails(self):
        r = self.run_range([], [("p", "running", ["docs/**"], False)], ["docs/a.md"], ["zzz/staged.md"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("docs/a.md: claimed by live session p", r.stderr)
        self.assertNotIn("zzz/staged.md", r.stderr)

    def test_own_expired_claim_still_fails_in_range(self):
        r = self.run_range(["README.md"], [], ["README.md"], [], own_age=45)
        self.assertEqual(r.returncode, 1)
        self.assertIn("claim expired 45 min ago: re-run aplexer work join to reclaim", r.stderr)


class ClaimsAudit(unittest.TestCase):
    def test_dry_run_flags_expired_and_never_sends(self):
        now = 10_000_000_000
        d = lambda age: {"workspace": "/w", "mode": "edit", "scopes": ["a/**"], "updated_at_ms": now - age * 60000}
        c = {"you": {"session": {"tag": "me", "state": "running"}, "declaration": d(100)},
             "peers": [{"session": {"tag": "old", "state": "running"}, "declarations": [d(90)]},
                       {"session": {"tag": "new", "state": "running"}, "declarations": [d(2)]}]}
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "ctx.json"; p.write_text(json.dumps(c))
            r = subprocess.run([sys.executable, str(R / "scripts/ping/claims-audit.py"), "--context", str(p),
                                "--now-ms", str(now), "--local-dir", t],
                               capture_output=True, text=True, env={**os.environ, "CLAIM_TTL_MINUTES": "30"})
            self.assertEqual(r.returncode, 1)
            self.assertIn("DRY-RUN would send to old", r.stdout)
            self.assertNotIn("to new", r.stdout)
            self.assertIn("EXPIRED (annotation only, not released)", r.stdout)
            self.assertIn("FileBus claims: no reader, expiry unenforced", r.stdout)
            self.assertEqual(os.listdir(t), ["ctx.json"])


SHA = "a" * 40
class Review(unittest.TestCase):
    def run_(self, line, author=("c", "m1")):
        return G.check([(SHA,) + author], G.parse_reviews(line))
    def test_approved(self):
        self.assertEqual(self.run_(f"Review: approved sha={SHA[:12]} reviewer=x/m2"), [])
    def test_self_and_same_model(self):
        self.assertTrue(self.run_(f"Review: approved sha={SHA} reviewer=c/m2"))
        self.assertTrue(self.run_(f"Review: approved sha={SHA} reviewer=x/m1"))
    def test_wrong_sha_and_missing(self):
        self.assertTrue(self.run_(f"Review: approved sha={'b'*40} reviewer=x/m2"))
        self.assertTrue(self.run_(""))
        self.assertTrue(self.run_(f"Review: approved sha={SHA} reviewer=x/m2", ("", "")))
    def test_last_verdict_wins(self):
        t = f"Review: approved sha={SHA} reviewer=x/m2\nReview: changes-requested sha={SHA} reviewer=x/m2"
        self.assertTrue(self.run_(t))
    def test_git_range(self):
        d = tempfile.mkdtemp()
        g = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True, env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        g("init", "-q"); g("commit", "-q", "--allow-empty", "-m", "base"); g("commit", "-q", "--allow-empty", "-m", "x\n\nAgent: codex/gpt")
        cs = subprocess.check_output(["git", "-C", d, "log", "-1", "--format=%H"], text=True).strip()
        os.chdir(d)
        self.assertEqual(G.git_commits("HEAD~1..HEAD"), [(cs, "codex", "gpt")])

if __name__ == "__main__":
    unittest.main()
