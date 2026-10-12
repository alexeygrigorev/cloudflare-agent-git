export function formatAgentSummary(status) {
    if (!status || typeof status !== 'object') {
        return '[STALE/UNKNOWN] Invalid status object';
    }

    const agents = Array.isArray(status.agents) ? status.agents : [];
    if (agents.length === 0) {
        return '[UNKNOWN] No agents found';
    }

    // Deterministic sorting
    const sortedAgents = [...agents].sort((a, b) => {
        const idA = a.agentId || '';
        const idB = b.agentId || '';
        return idA.localeCompare(idB);
    });

    return sortedAgents.map(agent => {
        // Do not copy secrets (e.g. token). Read actual core coordinator/status shape.
        const safeData = {
            agentId: agent.agentId || 'UNKNOWN',
            base: agent.baseSha || agent.base_sha || agent.base || 'UNKNOWN',
            head: agent.head || 'UNKNOWN',
            taskId: agent.taskId || 'UNKNOWN'
        };

        // Deterministic sorting
        const keys = Object.keys(safeData).sort();

        let hasMissing = false;
        const parts = keys.map(k => {
            const val = safeData[k];
            if (val === 'UNKNOWN' || val === null || val === undefined || val === '') {
                hasMissing = true;
                return `${k}: NOT_CHECKED/UNKNOWN`;
            }
            return `${k}: ${val}`;
        });

        // Determine state from pairs
        let isClean = !hasMissing;
        let isStale = false;
        let isNotChecked = false;
        let isUnknown = false;

        if (Array.isArray(status.pairs)) {
            const pairs = status.pairs.filter(p => p.pair && p.pair.includes(agent.agentId));
            if (pairs.length === 0) {
                isUnknown = true;
                isClean = false;
            } else {
                for (const p of pairs) {
                    if (p.stale) isStale = true;
                    if (p.status === 'not_checked') isNotChecked = true;
                    if (p.status === 'unknown') isUnknown = true;
                }
            }
        } else {
            isUnknown = true;
            isClean = false;
        }

        if (isStale) isClean = false;
        if (isNotChecked) isClean = false;
        if (isUnknown) isClean = false;

        const prefix = isStale ? '[STALE]' :
                       isNotChecked ? '[NOT_CHECKED]' :
                       isUnknown || hasMissing ? '[DIRTY/INCOMPLETE]' :
                       '[CLEAN]';

        return `${prefix} ${parts.join(' | ')}`;
    }).join('\n');
}

export function formatWarnings(status) {
    if (!status || typeof status !== 'object' || !Array.isArray(status.warnings)) {
        return "No warnings data available.";
    }
    if (status.warnings.length === 0) {
        return "";
    }

    const sortedWarnings = [...status.warnings].sort((a, b) => {
        const idA = a.id !== undefined && a.id !== null ? String(a.id) : 'unknown';
        const idB = b.id !== undefined && b.id !== null ? String(b.id) : 'unknown';
        return idA.localeCompare(idB);
    });

    return sortedWarnings.map(warning => {
        const id = warning.id !== undefined && warning.id !== null ? String(warning.id) : 'unknown';
        const reason = warning.reason !== undefined && warning.reason !== null
            ? String(warning.reason)
            : (warning.message !== undefined && warning.message !== null ? String(warning.message) : 'No reason');

        // Use pair if available (actual shape), fallback to owner
        let owners = 'unassigned';
        if (Array.isArray(warning.pair) && warning.pair.length > 0) {
            owners = [...warning.pair].sort().join(', ');
        } else if (warning.owner !== undefined && warning.owner !== null) {
            owners = String(warning.owner);
        }

        const resolution = warning.status !== undefined && warning.status !== null
            ? String(warning.status)
            : (warning.resolution !== undefined && warning.resolution !== null ? String(warning.resolution) : 'pending');

        let acksStr = 'No ACK';
        if (Array.isArray(warning.acks) && warning.acks.length > 0) {
            const sortedAcks = [...warning.acks].sort((a, b) => {
                const agentA = a.agent !== undefined && a.agent !== null ? String(a.agent) : '';
                const agentB = b.agent !== undefined && b.agent !== null ? String(b.agent) : '';
                return agentA.localeCompare(agentB);
            });
            acksStr = sortedAcks.map(ack => {
                const ackOwner = ack.agent !== undefined && ack.agent !== null ? String(ack.agent) : 'unknown';
                return `ACK by ${ackOwner} (Note: ACK does not imply approved merge)`;
            }).join(' | ');
        } else if (warning.ack) { // fallback to old format
            let ackOwner = owners;
            if (typeof warning.ack === 'object' && warning.ack.owner !== undefined) {
                ackOwner = String(warning.ack.owner);
            } else if (warning.ackOwner !== undefined) {
                ackOwner = String(warning.ackOwner);
            } else if (typeof warning.ack === 'string') {
                ackOwner = warning.ack;
            }
            acksStr = `ACK by ${ackOwner} (Note: ACK does not imply approved merge)`;
        }

        let checksStr = '';
        if (!warning.checks || !Array.isArray(warning.checks) || warning.checks.length === 0) {
            checksStr = ' | State: Dirty (missing checks never clean)';
        }

        return `[Warning ${id}] ${reason} | Owner: ${owners} | Status: ${resolution} | ${acksStr}${checksStr}`;
    }).join('\n');
}
