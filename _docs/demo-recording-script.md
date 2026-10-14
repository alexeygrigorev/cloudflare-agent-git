# Live Contest Demo Recording Script (Alexey — 14 October 2026)

> [!IMPORTANT]
> **Recording Window**: Today, **14 October 2026, 15:00–16:00 Europe/Berlin** (on your own computer).
> **Submission Deadline**: **15 October 2026 at 08:59 Europe/Berlin** (`14 October 2026 at 11:59 PM PDT`).
> **Live Worker Endpoint**: `https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev`
> **Public Repository**: `https://github.com/alexeygrigorev/cloudflare-agent-git`

---

## 1. Target Video Length and Contest Rules

- **Official Competition Rules (Section 4 & Challenge Page)**:
  - Require a **5 to 10 minute demo video** (*"Send a 5 to 10 minute demo, open source code, and instructions to run it"*), an open-source repository under a permissive license (`MIT`), reproducible run instructions, and use of **Cloudflare Workers** and **Cloudflare Artifacts** enabling multiple agents to work on changes concurrently.
  - **Content Rule**: Do not disparage any discernible competitor products; keep all comparisons factual and positive.
  - **Human Entry Rule**: The web form at `https://www.cloudflare.com/git-competition` must be submitted manually by a human.
- **Recommended Target Duration**:
  - **Full Standalone Contest Cut: `5:30 – 6:00`** (sits squarely inside the official **5:00–10:00** requirement while keeping a brisk, high-signal pace).
  - **Compact Fast Cut: `~3:30`** (if you want a tight ~3-minute live walkthrough—either as a companion to the frozen 8:00 `r2` video or by trimming the extended UI tour in Scene 4). Both timings are marked in the scene table below.

---

## 2. Operations Budget & Rehearsal Allowance (Read Before Running Live)

The live Cloudflare Worker (`agent-branches`, SQLite Durable Object `Coordinator`, Artifacts namespace `agent-branches-dev`) enforces hard fail-closed budget caps compiled into `prototype/src/cloudflare/budget.ts`:

- **Daily Cap (`MAX_DAILY_OPS`)**: **200 Artifacts operations per UTC day** (resets at `00:00 UTC` / `02:00 Europe/Berlin`; the 138 ops from 13 October were on the previous UTC day).
- **Monthly Cap (`MAX_MONTHLY_OPS`)**: **6,000 Artifacts operations per calendar month** (138 used on 13 October; 5,862 remaining).
- **Repository Cap (`MAX_REPOS`)**: **4 repositories maximum** at any moment (1 canonical + up to 3 forks).
- **Cost per Full Live Smoke Run (`python3 demo/cloud-smoke.py`)**: **~60 Artifacts operations** (creates 1 canonical repo + 2 agent forks, pushes seed + 2 concurrent agent commits, fetches into the runner, runs pairwise `git merge-tree`, runs 5 negative security checks, and deletes all 3 demo repos in cleanup).

### How Many Rehearsals Are Affordable Today?

1. **Raw Daily Cap Math (`200 ops/day`)**:
   - `3 full runs × 60 ops = 180 ops <= 200 ops/day` on raw cap alone, but the preflight gate below cuts this to **2 live runs total** today.
2. **Critical Preflight Gate (`MAX_BUDGET_DELTA_HARD = 90` in `prototype/demo/cloud-smoke.py`)**:
   - Before starting step `[2/8]`, `cloud-smoke.py` checks `GET /cloud/budget` and **refuses to start unless `remainingDayOps >= 90`**.
   - **Run 1**: Starts at `0` used (`200` remaining $\ge 90$) $\rightarrow$ uses `60` ops $\rightarrow$ ends at **`60 / 200`** (`140` remaining).
   - **Run 2**: Starts at `60` used (`140` remaining $\ge 90$) $\rightarrow$ uses `60` ops $\rightarrow$ ends at **`120 / 200`** (`80` remaining).
   - **Run 3**: Sees `80` remaining $< 90$ and **halts at preflight** (`Insufficient operational budget headroom: 80 daily ops remaining, required: >= 90`) unless you run with `--mock`.
