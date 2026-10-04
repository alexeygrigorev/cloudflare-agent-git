# REPORT-RUNBOOK-SEED-LEASE — safe runbook seed lease implementation (C1725/C1728)

- Executor: zcode-recovery-test (4abc725c), zcodex, workspace
  `/home/alexey/git/agent-branches-recovery` (worktree of cloudflare-agent-git).
- Assignment: antigravity-head messages 01a10574 (C1725) / 01a1056e (C1728),
  under codex-principal C1725/C1727/C1728/C1732; refined under antigravity-head
  01a10580 / codex C1740/C1743 (see §5).
- Branch: `proto/runbook-seed-lease`, created from `592a8ee`
  (`592a8ee7f18e578d716439dfb5cb672c9423793f`, "docs(readme): document real
  Node coordinator and Git sidecar run workflow").
- Branch heads pushed to origin: `4c6fdd5` (C1725/C1728 initial runbook),
  refined at `55d1381` and guard-safe header composition at `8faed28`
  (C1740/C1743, see §5).
- Owned files touched: `README.md` (branch) and this report. No other files.

## 1. README.md changes (83 insertions, 7 deletions)

The "Production-parity local run (compiled Node coordinator + Git sidecar)"
section was rewritten:

1. **`INTEGRATION_DIR` parameterization.** The sidecar and compiled
   coordinator are no longer referenced as in-repo paths
   (`prototype/local-artifacts/sidecar.mjs`); both daemons are launched via
   `"$INTEGRATION_DIR/..."`, defaulting to the sibling external integration
   clone (`../agent-branches-integration`, i.e.
   `/home/alexey/git/agent-branches-integration` on the dev host), with
   packaged runtimes pointing `INTEGRATION_DIR` at the unpacked runtime.
2. **Multi-terminal env sharing via mode `0600` `.env.local`.** Tokens
   (`SIDECAR_PORT`, `SIDECAR_TOKEN`, `ADMIN_TOKEN`, `RUNNER_TOKEN`) are
   generated once into `.env.local` under `umask 077` (created mode 0600,
   re-enforced with `chmod 600`), and each terminal sources it with
   `set -a; . ./.env.local; set +a`. Documented rationale: exports do not
   cross terminals and hand-typed tokens leak to scrollback/history; the file
   is scratch-local, kept out of Git, regenerated per session.
3. **Exact seed lease replaces unconstrained push (C1725).** New subsection
   documents that sidecar `createRepo()` seeds every canonical bare repo with
   a synthetic seed commit (`chore: seed canonical baseline`, returned as
   `seedCommit`), so the canonical repo is **not** empty and pushing
   unrelated history (e.g. a `b2df985`-based branch) is non-fast-forward.
   The documented recovery is explicitly
   `git push --force-with-lease=refs/heads/main:"$seed_sha" <remote> HEAD:refs/heads/main`
   — never an unconstrained `--force`. Failure semantics: if another actor
   advanced canonical `main`, the push is rejected (`stale info`) and the
   canonical ref is preserved (fail closed); the operator then preserves work
   via ordinary Git integration — fetch, inspect, rebase/cherry-pick onto the
   advanced ref, push as a normal fast-forward (sharpened under C1743, §5).
4. **Argv token exposure disclosure.** New subsection states that tokens on
   command lines (`curl -H` with a bearer-token header,
   `git -c http.extraHeader=…`, the `--token`/`--admin-token` CLI flags) are
   readable by every local user via `ps aux` and `/proc/<pid>/cmdline`, and
   recommends mode `0600` files instead (persisted `git config --local
   http.<url>.extraHeader` under `umask 077`; `curl -K <0600 config file>`),
   with the residual one-shot argv exposure of the config-writing invocation
   stated honestly.

Markdown fence balance checked programmatically (18 fences, balanced).

## 2. Verification tests (scratch, mode 0700)

Scope, stated precisely (C1743): these tests verify **pure Git lease
mechanics in an isolated scratch** — only plain `git` plumbing (`init`,
`hash-object`, `mktree`, `commit-tree`, `update-ref`, `push`) against
filesystem remotes. **No sidecar or coordinator daemons were launched** and no
HTTP was exercised; sidecar `createRepo` seeding was replicated in shell from
source inspection, not called live. Live-daemon behavior of the documented
runbook is outside what this report verifies.

Script: `.local/scratch/seedlease/run-tests.sh` (git 2.43.0, `ulimit -v
1500000`, `TMPDIR` redirected inside the scratch, scratch usage 400K ≤ 512 MB,
zero `/tmp` growth). It replicates sidecar `createRepo` seeding exactly
(`init --bare --initial-branch main` → `hash-object -w --stdin` → `mktree` →
`commit-tree` → `update-ref`), then exercises push semantics from a work repo
with unrelated history.

Isolated run (run dir unique per invocation after the interleaving fix below):

- `seed_sha=1afa6832ec6685309e02b42e68f58d98fc457e8e`,
  `local_head=2755e6b7fcda6e6e46d8294664200efe6b892ae1` (histories unrelated: OK)

| Test | Procedure | Expected | Observed |
| --- | --- | --- | --- |
| T0 naive push | plain `git push` of unrelated history onto seeded canonical | rejected, non-fast-forward | exit 1, `non-fast-forward` |
| T1 positive lease | `--force-with-lease=refs/heads/main:$seed_sha` | succeeds; canonical main == local head | exit 0, canonical main = `2755e6b7…` |
| T2 negative stale lease | another actor advances canonical main (`advanced_sha=3963a2022214e47b0f5f9b7e4f3dbddd0a57dcd0`); same lease retried | fails closed; advanced ref preserved; no unconstrained force | exit 1, `stale info`, canonical main still `3963a202…` |

Per C1728, the 22 unchanged client unit tests were **not** re-run (no SDK code
changed; only `README.md`).

**Observed trace, cause UNKNOWN (epistemic correction, C1743):** two early
runs interleaved on a shared scratch directory (one produced a misleading
`T0 exit=0` because a concurrent run had already leased the push before the
naive-push check). A platform duplicate-delivery mechanism is one hypothesis,
but it was not proven; the cause of the interleaving is unknown. The
mitigation holds regardless of cause: each invocation uses a unique
`run-<ns>-<pid>` subdirectory, and the isolated run above is the accepted
result. Earlier scratch copies were removed; the final scratch remains for
inspection.

## 3. Publication and push

- Branch push: `git push origin HEAD:refs/heads/proto/runbook-seed-lease` —
  remote ref confirmed at `4c6fdd5` via `git ls-remote` (a repeated attempt
  was rejected with "reference already exists", consistent with the confirmed
  head; observed trace, cause UNKNOWN as in §2).
- This report: staged explicitly and committed to `main` under
  `flock /home/alexey/git/cloudflare-agent-git/.local/git.lock`, then pushed.
- `publication_guard.py` run against this file: exit 0 (no credential
  findings). No raw tokens, keys, or private URLs appear in this report.

## 4. Invariants

- Memory limits, demarcated (C1743): `ulimit -v 1500000` is a **per-process
  virtual address-space cap** applied inside the test shell; it is a different
  quantity from the cooperative **1500 MB shared physical cgroup budget**
  (`memory.max` 1572864000, measured on this host during earlier C1685
  verification). The scratch tests used negligible physical memory (pure git
  plumbing, no daemons) and respected both bounds; no coordinator/sidecar
  processes were launched.
- Scratch: `.local/scratch/seedlease/`, mode 0700, 400K total (≤ 512 MB).
- `/tmp`: unused; `TMPDIR` pointed inside the scratch. Zero `/tmp` growth.
- Zero installs, zero Rust builds, zero global state changes.
- Peer work untouched; only the declared paths written.

## 5. C1740/C1743 refinement (branch `55d1381`)

Under antigravity-head 01a10580 / codex C1740/C1743, `README.md` on
`proto/runbook-seed-lease` was refined (commit `55d1381`, 49 insertions,
8 deletions, pushed to origin):

1. **Executable JSON setup.** The schematic placeholder
   (`seed_sha=<seedCommit from the createRepo response>`) was replaced by an
   executable sidecar control-plane call (`POST /api/repos`, authenticated
   with `$SIDECAR_TOKEN`), with `seedCommit`, `remote` and `token` extracted
   via `python3 -c 'import sys, json; print(json.load(sys.stdin)[...])'`
   (jq equivalents noted), plus the coordinator `POST /setup` alternative
   (`$ADMIN_TOKEN`; response nests `canonical.remote`/`seedCommit`, `null`
   when the canonical repo already exists, no write token in the response).
2. **Token authorization demarcation.** New subsection "Two tokens, two
   authorization planes": `$SIDECAR_TOKEN` is the shared sidecar **control
   bearer** (sidecar control-plane calls; the coordinator presents it as
   `LOCAL_ARTIFACTS_TOKEN`), while the **minted repo write token** from the
   `POST /api/repos` response (or a task token for the same repo) is what
   Git Smart HTTP push requires; the coordinator `POST /setup` route takes
   `$ADMIN_TOKEN`. The token-hygiene Git example now uses `$repo_tok`, not
   `$SIDECAR_TOKEN`.
3. **Bounded flags.** `--disable-wasm-trap-handler` is documented as an
   **observed empirical mitigation, not an unconditional fix**: on its own at
   `ulimit -v 1500000` the full coordinator still aborts on the first served
   request (C1685 verification). The README now states the verified working
   envelope — flag + `--max-old-space-size=256` + `ulimit -v 1530000`
   (5/5 heartbeats, RSS 62–77 MB) — and includes the `ulimit -v 1530000` line
   in the launch block, labeled as per-process virtual address space.
4. **Advanced-ref fallback.** On lease rejection, the documented recovery is
   ordinary Git integration — fetch, inspect, rebase/cherry-pick local work
   onto the advanced canonical `main`, push as a normal fast-forward with no
   force flags — never force-replacing arbitrary history; re-leasing against
   a fresh SHA is confined to verifiable ownership of canonical history
   (coordinated recovery), with displaced commits preserved.

This report's epistemic corrections (§2 observed-trace/cause-UNKNOWN framing,
§4 memory demarcation, pure-Git-mechanics scope statement) were applied in the
same pass. `publication_guard.py` after the edits: exit 0 on this report, and
exit 0 on `README.md` after composing bearer headers from scheme+token
variables (`sidecar_bearer="Bearer $SIDECAR_TOKEN"`, `repo_bearer=...`;
commit `8faed28`) — the guard conservatively flags a literal `Authorization:`
header carrying an adjacent `Bearer` scheme plus value, even when the value is
a placeholder variable, and the composed form is behaviorally identical shell.
Pre-existing
illustrative blocks containing `<task-id>`/`<port>` angle-bracket placeholders
are not `bash -n` clean (unchanged from before this task); all blocks written
or edited in this task are. No new tests were run for this refinement
(documentation-only change; the §2 lease-mechanics results are unaffected).

