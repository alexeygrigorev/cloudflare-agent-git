# Grok hook repair proposal — stale `Notification -> state-report waiting`

- Author: claude-scribe-grokhook (one-shot read-only executor, model zai-coding-plan/glm-5.3)
- Identity (`a whoami --json`): session `37c7ac87-e500-4380-a7d6-a4aea2d4de53`, tag `claude-scribe-grokhook`, engine `shell`, workspace `/home/alexey/git/cloudflare-agent-git`, parent `b3a92dd0` (claude-principal)
- Date: 2026-10-03 (Europe/Berlin). Scope: proposal only — nothing outside this file and the /tmp experiments below was modified. No builds run, no hook install against the real HOME.
- Fixes: research/antigravity/timeline-diagnostics/TIMELINE-DIAGNOSTIC-REPORT.md item 3 (grok-head `d85e5cd8`, `'waiting report expired'` rejection; `idle_prompt` Notification fired ~60 s after turn end, clobbered `idle` with an expiring `waiting`).

## 1. Installed state (evidence)

`~/.grok/hooks/aplexer.json`:

- sha256: `df3d7ce9d8d82535fbc5814494f9e299d5680d89ae37af41003eb9a9e69fbd3b`
- size 1337 bytes, mode `0600`, owner `alexey`
- mtime: 2026-10-03 03:29:27.196396244 +0200 (birth same second)

Full content (as installed):

```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report waiting || true",
            "type": "command"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer context hook --engine grok 2>/dev/null || true # aplexer-managed-awareness-hook-v1",
            "timeout": 5,
            "type": "command"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report working || true",
            "type": "command"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report idle || true",
            "type": "command"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report working || true",
            "type": "command"
          }
        ]
      }
    ]
  }
}
```

Two defects: (a) a matcher-free `Notification` group running `state-report waiting` — Grok's `idle_prompt` chime fires it ~60 s after the session settles (diagnostics report §3.B.4), clobbering `Stop`'s `idle`; (b) every command pins the mutable dev build `target/debug/aplexer`.

Timeline: file written 03:29 by a pre-fix dev build; the upstream fix landed 08:16 (commit `36829c4`, "exclude Grok notification from state hooks"); HEAD is `7efa493` (10:59); the dev build on disk was rebuilt 11:03 (post-fix, verified behaviorally below). The installed file was never refreshed after the fix.

## 2. What current source (HEAD 7efa493) says

Read-only inspection of /home/alexey/git/cloudflare-aplexer-protocol (verified `git rev-parse HEAD` = `7efa49386d756575f1003825b050643688fa3fc5`; working tree clean except untracked `.local/`).

- `GROK_EVENTS` (src/hooks/mod.rs:153-158) contains exactly four wirings — `Stop -> idle`, `UserPromptSubmit -> working`, `SessionStart -> working`, `PostToolUse -> awareness:grok` — and **no `Notification`**. The comment at src/hooks/mod.rs:150-152 states why: "Notification is excluded because Grok fires desktop notifications on turn completion, which would clobber Stop's idle state with an expiring waiting state." Pinned by test `grok_events_exclude_notification_to_prevent_idle_clobber` (src/hooks/tests/drivers.rs:33-36); grok also covered in the merge/unmerge idempotency test (src/hooks/tests/nested.rs:164).
- **What current source writes for grok**: `install_grok` (src/hooks/drivers.rs:609-614) starts from an **empty document** (`Value::Object(Default::default())`, drivers.rs:611), merges `GROK_EVENTS`, and writes the whole owned file (`install_owned_file`, drivers.rs:465-477 → `write_if_changed`, files.rs:60-70). So a grok install from a fixed binary **replaces the file wholesale** — the stale `Notification` entry cannot survive it. `uninstall_grok` (drivers.rs:620-621 → `remove_owned_file`, drivers.rs:479-487) deletes the owned file outright.
- **Does `merge_nested_hooks` remove a stale aplexer-managed Notification entry?** By itself, no: it only adds missing wirings (src/hooks/nested.rs:83-99) and its sole removal path, `strip_legacy_notices` (nested.rs:82, 108-130), strips only commands ending with the legacy marker `aplexer-managed-inbox-hook-v1` (notice.rs:15, 39-43). A bare `state-report waiting` command has no marker and is not touched. (The marker-blind, all-events removal lives in `unmerge_nested_hooks`, nested.rs:143-194, used only by uninstall, keyed by `is_managed_hook_command`, notice.rs:52-56.) For grok this is moot in practice because the grok driver never feeds the existing file to the merge — it rewrites from empty (drivers.rs:611). For **shared-file** engines (claude/codex/gemini, `install_nested_files`, drivers.rs:429-440 → `install_nested_file`, files.rs:78-93), a stale managed entry in the on-disk file WOULD persist across re-init; only the grok owned-file path is self-healing.
- **Can `a init --check` see the stale entry?** No. `check_grok` (drivers.rs:616-618) → `check_nested_file` (files.rs:95-113) → `missing_nested_hooks` (nested.rs:201-215) only checks that each *required* event has a group reporting the expected state. Extra/stale events are invisible; matching is path-independent (`is_state_report_command` = `contains("state-report")`, mod.rs:199-201; `reports_state` matches the `state-report <state>` word pair, mod.rs:208-216). This is why the machine contract reports grok "installed" today.

