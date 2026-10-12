import test from 'node:test';
import assert from 'node:assert';
import { formatWarnings } from './live-view.mjs';

test('formatWarnings - handles empty or missing status', () => {
    assert.strictEqual(formatWarnings(null), "No warnings data available.");
    assert.strictEqual(formatWarnings({}), "No warnings data available.");
    assert.strictEqual(formatWarnings({ warnings: [] }), "");
});

test('formatWarnings - formats a complete warning based on actual JSON shape', () => {
    const status = {
        warnings: [
            {
                id: "warn-3",
                pair: ["claude-0004", "codex-0005"],
                headsAtIssue: {
                    "claude-0004": "b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0",
                    "codex-0005": "c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1"
                },
                reason: "radar-conflict:test",
                status: "active",
                createdAt: "2026-10-03T14:25:10.000Z",
                invalidatedAt: null,
                acks: [
                    {
                        agent: "codex-0005",
                        head: "c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1",
                        note: "Understood",
                        at: "2026-10-03T14:26:00.000Z"
                    }
                ],
                checks: ["checked"]
            }
        ]
    };
    const result = formatWarnings(status);
    assert.strictEqual(result, "[Warning warn-3] radar-conflict:test | Owner: claude-0004, codex-0005 | Status: active | ACK by codex-0005 (Note: ACK does not imply approved merge)");
});

test('formatWarnings - handles missing checks (never clean)', () => {
    const status = {
        warnings: [
            {
                id: "warn-4",
                pair: ["agent-x", "agent-y"],
                reason: "Another issue",
                status: "resolved",
                acks: []
            }
        ]
    };
    const result = formatWarnings(status);
    assert.strictEqual(result, "[Warning warn-4] Another issue | Owner: agent-x, agent-y | Status: resolved | No ACK | State: Dirty (missing checks never clean)");
});

test('formatWarnings - sorts deterministically and handles absent fields', () => {
    const status = {
        warnings: [
            {
                reason: "Missing ID",
                acks: [{ agent: "agent-a" }]
            },
            {
                id: "warn-1",
                owner: "agent-a", // fallback to old owner
                acks: [{ agent: "agent-b" }],
                checks: []
            }
        ]
    };
    const result = formatWarnings(status);
    const expected = "[Warning unknown] Missing ID | Owner: unassigned | Status: pending | ACK by agent-a (Note: ACK does not imply approved merge) | State: Dirty (missing checks never clean)\n" +
                     "[Warning warn-1] No reason | Owner: agent-a | Status: pending | ACK by agent-b (Note: ACK does not imply approved merge) | State: Dirty (missing checks never clean)";
    assert.strictEqual(result, expected);
});

test('formatWarnings - handles legacy format for fallback completeness', () => {
    const status = {
        warnings: [
            {
                id: "W003",
                owner: "agent-z",
                ack: true,
                checks: ["ok"]
            }
        ]
    };
    const result = formatWarnings(status);
    assert.strictEqual(result, "[Warning W003] No reason | Owner: agent-z | Status: pending | ACK by agent-z (Note: ACK does not imply approved merge)");
});

test('formatWarnings - regression test for inherited Owner: contract compatibility', () => {
    const status = {
        warnings: [
            { id: 'W1', message: 'Inherited test case', owner: 'agent-B', ack: false, resolution: 'pending' },
            {
                id: 'W2',
                pair: ['agent-A', 'agent-B'],
                headsAtIssue: { 'agent-A': '1111', 'agent-B': '2222' },
                reason: 'test',
                status: 'active',
                acks: [{ agent: 'agent-B' }]
            }
        ]
    };
    const result = formatWarnings(status);
    const lines = result.split('\n');
    assert.strictEqual(lines.length, 2);

    // Literal Owner: singular label must be retained for inherited test contract
    assert.match(lines[0], /^\[Warning W1\]/);
    assert.match(lines[0], /Owner: agent-B/);
    assert.doesNotMatch(lines[0], /Owners:/);
    assert.match(lines[0], /No ACK/);
    assert.match(lines[0], /State: Dirty \(missing checks never clean\)/);

    // Actual schema with pair, headsAtIssue, reason, acks
    assert.match(lines[1], /^\[Warning W2\]/);
    assert.match(lines[1], /Owner: agent-A, agent-B/);
    assert.doesNotMatch(lines[1], /Owners:/);
    assert.match(lines[1], /ACK by agent-B \(Note: ACK does not imply approved merge\)/);
    assert.match(lines[1], /State: Dirty \(missing checks never clean\)/);
});
