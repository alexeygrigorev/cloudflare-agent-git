# Adapter Request Interface Compatibility Check

## 1. Adapter CLI Invocation

The `LauncherRequestRunner` in `consumer_execution_adapter.py` executes the `request` command. The exact CLI invocation issued by the default execution path is:

```bash
<python_executable> -m launcher --config-dir <config_dir> request \
  --goal "<goal>" \
  --cwd "<cwd>" \
  [--profile "<profile>"] \
  [--timeout <timeout>] \
  [--paths "<path>" ...] \
  [--target-commit "<target_commit>" --target-worktree "<target_worktree>"]
```

*Reference:* `/home/alexey/git/cloudflare-agent-git/scripts/coordination/consumer_execution_adapter.py` (Lines 154-165)

## 2. Compatibility Verdict

**Verdict: Compatible**

All flags conditionally or unconditionally issued by the adapter's default execution path exist on the `request` CLI parser implemented in `d3a4276`. 

*Reference:* `launcher/cli.py` (Lines 780-791)

**Mismatch list:**
* None. The CLI in `d3a4276` provides all fields expected by the adapter (`--goal`, `--cwd`, `--profile`, `--timeout`, `--paths`, `--target-commit`, `--target-worktree`).

## 3. Integration-Ordering Recommendation

Commit `d3a4276` can be safely merged into the QL main branch immediately. Because the interface surface exposed by `d3a4276` (`launcher/cli.py`, lines 780-791) fully satisfies the `request` invocation contract statically built by the consumer execution adapter (`scripts/coordination/consumer_execution_adapter.py`, lines 154-165), the changes are backward compatible with the current coordinator logic. No synchronized cross-repository updates or prerequisite pull requests in the coordination repository are required prior to this merge.