3. **Rule for Today's Session**:
   - **Do 0 live cloud rehearsals (or at most 1 live rehearsal = 60 ops), leaving 1 full live take (60 ops, 120/200 total) with a 1-retake buffer.**
   - Use `python3 demo/cloud-smoke.py --mock` (**0 cloud ops**, identical 8-step console output) and `GET /public/status` + `GET /cloud/budget` (**0 cloud ops**) for all practice runs.

---

## 3. Pre-Recording Checklist (Local Setup & Dry Run)

Every step below has been verified from a clean HTTPS clone in `/tmp` on a standard local machine (no Hetzner paths or internal services required).

### 3.1. Prerequisites
Verify local tool versions (`node >= 22`, `python3 >= 3.10`, `git`, `npm`):

```bash
node --version && npm --version && python3 --version && git --version
```

### 3.2. Clean Clone, Build, and Local UI Server (~15 seconds)

Run these commands on your computer before starting the screen recorder:

```bash
mkdir -p /tmp/contest-demo && cd /tmp/contest-demo
git clone https://github.com/alexeygrigorev/cloudflare-agent-git.git
cd cloudflare-agent-git/prototype
npm install --no-fund --no-audit
npm run build:node
```

Start the static Review UI server in a background terminal tab (leave it running on port `8765`):

```bash
python3 -m http.server 8765 --directory /tmp/contest-demo/cloudflare-agent-git/prototype/ui
```

### 3.3. Environment Variables and Tokens (In Your Main Demo Terminal)

In your primary recording terminal (inside `/tmp/contest-demo/cloudflare-agent-git/prototype`), export `GIT_TERMINAL_PROMPT=0` (prevents Git from ever popping up an interactive username/password prompt during negative auth tests), `BASE_URL`, and the two Worker tokens using silent `read -rsp` prompts so credentials never appear on screen or in shell history:

```bash
export GIT_TERMINAL_PROMPT=0
export BASE_URL="https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev"
read -rsp "ADMIN_TOKEN: " ADMIN_TOKEN && echo "ADMIN_TOKEN set" && export ADMIN_TOKEN
read -rsp "RUNNER_TOKEN: " RUNNER_TOKEN && echo "RUNNER_TOKEN set" && export RUNNER_TOKEN
clear
```

*(Note: If you do not have the deployed `ADMIN_TOKEN` and `RUNNER_TOKEN` handy on your local machine, you can either set fresh secrets with `npx wrangler secret put ADMIN_TOKEN` and `npx wrangler secret put RUNNER_TOKEN` from `prototype/`, or use the zero-token `--mock` + local walkthrough flow in Section 5.)*

### 3.4. Zero-Op Dry Run (Verify Everything Works Without Spending Artifacts Ops)

Run these read-only and local commands before hitting Record. Together they spend **0 Cloudflare Artifacts operations**:

```bash
# 1. Live Worker public snapshot (0 Artifacts ops)
curl -s "$BASE_URL/public/status" | python3 -m json.tool

# 2. Live Worker SQLite budget readback (0 Artifacts ops — verify repoCount == 0 and remainingDayOps >= 90)
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/cloud/budget" | python3 -m json.tool

# 3. Full 8-step smoke suite in local loopback mock mode (0 cloud ops, ~0.4s)
python3 demo/cloud-smoke.py --mock

# 4. Local 3-agent conflict & stale-409 harness (0 cloud ops, ~2s)
(cd .. && node prototype/demo/concurrent.mjs && ls -lh .local/result.json)

# 5. Local protocol walkthrough without BASE_URL (0 cloud ops, ~1.5s)
env -u BASE_URL python3 demo/walkthrough.py
clear
```

### 3.5. Windows, Tabs, and Font Sizes to Open

