# WORKLOG — claude-exec-l5 (Agent Branches demo target)

## Session identity (a whoami --json, 2026-10-03)

- id: `78661d2c-c415-4237-ac05-9f90e6a35da9`
- tag: `claude-exec-l5` (engine: shell / opencode, model `zai-coding-plan/glm-5.3`)
- parent_session: `b3a92dd0-a17e-4a62-940f-eb3b829393f6` (claude-principal)
- workspace: `/home/alexey/git/cloudflare-agent-git`
- worktree: `/home/alexey/git/agent-branches-l5`, branch `proto/l5-demo-target` (from `origin/main` @ 99e2db2)

## Mission

Build the canonical repo the demo agents will work on: a tiny Cloudflare-Worker-style
"shortlinks" service (zero npm dependencies, `node --test`), plus `TASKS.md` with 3
realistic overlapping tasks:

1. each task alone passes the full suite;
2. T1 + T2 must produce a **textual** git merge conflict (same function/file);
3. T2 + T3 must merge **cleanly** but break a test together (**semantic** conflict:
   T2 changes `ShortlinkService.create`'s contract, T3 adds a new caller on the old contract).

Proof: reference solutions kept as patches in `reference-solutions/` (NOT for demo agents),
and `verify-overlap.sh` prints the 3 facts.

## Progress

- [x] `a whoami --json` recorded (above)
- [x] worktree created, work declared (`demo-target/**`)
- [x] base service + test suite (commit "base")
- [x] TASKS.md
- [x] reference solutions on branches `demo-l5-task-{1,2,3}` + patches
- [x] verify-overlap.sh, all 3 facts verified (transcript below)
- [x] pushed, principal notified

## Verification transcript (verify-overlap.sh, 2026-10-03)

    demo-target overlap verification (base ff4decd7be)

    FACT 1 — each task alone passes the full suite:
             T1=PASS  T2=PASS  T3=PASS

    FACT 2 — merging T1 with T2 yields a TEXTUAL git merge conflict:
             CONFLICT in: demo-target/src/shortlinks.js

    FACT 3 — merging T2 with T3 is clean but the suite FAILS (SEMANTIC conflict):
             merge rc=0 (clean); failing test: "POST /links/bulk imports every link and returns slugs in order"

    ALL 3 FACTS VERIFIED

Also verified manually: in the T2+T3 merge the bulk endpoint returns 400 (assertion
`400 !== 201`) because T3's positional `create(item.slug, item.url)` hits T2's
object-form contract (`slug` destructures to undefined → "slug is required").

Reference branches: `demo-l5-task-1` (9f992dc), `demo-l5-task-2` (a292e7e),
`demo-l5-task-3` (e9d109a), all cut from BASE ff4decd; patches + notes in
`reference-solutions/` (harness-only, not for demo agents).
