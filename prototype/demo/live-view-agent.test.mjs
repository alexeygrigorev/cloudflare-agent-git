import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatAgentSummary } from './live-view.mjs';

test('formatAgentSummary formats real heads deterministically', () => {
    const status = {
        agents: [{
            taskId: 't-123',
            agentId: 'a-1',
            baseSha: 'base123',
            head: 'head123',
            secretToken: 'abc' // Should be ignored
        }],
        pairs: [{
            pair: ['a-1', 'b-2'],
            status: 'clean',
            stale: false
        }]
    };
    const result = formatAgentSummary(status);
    assert.equal(result, '[CLEAN] agentId: a-1 | base: base123 | head: head123 | taskId: t-123');
    assert.ok(!result.includes('secretToken'));
});

test('formatAgentSummary handles missing/unknown fields', () => {
    const status = {
        agents: [{ taskId: 't-1' }],
        pairs: [{ pair: ['undefined', 'b-2'] }]
    };
    const result = formatAgentSummary(status);
    assert.ok(result.includes('[DIRTY/INCOMPLETE]'));
    assert.ok(result.includes('agentId: NOT_CHECKED/UNKNOWN'));
});

test('formatAgentSummary handles absent optional fields', () => {
    const result = formatAgentSummary(null);
    assert.equal(result, '[STALE/UNKNOWN] Invalid status object');

    const result2 = formatAgentSummary({});
    assert.equal(result2, '[UNKNOWN] No agents found');
});

test('formatAgentSummary handles explicit stale state', () => {
    const status = {
        agents: [{
            taskId: 't-1',
            agentId: 'a-1',
            baseSha: 'base123',
            head: 'head123'
        }],
        pairs: [{
            pair: ['a-1', 'b-2'],
            stale: true,
            status: 'clean'
        }]
    };
    const result = formatAgentSummary(status);
    assert.equal(result, '[STALE] agentId: a-1 | base: base123 | head: head123 | taskId: t-1');
});

test('formatAgentSummary handles not_checked status explicitly', () => {
    const status = {
        agents: [{
            taskId: 't-1',
            agentId: 'a-1',
            baseSha: 'base123',
            head: 'head123'
        }],
        pairs: [{
            pair: ['a-1', 'b-2'],
            stale: false,
            status: 'not_checked'
        }]
    };
    const result = formatAgentSummary(status);
    assert.equal(result, '[NOT_CHECKED] agentId: a-1 | base: base123 | head: head123 | taskId: t-1');
});
