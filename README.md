# cloudflare-agent-git

Research and prototypes for an agent-native Git platform on Cloudflare Workers and Artifacts.

Current competition prototype: **Agent Branches** — submission write-up in
[`SUBMISSION.md`](SUBMISSION.md), local reproduction in [`live/`](live/README.md).
The coordinator's HTTP wire contract is
[`prototype/CONTRACT.md`](prototype/CONTRACT.md) (v0.1.2): `POST /setup`,
`POST /tasks`, `POST /events/push`, `POST /events/artifacts`, `POST /checks`,
`GET /status`, `GET /tasks/:id`, `POST /tasks/:id/tests`,
`POST /warnings/:id/ack`.