- **Display / OBS Layout**: `1920x1080` or `1280x720` at `30 fps`, Do Not Disturb enabled.
- **Window 1 — Terminal**:
  - **Font size**: **18–20 pt monospace** (~95 columns × 28 rows) so every `PASS` line and JSON field is crisp on video.
  - **Working directory**: `/tmp/contest-demo/cloudflare-agent-git/prototype` with `BASE_URL`, `ADMIN_TOKEN`, `RUNNER_TOKEN`, and `GIT_TERMINAL_PROMPT=0` exported.
- **Window 2 — Browser (Zoom set to `125%–150%`)**:
  - **Tab 1 (GitHub Repo)**: `https://github.com/alexeygrigorev/cloudflare-agent-git`
  - **Tab 2 (Live Public Status JSON)**: `https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev/public/status`
  - **Tab 3 (Review UI — Overview & Pair Radar)**: `http://localhost:8765/index.html?fixture=1`
  - **Tab 4 (Review UI — Semantic Test Conflict)**: `http://localhost:8765/index.html?fixture=semantic`
  - **Tab 5 (Review UI — Lost Push / Unknown Gate)**: `http://localhost:8765/index.html?fixture=lost-push`
  - **Tab 6 (Review UI — Agent Change Story)**: `http://localhost:8765/task.html?id=task-0001&fixture=1`

---

## 4. Scene-by-Scene Live Recording Script

- **6-Minute Full Cut (`5:30–6:00`)**: Follow the **Time (5–6m)** column; meets the official 5–10 minute contest requirement.
- **3-Minute Fast Cut (`~3:15`)**: below the official 5-minute minimum, so do not submit it as the contest video; use only as a companion/teaser. Follow the **Fast Cut (~3m)** column (skip the extra commands marked *(Optional for 6m cut)*).

