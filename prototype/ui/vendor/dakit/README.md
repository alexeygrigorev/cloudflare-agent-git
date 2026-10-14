# Vendored dakit

A read-only copy of the [dakit](https://github.com/DataTalksClub/dakit) design
system, so the review UI works offline from `python3 -m http.server` with no
CDN or third-party request.

- Source commit: `6ebc6f999a2253dd98fe9cff43d98175f8a102b6`
  ("Add check-borders CLI, test suite, and build enforcement";
  removes the `--dk-*-border` colour tokens and forbids accent borders)
- `dist/dakit.css` — the built bundle (tokens + base + components), unmodified.
- `fonts/` — self-hosted Inter and IBM Plex Mono (SIL OFL, see `fonts/license.txt`, copied from dakit's `fonts/LICENSE.md`).
  `dakit.css` loads them via `../fonts/`, so keep the two folders side by side.

Do not edit these files. To update, rebuild dakit (`node build.mjs`), copy
`dist/dakit.css` and `fonts/` over, and record the new commit here.
