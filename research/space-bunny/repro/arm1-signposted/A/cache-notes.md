# cache.py notes

## Policy: LRU, capacity 128

`CAPACITY = 128` entries in one `collections.OrderedDict`:

- hit: `move_to_end(key)`, return cached value — O(1), no store access.
- miss: `store.fetch(key)` (a `KeyError` for an unknown key propagates and
  nothing is cached), insert, then `popitem(last=False)` while over capacity.

Why LRU over FIFO: `read()` is the only path that fills the cache, so under
LRU a key that keeps being read stays warm, while FIFO evicts by insertion
order and can drop a hot key that merely happened to be cached first. The
cost is one `move_to_end` per hit. 128 is an arbitrary small bound; it is a
module constant, not a knob.

## Freshness after writes (requirement 3)

`store.write(key, value)` updates `_data` and then calls every registered
listener with that key; `wiring.py` registers `cache.invalidate` as the
listener. `invalidate(key)` pops the key, so the next `read` re-fetches.
`bulk.write_bulk` writes row by row through `store.write`, so every bulk row
invalidates too.

`cache.py` additionally registers `invalidate` itself at import time. Reason:
`app.py` — the public entry point the oracle exercises — imports `bulk` and
`cache` but never `wiring`, so if registration lived only in `wiring`, reads
through `app.get` could serve stale values depending on import order. Double
registration is harmless: `invalidate` is an idempotent `pop(key, None)`, so
a write with both listeners registered just evicts twice.

## Other requirements

- Signature: `read(key)` unchanged; on a miss `fetch` raises before anything
  is inserted, so unknown keys are never cached (no negative caching) and
  `KeyError` behaviour is preserved.
- Process isolation: entries live in one module-level dict per interpreter;
  no file, mmap or `multiprocessing` backing, so nothing is shared across
  processes (each process has its own `store._data` as well).

## Checks actually run

Scratch script `_scratch_cache_check.py` (deleted after running) asserted:

1. `read` of a never-written key raises `KeyError` and caches nothing.
2. write → read returns the value; a second read does not call `store.fetch`
   again (verified with a counting wrapper patched over `store.fetch`).
3. second `store.write` to the same key → next read returns the new value and
   `fetch` was called again (invalidation through the listener works).
4. `bulk.write_bulk` of two keys → both read back fresh.
5. write to a key that was never read → listener no-op, later read works.
6. filling past capacity keeps `len(cache._entries)` at 128; the 10 oldest
   keys are evicted; an evicted key re-fetches correctly on the next read.
7. touching a cached key protects it: after one more insert, the untouched
   oldest entry is evicted and the touched one survives.
8. write after a warm cache still invalidates (fresh value returned).
9. a subprocess writing through its own `store` leaves this process's cache
   untouched (read here still raises `KeyError`) — no cross-process sharing.
10. fresh interpreter using only `app` (never importing `wiring`):
    `set_bulk({'x': 1}) → get('x') == 1`, then `set_bulk({'x': 2}) →
    get('x') == 2`, and `get('missing')` raises `KeyError`. This exercises
    the import-time self-registration path.
11. fresh interpreter importing `wiring` first, then `cache`: duplicate
    listener registration, writes still invalidate correctly.

Also ran `python3 -c "import ast,sys; ast.parse(open('cache.py').read())"` —
clean. Files changed: `cache.py` only, plus this notes file.

Inherited behaviours, unchanged from the base: values are returned by
reference exactly as `store.fetch` returns them, and there is no locking
(`store` has none either).