| Scene | Time (5–6m) | Fast Cut (~3m) | On-Screen | Exact Commands or Clicks | Exact Words to Say |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. The Problem & Edge Architecture** | `0:00 – 0:50` | `0:00 – 0:35` | **Browser Tab 1**: GitHub repo `README.md` (scroll from title & Review UI screenshot down to **Cloudflare entry**). | Show `https://github.com/alexeygrigorev/cloudflare-agent-git`. Highlight the diagram/screenshot and the 3-line summary. | *"Hi, I'm Alexey, and this is Agent Branches. When multiple AI coding agents work on the same repository at the same time, two things break: first, agents collide on shared branches with textual conflicts or silent semantic breakages where each agent's tests pass alone but fail when combined. Second, humans have no clear view of what each agent branched from or whether two changes are actually safe together. Agent Branches gives every coding agent its own isolated Git fork stored in Cloudflare Artifacts, fronted by a Cloudflare Worker Smart HTTP gateway and a single-instance SQLite Durable Object coordinator. The coordinator never runs untrusted agent code or tests—it tracks branch heads, enforces role-scoped bearer tokens, and records pairwise merge and test checks from a trusted runner."* |
| **2. Live Edge Status & Fail-Closed Budget Preflight** | `0:50 – 1:40` | `0:35 – 1:05` | **Switch to Terminal** (`/tmp/contest-demo/cloudflare-agent-git/prototype`). | Run:<br>`curl -s "$BASE_URL/public/status" \| python3 -m json.tool`<br>Then run:<br>`curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/cloud/budget" \| python3 -m json.tool` | *"Our coordinator is deployed live on Cloudflare Workers with a SQLite Durable Object and the `agent-branches-dev` Artifacts namespace. First, let's query the public status endpoint—this reads a sanitized snapshot using zero Artifacts operations. Next, using our admin bearer token, let's inspect `/cloud/budget`. Before any Cloudflare Artifacts binding call or Git operation happens, the Durable Object reserves quota inside an atomic SQLite transaction: capped at 200 operations per day, 6,000 per month, at most 4 repositories, and 16 megabytes of storage. Right now `repoCount` is zero and we have plenty of daily headroom."* |
| **3. Live Cloudflare Artifacts Run: Two Concurrent Agents** | `1:40 – 2:55` | `1:05 – 1:55` | **Terminal**: Live execution of `cloud-smoke.py` against the deployed Worker (`~17.5s`). | Run:<br>`python3 demo/cloud-smoke.py --actors 2 --output report.json`<br>*(Let steps `[1/8]` through `[8/8]` and the `SMOKE REPORT SUMMARY` table print in full.)* | *"Now let's run our live end-to-end verification against the Cloudflare Worker and real Cloudflare Artifacts repositories. Watch the eight stages: Step 1 verifies budget headroom. Step 2 calls `POST /setup` to create the canonical Git repository in Cloudflare Artifacts. Step 3 pushes our baseline seed commit through the Worker's Smart HTTP Git gateway. In Step 4, two concurrent agents—actor 1 and actor 2—each get their own forked Artifacts repository and scoped write token via `POST /tasks`, clone over HTTPS, commit distinct changes concurrently, push back to their forks, and notify `/events/push`. In Step 5, our local trusted runner fetches both agent heads from Artifacts, executes a real `git merge-tree` trial merge, records test provenance, and submits typed pairwise check results to `POST /checks`. Step 6 runs five negative security checks, Step 7 cleans up the demo repositories, and Step 8 confirms all 14 verifications passed in under 18 seconds using exactly 60 budgeted operations."* |
| **4. Safety Refusals: 405, 409 Stale Vector, 403 & 401** | `2:55 – 3:50` | `1:55 – 2:25` | **Terminal**: Highlight the 5 `negative_*` `[PASS]` lines in the summary, then run 3 quick zero-op `curl` probes (and optional local 3-agent conflict harness). | Point to `negative_*` in terminal, then run:<br>`curl -i -s -X POST "$BASE_URL/public/status" \| head -n 5`<br>`curl -i -s "$BASE_URL/status" \| head -n 5`<br>*(Optional for 6m cut — local 3-agent collision + repair + 409)*:<br>`(cd .. && node prototype/demo/concurrent.mjs && cat .local/result.json)` | *"Notice the security and consistency boundaries verified in Step 6: `POST` to `/public/status` is refused with `HTTP 405 Method Not Allowed`. Unauthenticated requests to `/status` or `/cloud/budget` are refused with `HTTP 401`. Cross-task test reporting and cross-repository Git pushes using another agent's token are refused with `HTTP 403 Forbidden`. Most importantly, if a runner submits a check report for a stale head vector after an agent has already pushed a newer commit, the coordinator rejects it with `HTTP 409 Conflict` so outdated checks never overwrite current state. Running our local three-agent harness also shows positive millisecond push overlap where Agents A and B collide in `git merge-tree`, Agent A acknowledges the warning, and a new push automatically invalidates the old warning and resets the pair to `not_checked`."* |
| **5. Review UI: Pair Safety Radar, Semantic Conflicts & Unknown Gating** | `3:50 – 5:00` | `2:25 – 2:55` | **Switch to Browser Tabs 3, 4, 5, 6** (`http://localhost:8765/...`). | 1. Click **Tab 3** (`index.html?fixture=1`): point to the 3 agent cards, Pair Safety section, and Warnings table.<br>2. Click **Tab 4** (`index.html?fixture=semantic`): point to `claude-0004 ↔ codex-0005` (`Conflict`) and `claude-0004 ↔ grok-0006` (`Unknown — not safe`).<br>3. *(For 6m cut)* Click **Tab 5** (`?fixture=lost-push`) & **Tab 6** (`task.html?id=task-0001&fixture=1`). | *"Here is the Review UI—pure zero-framework static HTML and JavaScript that polls `/status` with generation guards. On the overview screen, we see every agent's intent, base commit, latest SHA, and compact timeline of pushes, warnings, and acknowledgements. Below is the Pair Safety Radar. Our core rule is that unknown is never rendered as safe. Switching to the semantic conflict view: here all three agents pass `npm test` with `exit 0` on their own forks, yet `claude-0004` and `codex-0005` both rewrote the same auth helper so their combined test run fails—flagged immediately as a test conflict. Meanwhile, a timed-out check shows `Unknown — not safe`, and in the lost-push view, an undelivered webhook marks the agent's head `Unknown` so no pair involving it can ever be called clean. Drilling into a single task shows the full change story, warning acknowledgements, and commit-pinned test evidence."* |
| **6. Cost Guardrails, Clean Clone Reproduction & Close** | `5:00 – 5:45` | `2:55 – 3:20` | **Switch to Terminal**, then finish on **Browser Tab 1** (`README.md` / `docs-submission/SUBMISSION.md`). | In Terminal, run:<br>`python3 -m json.tool report.json`<br>`env -u BASE_URL python3 demo/walkthrough.py`<br>Switch to **Browser Tab 1** (`README.md`). | *"Inspecting `report.json` from our live Cloudflare run, we see `real_cloudflare_proof: true`, all 14 verifications green, `repo_count_after_cleanup: 0`, and a 60-operation delta well inside our 200-per-day and 6,000-per-month caps—keeping us within the 10,000 free Artifacts operations included in the $5 per month Workers Paid plan with zero overage cost. Judges can reproduce the entire protocol locally in seconds with no cloud credentials required just by cloning the repo, running `npm install`, `npm run build:node`, and `python3 demo/walkthrough.py`. Everything is MIT-licensed and live in the repository. Thank you!"* |

