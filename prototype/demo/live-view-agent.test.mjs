import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatAgentSummary } from './live-view.mjs';

test('formatAgentSummary formats real heads deterministically', () => {
    const status = {
        taskId: 't-123',
        agentId: 'a-1',
        baseSha: 'base123',
        head: 'head123',
        secretToken: 'abc' // Should be ignored
    };
    const result = formatAgentSummary(status);
    // Keys sorted: agentId, base, head, taskId
    assert.equal(result, '[COMPLETE] agentId: a-1 | base: base123 | head: head123 | taskId: t-123');
    assert.ok(!result.includes('secretToken'));
});

test('formatAgentSummary handles missing/unknown fields', () => {
    const result = formatAgentSummary({ taskId: 't-1' });
    assert.ok(result.includes('[DIRTY/INCOMPLETE]'));
    assert.ok(result.includes('agentId: NOT_CHECKED/UNKNOWN'));
});

test('formatAgentSummary handles absent optional fields and stale status', () => {
    const result = formatAgentSummary(null);
    assert.equal(result, '[STALE/UNKNOWN] Invalid status object');
});

test('formatAgentSummary handles explicit stale state', () => {
    const result = formatAgentSummary({
        taskId: 't-1',
        agentId: 'a-1',
        baseSha: 'base123',
        head: 'head123',
        stale: true
    });
    assert.equal(result, '[STALE] agentId: a-1 | base: base123 | head: head123 | taskId: t-1');
});

test('formatAgentSummary handles not_checked status explicitly', () => {
    const result = formatAgentSummary({
        taskId: 't-1',
        agentId: 'a-1',
        baseSha: 'base123',
        head: 'head123',
        status: 'not_checked'
    });
    assert.equal(result, '[NOT_CHECKED] agentId: a-1 | base: base123 | head: head123 | taskId: t-1');
});
