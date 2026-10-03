import test from 'node:test';
import assert from 'node:assert/strict';
import { fresh, postJSON, get } from './_helpers.js';

test('GET /:slug redirects to the stored url with 302', async () => {
  const { call } = fresh();
  await call(postJSON('/links', { slug: 'docs', url: 'https://example.com/docs' }));
  const res = await call(get('/docs'));
  assert.equal(res.status, 302);
  assert.equal(res.headers.get('location'), 'https://example.com/docs');
});

test('GET /:slug returns 404 for an unknown slug', async () => {
  const { call } = fresh();
  const res = await call(get('/nope'));
  assert.equal(res.status, 404);
  const body = await res.json();
  assert.match(body.error, /no such slug/);
});

test('an expired link resolves to 404', async () => {
  const { call } = fresh();
  await call(postJSON('/links', { slug: 'temp', url: 'https://example.com/t', ttlSeconds: -1 }));
  const res = await call(get('/temp'));
  assert.equal(res.status, 404);
});

test('POST /links accepts ttlSeconds and keeps permanent links resolving', async () => {
  const { call } = fresh();
  const created = await call(postJSON('/links', { slug: 'keep', url: 'https://example.com/k', ttlSeconds: 3600 }));
  assert.equal(created.status, 201);
  assert.equal((await created.json()).expiresAt > Date.now(), true);
  await call(postJSON('/links', { slug: 'perm', url: 'https://example.com/p' }));
  const res = await call(get('/perm'));
  assert.equal(res.status, 302);
});
