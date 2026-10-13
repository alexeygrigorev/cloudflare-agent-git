#!/usr/bin/env python3
"""VictoriaMetrics client for private experiment metrics.

Numeric series only. Unknown stays absent, never zero: any value that is
None (or unparseable) produces no line at all. Label values use the string
"unknown" only for attribution buckets (provider/model/team), never for the
sampled numeric value itself.

Transport is the Prometheus import API over localhost; stdlib only.
"""
import collections
import json
import time
import urllib.parse
import urllib.request

VM_URL = 'http://127.0.0.1:8428'
IMPORT_PATH = '/api/v1/import/prometheus'


def _esc(value):
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _line(name, labels, value, ts_ms=None):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float('inf'), float('-inf')):
        return None
    # Integers render without a decimal point; nothing is ever zero-filled.
    text = str(int(number)) if number.is_integer() else repr(number)
    label_str = ''.join('{%s}' % ','.join('%s="%s"' % (k, _esc(v)) for k, v in labels.items())) if labels else ''
    suffix = ' %d' % int(ts_ms) if ts_ms is not None else ''
    return '%s%s %s%s' % (name, label_str, text, suffix)


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float('inf'), float('-inf')):
        return None
    return number


def usage_attribution(usage):
    """Resolve (provider, model) labels for a usage record.

    Returns ("unknown", "unknown") only as label buckets when the harness
    gives no provider/model binding; the token counts themselves stay real.
    """
    if not isinstance(usage, dict):
        return 'unknown', 'unknown'
    provider = usage.get('provider') or 'unknown'
    model = usage.get('model') or 'unknown'
    source = str(usage.get('source') or '')
    if source.startswith('owner-metadata-'):
        # source form: owner-metadata-<provider>-<model>
        rest = source[len('owner-metadata-'):]
        if '-' in rest:
            provider, model = rest.split('-', 1)
    elif source in ('codex-native-cumulative', 'codex-rollout'):
        provider, model = 'codex', provider if provider != 'unknown' else 'unknown'
        if model == 'unknown':
            model = 'unknown'
    elif source == 'claude-result-modelUsage':
        provider = 'claude' if provider == 'unknown' else provider
    models = usage.get('models')
    if model == 'unknown' and isinstance(models, dict) and len(models) == 1:
        only = next(iter(models))
        if isinstance(only, str) and only and only != 'unknown':
            model = only
    return str(provider), str(model)


