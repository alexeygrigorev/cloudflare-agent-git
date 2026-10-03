import unittest,tempfile,pathlib,json,gzip
import adapters
class AdapterTests(unittest.TestCase):
 def test_cumulative_baseline_and_task_transition(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=pathlib.Path(tmp)
   rows=[{'id':'a','tag':'worker','team_id':'t','pid_live':True,'reported_state':'idle','stale_hook':False,'cpu_seconds':1,'proc_start_ticks':1,'usage':{'source':'native','conversation_id':'c','total_tokens':100}},{'id':'b','tag':'resume','team_id':'t','pid_live':True,'reported_state':'idle','stale_hook':False,'cpu_seconds':1,'proc_start_ticks':2,'usage':{'source':'native','conversation_id':'c','total_tokens':90}}]
   first=adapters.temporal(store,rows,[{'id':'x','status':'ready'}],'2026-10-03T00:00:00Z');self.assertEqual(first['tokens_since_observer_known'],0)
   rows[0]['usage']['total_tokens']=150
   second=adapters.temporal(store,rows,[{'id':'x','status':'running'}],'2026-10-03T00:01:00Z');self.assertEqual(second['tokens_since_observer_known'],50);self.assertEqual(second['task_transitions_this_sample'][0]['from_status'],'ready')
 def test_compressed_archive_preserves_all_bytes(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=pathlib.Path(tmp);old=store/'snapshots-2026-10-02.jsonl';payload=(b'{"known":true}\n')*1000;old.write_bytes(payload)
   result=adapters.archive_history(store,store/'snapshots-2026-10-03.jsonl');self.assertFalse(old.exists());gz=next(store.glob('*.gz'))
   with gzip.open(gz,'rb') as f:self.assertEqual(f.read(),payload)
   self.assertGreater(result['total_bytes'],0)
 def test_counter_decrease_does_not_invent_negative_or_new_tokens(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=pathlib.Path(tmp);r={'id':'x','tag':'worker','team_id':'a','pid_live':True,'reported_state':'working','stale_hook':False,'usage':{'source':'native','conversation_id':'same','total_tokens':500}}
   adapters.temporal(store,[r],[],'2026-10-03T00:00:00Z');r['usage']['total_tokens']=100
   result=adapters.temporal(store,[r],[],'2026-10-03T00:01:00Z');self.assertEqual(result['tokens_since_observer_known'],0);self.assertEqual(result['conversations'][0]['latest_cumulative_tokens'],500)
 def test_export_reads_compressed_and_live_history(self):
  import importlib.util
  from unittest.mock import patch
  path=pathlib.Path(__file__).with_name('export.py');spec=importlib.util.spec_from_file_location('metrics_export',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   store=pathlib.Path(tmp)
   rows=[{'at':'2026-10-03T00:00:00Z','sessions':[{'id':'s','tag':'w','usage':{'source':'native','conversation_id':'c','total_tokens':100}}]},{'at':'2026-10-03T00:01:00Z','sessions':[{'id':'s','tag':'w','usage':{'source':'native','conversation_id':'c','total_tokens':180}}]}]
   with gzip.open(store/'snapshots-2026-10-03.jsonl.1.gz','wt') as f:f.write(json.dumps(rows[0])+'\n')
   (store/'snapshots-2026-10-03.jsonl').write_text(json.dumps(rows[1])+'\n')
   with patch.object(module,'STORE',store):result=module.summarize()
   self.assertEqual(result['snapshots'],2);self.assertEqual(result['conversations'][0]['tokens_delta_during_observation'],80)
 def test_failed_archive_digest_preserves_original(self):
  import io
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   store=pathlib.Path(tmp);source=store/'snapshots-2026-10-02.jsonl';source.write_bytes(b'X'*100);real=adapters.gzip.open
   def corrupt(path,mode,**kwargs):return io.BytesIO(b'Y'*100) if mode=='rb' else real(path,mode,**kwargs)
   with patch.object(adapters.gzip,'open',side_effect=corrupt):
    with self.assertRaisesRegex(OSError,'SHA256'):adapters.archive_history(store,store/'snapshots-2026-10-03.jsonl')
   self.assertEqual(source.read_bytes(),b'X'*100);self.assertEqual(len(list(store.glob('*.gz'))),0);self.assertTrue(list(store.glob('.archive-*.pending')))
 def test_export_distinct_evidence_and_missing_unknown(self):
  import importlib.util
  from unittest.mock import patch
  path=pathlib.Path(__file__).with_name('export.py');spec=importlib.util.spec_from_file_location('metrics_export_evidence',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);store=root/'.local/metrics';store.mkdir(parents=True);(root/'result.txt').write_text('actual output');(root/'directory').mkdir()
   snap={'at':'2026-10-03T00:00:00Z','sessions':[{'id':'a','tag':'worker'},{'id':'b','tag':'missing-only'}]};(store/'snapshots-2026-10-03.jsonl').write_text(json.dumps(snap)+'\n')
   latest={'tasks':[{'id':'t1','owner_tag':'worker','evidence_paths':['result.txt','result.txt','missing.txt','directory']},{'id':'t2','owner_tag':'missing-only','evidence_paths':['absent.txt']} ]};(store/'latest.json').write_text(json.dumps(latest))
   with patch.object(module,'STORE',store),patch.object(module,'ROOT',root):result=module.summarize()
   worker=result['per_tag']['worker'];self.assertEqual(worker['evidence_files_latest'],1);self.assertEqual(worker['evidence_coverage']['status'],'partial');self.assertEqual(worker['evidence_coverage']['unsupported_directory_paths'],['directory']);self.assertEqual(worker['evidence_coverage']['missing_paths'],['missing.txt']);self.assertIsNone(result['per_tag']['missing-only']['evidence_files_latest'])
if __name__=='__main__':unittest.main()
