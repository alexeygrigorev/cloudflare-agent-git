# Claude Code Engine State-Report Hooks Repair (2026-10-07)

## 1. Problem Diagnosis
- **Failure Symptom**: Interactive Claude Code Sonnet 5.5 sessions (e.g. `c7718c33`) exhibited empty UI / missing transcript on startup, and `a message hook-notice` / awareness events were not registering, causing `NOTREADY expired working` states.
- **Root Cause**: Running `a init --check --engine claude --json` reported exit code 1:
  ```json
  {
    "engines": [
      {
        "action": "absent",
        "engine": "claude",
        "installed": false,
        "message": "/home/alexey/.claude/settings.json missing events: SessionStart, UserPromptSubmit, PostToolUse; /home/alexey/.zlaude/settings.json missing events: SessionStart, UserPromptSubmit, PostToolUse",
        "paths": [
          "/home/alexey/.claude/settings.json",
          "/home/alexey/.zlaude/settings.json"
        ]
      }
    ],
    "initialized": false,
    "prompt": []
  }
  ```
  While `a state-report` commands were present in settings.json, the required `aplexer context hook --engine claude 2>/dev/null || true # aplexer-managed-awareness-hook-v1` command entries under `SessionStart`, `UserPromptSubmit`, and `PostToolUse` were missing.

## 2. Safe Repair Execution
1. **Private Beforeimages**:
   - Preserved exact configuration state prior to mutation:
     - `/home/alexey/git/cloudflare-agent-git/.local/recovery/claude-hooks-before-20261007093409/claude_settings.json`
     - `/home/alexey/git/cloudflare-agent-git/.local/recovery/claude-hooks-before-20261007093409/zlaude_settings.json`
2. **Hook Merging**:
   - Executed supported aplexer initialization:
     ```bash
     a init --engine claude
     ```
   - Both `/home/alexey/.claude/settings.json` and `/home/alexey/.zlaude/settings.json` were non-destructively updated to include the managed awareness hook entries alongside existing pocketshell and bash execution filters.
3. **Post-Repair Verification**:
   - Executed `a init --check --engine claude --json`:
     ```json
     {
       "engines": [
         {
           "action": "present",
           "engine": "claude",
           "installed": true,
           "message": "hook installed in /home/alexey/.claude/settings.json; hook installed in /home/alexey/.zlaude/settings.json",
           "paths": [
             "/home/alexey/.claude/settings.json",
             "/home/alexey/.zlaude/settings.json"
           ]
         }
       ],
       "initialized": true,
       "prompt": []
     }
     ```
   - Exit code: 0 (**PASS**).
