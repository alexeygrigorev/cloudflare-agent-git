import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,importlib.util,copy,unittest
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('consumer',pathlib.Path(__file__).with_name('death_monitor.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DeathObservation(unittest.TestCase):
    def setUp(self):
        k=lambda pid:dict(pid=pid,creation_filetime=pid*100)
        self.owner=dict(project='fixture',role='root',actor='actual',generation='generation',epoch=3)
        self.guardian=dict(k(10),session_id=2,user_sid='fixture-sid',source_sha256='source',task_action_sha256='action')
        self.check=dict(thread_id='owned-CID',history_receipt_sha256='a'*64,provider_turn_state='completed',pending_tool_count=0,protected_state='clear')
        self.base=dict(owner=self.owner,host='host',guardian=self.guardian,native=dict(id='actual',worker=k(20),workload=k(21),host_process=k(22)),model=dict(backend=k(23),job=dict(name='owned-Job',session_id=2)),checkpoint=self.check)
        self.job=Mock(return_value=dict(active_processes=0,source='QueryInformationJobObject'))
        self.ps=Mock(side_effect=lambda pid,stamp:'alive' if pid==10 else 'exited')
        self.current=Mock(return_value=self.guardian);self.outside=Mock(return_value=True)
        self.checkpoint=Mock(return_value=self.check);self.attempt=Mock(return_value=None)
        self.monitor=m.DeathMonitor(self.base,self.job,self.ps,self.current,self.outside,self.checkpoint,self.attempt)
        self.challenge=dict(owner=self.owner,nonce='server-nonce')
    def test_actual_api_queries_and_explicit_null_attempt(self):
        receipt=self.monitor.observe(self.challenge)
        self.assertIsNone(receipt['factory_attempt']);self.assertTrue(receipt['model']['job']['queried'])
        self.job.assert_called_once();self.attempt.assert_called_once();self.assertEqual(self.ps.call_count,5)
    def test_unknown_or_alive_native_backend_held(self):
        for blocked in (20,21,22,23):
            for result in ('alive','unknown'):
                with self.subTest(pid=blocked,result=result):
                    self.ps.side_effect=lambda pid,stamp:'alive' if pid==10 else result if pid==blocked else 'exited'
                    with self.assertRaises(m.Held):self.monitor.observe(self.challenge)
    def test_missing_job_never_becomes_zero(self):
        self.job.side_effect=FileNotFoundError('Job object absent')
        with self.assertRaises(FileNotFoundError):self.monitor.observe(self.challenge)
    def test_nonzero_or_boolean_zero_job_held(self):
        for active in (1,False,None):
            self.job.return_value=dict(active_processes=active,source='QueryInformationJobObject')
            with self.assertRaises(m.Held):self.monitor.observe(self.challenge)
    def test_provider_busy_pending_unknown_history_held(self):
        for changes in ({'provider_turn_state':'busy'},{'pending_tool_count':1},{'pending_tool_count':False},{'protected_state':'unknown'},{'history_receipt_sha256':'b'*64}):
            self.checkpoint.return_value=dict(self.check,**changes)
            with self.assertRaises(m.Held):self.monitor.observe(self.challenge)
    def test_foreign_challenge_has_no_kernel_query(self):
        with self.assertRaises(m.Held):self.monitor.observe(dict(self.challenge,owner=dict(self.owner,epoch=4)))
        self.job.assert_not_called();self.ps.assert_not_called()
    def test_guardian_incarnation_or_inside_job_held(self):
        self.current.return_value=dict(self.guardian,creation_filetime=999)
        with self.assertRaises(m.Held):self.monitor.observe(self.challenge)
        self.current.return_value=self.guardian;self.outside.return_value=False
        with self.assertRaises(m.Held):self.monitor.observe(self.challenge)
    def test_prior_factory_intent_never_replayed(self):
        self.attempt.return_value={'phase':'pending'}
        with self.assertRaises(m.Held):self.monitor.observe(self.challenge)

if __name__=='__main__':unittest.main()
