#!/usr/bin/env python3
"""Fresh quse gate for real OpenAI Codex launches, never reset redemption."""
import json, subprocess, sys

def decision(record):
    if record.get('status') != 'ok' or record.get('error'):
        return False, 'quota unavailable'
    if record.get('details', {}).get('limit_reached'):
        return False, 'provider limit reached'
    values = [v.get('percent_remaining') for v in record.get('windows', {}).values()
              if isinstance(v, dict) and isinstance(v.get('percent_remaining'), (float, int))]
    if not values:
        return False, 'no available quota window'
    remaining = min(values)
    return remaining > 15, f'minimum available window {remaining:g}% remaining; reserve 15%'

if __name__ == '__main__':
    try:
        result = subprocess.run(['quse', 'codex', '--json'], capture_output=True, text=True, timeout=45, check=True)
        allowed, reason = decision(json.loads(result.stdout).get('codex', {}))
    except Exception as exc:
        allowed, reason = False, f'quota read failed ({type(exc).__name__})'
    print(json.dumps({'provider':'codex','launch_allowed':allowed,'reason':reason}))
    sys.exit(0 if allowed else 75)