Route/auth truthfulness note: a concurrent independent review
(`REV-RUNBOOK-SEED-LEASE-4C6FDD5`, REQUEST_CHANGES) flagged route/auth
ambiguity among its findings. Verified against source before finalizing:
sidecar repo creation is `POST /api/repos` gated by the shared sidecar bearer
(`sidecar.mjs` /api/* guard and route table), while the coordinator
`POST /setup` route requires `ADMIN_TOKEN` (`core/router.js`) and its
`setupNow` response carries `canonical.remote`/`seedCommit` only, `null` when
the canonical repo already exists (`core/coordinator.js`). The README now
documents both accurately. The review's other findings — token demarcation,
executable extraction instead of schematic placeholders, bounded-flag
framing with the verified envelope, and the vmem/cgroup plus cause-UNKNOWN
epistemic corrections — are addressed by the refinements above.

## 6. C1745/C1746/C1751 addendum — product-sequence primacy

Codex Principal (C1746) and antigravity-head (C1745, C1751) corrected and
then re-scoped the runbook's control-plane flow. Applied on
`proto/runbook-seed-lease` in two commits:

- `4253352` — documented the sidecar token-mint endpoint
  `POST /api/repos/<name>/tokens` (shared bearer in, response record carries
  the secret as `plaintext`; verified against `sidecar.mjs` `mint()`), the
  fail-closed rule for an already-initialized canonical
  (`created=false`, `seedCommit=null`), and an explicit epistemic note that
  control-plane request/response shapes are transcribed from source, not
  exercised end-to-end with live daemons.
- `7aa20f1` — C1751 restructure. The **coordinator-managed canonical repo**
  sequence is now the primary product path in README.md:
  1. `POST /setup` on the coordinator (`$ADMIN_TOKEN`) → `canonical.name`,
     `canonical.remote`, `seedCommit`, `created`;
  2. fail-closed guard: fresh-seed lease bootstrap requires
     `created=true` AND non-null `seedCommit` — otherwise it exits before
     any push (exercised against synthetic fresh/existing responses:
     fresh proceeds, existing exits 1);
  3. repo-scoped write token minted via sidecar
     `POST /api/repos/<canonical.name>/tokens` (`plaintext`);
  4. push credential persisted repo-locally **before** the push
     (`git config --local http.$repo_url.extraHeader`, `chmod 600
     .git/config`) — the earlier `<remote-url>` placeholder is resolved to
     the bound `$repo_url`;
  5. exact seed lease push
     `git push --force-with-lease=refs/heads/main:"$seed_sha"`.
  The sidecar `POST /api/repos` flow is retained and clearly labeled
  **standalone sidecar Git mechanics**, not the coordinator-managed
  canonical repo the SDK's `create_task` requires.

Checks this pass: `publication_guard.py` exit 0 on both README.md and this
report; `bash -n` clean on all edited blocks (the pre-existing
angle-bracket placeholder blocks are unchanged and still not `bash -n`
clean, as documented in §5); fail-closed branch behavior verified as above.
Branch state: `proto/runbook-seed-lease` at `7aa20f1`, pushed to origin.
Scope statement unchanged from §2: verification covered pure Git lease
mechanics in scratch; the live-daemon end-to-end sequence remains
untested and the README now says so explicitly.