def build_series(snap, ts_ms=None):
    """Pure function: collector snapshot dict -> list of Prometheus import lines."""
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    lines = []

    def add(name, labels, value):
        row = _line(name, labels, value, ts_ms)
        if row is not None:
            lines.append(row)

    sessions = snap.get('sessions', []) if isinstance(snap, dict) else []
    counted = [s for s in sessions if isinstance(s, dict) and s.get('counted_as_agent')]

    agents_registered = collections.Counter()
    agents_live = collections.Counter()
    agents_working = collections.Counter()
    agents_idle = collections.Counter()
    for s in counted:
        key = (str(s.get('role') or 'unknown'), str(s.get('team_id') or 'unknown'))
        agents_registered[key] += 1
        if s.get('pid_live'):
            agents_live[key] += 1
            if s.get('hook_working'):
                agents_working[key] += 1
            if s.get('reported_state') in ('idle', 'waiting'):
                agents_idle[key] += 1
    for (role, team), count in agents_registered.items():
        labels = {'role': role, 'team': team}
        add('exp_agents_registered', labels, count)
        add('exp_agents_live', labels, agents_live.get((role, team), 0))
        add('exp_agents_working', labels, agents_working.get((role, team), 0))
        add('exp_agents_idle', labels, agents_idle.get((role, team), 0))

    tasks = snap.get('tasks', []) if isinstance(snap, dict) else []
    tasks_by_status = collections.Counter()
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tasks_by_status[(str(t.get('status') or 'unknown'), str(t.get('team_id') or t.get('project') or 'unknown'))] += 1
    for (status, team), count in tasks_by_status.items():
        add('exp_tasks', {'status': status, 'team': team}, count)

    observation = snap.get('observation', {}) if isinstance(snap, dict) else {}
    transitions = observation.get('task_transitions_this_sample', []) or []
    transition_counts = collections.Counter()
    for event in transitions:
        if not isinstance(event, dict):
            continue
        transition_counts[(str(event.get('from_status') or 'none'), str(event.get('to_status') or 'unknown'))] += 1
    for (from_status, to_status), count in transition_counts.items():
        add('exp_task_transitions', {'from_status': from_status, 'to_status': to_status}, count)

    seen_conversations = set()
    for s in sessions:
        if not isinstance(s, dict):
            continue
        usage = s.get('usage')
        if not isinstance(usage, dict) or not usage.get('conversation_id'):
            continue
        key = str(usage.get('source') or '') + ':' + str(usage['conversation_id'])
        if key in seen_conversations:
            continue
        seen_conversations.add(key)
        provider, model = usage_attribution(usage)
        labels = {
            'provider': provider,
            'model': model,
            'source': str(usage.get('source') or 'unknown'),
            'conversation': str(usage['conversation_id']),
        }
        add('exp_tokens_cumulative', labels, _num(usage.get('total_tokens')))
        add('exp_tokens_interval', labels, _num(usage.get('tokens_since_observer')))

    quota = snap.get('quota', {}) if isinstance(snap, dict) else {}
    providers = quota.get('providers', {}) if isinstance(quota, dict) else {}
    for provider, record in providers.items():
        if not isinstance(record, dict):
            continue
        if record.get('status') == 'ok':
            add('exp_quota_status_ok', {'provider': str(provider)}, 1)
        elif record.get('status'):
            add('exp_quota_status_ok', {'provider': str(provider)}, 0)
        for window, values in (record.get('windows') or {}).items():
            if not isinstance(values, dict):
                continue
            add('exp_quota_remaining', {'provider': str(provider), 'window': str(window)},
                _num(values.get('percent_remaining')))

    host = snap.get('host', {}) if isinstance(snap, dict) else {}
    disks = host.get('disks', {}) if isinstance(host, dict) else {}
    for mount, values in disks.items():
        if not isinstance(values, dict):
            continue
        add('exp_disk_free_bytes', {'mount': str(mount)}, _num(values.get('free_bytes')))
        add('exp_disk_total_bytes', {'mount': str(mount)}, _num(values.get('total_bytes')))
    load = host.get('load_average') if isinstance(host, dict) else None
    if isinstance(load, (list, tuple)):
        for period, value in zip(('1m', '5m', '15m'), load):
            add('exp_host_load', {'period': period}, _num(value))

    supervision = snap.get('supervision', {}) if isinstance(snap, dict) else {}
    principals = supervision.get('principals', {}) if isinstance(supervision, dict) else {}
    for name, record in principals.items():
        if not isinstance(record, dict) or record.get('alive') is None:
            continue
        add('exp_supervision_alive', {'principal': str(name)}, 1 if record['alive'] else 0)

    aggregate = snap.get('aggregate', {}) if isinstance(snap, dict) else {}
    add('exp_known_tokens_total', {}, _num(aggregate.get('known_conversation_tokens')))
    add('exp_tokens_since_observer_known', {}, _num(aggregate.get('tokens_since_observer_known')))
    add('exp_unregistered_live', {}, _num(aggregate.get('unregistered_live')))
    errors = snap.get('errors', []) if isinstance(snap, dict) else []
    add('exp_collector_errors', {}, len(errors) if isinstance(errors, list) else 0)
    add('exp_collector_up', {}, 1)
    return lines


def push_series(lines, vm_url=VM_URL, timeout=15):
    """POST Prometheus import lines. Returns (True, '') or (False, reason)."""
    if not lines:
        return True, 'no series to push'
    body = ('\n'.join(lines) + '\n').encode('utf-8')
    request = urllib.request.Request(
        vm_url.rstrip('/') + IMPORT_PATH, data=body, method='POST',
        headers={'Content-Type': 'text/plain; version=0.0.4'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status not in (200, 204):
                return False, 'import HTTP %s' % response.status
    except Exception as exc:
        return False, '%s: %s' % (type(exc).__name__, exc)
    return True, ''


def _get_json(url, timeout):
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def query(vm_url, expr, at=None, timeout=30):
    """Instant query. Returns the result list (possibly empty)."""
    params = {'query': expr}
    if at is not None:
        params['time'] = str(at)
    payload = _get_json(vm_url.rstrip('/') + '/api/v1/query?' + urllib.parse.urlencode(params), timeout)
    if payload.get('status') != 'success':
        raise ValueError('query failed: %r' % (payload,))
    return payload['data']['result']


def query_range(vm_url, expr, start, end, step='60s', timeout=60):
    """Range query. start/end are unix seconds or RFC3339 strings."""
    params = {'query': expr, 'start': str(start), 'end': str(end), 'step': step}
    payload = _get_json(vm_url.rstrip('/') + '/api/v1/query_range?' + urllib.parse.urlencode(params), timeout)
    if payload.get('status') != 'success':
        raise ValueError('query_range failed: %r' % (payload,))
    return payload['data']['result']
