import test from 'node:test';
import assert from 'node:assert';
import { formatWarnings } from './live-view.mjs';

test('formatWarnings - handles empty or missing status', () => {
    assert.strictEqual(formatWarnings(null), "No warnings data available.");
    assert.strictEqual(formatWarnings({}), "No warnings data available.");
    assert.strictEqual(formatWarnings({ warnings: [] }), "");
});

test('formatWarnings - formats a complete warning', () => {
    const status = {
        warnings: [
            {
                id: "W001",
                message: "Conflict detected",
                owner: "agent-b",
                resolution: "pending",
                ack: { owner: "agent-b" },
                checks: ["check1"]
            }
        ]
    };
    const result = formatWarnings(status);
    assert.strictEqual(result, "[Warning W001] Conflict detected | Owner: agent-b | Status: pending | ACK by agent-b (Note: ACK does not imply approved merge)");
});

test('formatWarnings - handles missing checks (never clean)', () => {
    const status = {
        warnings: [
            {
                id: "W002",
                message: "Another issue",
                owner: "agent-c",
                resolution: "resolved",
                ack: null
            }
        ]
    };
    const result = formatWarnings(status);
    assert.strictEqual(result, "[Warning W002] Another issue | Owner: agent-c | Status: resolved | No ACK | State: Dirty (missing checks never clean)");
});

test('formatWarnings - sorts deterministically and handles absent fields', () => {
    const status = {
        warnings: [
            {
                message: "Missing ID",
                ackOwner: "agent-a" // this alone doesn't trigger ack if ack isn't true or object, wait! 
            },
            {
                id: "A123",
                owner: "agent-a",
                ack: true,
                checks: []
            }
        ]
    };
    const result = formatWarnings(status);
    const expected = "[Warning A123] No message | Owner: agent-a | Status: pending | ACK by agent-a (Note: ACK does not imply approved merge) | State: Dirty (missing checks never clean)\n" +
                     "[Warning unknown] Missing ID | Owner: unassigned | Status: pending | No ACK | State: Dirty (missing checks never clean)";
    assert.strictEqual(result, expected);
});

test('formatWarnings - binds ACK displayed to actual warning owner if unspecified', () => {
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
    assert.strictEqual(result, "[Warning W003] No message | Owner: agent-z | Status: pending | ACK by agent-z (Note: ACK does not imply approved merge)");
});
