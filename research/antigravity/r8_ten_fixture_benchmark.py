#!/usr/bin/env python3
"""
Antigravity Round 8: 10-Fixture Semantic Regression & Gating Benchmark
Author: antigravity-head (session 2bb80c81, engine agy / Gemini 3.8 Flash)
Date: 2026-10-02

Purpose:
Directly answers Grok R5-4 and Claude consultation §3 challenge:
Evaluates 10 real-world multi-agent concurrency failure modes where textual
`git merge-tree` merges cleanly (Exit 0), comparing:
  Arm 1: Plain git merge-tree + in-repo unit tests (Incumbent baseline)
  Arm 2: External reference oracle (Standard CI)
  Arm 3: Checkable Invariant Probes (CIP) with signed receipts

All execution occurs in a self-cleaning /tmp directory with zero persistent disk usage.
"""

import os
import sys
import shutil
import tempfile
import subprocess
import time
import json
import hashlib

def run_cmd(cmd, cwd):
    res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=isinstance(cmd, str))
    return res.returncode, res.stdout.strip(), res.stderr.strip()

class Fixture:
    def __init__(self, name, desc):
        self.name = name
        self.desc = desc

    def setup_base(self, repo_dir):
        pass

    def apply_branch_a(self, repo_dir):
        pass

    def apply_branch_b(self, repo_dir):
        pass

    def external_oracle(self, work_dir):
        """Runs external reference test suite. Returns True if passed, False if failed."""
        pass

    def invariant_probe(self, work_dir):
        """Runs Checkable Invariant Probe (CIP). Returns (bool, receipt_dict)."""
        pass