---

## 5. Fallbacks If Anything Fails Live

If anything unexpected happens during the recording window, use the matching recovery below—none of these require editing code or redeploying:

### Fallback A: Preflight Fails With `Initial unrelated inventory detected (repoCount=... > 0)`
- **Why it happens**: A previous smoke run was interrupted before step `[7/8]` cleanup finished, leaving demo repos in the namespace.
- **1-Line Fix (takes 2 seconds, uses 3 ops)**:
  ```bash
  curl -s -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/cloud/demo-repos" | python3 -m json.tool
  ```
  Then re-run `python3 demo/cloud-smoke.py --actors 2 --output report.json`.

### Fallback B: Preflight Fails With `Insufficient operational budget headroom` (`remainingDayOps < 90`) or Missing Local Tokens
- **Why it happens**: Two full live runs were already executed in the current UTC day (`120 / 200` ops used, leaving `80 < 90` required by preflight), or `ADMIN_TOKEN` / `RUNNER_TOKEN` is not loaded in the current shell.
- **What to do on camera**:
  1. Show the live Worker's public status and/or budget cap response:
     ```bash
     curl -s "$BASE_URL/public/status" | python3 -m json.tool
     ```
  2. Run the smoke suite in explicit `--mock` mode PLUS the real local Node + Git sidecar walkthrough (`walkthrough.py`):
     ```bash
     python3 demo/cloud-smoke.py --mock --actors 2 --output report-mock.json
     env -u BASE_URL python3 demo/walkthrough.py
     ```
  3. Open `docs-submission/SUBMISSION.md` and `docs-submission/COST.md` in the browser and point to the recorded live smoke receipt against `https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev` (commit `99f3fca5`, 14/14 checks passed in 17.5s, 60 Artifacts operations, day counter 138/200).

### Fallback C: Submitting the Already-Approved Frozen Video `r2`
- If you prefer not to use the new live take or run out of time in the 15:00–16:00 window, the repository already contains the approved 8-minute video `r2` at `docs-submission/videos/agent-branches-demo-draft.mp4` (SHA-256 `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`, 1280x720 H.264/AAC), with full metadata and links ready in `docs-submission/SUBMISSION.md` and `docs-submission/VIDEO.md`.
