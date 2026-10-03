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
    def _write_rollout(self,path,conversation_id,total):
        rows=[{'timestamp':'t0','type':'session_meta','payload':{'id':conversation_id}},
              {'timestamp':'t1','type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':total-30,'output_tokens':30,'total_tokens':total,'cached_input_tokens':5,'reasoning_output_tokens':3}}}}]
        pathlib.Path(path).write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    def test_completed_session_disk_fallback_populates_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True)
            sessions=root/'state/aplexer/sessions'; (root/'coordination').mkdir()
            for sid,name in (('gone','session.json'),('gone2','session_record.json')):
                d=sessions/sid; d.mkdir(parents=True)
                (d/name).write_text(json.dumps({'id':sid,'tag':sid,'cwd':str(root),'engine':'zcodex','reported_state':'idle','reported_state_at_ms':1,'last_activity_ms':1}))
                self._write_rollout(root/(sid+'-rollout.jsonl'),'conv-'+sid,150 if sid=='gone' else 70)
                (d/'transcript.json').write_text(json.dumps({'engine':'zcodex','path':str(root/(sid+'-rollout.jsonl')),'engine_session_id':'conv-'+sid}))
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'gone','role':'executor','session_id':'gone'},{'tag':'gone2','role':'executor','session_id':'gone2'}]}]}))
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')),patch.object(collect,'proc',return_value={'alive':False}):
                snap=collect.collect()
            rows={r['tag']:r for r in snap['sessions']}
            for sid,total in (('gone',150),('gone2',70)):
                row=rows[sid]
                self.assertEqual(row['resolution'],'registered completed session on disk')
                self.assertEqual(row['id'],sid)
                self.assertEqual(row['usage']['source'],'codex-native-cumulative')
                self.assertEqual(row['usage']['total_tokens'],total)
                self.assertIsNone(row['usage']['cost_usd'])
            self.assertEqual(snap['aggregate']['known_conversation_tokens'],220)
            self.assertEqual(snap['aggregate']['agents_without_token_observation'],0)
    def test_missing_everywhere_stays_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            sessions=root/'state/aplexer/sessions'
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'lost','role':'executor','session_id':'vanished'}]}]}))
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')),patch.object(collect,'proc',return_value={'alive':False}):
                snap=collect.collect()
            row=snap['sessions'][0]
            self.assertEqual(row['resolution'],'missing')
            self.assertIsNone(row['usage'])
            self.assertIsNone(snap['aggregate']['known_conversation_tokens'])
    def test_rollout_telemetry_fallback_dedups_native_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            sessions=root/'state/aplexer/sessions'
            self._write_rollout(root/'rb-rollout.jsonl','conv-x',300)
            catalog=[{'id':'aaa','tag':'na','workspace':str(root),'workload_pid':1,'reported_state':'working'},{'id':'bbb','tag':'rb','workspace':str(root),'workload_pid':2,'reported_state':'working'}]
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'na','role':'head','session_id':'aaa'},{'tag':'rb','role':'executor','session_id':'bbb','telemetry':{'type':'zcodex-rollout','path':str(root/'rb-rollout.jsonl')}}]}]}))
            native={'aaa':{'conversation_id':'conv-x','source':'codex-native-cumulative','total_tokens':200,'cost_usd':None}}
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(catalog))),patch.object(collect,'proc',return_value={'alive':True}),patch.object(collect,'native_usage',side_effect=lambda s:native.get(s['id'])):
                snap=collect.collect()
            rows={r['tag']:r for r in snap['sessions']}
            self.assertEqual(rows['na']['usage']['total_tokens'],200)
            rb=rows['rb']['usage']
            self.assertEqual(rb['source'],'codex-rollout')
            self.assertEqual(rb['conversation_id'],'conv-x')
            self.assertEqual(rb['total_tokens'],300)
            self.assertIsNone(rb['cost_usd'])
            self.assertEqual(snap['aggregate']['known_conversation_tokens'],300)
            self.assertEqual(snap['aggregate']['usage_observed_conversations'],1)
    def test_opencode_session_id_and_saved_conversation_are_attributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            agents=[{'tag':'oc1','role':'executor','opencode_session_id':'ses_a','telemetry':{'type':'opencode-db'}},{'tag':'oc2','role':'executor','opencode_session_id':'ses_b'},{'tag':'oc3','role':'executor','telemetry':{'type':'opencode-db','conversation_id':'ses_c'}}]
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':agents}]}))
            captured={}
            def fake_read(root_arg,assigns,interval):
                captured['assigns']=assigns
                return {'sessions':[],'stores':[]}
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'read_opencode_usage',fake_read),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')),patch.object(collect,'proc',return_value={'alive':False}):
                snap=collect.collect()
            ids={a['conversation_id'] for a in captured['assigns']}
            self.assertEqual(ids,{'ses_a','ses_b','ses_c'})
    def _disk_record(self,sessions,sid,payload):
        d=sessions/sid; d.mkdir(parents=True)
        (d/'session.json').write_text(json.dumps(payload))
        return d
    def test_disk_fallback_rejects_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            sessions=root/'state/aplexer/sessions'
            self._disk_record(sessions,'wrongid',{'id':'OTHER','tag':'mm','cwd':str(root)})
            self._disk_record(sessions,'wrongws',{'id':'wrongws','tag':'mm2','cwd':'/somewhere/else'})
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'mm','role':'executor','session_id':'wrongid'},{'tag':'mm2','role':'executor','session_id':'wrongws'}]}]}))
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')),patch.object(collect,'proc',return_value={'alive':False}):
                snap=collect.collect()
            rows={r['tag']:r for r in snap['sessions']}
            for tag in ('mm','mm2'):
                self.assertEqual(rows[tag]['resolution'],'missing')
                self.assertIsNone(rows[tag]['usage'])
            self.assertIsNone(snap['aggregate']['known_conversation_tokens'])
    def test_disk_fallback_never_reports_reused_pid_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            sessions=root/'state/aplexer/sessions'
            self._disk_record(sessions,'pid1',{'id':'pid1','tag':'pp','cwd':str(root),'workload_pid':1,'reported_state':'working','reported_state_at_ms':1})
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'pp','role':'executor','session_id':'pid1'}]}]}))
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')),patch.object(collect,'proc',side_effect=lambda p:{'alive':p==1}):
                snap=collect.collect()
            row=snap['sessions'][0]
            self.assertEqual(row['resolution'],'registered completed session on disk')
            self.assertFalse(row['pid_live'])
            self.assertFalse(row['hook_working'])
    def test_disk_fallback_skips_ambiguous_live_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            sessions=root/'state/aplexer/sessions'
            self._disk_record(sessions,'gone3',{'id':'gone3','tag':'amb','cwd':str(root)})
            rows=[{'id':str(i),'tag':'amb','workspace':str(root),'workload_pid':i} for i in (1,2)]
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':[{'tag':'amb','role':'executor','session_id':'gone3'}]}]}))
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(rows))),patch.object(collect,'proc',return_value={'alive':True}),patch.object(collect,'native_usage',return_value=None):
                snap=collect.collect()
            row=next(r for r in snap['sessions'] if r['tag']=='amb' and r['team_id']=='a')
            self.assertEqual(row['resolution'],'ambiguous live tag')
            self.assertIsNone(row['usage'])
            self.assertEqual(snap['aggregate']['unregistered_live'],2)
    def test_rollout_large_tail_recovers_head_meta_and_mismatch_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); store=root/'.local/metrics'; store.mkdir(parents=True); (root/'coordination').mkdir()
            sessions=root/'state/aplexer/sessions'
            def big_rollout(path,meta_id):
                filler=json.dumps({'timestamp':'t','type':'response_item','payload':{'padding':'x'*80}})+'\n'
                body=[json.dumps({'timestamp':'t0','type':'session_meta','payload':{'id':meta_id}})+'\n']
                body.extend(filler for _ in range(26000))
                body.append(json.dumps({'timestamp':'t9','type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':700,'output_tokens':300,'total_tokens':1000}}}})+'\n')
                pathlib.Path(path).write_text(''.join(body))
            big_rollout(root/'big.jsonl','conv-big')
            small=[json.dumps({'timestamp':'t0','type':'session_meta','payload':{'id':'conv-y'}}),json.dumps({'timestamp':'t9','type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':60,'output_tokens':40,'total_tokens':100}}}})]
            (root/'mism.jsonl').write_text('\n'.join(small)+'\n')
            agents=[{'tag':'big','role':'executor','session_id':'sb','telemetry':{'type':'codex-rollout','path':str(root/'big.jsonl')}},{'tag':'mism','role':'executor','session_id':'sm','telemetry':{'type':'codex-rollout','path':str(root/'mism.jsonl'),'conversation_id':'other-id'}}]
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams':[{'id':'a','agents':agents}]}))
            with patch.object(collect,'quotas',return_value={}),patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),patch.object(collect,'APLEXER_STATE',sessions),patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')),patch.object(collect,'proc',return_value={'alive':False}):
                snap=collect.collect()
            rows={r['tag']:r for r in snap['sessions']}
            big=rows['big']['usage']
            self.assertEqual(big['conversation_id'],'conv-big')
            self.assertEqual(big['total_tokens'],1000)
            mism=rows['mism']['usage']
            self.assertEqual(mism['total_tokens'],100)
            self.assertIsNone(mism['conversation_id'])
            self.assertIn('disagree',mism['scope'])
            self.assertEqual(snap['aggregate']['known_conversation_tokens'],1000)
            self.assertEqual(snap['aggregate']['usage_observed_conversations'],1)
if __name__=='__main__': unittest.main()
