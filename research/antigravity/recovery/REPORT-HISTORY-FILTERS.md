# REPORT-HISTORY-FILTERS — Client-side product and date-range filters for `/history/`

**Date:** 2026-10-05  
**Scope:** Requirements for filtering the public Hourly history page. Inspected `website/history.py`, `website/assets/data/public_hourly_history.json`, `website/assets/site.css`, and `website/build.py`. No code, tests, launcher, or SPEC changes in this pass.  
**Trigger:** C2440 asked for explicit range/filters on the accepted public history snapshot, separate from the private task tracker.

---

## Current page

`history_page()` in `website/history.py` emits static HTML at site build. `build.py` writes it to `/history/` (`wide` layout). The only page script is site-wide `signup.js`. There is no product control, no date/hour range, and no query-string or hash state.

Surfaces that always show the full export:

| Surface | How it is built today |
|---|---|
| KPI strip | Four hardcoded strings (tokens, observed hours, sampled work, team count) |
| Occupancy chart | Python SVG; each bar sums all four products’ presence and sampled work |
| 24-hour ledger | Fixed six columns (time + four products + tokens); 24 rows |
| Task cards | Four hardcoded current-lane cards |

Data already on disk is enough to filter in the browser. `public_hourly_history.json` (~42 KB) is linked from the page and copied to `website/assets/data/`. Schema `1.0.0` has `products[]`, `product_token_summary`, and 24 half-open hourly buckets:

- Window: `[2026-10-04T07:00:00Z, 2026-10-05T07:00:00Z)` (Berlin 09:00 CEST → next 09:00)
- Product ids: `agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`
- Each bucket: `bucket_index`, `bucket_start_utc`, `bucket_end_utc`, `berlin_label`, per-product cells (`observation_status`, `presence_hours`, `sampled_working_hours`, …)
- `unattributed` is present in JSON and excluded from the table/chart; keep it out of the product chips

Buckets 0–3 are unobserved for the four products (collector not yet running). Token cells in the table are hardcoded (`bucket_index == 4` → dashboard 680,764; `== 5` → coordination 406,080). `product_token_summary` is loaded and unused.

The GitHub Pages site has no history API. Client-side filtering of this frozen export is the right place. A rebuild, not a live collector, is the source-update path.

---

## Product filter

Four independent toggles, default **all on**. Empty selection is an empty state, not “show all”.

Apply to:

1. **Ledger columns** — hide deselected product columns; hide the Tokens column when no remaining product has a token cell in range.
2. **Chart** — re-sum each visible hour from the selected products only. CSS hide cannot do this: bars are already aggregated in Python.
3. **KPIs** — recompute sampled work, observed-hour count, and tokens from the selection. Do not leave the global literals on screen.
4. **Task cards** — hide cards whose product is off. These cards are a current snapshot, not hourly history (C2440).

Do not add `unattributed` as a fifth chip. Do not fetch private `/api/tasks`.

---

## Date range

The export is 24 hours across two calendar dates, so a day picker is too coarse. Use **hour bounds snapped to bucket edges**, labeled in Berlin time, with UTC in a subtitle. Clamp to `[window.start_utc, window.end_utc)`. Half-open rule: a bucket is in range iff `start <= bucket_start_utc < end`.

Apply to chart bars, ledger rows, and KPIs. Keep unobserved rows that fall inside the range (do not drop the unobserved label). Date range does **not** filter task cards.

Empty overlap (inverted bounds, or a range with no buckets) shows an explicit empty state and zeroed KPIs. Observed-hour KPI counts only in-range buckets whose selected products are `observed` or `partial`. Token KPI includes a product’s tokens only when that product is selected **and** its attributed bucket is in range.

---

## Implementation shape (next change, not this report)

Progressive enhancement: the built HTML remains the full 24h / four-product view with JS off.

1. Mark rows/cells/cards with `data-product`, `data-start`, `data-end` (ISO UTC). Put per-bucket numbers in `data-*` (or a `<script type="application/json">` of the public payload) so the chart and KPIs can recompute without a second network hop. The existing JSON URL is the fallback.
2. Add a filter bar above the chart: product chips + from/to hour selects + reset. Vanilla JS, same pattern as `signup.js` (no new dependency).
3. Persist state in the query string, e.g. `?product=agent-branches,quota-launcher&from=2026-10-04T13:00:00Z&to=2026-10-05T07:00:00Z`, so a view is shareable. Invalid params fall back to the full window / all products.
4. Show the export `generated_at_utc` and window as the source stamp. Filtering never claims a live collector refresh.

Privacy and copy stay as today: no paths, session ids, or private task ids. Visible labels stay the four product names, not internal ids.

**Do not treat as done:** server-side filter endpoints, live 8766 adapters, or folding the private kanban into this page.
