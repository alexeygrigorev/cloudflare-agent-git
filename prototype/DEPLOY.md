# DEPLOY — agent-branches coordinator (production)

Pre-deploy security checklist status: PLAN-L1-REAL §5 (origin/proto/artifacts-spike),
implemented on `proto/deploy-prep`. A reviewed deploy after this document is a
single command (§Deploy). **Nothing here authorizes a deploy by itself** — the
competition rules and README still require the review gate.

## 0. Gates before ANY deploy (all must be checked, in order)

1. **§5.9 spike cleanup gate (due 2026-10-07, hard prerequisite)** — namespace
   `agent-branches-dev` + its 3 demo repos must be torn down per PLAN-L1-REAL
   §5.9 (revoke tokens → verify zero active per repo → DELETE repos → DELETE
   namespace → remove local 0600/`/tmp` scratch). This gate belongs to the
   claude-principal lane and must be recorded DONE before a public deploy.
2. **Independent §5 re-derivation review** of this exact revision (a
   reviewer re-walks auth/CORS/rate-limit/token-at-rest/webhook against the
   code). muse-r48's review at 3af4c08 must be closed on THIS branch, not the
   spike branch.
3. **ALLOWED_ORIGINS set to the real dashboard origin(s)** in
   `wrangler.jsonc` → `env.production.vars.ALLOWED_ORIGINS` (currently empty =
   fail closed). Empty at deploy time means no browser client can call the
   Worker — safe, but the UI will not work.
4. **Secrets set** (§Secrets below) — including `EVENTS_WEBHOOK_SECRET`,
   which is REQUIRED before any `/events/*` receiver is publicly reachable
   (§5.1: webhook auth is mandatory the moment the receiver ships).
5. **Namespace exists** (§Bootstrap) — `agent-branches-prod`, created once via
   REST; the binding does not create it.

## Prerequisites

- `CLOUDFLARE_API_TOKEN` scoped to **Artifacts Edit + Workers deploy for this
  account only**, and `CLOUDFLARE_ACCOUNT_ID`. The orchestrator provides them
  in `~/.config/cloudflare/agent-branches.env` (mode 0600). Load per shell:
  ```bash
  set -a; . ~/.config/cloudflare/agent-branches.env; set +a
  ```
  Never commit, echo or log either value (the redactor pattern in
  `src/redact.ts` covers accidental logs; `precommit-secret-scan.sh` covers
  staged diffs).
- wrangler ≥ 4.147 (pinned in devDependencies; no installs needed — reuse the
  lane's `node_modules`).

## Bootstrap (one-time, before first deploy)

Create the production namespace (REST — namespace create has no wrangler
subcommand, PLAN-L1-REAL §1; token comes from the env file above, never inline):

```bash
curl -sS -X POST "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/artifacts/namespaces" \
  -H "authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "content-type: application/json" \
  -d '{"name": "agent-branches-prod"}'
npx wrangler artifacts namespaces list   # verify it appears; dev ns must NOT be reused
```

Idempotency: re-running the POST on an existing name is a no-op/error from the
API — verify with the list call. The canonical repo and its base commit are
NOT created here; `POST /setup` (after deploy) creates them **inside the
bound namespace** via the Worker's own binding.

## Secrets (per environment; values NEVER in wrangler.jsonc or Git)

```bash
npx wrangler secret put ADMIN_TOKEN --env production           # admin routes (/setup, /tasks)
npx wrangler secret put RUNNER_TOKEN --env production          # trusted runner route (/checks)
npx wrangler secret put EVENTS_WEBHOOK_SECRET --env production # REQUIRED: /events/* HMAC (§5.1)
```

Each prompts for the value interactively (`--env production` is mandatory —
without it the secret lands on the wrong environment). Generate high-entropy
values (`openssl rand -hex 32`). Rotation = re-run `secret put` + restart
consumers; the Worker reads secrets per request, no redeploy needed.

Optional/local-only: `LOCAL_ARTIFACTS_URL`/`LOCAL_ARTIFACTS_TOKEN` belong to
the dev sidecar and must NOT be set on production.

Webhook senders compute `x-webhook-signature = hex(HMAC-SHA256(secret, "<timestamp>.<rawBody>"))`
with `x-webhook-timestamp` = unix seconds (±300 s replay window) — see
`src/webhook.ts`. A Cloudflare Artifacts event subscription must be configured
with this same shared secret at creation time (§5.1: verify at creation).

## Deploy (single reviewed command)

```bash
npx wrangler deploy --env production
```

This uploads the Worker + `Coordinator` DO (migration `v1`, new_sqlite_classes),
binds `ARTIFACTS` → namespace `agent-branches-prod`, and applies the `vars`
(`ALLOWED_ORIGINS`, `ARTIFACTS_NAMESPACE`, `RATE_LIMIT_PER_MINUTE`). Secrets
are referenced, never shipped in the bundle.

Post-deploy smoke (from this repo, real tokens, no logging of outputs):

```bash
BASE="https://agent-branches.<your-subdomain>.workers.dev"
curl -sS "$BASE/status" | head -c 200                       # 200, JSON
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/tasks"   # 401 without token
curl -sS -o /dev/null -w '%{http_code}\n' -X OPTIONS "$BASE/status" \
  -H 'origin: https://not-allowlisted.example'              # 403 (CORS closed)
curl -sS -X POST "$BASE/setup" -H "authorization: Bearer ${ADMIN_TOKEN?}"   # 201
```

## Rollback

```bash
npx wrangler rollback --env production        # interactively pick the previous version
npx wrangler versions list --env production   # audit what is/was live
```

Config mistakes (bad CORS var, namespace typo): fix `wrangler.jsonc` on a
branch, re-review, then plain `deploy` again — config-only changes need no
migration. DO data (model + rate-limit buckets) survives both paths; a
rollback never rewrites stored state.

## Teardown / cleanup (fully remove production)

```bash
# 1. Worker + DO + secrets (wrangler removes the script; DO class is retired
#    with the last deployment — verify the dashboard shows no remaining DO namespace):
npx wrangler delete --env production
# 2. Repos created by the coordinator (canonical + per-task forks), then the
#    namespace — REST DELETE, expect 202s; revoke repo tokens first (§5.2:
#    individual revocation by id from POST-create/list responses):
#    DELETE /accounts/{account_id}/artifacts/namespaces/agent-branches-prod/repos/{repo}
#    DELETE /accounts/{account_id}/artifacts/namespaces/agent-branches-prod
curl -sS "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/artifacts/namespaces" \
  -H "authorization: Bearer ${CLOUDFLARE_API_TOKEN}"   # verify gone
# 3. Rotate any secret that could have leaked; remove local 0600 env files.
```

## Deviations recorded for the reviewer

- **Read routes stay public** (GET /status, GET /tasks/:id) per CONTRACT —
  PLAN §5.1/§5.7 say "no coordinator route is public". The claude-principal
  deploy-prep instruction scoped item (3) to MUTATING routes; the public reads
  are compensated by the per-principal rate limit (default 120/min, anon IP
  bucket) but are still unauthenticated. Reviewer must either accept this with
  the rate limit as mitigation or extend auth to reads before deploy.
- **Webhook signature is enforced only when `EVENTS_WEBHOOK_SECRET` is set**;
  without it `/events/*` keep the CONTRACT bearer posture. Gate 0.4 makes the
  secret mandatory pre-deploy, so production always ships with signature +
  replay-window enforcement live.
- `compatibility_date` stays `2025-06-01` (PLAN §2.4: bump only with the full
  suite green and not required by the binding).
