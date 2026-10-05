# REPORT-HISTORY-EXPORT — Client-side JSON/CSV/Markdown of the filtered history view

**Date:** 2026-10-05  
**Scope:** Requirements for downloading the *currently filtered* public Hourly history. Inspected `website/history.py`, `website/assets/data/public_hourly_history.json` (42,049 bytes, identical to `research/antigravity/recovery/public_hourly_history_export.json`), `website/assets/site.css`, and `website/build.py`. No code, tests, launcher, or SPEC changes in this pass.  
**Depends on:** [REPORT-HISTORY-FILTERS.md](REPORT-HISTORY-FILTERS.md). Export without those filters is a second copy of the file already linked on the page.

---

## Current page

`history_page()` emits static HTML. `build.py` writes `/history/` (`wide`) and `shutil.copytree`s `website/assets/` into the output, so the frozen JSON is already a public file. The only page script is site-wide `signup.js`. There is no `Blob`/`download` path, no CSV, no Markdown, and no history-only JS.

What a reader can get today:

| Surface | What it is |
|---|---|
| Tracker-sources link | Full `schema_version` 1.0.0 JSON (`/cloudflare-agent-git/assets/data/public_hourly_history.json`) |
| Ledger / chart / KPIs | Full 24h × four products, baked in Python |
| Task cards | Hardcoded current-lane snapshot, not hourly history |

The JSON has `window`, `products[]`, window-level `product_token_summary`, and 24 half-open buckets. Each product cell: `observation_status`, `coverage_fraction`, `active_presence_agents`, `presence_hours`, `active_working_agents`, `sampled_working_hours`. Hourly buckets have **no token fields**. Table token cells are hardcoded in Python (`bucket_index == 4` dashboard 680,764; `== 5` coordination 406,080). `unattributed` is in JSON and already excluded from the table/chart.

GitHub Pages has no history API. Client-side download of the in-memory filtered view is the right place.

---

## What to export

Three formats of the **same filtered set** (selected products ∩ in-range buckets). Empty selection or empty overlap yields an explicit empty payload (and disabled buttons), matching the filter empty state — not a silent fallback to the full window.

Include:

- Selected product ids and display names
- In-range buckets, half-open rule unchanged (`start <= bucket_start_utc < end`)
- Unobserved in-range rows, with nulls kept as null (do not coerce to 0)
- Filter stamp: products, `from`, `to`, source `generated_at_utc`, export time
- Token summary for a product only when that product is selected **and** its attributed window-level bucket is in range (dashboard ↔ bucket 4, coordination ↔ bucket 5). Do not invent a per-hour token series.

Exclude: `unattributed`, private `/api/tasks`, TASKS.json, task cards (C2440: current snapshot, not hourly history), session ids, paths.

**JSON** — subset of schema 1.0.0 plus a `filter` object. Drop deselected products from each remaining bucket.

**CSV** — UTF-8, RFC4180. One row per `(bucket, selected product)`. Columns: `bucket_index`, `bucket_start_utc`, `bucket_end_utc`, `berlin_label`, `product_id`, `product_name`, `observation_status`, `coverage_fraction`, `presence_hours`, `sampled_working_hours`, `active_presence_agents`, `active_working_agents`. Empty numeric cells for unobserved. No BOM required.

**Markdown** — short header (window, filter, source stamp) plus a ledger table whose columns match the visible product columns.

Suggested filenames: `hourly-history-{from}_{to}_{products}.{json|csv|md}` with UTC hour stamps and product ids.

---

## Implementation shape (next change, not this report)

Ship **after or with** the filter bar. Reuse the same in-memory selection (query string / chips / hour bounds). Vanilla JS, no new dependency.

1. Prefer the payload already inlined for filters (`<script type="application/json">` or `data-*`). Fetch the existing JSON URL only as fallback.
2. `Blob` + temporary object URL + `<a download>`. Same-origin GitHub Pages can do this; opening the static JSON in a new tab is not a filtered export.
3. Put JSON / CSV / Markdown controls on the filter bar. Reuse `.button` type and focus styles; compact text controls, not a second CTA row. Disable when the filtered set is empty.
4. Load a history-only script from `history_page()` or a `page()` branch for `/history/`. Do not add another site-wide script beside `signup.js`.
5. JS off: keep the full JSON link. No download buttons, no claim that the static file is filtered.

Privacy and copy stay as today. Filtering and export never claim a live collector refresh.

**Do not treat as done:** server-side export endpoints, live 8766 adapters, folding task cards into the file, or a CSV token column that the JSON does not have.
