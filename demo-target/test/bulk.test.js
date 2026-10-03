import test from 'node:test';
import assert from 'node:assert/strict';
import { fresh, postJSON, get } from './_helpers.js';

test('POST /links/bulk imports every link and returns slugs in order', async () => {
  const { call } = fresh();
  const res = await call(
    postJSON('/links/bulk', {
      links: [
        { slug: 'docs', url: 'https://example.com/docs' },
        { slug: 'api', url: 'https://example.com/api' },
      ],
    }),
  );
  assert.equal(res.status, 201);
  const body = await res.json();
  assert.equal(body.created, 2);
  assert.deepEqual(body.slugs, ['docs', 'api']);
  assert.equal((await call(get('/docs'))).status, 302);
  assert.equal((await call(get('/api'))).status, 302);
});

test('POST /links/bulk with an empty list creates nothing', async () => {
  const { call } = fresh();
  const res = await call(postJSON('/links/bulk', { links: [] }));
  assert.equal(res.status, 201);
  const body = await res.json();
  assert.deepEqual(body, { created: 0, slugs: [] });
});

test('POST /links/bulk rejects a malformed body with 400', async () => {
  const { call } = fresh();
  const res = await call(postJSON('/links/bulk', { links: 'nope' }));
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.match(body.error, /links/);
});
