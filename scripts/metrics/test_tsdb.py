import http.server
import json
import threading
import unittest

import tsdb


def make_snap():
    return {
        'at': '2026-10-13T19:00:00+00:00',
        'aggregate': {
            'known_conversation_tokens': 500,
            'tokens_since_observer_known': 120,
            'unregistered_live': 2,
        },
        'errors': [],
        'sessions': [
            {'id': 'a', 'tag': 'head-1', 'role': 'head', 'team_id': 'T1',
             'counted_as_agent': True, 'pid_live': True, 'hook_working': True,
             'reported_state': 'working',
             'usage': {'source': 'codex-native-cumulative', 'conversation_id': 'c1',
                       'total_tokens': 300, 'tokens_since_observer': 100}},
            {'id': 'b', 'tag': 'w-1', 'role': 'executor', 'team_id': 'T1',
             'counted_as_agent': True, 'pid_live': True, 'hook_working': False,
             'reported_state': 'idle', 'usage': None},
            {'id': 'c', 'tag': 'svc', 'role': 'service', 'team_id': 'T1',
             'counted_as_agent': False, 'pid_live': True, 'hook_working': False,
             'reported_state': 'working',
             'usage': {'source': 'owner-metadata-zai-glm', 'conversation_id': 'c2',
                       'total_tokens': 200, 'tokens_since_observer': None}},
        ],
        'tasks': [
            {'id': 't1', 'status': 'running', 'team_id': 'T1'},
            {'id': 't2', 'status': 'blocked', 'team_id': 'T2'},
            {'id': 't3', 'status': 'blocked', 'team_id': 'T2'},
        ],
        'observation': {'task_transitions_this_sample': [
            {'task_id': 't1', 'from_status': 'ready', 'to_status': 'running'},
        ]},
        'quota': {'providers': {
            'zai': {'status': 'ok', 'windows': {
                '5h': {'percent_remaining': 86.0},
                '7d': {'percent_remaining': None}}},
            'claude': {'status': 'error', 'windows': {}},
        }},
        'host': {'load_average': [1.5, 1.0, 0.5],
                 'disks': {'root': {'free_bytes': 10, 'total_bytes': 100}}},
        'supervision': {'principals': {'codex-principal': {'alive': True}}},
    }


class SeriesTests(unittest.TestCase):
    def test_counts_and_labels(self):
        lines = tsdb.build_series(make_snap(), ts_ms=1000)
        joined = '\n'.join(lines)
        self.assertIn('exp_agents_registered{role="head",team="T1"} 1 1000', joined)
        self.assertIn('exp_agents_live{role="executor",team="T1"} 1 1000', joined)
        self.assertIn('exp_agents_working{role="executor",team="T1"} 0 1000', joined)
        self.assertIn('exp_agents_idle{role="executor",team="T1"} 1 1000', joined)
        self.assertIn('exp_tasks{status="blocked",team="T2"} 2 1000', joined)
        self.assertIn('exp_task_transitions{from_status="ready",to_status="running"} 1 1000', joined)
        # Services are not counted as agents.
        self.assertNotIn('role="service"', joined)

    def test_unknown_stays_absent_never_zero(self):
        lines = tsdb.build_series(make_snap(), ts_ms=1000)
        joined = '\n'.join(lines)
        # claude has no windows -> no quota series; zai 7d is None -> absent.
        self.assertNotIn('provider="claude"', [l for l in joined.splitlines() if l.startswith('exp_quota_remaining')])
        self.assertIn('exp_quota_remaining{provider="zai",window="5h"} 86 1000', joined)
        self.assertNotIn('window="7d"', joined)
        # tokens_since_observer None for c2 -> no interval line for c2.
        interval = [l for l in lines if l.startswith('exp_tokens_interval')]
        self.assertEqual(len(interval), 1)
        self.assertIn('conversation="c1"', interval[0])
        for line in lines:
            value = line.rsplit(' ', 2)[-2]
            self.assertNotIn(value.lower(), ('nan', '+inf', '-inf'))

    def test_token_attribution(self):
        lines = tsdb.build_series(make_snap(), ts_ms=1000)
        joined = '\n'.join(lines)
        self.assertIn('provider="codex"', joined)
        self.assertIn('provider="zai",model="glm"', joined)
        self.assertIn('exp_known_tokens_total 500 1000', joined)
        self.assertIn('exp_host_load{period="1m"} 1.5 1000', joined)
        self.assertIn('exp_disk_free_bytes{mount="root"} 10 1000', joined)
        self.assertIn('exp_supervision_alive{principal="codex-principal"} 1 1000', joined)
        self.assertIn('exp_collector_up 1 1000', joined)
        self.assertIn('exp_collector_errors 0 1000', joined)

    def test_label_escaping(self):
        snap = make_snap()
        snap['sessions'][0]['team_id'] = 'we"ird\\team'
        lines = tsdb.build_series(snap, ts_ms=1)
        self.assertTrue(any('team="we\\"ird\\\\team"' in l for l in lines))

    def test_history_rows_without_flags_infer_role_and_working(self):
        # Archived history projections predate counted_as_agent/hook_working.
        snap = make_snap()
        for s in snap['sessions']:
            s.pop('counted_as_agent', None)
            s.pop('hook_working', None)
        lines = tsdb.build_series(snap, ts_ms=1000)
        joined = '\n'.join(lines)
        self.assertIn('exp_agents_registered{role="head",team="T1"} 1 1000', joined)
        self.assertIn('exp_agents_working{role="head",team="T1"} 1 1000', joined)
        self.assertIn('exp_agents_idle{role="executor",team="T1"} 1 1000', joined)
        # Services stay excluded even under inference.
        self.assertNotIn('role="service"', joined)


class ClientTests(unittest.TestCase):
    def test_push_and_query_roundtrip_against_stub(self):
        received = {}

        class Stub(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                received['body'] = self.rfile.read(length)
                received['path'] = self.path
                self.send_response(204)
                self.end_headers()

            def do_GET(self):
                received['query_path'] = self.path
                payload = json.dumps({'status': 'success', 'data': {'result': [{'ok': True}]}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Stub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = 'http://127.0.0.1:%d' % server.server_address[1]
            ok, err = tsdb.push_series(['exp_a{x="y"} 1 1000'], vm_url=url)
            self.assertTrue(ok, err)
            self.assertEqual(received['path'], '/api/v1/import/prometheus')
            self.assertEqual(received['body'], b'exp_a{x="y"} 1 1000\n')
            self.assertEqual(tsdb.query(url, 'exp_a'), [{'ok': True}])
            self.assertIn('/api/v1/query?', received['query_path'])
            ok, _ = tsdb.push_series([], vm_url=url)
            self.assertTrue(ok)
        finally:
            server.shutdown()

    def test_push_failure_reports_reason(self):
        ok, err = tsdb.push_series(['exp_a 1 1'], vm_url='http://127.0.0.1:1', timeout=2)
        self.assertFalse(ok)
        self.assertTrue(err)


if __name__ == '__main__':
    unittest.main()
