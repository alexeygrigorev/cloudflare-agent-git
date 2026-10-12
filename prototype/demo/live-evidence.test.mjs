import test from 'node:test';
import assert from 'node:assert/strict';
import { sanitizeEvidence } from './live-evidence.mjs';

test('retains task IDs, commit heads, timestamps, topology gates', () => {
  const input = {
    taskId: 'task-123',
    head: 'e009ff8eb58c8a4f0306b2be1867478b262ca607',
    timestamp: '2026-10-11T14:19:24+02:00',
    topology: { gate: 'pending' },
    status: 'unknown'
  };
  assert.deepEqual(sanitizeEvidence(input), input);
});

test('recursively redacts sensitive keys', () => {
  const input = {
    normal: 'value',
    token: 'secret123',
    nested: {
      myPassword: 'pass',
      Authorization: 'Bearer x',
      SECRET_KEY: 'abc'
    }
  };
  const expected = {
    normal: 'value',
    token: '[REDACTED]',
    nested: {
      myPassword: '[REDACTED]',
      Authorization: '[REDACTED]',
      SECRET_KEY: '[REDACTED]'
    }
  };
  assert.deepEqual(sanitizeEvidence(input), expected);
});

test('redacts credential URL userinfo', () => {
  const credentialUrl = new URL('https://example.com/api');
  credentialUrl.username = 'user';
  credentialUrl.password = 'pass';
  const input = {
    url: credentialUrl.toString(),
    normal: 'https://example.com'
  };
  const expected = {
    url: 'https://REDACTED:REDACTED@example.com/api',
    normal: 'https://example.com'
  };
  assert.deepEqual(sanitizeEvidence(input), expected);
});

test('retains explicit unknown values (not zero)', () => {
  const input = {
    val1: 'unknown',
    val2: 0,
    val3: null,
    secret: 'unknown',
    token: 'unknown',
    password: 0
  };
  const expected = {
    val1: 'unknown',
    val2: 0,
    val3: null,
    secret: 'unknown',
    token: 'unknown',
    password: '[REDACTED]'
  };
  assert.deepEqual(sanitizeEvidence(input), expected);
});
