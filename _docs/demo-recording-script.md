# Demo recording steps

## Prepare the environment

1. Check versions: `node --version` (>= 22), `npm --version`, `python3 --version` (>= 3.10), `git --version`.
2. Get the code: `git clone https://github.com/alexeygrigorev/cloudflare-agent-git.git && cd cloudflare-agent-git` (or in an existing clone: `git pull origin main`).
3. Install and build: `cd prototype && npm install --no-fund --no-audit && npm run build:node`.
4. Create `prototype/.env` (from inside `prototype/`): `scp hetzner:~/.config/cloudflare/agent-branches-live.env .env`, then add the URL: `grep '^BASE_URL=' .env.example >> .env`.
   - `BASE_URL`: the deployed Worker URL (https).
   - `ADMIN_TOKEN`: admin bearer token (budget, cleanup).
   - `RUNNER_TOKEN`: trusted runner token (submits checks).
   - Without Hetzner access: `cp .env.example .env` and paste the two tokens.
5. Check that `.env` is ignored: `git check-ignore .env` prints `.env`.
6. Load the variables into the shell for curl: `set -a; . ./.env; set +a; export GIT_TERMINAL_PROMPT=0; clear`.
7. Dry run at zero cost: `python3 demo/cloud-smoke.py --mock` (should end 8/8 PASS).
8. Check the budget: `curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/cloud/budget" | python3 -m json.tool` (you need `remainingDayOps` >= 90 and `repoCount` 0).
9. Start the UI server in a second terminal: `python3 -m http.server 8765 --directory ui` (from `prototype/`).

## Record

1. Show the README at https://github.com/alexeygrigorev/cloudflare-agent-git. Say: "Agent Branches gives each coding agent its own Git fork on Cloudflare Artifacts."
2. `curl -s "$BASE_URL/public/status" | python3 -m json.tool`. Say: "This is the live Worker on Cloudflare."
3. `python3 demo/cloud-smoke.py --actors 2 --output report.json`. Say: "Two agents push at the same time, and a trusted runner checks them."
4. `curl -i -s -X POST "$BASE_URL/public/status" | head -n 5`. Say: "Writes to public endpoints are refused with 405."
5. Open http://localhost:8765/index.html?fixture=1. Say: "One pair conflicts, so the changes are not safe to combine."
6. Open http://localhost:8765/index.html?fixture=semantic. Say: "Each agent's tests pass alone, but the combined tests fail."
7. Open http://localhost:8765/index.html?fixture=lost-push. Say: "A lost push stays unknown, never safe."
8. Open http://localhost:8765/task.html?id=task-0001&fixture=1. Say: "The tests ran on an older change, so this one is not proven safe."
9. `python3 -m json.tool report.json`. Say: "All checks passed, repos cleaned up, well inside the budget."

## Fallback

1. If the live run fails: run `curl -s -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/cloud/demo-repos"` if repos were left over, otherwise record `python3 demo/cloud-smoke.py --mock` and use the frozen video `docs-submission/videos/agent-branches-demo-draft.mp4`.