## 3. CLI surface and safe dry-run (GROK_HOME override, /tmp only)

`aplexer init` installs hooks; `--check` touches nothing; `--engine grok` limits action to grok and leaves the shell-prompt block alone (`aplexer init --help`). Target resolution honors `$GROK_HOME` (absolute) before `$HOME/.grok` (src/hooks/mod.rs:295-314, `resolve_targets_from_env`; path built at drivers.rs:605-606). This allowed an install dry-run against a /tmp copy without touching the real HOME:

1. Copied the installed file into `/tmp/opencode/grokhook.*/grok-home/hooks/aplexer.json`.
2. `GROK_HOME=<tmp> /home/alexey/.local/bin/aplexer init --engine grok --check --json` → `installed: true, initialized: true` (exit 0). Confirms check cannot see the stale entry.
3. `GROK_HOME=<tmp> /home/alexey/.local/bin/aplexer init --engine grok` → rewrote the file **still containing `Notification -> waiting`**, only swapping the command path to `/home/alexey/.local/bin/aplexer`. **The installed CLI predates the fix and reinstalls the bug.**
4. Same experiment with the dev build `/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer` (rebuilt 11:03, post-`36829c4`): `init --engine grok` wrote exactly the fixed four-event table (no `Notification`), embedding the dev-build path; its `--check` then reports installed. Its output, with the path swapped to the pinned binary, is the target JSON below (validated: the dev build's `--check` reports `installed: true` on the pinned variant; the installed CLI's `--check` reports `missing events: Notification`, exit 1 — expected, see risks).

Both binaries report version `a 0.1.9`; the sha is the real discriminator.

## 4. Binary pin

Candidates:

- `/home/alexey/.local/bin/aplexer` — sha256 `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4`, built 2026-10-02 22:53, `a 0.1.9`, symlinked as `~/.local/bin/a`. Immutable in practice (not touched by cargo).
- `/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer` — sha256 `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd`, mtime 2026-10-03 11:03. Mutable dev build.

Risks:

- **Dev build (status quo)**: any `cargo build`/`cargo clean` in the protocol repo changes or deletes the binary under a live hook. Deletion kills all grok state reporting silently (`|| true` swallows the failure) — the exact "stale grok-head" failure mode this repair prevents. Uncontrolled version drift. Reject.
- **Pinned installed binary (recommended)**: hook execution only uses `state-report` and `context hook`, whose behavior did not change between `8d49a216` and HEAD for grok (the `36829c4`/`7efa493` changes target OpenCode debounce/reasoning-gap logic). Residual risk is administrative, not runtime: until `~/.local/bin/aplexer` is upgraded to a build ≥ `36829c4`, (a) any `a init` / `a init --engine grok` run **from it** rewrites the grok file back to the broken five-event table (empirically shown in §3.3), and (b) its `a init --check --json` reports grok `missing events: Notification` (exit 1), which can mislead an operator into exactly that regression. Mitigations: this document; upgrade `~/.local/bin/aplexer` to a release build of ≥ `36829c4` (owner: a principal — builds were out of scope for this read-only executor); after upgrade, `a init --engine grok` converges to the same target content and `--check` goes green.

Recommendation: pin `/home/alexey/.local/bin/aplexer` (sha `8d49a216…`) and treat the binary upgrade as the follow-up that makes re-init safe.

## 5. Repair proposal (exact, reversible)

**Approach note**: the timeline-diagnostics report (§3.D.1) proposed keeping `Notification` with `matcher: "permission_prompt"`. Upstream instead removed the Notification wiring entirely (`36829c4`, comment at mod.rs:150-152, test at tests/drivers.rs:33-36). This proposal follows upstream: exclusion is the committed, tested behavior; any future fixed-binary `a init --engine grok` rewrites the owned file from empty (drivers.rs:611) and would wipe a hand-added matcher group, so a hand-added matcher would fight the toolchain. The cost of exclusion — losing a genuine `permission_prompt -> waiting` signal for grok — is upstream's accepted tradeoff.

Owner/applier: claude-principal (or a delegate it supervises). One file changes; grok-head itself only needs to be observed afterwards.

