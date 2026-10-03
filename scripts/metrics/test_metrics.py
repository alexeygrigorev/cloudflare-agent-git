import unittest, tempfile, pathlib, types, json
from unittest.mock import patch
import collect
class MetricsTests(unittest.TestCase):
    def test_identity_dedup_unknown_and_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'alpha','agents':[{'tag':'head','role':'head','session_id':'one'},{'tag':'worker','role':'executor'}]}],'agents':[{'tag':'service','role':'service'}]}))
            (root/'coordination/TASKS.json').write_text(json.dumps({'tasks':[{'id':'t1','team_id':'alpha','owner_tag':'worker','status':'blocked','blocked_on':['t0'],'evidence_paths':['result.txt'],'acceptance_status':'pending','next_action':'independent replay','assignment_ack':False,'updated_at':'2026-10-03T00:00:00Z'}]}))
            (root/'result.txt').write_text('public artifact')
            catalog=[{'id':'one','tag':'head','workspace':str(root),'workload_pid':1,'reported_state':'working'},{'id':'two','tag':'worker','workspace':str(root),'workload_pid':2,'reported_state':'idle'},{'id':'three','tag':'service','workspace':str(root),'workload_pid':3}]
            use={'conversation_id':'same','source':'native','total_tokens':200,'cost_usd':None}
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(catalog))),patch.object(collect,'proc',return_value={'alive':True}),patch.object(collect,'native_usage',side_effect=lambda s:use if s['id'] in ('one','two') else None):
                snap=collect.collect()
            self.assertEqual(snap['aggregate']['registered_agents'],2)
            self.assertEqual(snap['aggregate']['services_and_writers'],1)
            self.assertEqual(snap['aggregate']['known_conversation_tokens'],200)
            self.assertEqual(snap['aggregate']['agents_hook_working'],1)
            self.assertEqual(snap['aggregate']['tasks_by_status']['blocked'],1)
            self.assertIsNone(snap['sessions'][0]['usage']['cost_usd'])
            self.assertTrue((store/'latest.json').is_file())
            history=json.loads(next(store.glob('snapshots-*.jsonl')).read_text().splitlines()[-1])
            task=history['tasks'][0]; self.assertEqual(task['team_id'],'alpha'); self.assertEqual(task['next_action'],'independent replay'); self.assertEqual(task['evidence_paths'],['result.txt']); self.assertFalse(task['assignment_ack']); self.assertEqual(task['acceptance_status'],'pending')
            worker=next(r for r in history['sessions'] if r['tag']=='worker'); self.assertEqual(worker['evidence'][0]['path'],'result.txt'); self.assertEqual(worker['evidence'][0]['bytes'],15); self.assertEqual(worker['tasks'][0]['id'],'t1')
            self.assertNotIn('prompt',history); self.assertNotIn('transcript',worker)
    def test_ambiguous_tag_is_not_falsely_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'worker','role':'executor'}]}]}))
            rows=[{'id':str(i),'tag':'worker','workspace':str(root),'workload_pid':i} for i in (1,2)]
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(rows))),patch.object(collect,'proc',side_effect=lambda p:{'alive':p is not None}),patch.object(collect,'native_usage',return_value=None):
                snap=collect.collect()
            self.assertEqual(snap['sessions'][0]['resolution'],'ambiguous live tag')
            self.assertFalse(snap['sessions'][0]['pid_live'])
            self.assertEqual(snap['aggregate']['unregistered_live'],2)
            self.assertIsNone(snap['aggregate']['known_conversation_tokens'])
if __name__=='__main__': unittest.main()
