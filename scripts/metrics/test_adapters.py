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
 def test_rolling_retention_relocates_old_chunks_below_threshold(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=pathlib.Path(tmp)
   dayfile=store/'snapshots-2026-10-06.jsonl'
   dayfile.write_bytes(b'{"active":true}\n'*10)
   old1=store/'snapshots-2026-10-04.jsonl.1.gz';old1.write_bytes(b'A'*400)
   old2=store/'snapshots-2026-10-05.jsonl.1.gz';old2.write_bytes(b'B'*400)
   today_gz=store/'snapshots-2026-10-06.jsonl.1.gz';today_gz.write_bytes(b'C'*100)
   adapters.archive_history(store,dayfile,max_active_bytes=1000,floor_active_bytes=500)
   archive_dir=store/'archive'
   self.assertTrue((archive_dir/'snapshots-2026-10-04.jsonl.1.gz').exists())
   self.assertFalse(old1.exists())
   self.assertTrue((archive_dir/'snapshots-2026-10-05.jsonl.1.gz').exists())
   self.assertFalse(old2.exists())
   manifest_path=archive_dir/'manifest.json'
   self.assertTrue(manifest_path.exists())
   manifest=json.loads(manifest_path.read_text())
   files_in_manifest={r['file'] for r in manifest['archives']}
   self.assertIn('snapshots-2026-10-04.jsonl.1.gz',files_in_manifest)
   self.assertIn('snapshots-2026-10-05.jsonl.1.gz',files_in_manifest)
   self.assertEqual(manifest['total_bytes'],800)
   self.assertEqual(manifest['file_count'],2)
   for entry in manifest['archives']:
    self.assertIn('sha256',entry)
    self.assertIn('bytes',entry)
    self.assertIn('mtime_ns',entry)
    self.assertIn('relocated_at',entry)
   self.assertEqual(archive_dir.stat().st_mode&0o777,0o700)
   self.assertEqual(manifest_path.stat().st_mode&0o777,0o600)
   self.assertEqual((archive_dir/'snapshots-2026-10-04.jsonl.1.gz').stat().st_mode&0o777,0o600)
   self.assertEqual((archive_dir/'snapshots-2026-10-05.jsonl.1.gz').stat().st_mode&0o777,0o600)
   self.assertTrue(dayfile.exists())
   self.assertTrue(today_gz.exists())
   self.assertFalse((archive_dir/dayfile.name).exists())
   ret_manifest=json.loads((store/'retention-manifest.json').read_text())
   active_files=[p for p in store.glob('snapshots-*') if p.is_file()]
   self.assertEqual(ret_manifest['total_bytes'],sum(p.stat().st_size for p in active_files))
   self.assertEqual(ret_manifest['total_bytes'],dayfile.stat().st_size+today_gz.stat().st_size)
   active_names={r['file'] for r in ret_manifest['archives']}
   self.assertIn(dayfile.name,active_names)
   self.assertIn(today_gz.name,active_names)
   self.assertNotIn('snapshots-2026-10-04.jsonl.1.gz',active_names)
   self.assertNotIn('snapshots-2026-10-05.jsonl.1.gz',active_names)
 def test_adapters_cli_main_dry_run_and_execution(self):
  import io, contextlib, datetime as dt
  with tempfile.TemporaryDirectory() as tmp:
   store = pathlib.Path(tmp)
   today_str = dt.date.today().isoformat()
   dayfile = store / f'snapshots-{today_str}.jsonl'
   dayfile.write_bytes(b'{"active":true}\n' * 10)
   old1 = store / 'snapshots-2026-10-04.jsonl.1.gz'
   old1.write_bytes(b'A' * 400)
   old2 = store / 'snapshots-2026-10-05.jsonl.1.gz'
   old2.write_bytes(b'B' * 400)
   today_gz = store / f'snapshots-{today_str}.jsonl.1.gz'
   today_gz.write_bytes(b'C' * 200)

   buf = io.StringIO()
   with contextlib.redirect_stdout(buf):
    code = adapters.cli_main(['--store', str(store), '--dry-run', '--json'])
   self.assertEqual(code, 0)
   dry_out = json.loads(buf.getvalue())

   self.assertEqual(dry_out.get('status'), 'ok')
   self.assertTrue(dry_out.get('dry_run'))
   self.assertIsInstance(dry_out.get('active_bytes'), int)
   self.assertIsInstance(dry_out.get('active_files'), int)
   self.assertIsInstance(dry_out.get('candidate_files'), list)
   self.assertIsInstance(dry_out.get('candidate_bytes'), int)
   self.assertIsInstance(dry_out.get('manifest_path'), str)

   self.assertIn('snapshots-2026-10-04.jsonl.1.gz', dry_out['candidate_files'])
   self.assertIn('snapshots-2026-10-05.jsonl.1.gz', dry_out['candidate_files'])
   self.assertNotIn(today_gz.name, dry_out['candidate_files'])
   self.assertEqual(dry_out['candidate_bytes'], 800)
   self.assertEqual(dry_out['active_files'], 4)
   self.assertTrue(old1.exists())
   self.assertTrue(old2.exists())
   self.assertTrue(today_gz.exists())
   self.assertTrue(dayfile.exists())
   self.assertFalse((store / 'archive').exists())
   self.assertFalse((store / 'retention-manifest.json').exists())

   buf = io.StringIO()
   with contextlib.redirect_stdout(buf):
    self.assertEqual(adapters.cli_main(['--store', str(store), '--dry-run']), 0)
   self.assertIn('Dry run:', buf.getvalue())

   buf = io.StringIO()
   with contextlib.redirect_stdout(buf):
    code = adapters.cli_main(['--store', str(store), '--force', '--json'])
   self.assertEqual(code, 0)
   force_out = json.loads(buf.getvalue())

   self.assertEqual(force_out.get('status'), 'ok')
   self.assertIsInstance(force_out.get('active_bytes'), int)
   self.assertIsInstance(force_out.get('active_files'), int)
   self.assertIsInstance(force_out.get('manifest_path'), str)
   self.assertEqual(force_out['manifest_path'], str(store / 'retention-manifest.json'))

   self.assertFalse(old1.exists())
   self.assertFalse(old2.exists())
   archive_dir = store / 'archive'
   self.assertTrue(archive_dir.is_dir())
   self.assertTrue((archive_dir / old1.name).exists())
   self.assertTrue((archive_dir / old2.name).exists())
   self.assertTrue((archive_dir / 'manifest.json').exists())
   self.assertTrue(dayfile.exists())
   self.assertTrue(today_gz.exists())
   self.assertEqual(force_out['active_files'], 2)
   self.assertEqual(force_out['active_bytes'], dayfile.stat().st_size + today_gz.stat().st_size)
   self.assertLess(force_out['active_bytes'], dry_out['active_bytes'])
   self.assertTrue((store / 'retention-manifest.json').exists())

   buf = io.StringIO()
   with contextlib.redirect_stdout(buf):
    self.assertEqual(adapters.cli_main(['--store', str(store)]), 0)
   self.assertIn('Active store:', buf.getvalue())
if __name__=='__main__':unittest.main()

