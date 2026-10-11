import test from 'node:test';
import assert from 'node:assert/strict';
import { formatWarnings } from './live-view.mjs';

test('formatWarnings handles empty/missing data', () => {
  assert.strictEqual(formatWarnings(null), "No warnings data available.");
  assert.strictEqual(formatWarnings({}), "No warnings data available.");
  assert.strictEqual(formatWarnings({ warnings: [] }), "");
});

test('formatWarnings formats and sorts deterministically', () => {
  const status = {
    warnings: [
      { id: 'W2', message: 'Second', owner: 'agent-A', ack: true, ackOwner: 'agent-A', resolution: 'resolved', checks: ['done'] },
      { id: 'W1', message: 'First', owner: 'agent-B', ack: false, resolution: 'pending' },
    ]
  };
  const result = formatWarnings(status);
  const lines = result.split('\n');
  assert.strictEqual(lines.length, 2);
  assert.match(lines[0], /^\[Warning W1\]/);
  assert.match(lines[0], /Owner: agent-B/);
  assert.match(lines[0], /No ACK/);
  assert.match(lines[0], /State: Dirty \(missing checks never clean\)/);

  assert.match(lines[1], /^\[Warning W2\]/);
  assert.match(lines[1], /ACK by agent-A/);
  assert.match(lines[1], /\(Note: ACK does not imply approved merge\)/);
  assert.doesNotMatch(lines[1], /Dirty/);
});
