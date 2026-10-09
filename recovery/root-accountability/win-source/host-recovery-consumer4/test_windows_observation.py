import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,hashlib,json,importlib.util,unittest,time,uuid,os
HERE=pathlib.Path(__file__).resolve().parent;CORE=HERE.parent/'next12'
if hashlib.sha256((CORE/'core-pins.json').read_bytes()).hexdigest()!='2f4d93e4bd31218474a1d270c5627d7fa00647e3eac3d59bb3fd4ebec7ec4f58':raise RuntimeError('core pin')
for entry in json.loads((CORE/'core-pins.json').read_text(encoding='utf-8-sig'))['entries']:
    if hashlib.sha256((CORE/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:raise RuntimeError('core dependency pin')
sys.path.insert(0,str(CORE))
from win35_root_job import WindowsJob,current_process_binding,recorded_process_state,BasicAccounting
spec=importlib.util.spec_from_file_location('observation',HERE/'windows_observation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ActualOwnedJob(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','native Windows Job APIs required')
    def test_retained_query_handle_survives_owned_backend_death(self):
        job=WindowsJob('Local\\Win35Root-'+uuid.uuid4().hex);self.addCleanup(job.close)
        backend=job.start([sys.executable,'-I','-S','-c','import time;time.sleep(30)'],str(HERE))
        self.addCleanup(lambda:backend.kill() if backend.poll() is None else None)
        binding=dict(pid=backend.pid,creation_filetime=backend.creation_filetime)
        observer=m.JobObservation(job.api,BasicAccounting,job.name,binding,current_process_binding(),recorded_process_state)
        self.addCleanup(observer.close)
        self.assertTrue(observer.outside());self.assertGreaterEqual(observer.query()['active_processes'],1)
        backend.kill();backend.wait();self.assertEqual(observer.query()['active_processes'],0)
        self.assertTrue(observer.outside())
    def test_backend_guardian_overlap_rejected_before_open(self):
        with self.assertRaisesRegex(RuntimeError,'overlaps'):
            m.JobObservation(None,None,'Local\\Win35Root-'+'a'*32,dict(pid=1),dict(pid=1),None)
    def test_unknown_job_name_rejected_before_open(self):
        with self.assertRaisesRegex(RuntimeError,'Job name'):
            m.JobObservation(None,None,'foreign-job',dict(pid=1),dict(pid=2),None)

if __name__=='__main__':unittest.main()
