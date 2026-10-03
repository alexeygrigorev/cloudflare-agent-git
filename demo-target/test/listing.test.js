import test from 'node:test';
import assert from 'node:assert/strict';
import { fresh, postJSON, get } from './_helpers.js';

test('GET /links returns every stored link', async () => {
  const { call } = fresh();
  await call(postJSON('/links', { slug: 'docs', url: 'https://example.com/docs' }));
  await call(postJSON('/links', { slug: 'api', url: 'https://example.com/api' }));
  const res = await call(get('/links'));
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.links.length, 2);
  assert.deepEqual(
    body.links.map((l) => l.slug),
    ['docs', 'api'],
  );
  assert.equal(body.links.every((l) => l.visits === 0), true);
});

test('redirects increment the visit counter', async () => {
  const { call } = fresh();
  await call(postJSON('/links', { slug: 'docs', url: 'https://example.com/docs' }));
  await call(get('/docs'));
  await call(get('/docs'));
  const res = await call(get('/links'));
  const body = await res.json();
  assert.equal(body.links[0].visits, 2);
});

test('service.list() is empty before any create', () => {
  const { service } = fresh();
  assert.deepEqual(service.list(), []);
});
