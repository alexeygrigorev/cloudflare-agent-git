# Agent Branches Contest Submission

## Project Name

AgentBranches

## Vision

Agent Branches provides autonomous coding agents with isolated Git forks and branches governed by a lightweight coordinator. In multi-agent coding environments, independent agents frequently collide when writing to shared branches, causing broken builds and difficult merge rollbacks. Each agent gets a private fork while a coordinator tracks its work-in-progress head and warns when concurrent changes conflict.

A trusted speculative runner periodically reads active head vectors. The runner executes pairwise trial merges using git merge-tree and runs budgeted test suites before code moves toward trunk. When the runner detects semantic conflicts or failing tests, it records warnings directly on the coordinator. Agents read these warnings and acknowledge them or push updated commits with fixes.

The coordinator doesn't execute agent code, Git commands, or tests. It tracks branch heads, verifies role-scoped bearer tokens, and records test results alongside commit references. A client-side review dashboard shows active agent tasks, base commits, conflict badges, and warning acknowledgment records.

## Cloudflare Platform Usage

Agent Branches uses Cloudflare's serverless platform to provide a distributed coordination service:

1. Cloudflare Workers: The Worker acts as the public API router and smart gateway proxy. It routes REST requests for task tracking, handles CORS preflight requests, verifies role-based Bearer credentials (ADMIN_TOKEN, RUNNER_TOKEN, and per-task agent tokens), and proxies Git Smart HTTP requests (git-upload-pack and git-receive-pack).

2. Durable Objects with SQLite storage: The coordinator core runs inside a single-instance Durable Object named Coordinator. Using Durable Objects with embedded SQLite storage gives the coordinator atomic transactions, linearizable head updates, and consistent warning records across concurrent agents without requiring an external database service.

3. Cloudflare Artifacts: Agent Branches binds to Cloudflare Artifacts using namespace agent-branches-dev to store Git repositories and packfiles at the edge. Storing agent forks directly in Artifacts provides durable, low-latency object storage for Git repositories without requiring dedicated server infrastructure.

Agents execute tasks and test suites on local developer machines or dedicated runner nodes, completely isolated from Cloudflare edge execution. The architecture also preserves a zero-dependency plain Node coordinator fallback, allowing developers to test the complete protocol locally without cloud credentials.

## Repository Public URL

You can find the project repository at [Agent Branches on GitHub](https://github.com/alexeygrigorev/cloudflare-agent-git).

## Approved Video, Path, and Hash

The approved submission video has these details:
- Public video path: `~/contest-submission/agent-branches-video-r2.mp4`
- Repository video link: `docs-submission/videos/agent-branches-demo-draft.mp4` (immutable commit `7459ff4` in `cloudflare-agent-git`)
- SHA-256 hash: `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`
- File size: 13,289,068 bytes
- Duration: 480.002902 seconds (8:00)
- Video format: 1280x720, H.264 video, AAC audio
- Human approval: Founder journal entry on `main` at commit `1934347` records approval of draft `r2` on 12 October 2026 ~05:05 Europe/Berlin.

## Run Instructions

The Cloudflare Worker is live at https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev (Worker `agent-branches`, version `e962956f`, deployed 13 October 2026 ~22:57 Europe/Berlin with a SQLite Durable Object coordinator and the Artifacts namespace `agent-branches-dev`). `GET /public/status` is public; every write needs a bearer token. The full live smoke run (`python3 prototype/demo/cloud-smoke.py`, commit `898caf0`) PASSED on 13 October 2026 at ~23:03 Europe/Berlin in 17.5 s, with all 14 verifications passing and 60 budgeted operations used. Covered: preflight budget headroom, sanitized public status, a real canonical Artifacts repository create, the seed push, two concurrent scripted agents forking and pushing, push callbacks, a clean pairwise `git merge-tree` check, typed trusted-runner `POST /checks`, and refusals for 405 (method), 409 (stale vector), 403 (cross-task and cross-repo push) and 401 (unauthenticated). Demo repositories were cleaned up afterwards. The approved video records the earlier Node runtime.

Local reproduction requires Node.js 22 or newer and Python 3.10 or newer, plus Git and npm.

Install dependencies and run the protocol walkthrough:

```bash
git clone https://github.com/alexeygrigorev/cloudflare-agent-git.git
cd cloudflare-agent-git/prototype
npm install
npm run build:node
python3 demo/walkthrough.py
npm run test:all
```

The walkthrough script starts its own coordinator and Git sidecar, then removes temporary processes and state. It uses scripted Git clients without calling Cloudflare or launching model agents.

For an explicit local mock of the cloud smoke client:

```bash
python3 demo/cloud-smoke.py --mock
```

The founder approved the live deployment on 13 October 2026 (the account is on Workers Paid). To smoke-test the live Worker yourself you need the deployment's admin and runner tokens: `BASE_URL=https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev ADMIN_TOKEN=... RUNNER_TOKEN=... python3 demo/cloud-smoke.py`.

## Privacy and Intake Notice

Personal submission details remain in a private intake file (`form-intake.json`) pending manual human completion. These details include team member names, contact information, attendee lists, and contest eligibility checkbox selections.

Public product documentation contains zero personal data. Final contest form submission is executed manually by a human administrator.
