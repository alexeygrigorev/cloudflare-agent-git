"""AST-based disjointness check for the G3 no-symbol-overlap claim.

Reports, from the two candidate trees, the files each task changed and the
top-level symbols each task DEFINES. Asserts the two sets are disjoint.
This is a property of the patches only. It is NOT a statement about any
external comparator tool's detection: no such tool was executed here.
"""
import ast
import pathlib
import re
import subprocess
import sys


def defined_symbols(path):
    """Only Python sources are AST-parsed. A task's changed-file list legitimately
    includes markdown notes; parsing those raises SyntaxError on ordinary prose."""
    if not path.endswith(".py"):
        return set()
    tree = ast.parse(pathlib.Path(path).read_text())
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def mentions(text, symbol):
    """Identifier-token match, not raw substring.

    A raw substring test reports A's `read` as "mentioned" by B whenever B
    writes `read_all`, which is a false positive, not a real cross-reference.
    """
    return re.search(rf"\b{re.escape(symbol)}\b", text) is not None


def changed_files(repo, base, head):
    """Diff base..head explicitly. Never diff against a worktree HEAD that may
    already carry another task's merge - that silently attributes both patches
    to one task (a mistake this checker was written to make visible)."""
    out = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=repo, capture_output=True, text=True, check=True).stdout.split()
    return sorted(out)


def main():
    a_repo, b_repo, base = sys.argv[1], sys.argv[2], sys.argv[3]
    a_head = sys.argv[4] if len(sys.argv) > 4 else "HEAD"
    b_head = sys.argv[5] if len(sys.argv) > 5 else "HEAD"
    a_files = changed_files(a_repo, base, a_head)
    b_files = changed_files(b_repo, base, b_head)
    a_syms = set().union(*[defined_symbols(f"{a_repo}/{f}") for f in a_files]) if a_files else set()
    b_syms = set().union(*[defined_symbols(f"{b_repo}/{f}") for f in b_files]) if b_files else set()

    print(f"A changed files : {a_files}")
    print(f"B changed files : {b_files}")
    print(f"A defines       : {sorted(a_syms)}")
    print(f"B defines       : {sorted(b_syms)}")

    file_overlap = set(a_files) & set(b_files)
    sym_overlap = a_syms & b_syms
    print(f"\nfile overlap   : {sorted(file_overlap) or 'EMPTY'}")
    print(f"symbol overlap : {sorted(sym_overlap) or 'EMPTY'}")

    # cross-mention check: does A's diff text ever name a symbol B defines?
    a_text = subprocess.run(["git", "diff", base, a_head], cwd=a_repo,
                            capture_output=True, text=True, check=True).stdout
    b_text = subprocess.run(["git", "diff", base, b_head], cwd=b_repo,
                            capture_output=True, text=True, check=True).stdout
    b_leaked = sorted(s for s in a_syms if mentions(b_text, s))
    leaked = sorted(s for s in b_syms if mentions(a_text, s))
    print(f"A diff mentions B symbols : {leaked or 'NONE'}")
    print(f"B diff mentions A symbols : {b_leaked or 'NONE'}")

    if not file_overlap and not sym_overlap and not leaked and not b_leaked:
        print("\nRESULT: patches are disjoint by files, defined symbols, and cross-mention.")
        return 0
    print("\nRESULT: DISJOINTNESS FAILS - do not claim no-symbol-overlap.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
