# Vendored dakit

A read-only copy of the [dakit](https://github.com/DataTalksClub/dakit) design
system, so the review UI works offline from `python3 -m http.server` with no
CDN or third-party request.

- Source commit: `aa613843bd1212d72489d3e039d38b7f7a57c4d8`
  ("Soften dialogs to a single flat sheet in both themes")
- `dist/dakit.css` — the built bundle (tokens + base + components), unmodified.
- `fonts/` — self-hosted Inter and IBM Plex Mono (SIL OFL, see `fonts/license.txt`, copied from dakit's `fonts/LICENSE.md`).
  `dakit.css` loads them via `../fonts/`, so keep the two folders side by side.

Do not edit these files. To update, rebuild dakit (`node build.mjs`), copy
`dist/dakit.css` and `fonts/` over, and record the new commit here.
