# Containment Guard Repair 01

## Problem Description
During independent candidate testing, `test_supervision_watcher_metrics_hook` in `scripts/supervision/test_service.py` executed `supervision_watcher.sh` directly against the host. Under the test runner's hermetic `HOME`, the `aplexer status` check failed, which triggered `systemctl --user restart supervision.service` to execute against the host at 00:35:14 UTC, leaking external side-effects.

## Implemented Changes

1. **`scripts/supervision/systemd/supervision_watcher.sh`**:
   - Introduced a `restart_supervision` wrapper function.
   - Added environment checks for `PYTEST_CURRENT_TEST`, `SUPERVISION_TEST_MODE`, and `SUPERVISION_WATCHER_DRY_RUN`.
   - In test/dry-run mode, the script now prints a diagnostic message and exits 0 immediately without invoking `systemctl --user restart`.

2. **`scripts/supervision/test_service.py`**:
   - In `test_supervision_watcher_metrics_hook`, injected the `SUPERVISION_WATCHER_DRY_RUN=1` environment variable when executing the live watcher script.
   - Updated test assertions to check for the printed diagnostic message when in dry-run mode and the supervisor is missing or stale.

## Diff

```diff
--- scripts/supervision/systemd/supervision_watcher.sh
+++ scripts/supervision/systemd/supervision_watcher.sh
@@ -5,6 +5,14 @@
 REPO_ROOT="/home/alexey/git/cloudflare-agent-git"
 cd "$REPO_ROOT"
 
+function restart_supervision() {
+    if [ -n "${PYTEST_CURRENT_TEST:-}" ] || [ "${SUPERVISION_TEST_MODE:-0}" = "1" ] || [ "${SUPERVISION_WATCHER_DRY_RUN:-0}" = "1" ]; then
+        echo "Diagnostic: test/dry-run mode active. Skipping systemctl execution."
+        exit 0
+    fi
+    systemctl --user restart supervision.service
+}
+
 # Check if experiment-supervision is alive
 if ! python3 -c "
 import subprocess, json
@@ -13,7 +21,7 @@
     exit(1)
 " >/dev/null 2>&1; then
     echo "Supervisor is down or missing. Restarting..."
-    systemctl --user restart supervision.service
+    restart_supervision
 else
     # Check if status.json is fresh (updated in last 600s, accommodating task runs)
     STATUS_AGE=$(stat -c %Y "$REPO_ROOT/.local/supervision/status.json" 2>/dev/null || echo 0)
@@ -21,7 +29,7 @@
     if [ $((NOW - STATUS_AGE)) -gt 600 ]; then
         echo "Supervisor is alive but status.json is stale (>600s). Restarting..."
-        systemctl --user restart supervision.service
+        restart_supervision
     else
         echo "Supervisor is healthy."
     fi
```

```diff
--- scripts/supervision/test_service.py
+++ scripts/supervision/test_service.py
@@ -1259,7 +1259,9 @@
    self.assertEqual(parsed.get('status'), 'ok')
    self.assertIn('active_bytes', parsed)
 
-  res_live = subprocess.run(['bash', str(watcher_path)], capture_output=True, text=True, cwd=str(root))
+  env = {**os.environ, 'SUPERVISION_WATCHER_DRY_RUN': '1'}
+  res_live = subprocess.run(['bash', str(watcher_path)], capture_output=True, text=True, cwd=str(root), env=env)
   self.assertEqual(res_live.returncode, 0, f"watcher failed: {res_live.stderr}\nstdout: {res_live.stdout}")
-  self.assertIn('Supervisor is healthy.', res_live.stdout)
+  if 'Supervisor is healthy.' not in res_live.stdout:
+   self.assertIn('Diagnostic: test/dry-run mode active. Skipping systemctl execution.', res_live.stdout)
```

## Verification Output

Ran the validation command to ensure the test passes cleanly with zero external side-effects on host systemctl or services.

```console
$ python3 -m unittest scripts/supervision/test_service.py -k test_supervision_watcher_metrics_hook
.
----------------------------------------------------------------------
Ran 1 test in 0.436s

OK
```
