import unittest, tempfile, pathlib, types, json
from unittest.mock import patch
import collect
class MetricsTests(unittest.TestCase):
    def setUp(self):
        # Hermetic VictoriaMetrics push: capture series, report success.
        self.pushed_series = []
        def _fake_push(lines, vm_url=collect.VM_URL, timeout=15):
            self.pushed_series.extend(lines)
            return True, ''
        p = patch.object(collect.tsdb, 'push_series', side_effect=_fake_push)
        p.start()
        self.addCleanup(p.stop)
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
            # No new per-minute snapshot files are written; numeric history
            # goes to VictoriaMetrics and details to SQLite on change.
            self.assertEqual(list(store.glob('snapshots-*.jsonl')), [])
            self.assertEqual(list(store.glob('snapshots-*.gz')), [])
            joined = '\n'.join(self.pushed_series)
            self.assertIn('exp_agents_registered{role="head"', joined)
            self.assertIn('exp_tasks{status="blocked"', joined)
            import state as state_store
            stored_tasks = {t['id']: t for t in state_store.read_tasks(store)}
            self.assertEqual(stored_tasks['t1']['status'], 'blocked')
            self.assertEqual(stored_tasks['t1']['next_action'], 'independent replay')
            self.assertEqual(stored_tasks['t1']['evidence_paths'], ['result.txt'])
            stored_evidence = state_store.read_evidence(store)
            self.assertEqual(len(stored_evidence), 1)
            self.assertEqual(stored_evidence[0]['path'], 'result.txt')
            self.assertEqual(stored_evidence[0]['bytes'], 15)
            self.assertTrue(snap['tsdb']['push_ok'])
            latest = json.loads((store/'latest.json').read_text())
            self.assertTrue(latest['tsdb']['push_ok'])
            self.assertNotIn('prompt', latest); self.assertNotIn('transcript', json.dumps(latest['sessions'][0]))
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

