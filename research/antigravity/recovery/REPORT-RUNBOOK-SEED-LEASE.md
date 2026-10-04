# REPORT-RUNBOOK-SEED-LEASE — safe runbook seed lease implementation (C1725/C1728)

- Executor: zcode-recovery-test (4abc725c), zcodex, workspace
  `/home/alexey/git/agent-branches-recovery` (worktree of cloudflare-agent-git).
- Assignment: antigravity-head messages 01a10574 (C1725) / 01a1056e (C1728),
  under codex-principal C1725/C1727/C1728/C1732.
- Branch: `proto/runbook-seed-lease`, created from `592a8ee`
  (`592a8ee7f18e578d716439dfb5cb672c9423793f`, "docs(readme): document real
  Node coordinator and Git sidecar run workflow").
- Branch head pushed to origin: `4c6fdd55131b454ed99dee5dbafb31a3c3dd251e`.
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
   canonical ref is preserved (fail closed); the operator must fetch, inspect,
   and re-lease against a freshly verified SHA.
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

Script: `.local/scratch/seedlease/run-tests.sh` (git 2.43.0, `ulimit -v
1500000`, `TMPDIR` redirected inside the scratch, scratch usage 400K ≤ 512 MB,
zero `/tmp` growth). It replicates sidecar `createRepo` seeding exactly
(`init --bare --initial-branch main` → `hash-object -w --stdin` → `mktree` →
`commit-tree` → `update-ref`), then exercises push semantics from a work repo
with unrelated history.

Isolated run (run dir unique per invocation after the duplicate-delivery fix):

- `seed_sha=1afa6832ec6685309e02b42e68f58d98fc457e8e`,
  `local_head=2755e6b7fcda6e6e46d8294664200efe6b892ae1` (histories unrelated: OK)

| Test | Procedure | Expected | Observed |
| --- | --- | --- | --- |
| T0 naive push | plain `git push` of unrelated history onto seeded canonical | rejected, non-fast-forward | exit 1, `non-fast-forward` |
| T1 positive lease | `--force-with-lease=refs/heads/main:$seed_sha` | succeeds; canonical main == local head | exit 0, canonical main = `2755e6b7…` |
| T2 negative stale lease | another actor advances canonical main (`advanced_sha=3963a2022214e47b0f5f9b7e4f3dbddd0a57dcd0`); same lease retried | fails closed; advanced ref preserved; no unconstrained force | exit 1, `stale info`, canonical main still `3963a202…` |

Per C1728, the 22 unchanged client unit tests were **not** re-run (no SDK code
changed; only `README.md`).

**Environment quirk, disclosed:** the sandbox duplicate-delivers commands; two
early runs collided on a shared scratch directory (one produced a misleading
`T0 exit=0` because a duplicate run had already leased the push before the
naive-push check). Fixed by making each invocation use a unique
`run-<ns>-<pid>` subdirectory; the isolated run above is the accepted result.
Earlier scratch copies were removed; the final scratch remains for inspection.

## 3. Publication and push

- Branch push: `git push origin HEAD:refs/heads/proto/runbook-seed-lease` —
  remote ref confirmed at `4c6fdd5` via `git ls-remote` (first delivery
  succeeded; the duplicate-delivered second attempt was rejected with
  "reference already exists", consistent with the confirmed head).
- This report: staged explicitly and committed to `main` under
  `flock /home/alexey/git/cloudflare-agent-git/.local/git.lock`, then pushed.
- `publication_guard.py` run against this file: exit 0 (no credential
  findings). No raw tokens, keys, or private URLs appear in this report.

## 4. Invariants

- Memory cap: `ulimit -v 1500000` inside the test shell. Cooperative 1500M
  convention respected; no coordinator/sidecar processes launched.
- Scratch: `.local/scratch/seedlease/`, mode 0700, 400K total (≤ 512 MB).
- `/tmp`: unused; `TMPDIR` pointed inside the scratch. Zero `/tmp` growth.
- Zero installs, zero Rust builds, zero global state changes.
- Peer work untouched; only the declared paths written.
