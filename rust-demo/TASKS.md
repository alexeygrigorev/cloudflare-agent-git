# TASKS.md — three overlapping agent tasks on `rust-demo/crate`

Three agents work on the same tiny crate (`rust-demo/crate/`, branch base =
the commit that introduced it, `bc515c4` "rust-demo: zero-dep shortlinks
crate..."). Each agent gets its own git worktree/clone of the same base
commit and its own branch. The tasks are individually reasonable — that is
the point: each one is green alone, and two of the three pairwise merges
break. This is the demo fodder for agent-branches-style coordination.

**Never ship `rust-demo/.harness/` to the agents** — it contains the
reference solutions and the proof harness. Only `TASKS.md` and the crate
source at the base commit go to each agent.

All builds/tests MUST go through
`/home/alexey/git/cloudflare-agent-git/scripts/guard/build_guard.py`, use
`cargo --jobs 2`, and point `CARGO_TARGET_DIR` inside `rust-demo/`.
Do not change cargo profiles. Zero new dependencies.

---

## T1 — count a hit on every successful resolve

You own branch `t1`, file ownership: `src/lib.rs` (function `resolve` and
the `Entry` struct) and `tests/basic.rs`.

Currently `ShortLinks::hits` never moves: nothing increments it. Make every
**successful** `resolve` count one hit. Keep the public signature
`pub fn resolve(&self, code: &str) -> Option<&str>` unchanged (callers rely
on it) — you will need interior mutability from `std` (`Cell`/`RefCell`) for
the per-entry counter. Unknown codes must NOT count.

Acceptance:
- `cargo test --jobs 2` green (add at least one new test: resolving a code
  twice gives `hits == 2`; unknown code leaves hits at `None`/zero).
- `stats::summary` still works (total_hits now reflects resolves).

## T2 — richer resolve result

You own branch `t2`, file ownership: `src/lib.rs` (function `resolve`) and
`tests/basic.rs`.

Callers keep asking "which code did I actually hit?" after normalization
(case/whitespace). Change the public API:

```rust
pub struct Resolved<'a> {
    pub url: &'a str,
    pub code: String, // the canonical base62 code that matched
}

pub fn resolve(&self, code: &str) -> Option<Resolved<'_>>;
```

Update every in-repo caller and test to the new contract. Do NOT implement
`Display` for `Resolved`, do NOT add convenience methods beyond `#[derive/
manual Debug]`, and do not touch `src/stats.rs` — other lanes depend on that
file staying as-is.

Acceptance:
- `cargo test --jobs 2` green with the new signature.

## T3 — audit log helper

You own branch `t3`, file ownership: `src/stats.rs` (append only) and a new
`tests/audit.rs`.

Support wants a copy-pasteable audit line per code. Append to `src/stats.rs`:

```rust
/// "code -> url" for a known code, None for unknown codes.
pub fn audit_line(links: &ShortLinks, code: &str) -> Option<String> {
    let url = links.resolve(code)?;
    Some(format!("{code} -> {url}"))
}
```

Add `tests/audit.rs` exercising known and unknown codes. Do not modify any
other file (no lib.rs changes; the crate's public API is stable for this
task).

Acceptance:
- `cargo test --jobs 2` green.

---

## What these tasks demonstrate (for the harness, not for the agents)

| Pair   | Git merge | After merge                      | Why |
|--------|-----------|----------------------------------|-----|
| T1+T2  | **textual conflict** (both rewrite `resolve` + `Entry` in `src/lib.rs`) | unresolved | same function, two intents |
| T2+T3  | **clean** (disjoint files: lib.rs vs stats.rs/tests/audit.rs) | **breaks**: `cargo test` fails to compile — `audit_line` destructures `Option<&str>` but `resolve` now returns `Option<Resolved>` which has no `Display` | semantic/contract collision across ownership boundaries |
| T1 alone, T2 alone, T3 alone | — | each green | each is locally correct |

`rust-demo/verify-overlap.sh` proves all three facts from the reference
patches; run it before dispatching the tasks or after any change to them.