class NativeHarnessCoverageTests(unittest.TestCase):
    def fixture(self, role='author'):
        actor='11111111-1111-4111-8111-111111111111'
        claim='22222222-2222-4222-8222-222222222222'
        ack='33333333-3333-4333-8333-333333333333'
        executor={'id':'native-task','native_session_id':'/root/renamed_native_task',
                  'parent_native_session':'parent-session','provider':'codex native harness',
                  'model':'gpt-6.1-sol','worker_bus_actor':actor,'role':role}
        first={'own_actor':actor,'claim_message_id':claim,'scope_ACK':ack,
               'actual_native_session':executor['native_session_id'],
               'actual_provider':'codex native harness','actual_model':'gpt-6.1-sol',
               'actual_first_tool_exit':0,'qualified_utc':'2026-10-14T00:00:00Z',
               ('review_authorized' if role=='reviewer' else 'edit_authorized'):True}
        task={'id':'native-task','worker_native':executor['native_session_id'],
              'worker_bus_actor':actor,'parent_native_session':'parent-session',
              'worker_model':'gpt-6.1-sol',
              'team_id':'agent-quota-launcher','first_action':first,'status':'in_progress'}
        return {'delivery_executors':[executor]},[task]

    def project(self, registry, tasks):
        import datetime
        return collect.native_harness_coverage(
            registry,tasks,datetime.datetime(2026,10,15,tzinfo=datetime.timezone.utc))

    def test_actual_schema_and_renamed_semantic_roles(self):
        for role in ('author','reviewer'):
            with self.subTest(role=role):
                registry,tasks=self.fixture(role)
                result=self.project(registry,tasks);row=result['records'][0]
                self.assertEqual(row['project_id'],'quota-launcher')
                self.assertEqual(row['category'],'subagent')
                self.assertEqual(row['task_role'],role)
                self.assertEqual(row['parent_native_session'],'parent-session')
                self.assertEqual(row['worker_bus_actor'],tasks[0]['worker_bus_actor'])
                self.assertEqual(row['first_action']['status'],'recorded')
                self.assertEqual(row['receipt_state'],'first_action_recorded')
                self.assertEqual(row['current_state'],'UNKNOWN')
                for key in ('pid_live','hook_working','active'):
                    self.assertIsNone(row[key])
                self.assertIsNone(result['current_live'])
                self.assertIsNone(result['accepted_today'])
                self.assertNotIn('session_id',row)
                self.assertNotIn('workload_pid',row)

    def test_receipts_are_historical_not_current_liveness(self):
        registry,tasks=self.fixture()
        tasks[0]['first_action']['qualified_utc']='2020-01-01T00:00:00Z'
        registry['delivery_executors'][0]['status']='working'
        row=self.project(registry,tasks)['records'][0]
        self.assertEqual(row['first_action']['status'],'recorded')
        self.assertIsNone(row['active'])
        self.assertEqual(row['current_state'],'UNKNOWN')

    def test_negative_first_tool_auth_ack_model_and_source(self):
        cases=[('actor',lambda e,t:t['first_action'].update(own_actor='other')),
               ('claim',lambda e,t:t['first_action'].pop('claim_message_id')),
               ('ack',lambda e,t:t['first_action'].update(scope_ACK='not-a-receipt')),
               ('first_tool',lambda e,t:t['first_action'].pop('actual_first_tool_exit')),
               ('bool_exit',lambda e,t:t['first_action'].update(actual_first_tool_exit=False)),
               ('failed_tool',lambda e,t:t['first_action'].update(actual_first_tool_exit=2)),
               ('auth',lambda e,t:t['first_action'].update(edit_authorized=False)),
               ('source',lambda e,t:t['first_action'].update(actual_provider='zai')),
               ('future',lambda e,t:t['first_action'].update(qualified_utc='2030-01-01T00:00:00Z')),
               ('undated',lambda e,t:t['first_action'].update(qualified_utc='2026-10-14T00:00:00')),
               ('path',lambda e,t:t['first_action'].update(actual_native_session='/root/parent')),
               ('parent',lambda e,t:e.update(parent_native_session='another-parent')),
               ('missing_actor',lambda e,t:e.pop('worker_bus_actor')),
               ('project_mismatch',lambda e,t:e.update(project_id='agent-dashboard')),
               ('model',lambda e,t:e.pop('model')),
               ('malformed_model',lambda e,t:e.update(model={'not':'identity'})),
               ('tracker_model_conflict',lambda e,t:t.update(worker_model='gpt-6-sol')),
               ('tracker_model_missing',lambda e,t:t.pop('worker_model')),
               ('first_model_conflict',lambda e,t:t['first_action'].update(actual_model='gpt-6-sol')),
               ('unsupported_source',lambda e,t:e.update(provider='unsupported')),
               ('malformed',lambda e,t:t.update(first_action=['not','receipt']))]
        for name,change in cases:
            with self.subTest(name=name):
                registry,tasks=self.fixture();e=registry['delivery_executors'][0];change(e,tasks[0])
                result=self.project(registry,tasks);row=result['records'][0]
                self.assertEqual(row['first_action']['status'],'invalid')
                self.assertEqual(result['first_action_receipts_recorded'],0)
                self.assertIsNone(row['active'])
                if name in ('model','malformed_model','tracker_model_conflict','tracker_model_missing','first_model_conflict'):
                    self.assertEqual(row['model'],'UNKNOWN')
                    self.assertIn('missing or mismatched native model references',row['unknowns'])

    def test_missing_input_project_task_and_malformed_taskpath(self):
        self.assertEqual(self.project({},[])['input_status'],'missing or malformed delivery_executors')
        self.assertEqual(self.project({'delivery_executors':None},[])['records'],[])
        for project in (None,'unsupported',{'malformed':True}):
            registry,tasks=self.fixture();tasks[0]['team_id']=project
            row=self.project(registry,tasks)['records'][0]
            self.assertIsNone(row['project_id'])
            self.assertIn('missing or unsupported project',row['unknowns'])
            self.assertEqual(row['first_action']['status'],'invalid')
        registry,tasks=self.fixture()
        self.assertIn('missing or ambiguous tracker task',self.project(registry,[])['records'][0]['unknowns'])
        registry['delivery_executors'][0]['native_session_id']=['bad']
        result=self.project(registry,tasks)
        self.assertIn('missing or unsupported native taskpath',result['records'][0]['unknowns'])
        self.assertEqual(result['registered_taskpaths'],0)
        tasks[0]['first_action']=None
        self.assertEqual(self.project(registry,tasks)['records'][0]['first_action']['status'],'missing')

    def test_terminal_release_and_done_date_never_acceptance(self):
        for status,release in [('in_progress','44444444-4444-4444-8444-444444444444'),
                               ('changes_requested',None),('done',None)]:
            with self.subTest(status=status):
                registry,tasks=self.fixture();tasks[0].update(status=status,ownrelease=release,
                    updated_at='2026-10-15T00:00:00Z',acceptance_status='accepted')
                result=self.project(registry,tasks);row=result['records'][0]
                self.assertFalse(row['active'])
                self.assertEqual(result['terminal_or_released'],1)
                self.assertEqual(row['current_state'],'UNKNOWN')
                self.assertIsNone(result['accepted_today'])
                self.assertEqual(row['release_message_id'],release)
        registry,tasks=self.fixture();tasks[0]['ownrelease']='bad'
        row=self.project(registry,tasks)['records'][0]
        self.assertIsNone(row['active'])
        self.assertIn('malformed release reference',row['unknowns'])

    def test_duplicate_taskpaths_cannot_multiply_receipt_coverage(self):
        import copy
        registry,tasks=self.fixture()
        registry['delivery_executors'].append(copy.deepcopy(registry['delivery_executors'][0]))
        result=self.project(registry,tasks)
        self.assertEqual(result['registered_taskpaths'],1)
        self.assertEqual(result['first_action_receipts_recorded'],0)
        self.assertIn('duplicate taskpath',result['records'][0]['unknowns'])
        registry,tasks=self.fixture();tasks.append(copy.deepcopy(tasks[0]))
        self.assertEqual(self.project(registry,tasks)['first_action_receipts_recorded'],0)

    def mocked_snapshot(self, registry, tasks, catalog):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);store=root/'.local/metrics';store.mkdir(parents=True)
            (root/'coordination').mkdir()
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))
            (root/'coordination/TASKS.json').write_text(json.dumps({'tasks':tasks}))
            catalog=[dict(row,workspace=str(root)) for row in catalog]
            disk=types.SimpleNamespace(f_bavail=100,f_frsize=4096,f_blocks=200)
            with patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),\
                 patch.object(collect,'PRODUCT_WORKSPACES',[]),\
                 patch.object(collect,'APLEXER_STATE',root/'absent-sessions'),\
                 patch.object(collect,'quotas',return_value={}),\
                 patch.object(collect,'read_opencode_usage',return_value={'sessions':[],'stores':[]}),\
                 patch.object(collect,'native_usage',return_value=None),\
                 patch.object(collect,'proc',side_effect=lambda p:{'alive':p in (123,124)}),\
                 patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(catalog))),\
                 patch.object(collect.subprocess,'check_output',side_effect=AssertionError('unexpected process probe')),\
                 patch.object(collect.os,'getloadavg',return_value=(0,0,0)),\
                 patch.object(collect.os,'statvfs',return_value=disk),\
                 patch.object(collect,'record_state_sample',return_value={}),\
                 patch.object(collect.tsdb,'push_series',return_value=(True,'')):
                return collect.collect()

    def ordinary_registry_and_catalog(self):
        ordinary={'id':'ordinary-task','project_id':'quota-launcher','tag':'worker',
                  'role':'executor','session_id':'worker-sid','provider':'opencode'}
        registry={'projects':[{'id':'quota-launcher'}],
                  'teams':[{'id':'quota-launcher','agents':[
                      {'tag':'head','role':'head','session_id':'head-sid'}]}],
                  'delivery_executors':[ordinary]}
        catalog=[{'id':'head-sid','tag':'head','workload_pid':123,'reported_state':'working'},
                 {'id':'worker-sid','tag':'worker','workload_pid':124,'reported_state':'working'}]
        return registry,catalog

    def test_ordinary_executor_parent_metadata_preserves_full_collector_counts(self):
        for metadata in ({},{'parent_native_session':'/root/parent'},
                         {'parent_native_session':'parent-session'},
                         {'parent_native_session':'/root/parent',
                          'native_session_id':'55555555-5555-4555-8555-555555555555'}):
            with self.subTest(metadata=metadata):
                registry,catalog=self.ordinary_registry_and_catalog()
                registry['delivery_executors'][0].update(metadata)
                snap=self.mocked_snapshot(registry,[],catalog)
                for counter in ('registered_agents','agents_pid_live','agents_hook_working'):
                    self.assertEqual(snap['aggregate'][counter],2)
                self.assertEqual(snap['aggregate']['roles']['executor']['registered'],1)
                self.assertEqual(snap['native_harness_coverage']['registered_records'],0)
                self.assertEqual({r['tag'] for r in snap['sessions']},{'head','worker'})

    def test_malformed_executor_inputs_keep_full_snapshot_and_ordinary_counts(self):
        for malformed in (None,'not-a-list',{'tag':'worker'},[None,'bad',42,[]],
                          [{'project_id':['quota-launcher'],'tag':'broken'}],
                          [{'project_id':'quota-launcher','tag':['broken']}],
                          [{'workspace':['malformed-path']}],
                          [{'project_id':'quota-launcher','session_id':{'bad':'id'}}]):
            with self.subTest(malformed=malformed):
                registry,catalog=self.ordinary_registry_and_catalog()
                registry['teams'][0]['agents'].append(registry['delivery_executors'][0])
                registry['delivery_executors']=malformed
                snap=self.mocked_snapshot(registry,[],catalog)
                coverage=snap['native_harness_coverage']
                self.assertEqual(snap['aggregate']['registered_agents'],2)
                self.assertEqual(snap['aggregate']['agents_pid_live'],2)
                self.assertEqual(snap['aggregate']['agents_hook_working'],2)
                self.assertNotEqual(coverage['input_status'],'observed')
                self.assertEqual(coverage['records'],[])
                self.assertIsNone(coverage['current_live'])
                self.assertIsNone(coverage['accepted_today'])
                if isinstance(malformed,list):self.assertEqual(coverage['malformed_entries'],len(malformed))

    def test_mixed_native_ordinary_and_malformed_records_keep_supported_sources(self):
        registry,tasks=self.fixture()
        ordinary,catalog=self.ordinary_registry_and_catalog()
        registry.update(teams=ordinary['teams'],projects=ordinary['projects'])
        registry['delivery_executors'] += ordinary['delivery_executors']+[None,'bad',42]
        registry['delivery_executors'][1]['parent_native_session']='/root/parent'
        tasks[0]['worker_model']='gpt-6-sol'
        snap=self.mocked_snapshot(registry,tasks,catalog)
        self.assertEqual(snap['aggregate']['registered_agents'],2)
        self.assertEqual(snap['aggregate']['agents_pid_live'],2)
        coverage=snap['native_harness_coverage'];row=coverage['records'][0]
        self.assertEqual(coverage['registered_records'],1)
        self.assertEqual(coverage['malformed_entries'],3)
        self.assertEqual(row['model'],'UNKNOWN')
        self.assertEqual(row['model_references']['registry'],'gpt-6.1-sol')
        self.assertEqual(row['model_references']['tracker'],'gpt-6-sol')
        self.assertEqual(row['first_action']['status'],'invalid')
        self.assertEqual(coverage['first_action_receipts_recorded'],0)

    def test_native_children_never_borrow_parent_pid_or_change_aggregates(self):
        registry,tasks=self.fixture()
        registry['delivery_executors'][0].update(project_id='quota-launcher',tag='head',
            session_id='parent-session',workload_pid=123,reported_state='working')
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);store=root/'.local/metrics';store.mkdir(parents=True)
            (root/'coordination').mkdir()
            registry['projects']=[{'id':'quota-launcher'}]
            registry['teams']=[{'id':'quota-launcher','agents':[
                {'tag':'head','role':'head','session_id':'parent-session'}]}]
            (root/'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))
            (root/'coordination/TASKS.json').write_text(json.dumps({'tasks':tasks}))
            catalog=[{'id':'parent-session','tag':'head','workspace':str(root),
                      'workload_pid':123,'reported_state':'working'}]
            empty_usage={'sessions':[],'stores':[]}
            with patch.object(collect,'ROOT',root),patch.object(collect,'STORE',store),\
                 patch.object(collect,'APLEXER_STATE',root/'absent-sessions'),\
                 patch.object(collect,'quotas',return_value={}),\
                 patch.object(collect,'read_opencode_usage',return_value=empty_usage),\
                 patch.object(collect,'native_usage',return_value=None),\
                 patch.object(collect,'proc',side_effect=lambda p:{'alive':p==123}),\
                 patch.object(collect.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(catalog))),\
                 patch.object(collect.tsdb,'push_series',return_value=(True,'')):
                snap=collect.collect()
            self.assertEqual(snap['aggregate']['registered_agents'],1)
            self.assertEqual(snap['aggregate']['agents_pid_live'],1)
            self.assertEqual(snap['aggregate']['agents_hook_working'],1)
            self.assertEqual(snap['aggregate']['roles']['subagent']['registered'],0)
            self.assertEqual(len(snap['sessions']),1)
            child=snap['native_harness_coverage']['records'][0]
            self.assertIsNone(child['pid_live'])
            self.assertIsNone(child['hook_working'])
            self.assertEqual(child['taskpath'],'/root/renamed_native_task')
            self.assertIsNone(snap['aggregate']['known_conversation_tokens'])

if __name__=='__main__': unittest.main()
