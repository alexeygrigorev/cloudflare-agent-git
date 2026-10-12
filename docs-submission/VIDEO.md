# Approved Submission Video

## Video Metadata

The founder approved video `r2` for submission on 12 October 2026 at 05:05 Europe/Berlin. The human founder journal records this approval on `main` at commit `1934347` (`_docs/founder-journal/2026-10-12.md`).

- File name: `agent-branches-video-r2.mp4`
- SHA-256: `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`
- File size: 13,289,068 bytes
- Duration: 480.002902 seconds (8:00)
- Resolution and format: 1280x720, H.264 video, AAC audio
- Public portable path: `~/contest-submission/agent-branches-video-r2.mp4`
- Repository video link: `docs-submission/videos/agent-branches-demo-draft.mp4` (immutable commit `7459ff4` in `cloudflare-agent-git`)
- Status: Frozen. Bytes remain unchanged without reencoding.

## Narration Disclosure and Historical Context

Video `r2` records the earlier Node coordinator on a Hetzner host. Cloudflare Workers was a reference architecture at that stage.

We recorded this video before the 05:18 Europe/Berlin directive on 12 October 2026. The founder required a Cloudflare Workers coordinator with SQLite-backed Durable Objects and real Cloudflare Artifacts.

We disclose this sequence transparently:
- The approved video bytes remain frozen and unchanged.
- The video doesn't claim to depict the live Cloudflare deployment.
- The video demonstrates genuine multi-agent coordination with real model agents executing tasks.
- It displays protocol evidence replay using historical fixture labels.
- Live Cloudflare edge deployment verification remains pending Root predeploy checks.

## Concurrency and Execution Facts

The demonstration and associated test records reflect two distinct runs:

- Run 1 (Historical multi-agent execution): Three native Gemini 3.1 Pro agents ran concurrently across tasks A, B, and C during a measured 113-second active overlap window on the same host. The agents pushed commits sequentially in the order Task B, then Task A, and finally Task C. Historical test verification confirmed 314 passing tests across three pairs (107/102/105).
- Run 2 (Fresh rehearsal test run): An initial rehearsal run of 321 tests showed two failures. Task B acknowledged the conflict warnings on record using its own credentials and pushed corrective commit `2dc07a1b`, achieving 323 passing test executions (108/107/108).

Additional protocol boundaries verified in test records:
- Stale vector rejection: Submitting check results against a stale head vector returns HTTP 409 Conflict, preserving coordinator state without mutation.
- Physical transport gate: Cross-host physical transport remains an optional enhancement rather than a blocking submission requirement. The project accepted the AgentBus AC60 interface on `main` at commit `f389b716`.
