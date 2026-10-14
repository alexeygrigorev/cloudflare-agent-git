# Submission video

The project was submitted by Alexey on 15 October 2026 with [this Loom recording](https://www.loom.com/share/f8b67486801b4cee8d8970fa3d405553). A visually inspected confirmation screenshot states that the entry was received; private submission identifiers are omitted. See the [founder log](../_docs/founder-journal/2026-10-15.md).

The metadata and execution facts below describe the earlier approved recording, retained as historical evidence. They do not describe the new Loom recording, which has not been independently viewed here.

## Earlier approved recording

## Video Metadata

The founder approved video `r2` for submission on 12 October 2026 at 05:05 Europe/Berlin. The human founder journal records this approval on `main` at commit `1934347` (`_docs/founder-journal/2026-10-12.md`).

- File name: `agent-branches-video-r2.mp4`
- SHA-256: `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`
- File size: 13,289,068 bytes
- Duration: 480.002902 seconds (8:00)
- Resolution and format: 1280x720, H.264 video, AAC audio
- Public video URL (GitHub blob viewer): `https://github.com/alexeygrigorev/cloudflare-agent-git/blob/main/docs-submission/videos/agent-branches-demo-draft.mp4`
- Public video direct download (raw URL): `https://raw.githubusercontent.com/alexeygrigorev/cloudflare-agent-git/main/docs-submission/videos/agent-branches-demo-draft.mp4`
- Local host portable path: `~/contest-submission/agent-branches-video-r2.mp4` (machine-local filesystem path on the recording host, not an external URL)
- Repository video link: `docs-submission/videos/agent-branches-demo-draft.mp4` (immutable commit `7459ff4` in `cloudflare-agent-git`)
- Status: Frozen. Bytes remain unchanged without reencoding.

## Narration Disclosure and Historical Context

Video `r2` records the earlier Node coordinator on a Hetzner host. Cloudflare Workers was an implemented reference architecture at that stage.

We recorded this video before the 05:18 Europe/Berlin directive on 12 October 2026. While the Cloudflare Workers coordinator with SQLite-backed Durable Objects and Cloudflare Artifacts is fully implemented in prototype code (`prototype/src/cloudflare/`), the recorded video specifically demonstrates the earlier verified local Node runtime coordination.

We disclose this sequence transparently:
- The approved video bytes remain frozen and unchanged (SHA-256 `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`).
- The video doesn't claim to depict a live Cloudflare edge deployment.
- The video demonstrates genuine multi-agent coordination with real model agents executing tasks on the verified local Node runtime.
- It displays protocol evidence replay using historical fixture labels.
- Live Cloudflare edge deployment and smoke verification were executed and verified by Root per receipt issue #55 (commit `99f3fca5`, 14/14 passing verifications, 17.5 s duration, 60 Artifacts operations used with reported day counter 138 of 200 daily cap at endpoint `https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev`).

## Concurrency and Execution Facts

The demonstration and associated test records reflect two distinct runs:

- Run 1 (Historical multi-agent execution): Three native Gemini 3.1 Pro agents ran concurrently across tasks A, B, and C during a measured 113-second active overlap window on the same host. The agents pushed commits sequentially in the order Task B, then Task A, and finally Task C. Historical test verification confirmed 314 passing tests across three pairs (107/102/105).
- Run 2 (Fresh rehearsal test run): An initial rehearsal run of 321 tests showed two failures. Task B acknowledged the conflict warnings on record using its own credentials and pushed corrective commit `2dc07a1b`, achieving 323 passing test executions (108/107/108).

Additional protocol boundaries verified in test records:
- Stale vector rejection: Submitting check results against a stale head vector returns HTTP 409 Conflict, preserving coordinator state without mutation.
- Physical transport gate: Cross-host physical transport remains an optional enhancement rather than a blocking submission requirement. The project accepted the AgentBus AC60 interface on `main` at commit `f389b716`.
