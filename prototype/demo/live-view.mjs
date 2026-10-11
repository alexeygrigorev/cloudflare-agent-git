export function formatAgentSummary(status) {
    if (!status || typeof status !== 'object') {
        return '[STALE/UNKNOWN] Invalid status object';
    }

    // Do not copy secrets (e.g. token). Read actual core coordinator/status shape.
    const safeData = {
        agentId: status.agentId || 'UNKNOWN',
        base: status.baseSha || status.base_sha || status.base || 'UNKNOWN',
        head: status.head || 'UNKNOWN',
        taskId: status.taskId || 'UNKNOWN'
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

    const formatted = parts.join(' | ');

    if (hasMissing) {
        return `[DIRTY/INCOMPLETE] ${formatted}`;
    }

    return `[COMPLETE] ${formatted}`;
}

export function formatWarnings(status) {
  if (!status || !Array.isArray(status.warnings)) {
    return "No warnings data available.";
  }

  const sortedWarnings = [...status.warnings].sort((a, b) => {
    const idA = String(a.id || '');
    const idB = String(b.id || '');
    return idA.localeCompare(idB);
  });

  return sortedWarnings.map(warning => {
    const id = warning.id || 'unknown';
    const message = warning.message || 'No message';
    const owner = warning.owner || 'unassigned';
    const resolution = warning.resolution || 'pending';
    const checks = warning.checks;

    let ackStr = 'No ACK';
    if (warning.ack) {
       const ackOwner = typeof warning.ack === 'object' ? warning.ack.owner : (warning.ackOwner || owner);
       ackStr = `ACK by ${ackOwner} (Note: ACK does not imply approved merge)`;
    }

    let checksStr = '';
    if (!checks || (Array.isArray(checks) && checks.length === 0)) {
      checksStr = ' | State: Dirty (missing checks never clean)';
    }

    return `[Warning ${id}] ${message} | Owner: ${owner} | Status: ${resolution} | ${ackStr}${checksStr}`;
  }).join('\n');
}
