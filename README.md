# cloudflare-agent-git

Research and prototypes for an agent-native Git platform on Cloudflare Workers and Artifacts.

Current competition prototype: **Agent Branches** — submission write-up in
[`SUBMISSION.md`](SUBMISSION.md), local reproduction in [`live/`](live/README.md).
The coordinator's HTTP wire contract is
[`prototype/CONTRACT.md`](prototype/CONTRACT.md) (v0.1.2): `POST /setup`,
`POST /tasks`, `POST /events/push`, `POST /events/artifacts`, `POST /checks`,
`GET /status`, `GET /tasks/:id`, `POST /tasks/:id/tests`,
`POST /warnings/:id/ack`.

## Quickstart (verified 2026-10-04 against CONTRACT v0.1.2)

Prerequisites: `node` + `npx` (wrangler dev), `python3`, `git`, `rsync`;
headless Chrome only for the demo's screenshot step.

```sh
# 0) full end-to-end demo (branch proto/live; 36/36 assertions in run 3)
git clone https://github.com/alexeygrigorev/cloudflare-agent-git.git
cd cloudflare-agent-git
git checkout proto/live

# 1) untracked token file live/.dev.vars (never committed; mode 600).
#    Tokens are arbitrary bearer strings you choose:
cat > live/.dev.vars <<'EOF'
export ADMIN_TOKEN='<random>'
export RUNNER_TOKEN='<random>'
export SIDECAR_TOKEN='<random>'
export SIDECAR_PORT=8799
export WORKER_PORT=8787
export UI_PORT=8788
EOF
chmod 600 live/.dev.vars

# 2) from the repo root (so `python3 -m radar` resolves) — one command runs
#    the whole demo; steps are idempotent via markers in live/state/:
bash live/run-demo.sh > live/run-3.log 2>&1
echo "exit=$?"   # 0 on success (never pipe the script into tail -f; read the log)

# 3) inspect results
cat live/evidence/run-3/result.json    # assertions, machine-readable
cat live/evidence/run-3/summary.txt    # same, human-readable
python3 -m json.tool live/evidence/run-3/status.json | head -40
```

Details: [`live/README.md`](live/README.md) (exact commands, port hygiene,
gap list), [`SUBMISSION.md`](SUBMISSION.md) (§"Try it locally", deploy plan,
limitations), [`docs-submission/DEMO-SCRIPT.md`](docs-submission/DEMO-SCRIPT.md)
(8-minute video script against committed evidence).

## Prototype dev loop (verified timings)

```sh
cd prototype
npm install          # single workerd stack
npm run typecheck    # tsc --noEmit (~2 s)
npm test             # worker suites in workerd vs real-git sidecar: 67/67 (~35 s)
npm run test:sidecar # sidecar tests: 16/16 (~2 s)
npm run test:all     # typecheck + both suites

# local dev: sidecar + worker (two terminals)
npm run sidecar                    # binds 127.0.0.1:8790 (env-overridable)
cp .dev.vars.example .dev.vars     # set ADMIN_TOKEN, RUNNER_TOKEN, ...
npx wrangler dev --local           # localhost only
```

Auth (all mutating routes are bearer-gated, fail closed with 503 when a
secret is unset): `POST /setup` and `POST /tasks` need `ADMIN_TOKEN`;
`POST /checks` needs `RUNNER_TOKEN` and a `contract: "0.1"` (typed) or
`"0.0"` (legacy) field — missing/unknown is 400, moved heads are 409;
`/events/push`, `/tasks/:id/tests`, `/warnings/:id/ack` accept `ADMIN_TOKEN`
or the agent's per-task token (cross-agent writes are 403); reads
(`GET /status`, `GET /tasks/:id`) are open. Agent pushes use ordinary git
with the task token (`git -c http.extraHeader="Authorization: Bearer $TOKEN"
push`), plus a token-authenticated `POST /events/push` report.

CLI + radar matrix:

```sh
python3 agent-branches task create --agent claude --intent "fix login loop" --admin-token "$ADMIN_TOKEN"
python3 agent-branches status            # coordinator status (reads are open)
python3 -m radar --l1                    # CONTRACT v0.1 checks payload for POST /checks
python3 agent-branches checks --file radar1-l1.json --runner-token "$RUNNER_TOKEN"
```

Newcomer verification report (commands tested, timings, doc fixes):
[`research/antigravity/runbook/CLI-NEWCOMER-REPORT.md`](research/antigravity/runbook/CLI-NEWCOMER-REPORT.md).
