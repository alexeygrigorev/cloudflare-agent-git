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

    if (status.stale === true) {
        return `[STALE] ${formatted}`;
    }

    if (status.status === 'not_checked' || status.status === 'unknown') {
        return `[NOT_CHECKED] ${formatted}`;
    }

    if (hasMissing) {
        return `[DIRTY/INCOMPLETE] ${formatted}`;
    }

    return `[COMPLETE] ${formatted}`;
}

export function formatWarnings(status) {
  if (!status || !Array.isArray(status.warnings)) {
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
    const message = warning.message !== undefined && warning.message !== null ? String(warning.message) : 'No message';
    const owner = warning.owner !== undefined && warning.owner !== null ? String(warning.owner) : 'unassigned';
    const resolution = warning.resolution !== undefined && warning.resolution !== null ? String(warning.resolution) : 'pending';
    const checks = warning.checks;

    let ackStr = 'No ACK';
    if (warning.ack) {
       let ackOwner = owner;
       if (typeof warning.ack === 'object' && warning.ack.owner !== undefined) {
           ackOwner = String(warning.ack.owner);
       } else if (warning.ackOwner !== undefined) {
           ackOwner = String(warning.ackOwner);
       } else if (typeof warning.ack === 'string') {
           ackOwner = warning.ack;
       }
       ackStr = `ACK by ${ackOwner} (Note: ACK does not imply approved merge)`;
    }

    let checksStr = '';
    if (!checks || !Array.isArray(checks) || checks.length === 0) {
      checksStr = ' | State: Dirty (missing checks never clean)';
    }

    return `[Warning ${id}] ${message} | Owner: ${owner} | Status: ${resolution} | ${ackStr}${checksStr}`;
  }).join('\n');
}
