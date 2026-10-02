#!/usr/bin/env python3
"""Reproduce a clean textual merge with incompatible concurrent changes.

Synthetic fixture, not a live coding-agent demo or Artifacts validation.
Requires Python 3 and Git. Leaves no repository behind.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(args, cwd, check=True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True,
                            timeout=30, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"})
    if check and result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result


def git(repo, *args):
    return run(["git", *args], repo).stdout.strip()


def write(repo, name, body):
    (repo / name).write_text(body)


def commit(repo, message, paths):
    git(repo, "add", "--", *paths)
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def checks(repo):
    p = run(["python3", "-m", "unittest", "discover", "-v"], repo, check=False)
    return {"exit_code": p.returncode, "passed": p.returncode == 0,
            "output": p.stderr.strip()}


def main():
    with tempfile.TemporaryDirectory(prefix="agent-merge-fixture-") as directory:
        repo = Path(directory)
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "Synthetic Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
        git(repo, "config", "commit.gpgsign", "false")
        write(repo, "greeting.py", "def greet(person):\n    return 'Hi ' + person['name']\n")
        write(repo, "test_greeting.py", "import unittest\nfrom greeting import greet\n\nclass Greeting(unittest.TestCase):\n    def test_existing_caller(self):\n        self.assertEqual(greet({'name': 'Ada'}), 'Hi Ada')\n")
        base = commit(repo, "baseline", ["greeting.py", "test_greeting.py"])
        git(repo, "checkout", "-b", "agent-a")
        write(repo, "greeting.py", "def greet(person):\n    return 'Hi ' + person['given']\n")
        write(repo, "test_greeting.py", "import unittest\nfrom greeting import greet\n\nclass Greeting(unittest.TestCase):\n    def test_existing_caller(self):\n        self.assertEqual(greet({'given': 'Ada'}), 'Hi Ada')\n")
        a = commit(repo, "A migrates greeting contract and existing caller", ["greeting.py", "test_greeting.py"])
        a_check = checks(repo)
        git(repo, "checkout", "-b", "agent-b", base)
        write(repo, "new_caller.py", "from greeting import greet\n\ndef welcome():\n    return greet({'name': 'Lin'})\n")
        write(repo, "test_new_caller.py", "import unittest\nfrom new_caller import welcome\n\nclass NewCaller(unittest.TestCase):\n    def test_welcome(self):\n        self.assertEqual(welcome(), 'Hi Lin')\n")
        b = commit(repo, "B adds caller on original contract", ["new_caller.py", "test_new_caller.py"])
        b_check = checks(repo)
        git(repo, "checkout", "agent-a")
        merge = run(["git", "merge", "--no-edit", "agent-b"], repo)
        combined = checks(repo)
        result = {"fixture": "synthetic, no agents or Cloudflare", "base": base,
                  "agent_a": {"commit": a, **a_check}, "agent_b": {"commit": b, **b_check},
                  "text_merge_exit": merge.returncode,
                  "combined": {"commit": git(repo, "rev-parse", "HEAD"), **combined}}
        print(json.dumps(result, indent=2))
        if not (a_check["passed"] and b_check["passed"] and merge.returncode == 0
                and not combined["passed"] and "KeyError: 'given'" in combined["output"]):
            raise SystemExit("Fixture did not produce the expected incompatibility")


if __name__ == "__main__":
    main()
