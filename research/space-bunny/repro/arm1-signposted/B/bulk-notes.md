# bulk.py fast path notes

## What the fast path does

`write_bulk` no longer calls `store.write` once per row. It commits every
value straight into `store._data` in one tight loop, then delivers the
notifications in a second tight loop: for each key (in `items` order), for
each registered listener (in registration order), it makes the same
`fn(key)` call `store.write` would have made. The observable notification
sequence is identical to the old behaviour — wiring.py's registered
`cache.invalidate` sees every key, so downstream caches stay coherent —
but the per-row re-entry into `write()` and its listener loop are gone.
An empty `items` returns immediately; if `store` ever stops exposing
`_data`/`_listeners`, the code falls back to the original per-row `write`
loop rather than risking missed notifications.

## What it trades away

- **Timing, not content, of notifications.** All new values are committed
  before the first listener runs, so a listener that re-reads the store now
  sees the whole batch's new values instead of a half-old/half-new mix. A
  listener depending on mid-bulk interleaving would notice; `cache.invalidate`
  does not.
- **Store internals.** The fast path touches `store._data` and
  `store._listeners` directly, coupling bulk.py to store.py's layout (fixed
  base file). The fallback path covers any drift.
- **Failure point moves.** If a listener raises, every value is already
  committed when the exception propagates (before, later rows were never
  written).
- **A hard floor stays.** The notification contract requires one listener
  call per key per listener, so asymptotics are unchanged; the win is the
  constant factor (about 1.5x at 0 listeners, ~1.2x at 3 listeners, 20k
  rows). The single-row `store.write` path is untouched.

## Checks run

- Scratch script (deleted after running) against `store` + `wiring` + `app`
  with a simulated memoizing cache patched over `cache` (memoizing `read`,
  real `invalidate`, registered before wiring import):
  - bulk write then reads via `app.get`, raw `fetch`, and `read_all`;
  - second bulk write with different values over the same keys — cached
    reads returned the new values, proving invalidations fired (this is the
    stale-read trap); notification keys recorded matched the batch exactly;
  - empty `write_bulk({})` writes nothing and notifies nobody;
  - single-row `store.write` still cache-coherent across rewrites;
  - with two extra listeners, both were called for every key;
  - a listener re-reading the store during notification saw the committed
    value.
- Benchmark (fresh process, disjoint fresh key sets, min of two reps, 20k
  rows): fast 3.2 ms vs per-row 4.7 ms at 0 listeners; 7.1 ms vs 8.6 ms at
  3 listeners.
- `python3 -c "import ast,sys; ast.parse(open('bulk.py').read())"` — clean.
