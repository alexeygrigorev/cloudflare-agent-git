export function sanitizeEvidence(receipt) {
  if (receipt === null || receipt === undefined) {
    return receipt;
  }
  
  if (typeof receipt === 'string') {
    if (receipt === 'unknown') {
      return receipt;
    }
    try {
      if (receipt.includes('://')) {
        const url = new URL(receipt);
        if (url.username || url.password) {
          url.username = 'REDACTED';
          url.password = 'REDACTED';
          return url.toString();
        }
      }
    } catch (e) {
      // Not a valid URL
    }
    return receipt;
  }
  
  if (Array.isArray(receipt)) {
    return receipt.map(item => sanitizeEvidence(item));
  }
  
  if (typeof receipt === 'object') {
    const sanitized = {};
    const redactKeys = ['token', 'password', 'authorization', 'secret'];
    for (const [key, value] of Object.entries(receipt)) {
      if (value === 'unknown') {
        sanitized[key] = value;
      } else if (redactKeys.some(k => key.toLowerCase().includes(k))) {
        sanitized[key] = 'REDACTED';
      } else {
        sanitized[key] = sanitizeEvidence(value);
      }
    }
    return sanitized;
  }
  
  return receipt;
}