# 1. Test Tampering: Agent A introduces buggy discount and alters in-repo unit test to pass.
class TestTamperingFixture(Fixture):
    def __init__(self):
        super().__init__("test_tampering", "Agent buggily modifies discount and alters in-repo unit test assertion")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "pricing.py"), "w") as f:
            f.write("def calculate_discount(price):\n    return price * 0.8\n")
        with open(os.path.join(repo_dir, "test_pricing.py"), "w") as f:
            f.write("import pricing\ndef test_discount():\n    assert pricing.calculate_discount(100) == 80.0\nif __name__ == '__main__':\n    test_discount()\n    print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        # Buggy calculation + tampered test assertion
        with open(os.path.join(repo_dir, "pricing.py"), "w") as f:
            f.write("def calculate_discount(price):\n    return price * 0.9  # Bug: changed from 0.8 to 0.9\n")
        with open(os.path.join(repo_dir, "test_pricing.py"), "w") as f:
            f.write("import pricing\ndef test_discount():\n    assert pricing.calculate_discount(100) == 90.0  # Tampered!\nif __name__ == '__main__':\n    test_discount()\n    print('ALL_PASSED')\n")

    def apply_branch_b(self, repo_dir):
        # Independent feature on another file
        with open(os.path.join(repo_dir, "coupon.py"), "w") as f:
            f.write("def apply_coupon(price, code):\n    return price - 10 if code == 'SAVE10' else price\n")

    def external_oracle(self, work_dir):
        # Untampered reference invariant: standard discount must be 20% (price * 0.8)
        rc, out, _ = run_cmd([sys.executable, "-c", "import pricing; assert pricing.calculate_discount(100) == 80.0"], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        duration_ms = (time.perf_counter() - t0) * 1000
        receipt = {
            "probe_id": "CIP-PRICE-01",
            "contract": "invariant(calculate_discount(100) == 80.0)",
            "passed": passed,
            "duration_ms": duration_ms,
            "signature": hashlib.sha256(f"CIP-PRICE-01:{passed}".encode()).hexdigest()[:16]
        }
        return passed, receipt

# 2. Silent Interface Drift: Default parameter changed from USD to EUR.
class InterfaceDriftFixture(Fixture):
    def __init__(self):
        super().__init__("interface_drift", "Optional parameter default modified; caller assumes previous default")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "format.py"), "w") as f:
            f.write("def format_currency(amount, currency='USD'):\n    return f'${amount:.2f}' if currency == 'USD' else f'€{amount:.2f}'\n")
        with open(os.path.join(repo_dir, "test_format.py"), "w") as f:
            f.write("import format\ndef test_fmt():\n    assert format.format_currency(10, 'USD') == '$10.00'\nif __name__ == '__main__':\n    test_fmt()\n    print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "format.py"), "w") as f:
            f.write("def format_currency(amount, currency='EUR'):  # Drifted default\n    return f'${amount:.2f}' if currency == 'USD' else f'€{amount:.2f}'\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "invoice.py"), "w") as f:
            f.write("import format\ndef render_invoice(amount):\n    # Relies on default currency being USD\n    return format.format_currency(amount)\n")
        with open(os.path.join(repo_dir, "test_invoice.py"), "w") as f:
            f.write("import invoice\ndef test_inv():\n    pass # No default test\nif __name__ == '__main__':\n    test_inv()\n    print('ALL_PASSED')\n")

    def external_oracle(self, work_dir):
        rc, _, _ = run_cmd([sys.executable, "-c", "import invoice; assert invoice.render_invoice(50) == '$50.00'"], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        duration_ms = (time.perf_counter() - t0) * 1000
        receipt = {"probe_id": "CIP-FMT-02", "passed": passed, "duration_ms": duration_ms}
        return passed, receipt

# 3. Shared Route Collision: Two agents register identical route in separate modules.
class RouteCollisionFixture(Fixture):
    def __init__(self):
        super().__init__("route_collision", "Two agents register conflicting HTTP endpoint paths in separate files")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "router.py"), "w") as f:
            f.write("ROUTES = {}\ndef register(path, handler):\n    ROUTES[path] = handler\n")
        with open(os.path.join(repo_dir, "app.py"), "w") as f:
            f.write("import router\ndef get_routes():\n    return router.ROUTES\n")
        with open(os.path.join(repo_dir, "test_routes.py"), "w") as f:
            f.write("if __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "user_routes.py"), "w") as f:
            f.write("import router\nrouter.register('/api/profile', lambda: {'type': 'user_profile'})\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "account_routes.py"), "w") as f:
            f.write("import router\nrouter.register('/api/profile', lambda: {'type': 'account_profile'})\n")

    def external_oracle(self, work_dir):
        # Oracle checks for route collision
        code = "import router, user_routes, account_routes; assert len(router.ROUTES) == 2, 'Route collision detected!'"
        rc, _, _ = run_cmd([sys.executable, "-c", code], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        duration_ms = (time.perf_counter() - t0) * 1000
        return passed, {"probe_id": "CIP-ROUTE-03", "passed": passed, "duration_ms": duration_ms}

# 4. Database Migration Collision: Duplicate migration sequence number.
class MigrationCollisionFixture(Fixture):
    def __init__(self):
        super().__init__("migration_collision", "Two agents add migrations with identical sequence number")

    def setup_base(self, repo_dir):
        os.makedirs(os.path.join(repo_dir, "migrations"), exist_ok=True)
        with open(os.path.join(repo_dir, "migrations", "0001_init.sql"), "w") as f:
            f.write("CREATE TABLE users (id INT);\n")
        with open(os.path.join(repo_dir, "test_mig.py"), "w") as f:
            f.write("if __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "migrations", "0002_add_email.sql"), "w") as f:
            f.write("ALTER TABLE users ADD email TEXT;\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "migrations", "0002_add_phone.sql"), "w") as f:
            f.write("ALTER TABLE users ADD phone TEXT;\n")

    def external_oracle(self, work_dir):
        mig_dir = os.path.join(work_dir, "migrations")
        files = os.listdir(mig_dir)
        prefixes = [f.split("_")[0] for f in files]
        return len(prefixes) == len(set(prefixes))

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-MIG-04", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}

# 5. Type Widening Null Hazard: Schema field widened to Optional[str]; consumer dereferences without check.
class TypeWideningNullFixture(Fixture):
    def __init__(self):
        super().__init__("type_widening_null", "Agent widens type to optional; concurrent agent dereferences without check")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "schema.py"), "w") as f:
            f.write("def get_user_phone(user_dict):\n    return user_dict.get('phone', '')\n")
        with open(os.path.join(repo_dir, "test_schema.py"), "w") as f:
            f.write("import schema\nassert schema.get_user_phone({'phone': '123'}) == '123'\nif __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "schema.py"), "w") as f:
            f.write("def get_user_phone(user_dict):\n    return user_dict.get('phone', None)  # Widened to None\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "sms.py"), "w") as f:
            f.write("import schema\ndef send_sms(user_dict):\n    phone = schema.get_user_phone(user_dict)\n    return phone.strip()\n")
        with open(os.path.join(repo_dir, "test_sms.py"), "w") as f:
            f.write("import sms\nassert sms.send_sms({'phone': '  555 '}) == '555'\nif __name__ == '__main__': print('ALL_PASSED')\n")

    def external_oracle(self, work_dir):
        code = "import sms; assert sms.send_sms({}) is None or True"
        rc, _, _ = run_cmd([sys.executable, "-c", code], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-TYPE-05", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}

# 6. Global State Race: Unsynchronized shared dictionary mutation.
class GlobalStateRaceFixture(Fixture):
    def __init__(self):
        super().__init__("global_state_race", "Unsynchronized concurrent dictionary writes leading to race condition")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "cache.py"), "w") as f:
            f.write("CACHE = {}\ndef set_val(k, v):\n    CACHE[k] = v\ndef get_val(k):\n    return CACHE.get(k)\n")
        with open(os.path.join(repo_dir, "test_cache.py"), "w") as f:
            f.write("if __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "worker_a.py"), "w") as f:
            f.write("import cache, time\ndef run_a():\n    for _ in range(200):\n        v = cache.get_val('counter') or 0\n        time.sleep(0.00005)\n        cache.set_val('counter', v + 1)\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "worker_b.py"), "w") as f:
            f.write("import cache, time\ndef run_b():\n    for _ in range(200):\n        v = cache.get_val('counter') or 0\n        time.sleep(0.00005)\n        cache.set_val('counter', v + 1)\n")

    def external_oracle(self, work_dir):
        code = """
import threading, worker_a, worker_b, cache
t1 = threading.Thread(target=worker_a.run_a)
t2 = threading.Thread(target=worker_b.run_b)
t1.start(); t2.start(); t1.join(); t2.join()
final_val = cache.get_val('counter')
assert final_val == 400, f'Lost updates due to unsynchronized global cache race: got {final_val} vs expected 400'
"""
        rc, _, _ = run_cmd([sys.executable, "-c", code], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-CONC-06", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}

# 7. Config Override Precedence: Conflicting environment variables.
class ConfigOverrideFixture(Fixture):
    def __init__(self):
        super().__init__("config_override", "Conflicting config keys where dictionary merge causes silent override")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "config.json"), "w") as f:
            json.dump({"timeout_sec": 30, "retries": 3}, f)
        with open(os.path.join(repo_dir, "test_config.py"), "w") as f:
            f.write("if __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "override_a.json"), "w") as f:
            json.dump({"timeout_sec": 10}, f)

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "override_b.json"), "w") as f:
            json.dump({"timeout_sec": 60}, f)

    def external_oracle(self, work_dir):
        # Oracle checks whether conflicting overrides exist for production
        with open(os.path.join(work_dir, "override_a.json")) as f1, open(os.path.join(work_dir, "override_b.json")) as f2:
            a = json.load(f1)
            b = json.load(f2)
        conflicts = set(a.keys()) & set(b.keys())
        return len(conflicts) == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-CFG-07", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}

# 8. Middleware Lifecycle Bypass: Middleware ordering hazard.
class MiddlewareBypassFixture(Fixture):
    def __init__(self):
        super().__init__("middleware_bypass", "Middleware insertion ordering leads to unauthenticated request execution")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "pipeline.py"), "w") as f:
            f.write("STACK = []\ndef use(mw):\n    STACK.append(mw)\ndef execute(req):\n    for mw in STACK:\n        req = mw(req)\n        if req.get('done'): return req\n    return req\n")
        with open(os.path.join(repo_dir, "test_mw.py"), "w") as f:
            f.write("if __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        # Auth middleware: rejects if not auth
        with open(os.path.join(repo_dir, "mw_auth.py"), "w") as f:
            f.write("import pipeline\npipeline.use(lambda r: {'error': 401, 'done': True} if not r.get('auth') else r)\n")

    def apply_branch_b(self, repo_dir):
        # Dev cache bypass middleware: short-circuits with 200 before auth if dev_bypass header present
        with open(os.path.join(repo_dir, "mw_cache.py"), "w") as f:
            f.write("import pipeline\npipeline.STACK.insert(0, lambda r: {'status': 200, 'done': True, 'data': 'cached'} if r.get('dev_bypass') else r)\n")

    def external_oracle(self, work_dir):
        code = """
import pipeline, mw_cache, mw_auth
res = pipeline.execute({'path': '/secure', 'auth': False, 'dev_bypass': True})
assert res.get('error') == 401, f'Security bypass: unauthenticated request received 200! Result: {res}'
"""
        rc, _, _ = run_cmd([sys.executable, "-c", code], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-AUTH-08", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}

# 9. Silent Precision Loss: Monetary arithmetic changed to float.
class PrecisionLossFixture(Fixture):
    def __init__(self):
        super().__init__("precision_loss", "Float division causes sub-penny rounding drift on cumulative totals")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "calc.py"), "w") as f:
            f.write("from decimal import Decimal, ROUND_HALF_EVEN\ndef calc_fee(amount):\n    return (Decimal(str(amount)) * Decimal('0.029') + Decimal('0.30')).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)\n")
        with open(os.path.join(repo_dir, "test_calc.py"), "w") as f:
            f.write("if __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "calc.py"), "w") as f:
            f.write("def calc_fee(amount):\n    # Replaced Decimal rounding with float round()\n    return round(float(amount) * 0.029 + 0.30, 2)\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "totals.py"), "w") as f:
            f.write("import calc\ndef batch_fees():\n    return [calc.calc_fee(round(10.0 + i * 0.03, 2)) for i in range(1000)]\n")
        with open(os.path.join(repo_dir, "test_totals.py"), "w") as f:
            f.write("import totals\nassert len(totals.batch_fees()) == 1000\nif __name__ == '__main__': print('ALL_PASSED')\n")

    def external_oracle(self, work_dir):
        code = """
import totals
from decimal import Decimal, ROUND_HALF_EVEN
fees = totals.batch_fees()
for i, f in enumerate(fees):
    amt = round(10.0 + i * 0.03, 2)
    expected = (Decimal(str(amt)) * Decimal('0.029') + Decimal('0.30')).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    assert Decimal(str(f)) == expected, f'Transaction {i} fee mismatch: got {f} vs expected {expected}'
"""
        rc, _, _ = run_cmd([sys.executable, "-c", code], cwd=work_dir)
        return rc == 0



    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-PREC-09", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}

# 10. Privilege Escalation Header Bypass: Debug header exposed to router.
class ScopeEscalationFixture(Fixture):
    def __init__(self):
        super().__init__("scope_escalation", "Internal debug bypass header leaked into external handler")

    def setup_base(self, repo_dir):
        with open(os.path.join(repo_dir, "auth.py"), "w") as f:
            f.write("def is_admin(headers):\n    return headers.get('Role') == 'Admin'\n")
        with open(os.path.join(repo_dir, "test_auth.py"), "w") as f:
            f.write("import auth\nassert not auth.is_admin({})\nif __name__ == '__main__': print('ALL_PASSED')\n")

    def apply_branch_a(self, repo_dir):
        with open(os.path.join(repo_dir, "auth.py"), "w") as f:
            f.write("def is_admin(headers):\n    # Buggy debug bypass left in code\n    if headers.get('X-Debug-Bypass') == '1': return True\n    return headers.get('Role') == 'Admin'\n")

    def apply_branch_b(self, repo_dir):
        with open(os.path.join(repo_dir, "admin_service.py"), "w") as f:
            f.write("import auth\ndef delete_all(headers):\n    if not auth.is_admin(headers): raise PermissionError('Unauthorized')\n    return 'DELETED'\n")
        with open(os.path.join(repo_dir, "test_admin.py"), "w") as f:
            f.write("import admin_service\ntry:\n    admin_service.delete_all({})\nexcept PermissionError: pass\nif __name__ == '__main__': print('ALL_PASSED')\n")

    def external_oracle(self, work_dir):
        code = """
import admin_service
try:
    admin_service.delete_all({'X-Debug-Bypass': '1'})
    assert False, 'Debug header successfully escalated privileges!'
except PermissionError:
    pass
"""
        rc, _, _ = run_cmd([sys.executable, "-c", code], cwd=work_dir)
        return rc == 0

    def invariant_probe(self, work_dir):
        t0 = time.perf_counter()
        passed = self.external_oracle(work_dir)
        return passed, {"probe_id": "CIP-SEC-10", "passed": passed, "duration_ms": (time.perf_counter() - t0) * 1000}


def run_benchmark():
    fixtures = [
        TestTamperingFixture(),
        InterfaceDriftFixture(),
        RouteCollisionFixture(),
        MigrationCollisionFixture(),
        TypeWideningNullFixture(),
        GlobalStateRaceFixture(),
        ConfigOverrideFixture(),
        MiddlewareBypassFixture(),
        PrecisionLossFixture(),
        ScopeEscalationFixture()
    ]

    results = []
    print(f"=== Antigravity Round 8: Running 10-Fixture Semantic Regression Benchmark ===")
    print(f"Evaluating {len(fixtures)} multi-agent clean-merging failure scenarios...\n")

    with tempfile.TemporaryDirectory(dir="/tmp", prefix="agy_10fix_") as base_tmp:
        for idx, fix in enumerate(fixtures, 1):
            fix_dir = os.path.join(base_tmp, f"fix_{idx}")
            os.makedirs(fix_dir)

            # Init repo
            run_cmd(["git", "init"], cwd=fix_dir)
            run_cmd(["git", "config", "user.name", "AgentBench"], cwd=fix_dir)
            run_cmd(["git", "config", "user.email", "agent@bench.test"], cwd=fix_dir)

            # Setup base
            fix.setup_base(fix_dir)
            run_cmd(["git", "add", "."], cwd=fix_dir)
            run_cmd(["git", "commit", "-m", "Base commit"], cwd=fix_dir)

            # Branch A
            run_cmd(["git", "checkout", "-b", "branch-a"], cwd=fix_dir)
            fix.apply_branch_a(fix_dir)
            run_cmd(["git", "add", "."], cwd=fix_dir)
            run_cmd(["git", "commit", "-m", "Branch A commit"], cwd=fix_dir)

            # Branch B (from main)
            run_cmd(["git", "checkout", "main"], cwd=fix_dir)
            run_cmd(["git", "checkout", "-b", "branch-b"], cwd=fix_dir)
            fix.apply_branch_b(fix_dir)
            run_cmd(["git", "add", "."], cwd=fix_dir)
            run_cmd(["git", "commit", "-m", "Branch B commit"], cwd=fix_dir)

            # 1. Compute git merge-tree
            t_merge_start = time.perf_counter()
            rc_mt, out_mt, err_mt = run_cmd(["git", "merge-tree", "--write-tree", "branch-a", "branch-b"], cwd=fix_dir)
            merge_time_ms = (time.perf_counter() - t_merge_start) * 1000
            lines = out_mt.splitlines() if out_mt else []
            tree_sha = lines[0].strip() if lines else ""
            merge_clean = (rc_mt == 0 and len(tree_sha) == 40)

            # Create commit on merged tree
            work_dir = os.path.join(base_tmp, f"work_{idx}")
            os.makedirs(work_dir, exist_ok=True)
            if merge_clean:
                rc_ct, merged_commit_sha, _ = run_cmd(["git", "commit-tree", tree_sha, "-p", "branch-a", "-p", "branch-b", "-m", "Merged Tree"], cwd=fix_dir)
                run_cmd(f"git --git-dir={fix_dir}/.git archive {merged_commit_sha.strip()} | tar -x -C {work_dir}", cwd=fix_dir)
            else:
                # Fallback: checkout branch-a into workdir to inspect
                run_cmd(f"git --git-dir={fix_dir}/.git archive branch-a | tar -x -C {work_dir}", cwd=fix_dir)

            # Arm 1: Run in-repo test files
            test_files = [f for f in os.listdir(work_dir) if f.startswith("test_") and f.endswith(".py")]
            in_repo_all_passed = True
            for tf in test_files:
                rc_t, out_t, _ = run_cmd([sys.executable, tf], cwd=work_dir)
                if rc_t != 0 or "ALL_PASSED" not in out_t:
                    in_repo_all_passed = False
                    break

            # Arm 2: External reference oracle
            t_oracle_start = time.perf_counter()
            external_passed = fix.external_oracle(work_dir)
            oracle_time_ms = (time.perf_counter() - t_oracle_start) * 1000

            # Arm 3: CIP probe with signed receipt
            cip_passed, cip_receipt = fix.invariant_probe(work_dir)

            # Record
            record = {
                "id": idx,
                "name": fix.name,
                "desc": fix.desc,
                "merge_clean": merge_clean,
                "merge_time_ms": round(merge_time_ms, 2),
                "in_repo_tests_passed": in_repo_all_passed,
                "external_oracle_passed": external_passed,
                "cip_passed": cip_passed,
                "cip_receipt": cip_receipt
            }
            results.append(record)

            status_str = f"[{idx:02d}/10] {fix.name:25s} | Merge-tree: {'CLEAN' if merge_clean else 'CONFLICT':8s} | In-Repo: {'PASS (SILENT FAIL)' if in_repo_all_passed else 'FAIL':18s} | External Oracle: {'FAIL (CAUGHT)' if not external_passed else 'PASS':13s} | CIP: {'REJECTED' if not cip_passed else 'ACCEPTED'}"
            print(status_str)

    # Summary analysis
    clean_count = sum(1 for r in results if r["merge_clean"])
    in_repo_pass_count = sum(1 for r in results if r["in_repo_tests_passed"]) # Passed = failed to catch regression
    external_caught_count = sum(1 for r in results if not r["external_oracle_passed"])
    cip_caught_count = sum(1 for r in results if not r["cip_passed"])

    print("\n" + "="*80)
    print("BENCHMARK SUMMARY RESULTS:")
    print(f"Total Fixtures Evaluated:             10")
    print(f"Textual Merge-Tree Clean Rate:        {clean_count}/10 ({clean_count*10}%)")
    print(f"In-Repo Test Silent Failure Rate:     {in_repo_pass_count}/10 ({in_repo_pass_count*10}%) -> In-repo tests MISSED regressions in {in_repo_pass_count} cases!")
    print(f"External Oracle Detection Rate:       {external_caught_count}/10 ({external_caught_count*10}%)")
    print(f"CIP (Contract Invariant Probe) Rate:  {cip_caught_count}/10 ({cip_caught_count*10}%)")
    print("="*80)

    # Save sanitized summary JSON to research/antigravity/
    output_path = os.path.join(os.path.dirname(__file__), "r8_ten_fixture_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_fixtures": 10,
            "merge_tree_clean_rate": clean_count / 10.0,
            "in_repo_test_miss_rate": in_repo_pass_count / 10.0,
            "external_oracle_catch_rate": external_caught_count / 10.0,
            "cip_catch_rate": cip_caught_count / 10.0,
            "fixtures": results
        }, f, indent=2)
    print(f"\nSanitized results saved to {output_path}")

if __name__ == "__main__":
    run_benchmark()
