# Muse round 15 (C-INDEPENDENT-RUNTIME-NEXT): cold-wire stub test bf9d7ed22a

Reviewer: muse-reviewer (7e6e9bb0), per codex-principal 01a0ffcf. Read-only
review + node probes only. NO cargo build, NO test execution (24GB target
risk), NO global install. Owner (via Antigravity scheduling) holds execution.

## Verdict: test design SOUND, four qualifications before it counts as proof

1. **Real execution, not skip — CONDITIONAL on node.** The `node_available()`
   gate skips loudly (stderr) when node is absent. node v24.13.1 IS present
   on this host, so the test would execute for real here; on a node-less
   builder it passes vacuously. Recommend CI pin: fail (not skip) when node
   is required, or record node presence in the result artifact. Verified
   present here, so the design is live, not theoretical.
2. **Old-yolo negative WITHOUT compile — VALIDATED at stub level.** I
   replicated the stub's mode branch under node directly (/tmp scratch,
   cleaned): `--mode yolo` appends inner, `--mode build` appends nothing.
   Therefore reverting client.rs to yolo MUST yield 2 probe lines (test
   fails) — the negative control holds by construction, no rebuild needed
   to trust it. The argv log + counter file give post-failure forensics. ✓
3. **Single-count vs retry/resume — NOT separated.** The test drives ONE turn;
   the stub emits tool_call only on first invocation (counter-gated) and
   text thereafter, so retry/resume re-execution is stubbed away, never
   exercised. The `==1` assertion additionally conflates "outer ran once"
   with "nothing else wrote" (mitigated by the argv log). Proven: single
   executor per fresh turn. Unproven: retried/resumed turns stay
   single-effect. Recommend a second-turn retry probe (same command,
   resumed session) as the explicit follow-up before claiming stable-op
   safety.
4. **Env isolation — real flake vector, cheap fix available.** EnvVarGuard
   mutates process-global HOME/ZCODE_CJS/ZCODE_WARM with drop-restore; safe
   under nextest (per-process), RACED under plain `cargo test` threads —
   sibling suites (mcp_oauth, rmcp_client) also mutate env, and no
   `#[serial]` anywhere near this test although the repo already depends on
   serial_test (used by those very siblings). The window spans a full mock-
   server turn (seconds), not microseconds. Recommend `#[serial]` on the
   test now (one line, owner-side), and document nextest-vs-cargo behavior.
   Residual even then: serial only orders serial-marked tests.

## Statuses and budget (real, unmasked)
- No build, no test process launched by me: codex-rs/target ABSENT (du 0),
  dupexec .local 28K. Zero build growth attributable to this review.
- Disk: / 73% (115G free), /tmp 85% (68G free) — ample floor, no pressure.
- My node probes cleaned their /tmp scratch; exit codes read directly, no
  pipe-masked statuses in any verdict above.

## Scheduling note for Antigravity (runtime head)
Execution (build + suite + retry probe) is yours to schedule with the owner;
my acceptance for the one-effect claim: pinned binary hash, COUNT 2→1
demonstrated on the yolo-vs-build pair (stub level already proven here),
retry/resume single-effect, serial/env discipline recorded. Preserve the
DIAGNOSIS/PATCH history; do not treat this review as execution.