Target `~/.grok/hooks/aplexer.json` (sha256 `4b3f0048d72051589d1db731fa8dcf2c83baf4b9ce26a346c651aeae8611eb82`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/aplexer context hook --engine grok 2>/dev/null || true # aplexer-managed-awareness-hook-v1",
            "timeout": 5,
            "type": "command"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/aplexer state-report working || true",
            "type": "command"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/aplexer state-report idle || true",
            "type": "command"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/aplexer state-report working || true",
            "type": "command"
          }
        ]
      }
    ]
  }
}
```

Steps (run by the applier, not by this executor):

```bash
# 0) sanity: file still matches the audited state
sha256sum ~/.grok/hooks/aplexer.json   # expect df3d7ce9d8d82535fbc5814494f9e299d5680d89ae37af41003eb9a9e69fbd3b

# 1) backup (rollback anchor)
cp -p ~/.grok/hooks/aplexer.json ~/.grok/hooks/aplexer.json.bak-$(date +%Y%m%d-%H%M%S)

# 2) stage + apply (mode preserved; cp window is safe — grok loads hooks at session start, not per event)
#    (target content = JSON block above; write it to /tmp/grok-target.json first)
install -m 600 /tmp/grok-target.json ~/.grok/hooks/aplexer.json

# 3) immediate structural verification (dev build implements the fixed table)
GROK_HOME=$HOME/.grok /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer init --engine grok --check --json
#   expect {"engine":"grok","installed":true,...}; NOTE: the pinned 8d49a216 CLI instead says
#   "missing events: Notification" (exit 1) — expected and correct until the binary upgrade.
sha256sum ~/.grok/hooks/aplexer.json   # expect 4b3f0048d72051589d1db731fa8dcf2c83baf4b9ce26a346c651aeae8611eb82
```

Rollback:

```bash
cp -p ~/.grok/hooks/aplexer.json.bak-<date> ~/.grok/hooks/aplexer.json
# (restores the pre-repair state byte-for-byte, mode 600 preserved by cp -p)
```

Runtime verification (the actual success gate — after grok-head's next completed turn):

1. `a list` / `a snapshot --json` shows grok-head `reported_state: idle` that **persists > 120 s** after the turn's `Stop` (previously the `idle_prompt` Notification clobbered it at ~60 s; 120 s clean proves the clobber is gone).
2. Native deliver to grok-head succeeds (e.g. `a message send --to grok-head ...` or `a send`): the original failure was `'waiting report expired'` rejecting delivery.
3. Negative check: grok's `updates.jsonl` shows no `hook_execution` for `Notification` after the idle chime window.

Reviewers: claude-principal (issuer; per the diagnostics report §E the grok fix review was already assigned to Claude Principal `01a1015a-678f` / grok-reviewer — review focus here shifts from "matcher schema compatibility" to "exclusion parity with upstream `36829c4` + binary-pin decision"); independent second opinion: codex-principal. grok-head should be informed via aplexer before/after the apply.

## 6. UNKNOWNs

- Whether a running Grok session reloads `~/.grok/hooks/aplexer.json` without a restart (docs suggest hooks load at session start; not verified here). If it does not, grok-head keeps the stale in-memory hook table until its next session start — repair takes effect then, not immediately. Falsification: run the §5 verification; if a `Notification` hook_execution still appears ~60 s after a post-apply turn end, a grok-head restart (grok-head's decision, at a safe checkpoint) is needed.
- Whether any routine automation (principals, doctor, future `a init`) runs `a init --engine grok` or bare `a init` from the stale `8d49a216` binary before it is upgraded — that would silently regress the file to the broken table (§3.3). Mitigation: broadcast this caveat to principals; prioritize the binary upgrade.
- Exact installed-CLI provenance of the current `~/.grok/hooks/aplexer.json` (03:29 run): inferred from the embedded dev path and pre-`36829c4` event table; no log was consulted.
- Whether Grok ever emits a genuine `permission_prompt` notification this host would want mapped to `waiting`: currently no; if wanted later, it must land upstream in `GROK_EVENTS` (with `matcher`), not as a local hand-edit, or the next owned-file rewrite removes it.

## 7. Experiment artifacts

- /tmp/opencode/grokhook.eBmR3J/ — installed-CLI dry-run (check + install; output still contains Notification)
- /tmp/opencode/grokhook2.KU4Fi6/ — dev-build dry-run (install writes the fixed table)
- /tmp/opencode/grokhook3.59c0Nb/ — pinned-path target JSON validated against both binaries' `--check`

/tmp is ephemeral; this section is the durable record. All source citations: /home/alexey/git/cloudflare-aplexer-protocol @ 7efa493 (read-only).
