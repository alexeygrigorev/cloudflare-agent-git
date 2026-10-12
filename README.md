# Agent Branches

Give each coding agent a repository fork, track its latest commit, and check how concurrent changes combine before merging them. A trusted runner tests pairs of changes and records conflict warnings for the agents to acknowledge or fix.

![Agent Branches review interface](prototype/ui/ui-evidence/index-base.png)

## Try it locally

Requires Node.js 22 or newer (tested with Node 24), Python 3.10 or newer, Git, and npm.

```bash
git clone https://github.com/alexeygrigorev/cloudflare-agent-git.git
cd cloudflare-agent-git/prototype
npm install
npm run build:node
python3 demo/walkthrough.py
npm run test:all
```

The walkthrough script starts a local coordinator and Git sidecar, then pushes a commit and verifies the callback. It submits checks before removing temporary state and stopping its processes.

## Watch the demo

[Watch the approved eight-minute video](docs-submission/videos/agent-branches-demo-draft.mp4). It shows earlier agent activity and protocol evidence from the Node runtime. Cloudflare deployment verification is separate and remains pending. [Recording details and SHA-256](docs-submission/VIDEO.md).

## Cloudflare entry

The Cloudflare adapter uses a Worker, one SQLite-backed Durable Object, and the Artifacts Git repository binding. Agents and test runners execute on developer computers while the coordinator records their results. The Node adapter supports local testing.

[Prototype instructions](prototype/README.md) · [Submission text](docs-submission/SUBMISSION.md) · [Cloudflare costs and limits](docs-submission/COST.md) · [Demo script](docs-submission/DEMO-SCRIPT.md)

MIT licensed.
