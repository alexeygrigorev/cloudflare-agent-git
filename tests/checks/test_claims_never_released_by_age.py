import re, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[2]


class ClaimsNeverReleasedByAge(unittest.TestCase):
    FILES = ["scripts/guards/claims_check.py", "scripts/ping/claims-audit.py"]
    BAD_CMDS = ("leave", "release", "reassign", "delete", "remove", "revoke", "kill")

    def test_no_release_by_age(self):
        import ast
        msg = ("claims are never released, deleted or reassigned by age: the principal ruled that an expired claim is only "
               "annotated, warned about or reminded (see _docs/07-supervision.md)")
        for rel in self.FILES:
            src = (R / rel).read_text()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                    self.assertNotIn(name, ("unlink", "remove", "rmtree", "rmdir", "replace", "rename"), f"{rel}: {name}() {msg}")
                    if name in ("run", "Popen", "call", "check_call", "check_output"):
                        strs = [c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str)]
                        if "work" in strs:
                            for b in self.BAD_CMDS:
                                self.assertNotIn(b, strs, f"{rel}: aplexer work {b} {msg}")
                        self.assertFalse(any(re.search(r"\bwork (leave|release)", s) for s in strs), f"{rel}: {msg}")
                        self.assertNotIn("work leave", " ".join(strs), msg)


if __name__ == "__main__":
    unittest.main()
