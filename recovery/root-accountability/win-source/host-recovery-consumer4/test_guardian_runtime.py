import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import importlib.util,pathlib,unittest,tempfile,json
from unittest.mock import Mock,patch
spec=importlib.util.spec_from_file_location('guardian',pathlib.Path(__file__).with_name('guardian_runtime.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RuntimeBoundaries(unittest.TestCase):
    def test_windows_script_path_is_normalized_on_both_sides(self):
        script=pathlib.PureWindowsPath('C:/Users/User/owned/guardian_runtime.py')
        command='python.exe -I -S "C:\\Users\\User\\owned\\guardian_runtime.py" Guard'
        self.assertNotIn(str(script),command.replace('\\','/'))
        self.assertTrue(m.owned_script_command(command,script))
        self.assertTrue(m.owned_script_command(command.upper(),script))
        self.assertFalse(m.owned_script_command(command,pathlib.PureWindowsPath('C:/foreign/guardian_runtime.py')))

    def test_archive_retains_live_acquired_job_for_next_death(self):
        h=m.WindowsHooks.__new__(m.WindowsHooks);h.writer=Mock();h.write_recovery=Mock()
        h.observer=Mock();h.monitor=object();h.baseline=object()
        observer,monitor,baseline=h.observer,h.monitor,h.baseline
        h.archive_completed({'permit':{'challenge':'actual-nonce'},'phase':'completed'})
        observer.close.assert_not_called()
        self.assertIs(h.observer,observer);self.assertIs(h.monitor,monitor);self.assertIs(h.baseline,baseline)
        self.assertEqual(h.write_recovery.call_args.args[0]['phase'],'archived-completed')
    def test_checkpoint_reads_one_current_snapshot(self):
        h=m.WindowsHooks.__new__(m.WindowsHooks);h.state=Mock(return_value=({}, {'actual':'state'},{'owner':'actual-owner'}))
        with patch.object(m,'live_checkpoint',return_value='proof') as classify:
            self.assertEqual(h.current_checkpoint(),'proof')
            h.state.assert_called_once();classify.assert_called_once_with({}, {'actual':'state'},'actual-owner')
    def test_unknown_history_is_not_clear(self):
        owner={'epoch':3};s=dict(thread_owner=owner,fence_owner=owner,conversation_id='cid',provider_pending_tools={},provider_turn_state='completed')
        with self.assertRaises(RuntimeError):m.live_checkpoint({},s,owner)
        s.update(api_history_receipt_sha256='a'*64,api_history_validated=True)
        self.assertEqual(m.live_checkpoint({},s,owner)['protected_state'],'clear')
        for changes in ({'provider_turn_state':'busy'},{'provider_pending_tools':{'tool':'pending'}},{'api_history_validated':False}):
            self.assertEqual(m.live_checkpoint({},dict(s,**changes),owner)['protected_state'],'unknown')
    def test_present_empty_factory_journal_is_not_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'factory.json';p.write_text('{}')
            store=m.PrivateFactoryStore(p,lambda x:json.loads(x.read_text()),Mock())
            self.assertEqual(store.read(),{})
    def test_foreign_nonce_owner_does_not_get_credential_merge(self):
        h=m.WindowsHooks.__new__(m.WindowsHooks);h.current_profile=Mock(return_value={'project':'win35-root'})
        h.writer=Mock()
        with self.assertRaises(RuntimeError):h.prepare_credential_merge({'status':'enrolled_held_api_candidate','actor':'old'}, {'actor':'new','generation':'gen','root_tag':'tag'})
        h.writer.save.assert_not_called()
    def test_observe_route_reports_current_merged_profile_hash_for_next_death(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);state_dir=root/'state';state_dir.mkdir()
            for name in ('root-runtime.json','control-journal.private.json'):(state_dir/name).touch()
            p={'actor':'first','generation':'first-gen','state_dir':str(state_dir),'root_tag':'owned','aplexer_exe':'fixed-exe','expected_host':'actual-host'}
            owner={'actor':'first','epoch':3}
            s={'thread_owner':owner,'fence_owner':owner,'pid':500,'process_creation_filetime':5000,'job_name':'owned-job','conversation_id':'actual-cid','api_history_receipt_sha256':'a'*64,'provider_pending_tools':{},'provider_turn_state':'completed','api_history_validated':True}
            h=m.WindowsHooks.__new__(m.WindowsHooks);h.current_profile=lambda:p;h.state=lambda:(p,s,{'owner':owner})
            h.process_state=Mock(return_value='alive');h.observer=None;h.observer_key=None;h.monitor=None;h.baseline=None
            observer=Mock();h.modules={'windows_observation':Mock(),'death_monitor':Mock(),'fixed_factory':Mock()}
            h.modules['windows_observation'].JobObservation.return_value=observer
            h.modules['fixed_factory'].rows.side_effect=lambda value:value
            h.api=Mock();h.accounting=Mock();h.binding=Mock();h.credential={'credential':{'private':'fixture-only'}}
            h.guardian={k:1 for k in ('pid','creation_filetime','session_id','user_sid','task_action_sha256','source_sha256')}
            h.load=lambda path:{'native':{'id':p['actor']},'kernel':{'pid':400,'creation_filetime':4000}}
            h.read_factory=Mock(return_value=None)
            current_hash=['5'*64]
            def catalog(*args,**kwargs):return json.dumps([{'id':p['actor'],'tag':'owned','worker_alive':True,'worker_pid':200,'workload_pid':300}])
            with patch.object(m,'BASE',root),patch.object(m,'sha',side_effect=lambda path:current_hash[0]),patch.object(m,'native_context',side_effect=lambda pid:{'pid':pid,'creation_filetime':pid*10}),patch.object(m.subprocess,'check_output',side_effect=catalog),patch.object(m,'host_request') as requests:
                h.observe_live()
                self.assertEqual(requests.call_args.args[2]['baseline']['profile_sha256'],'5'*64)
                p.update(actor='genuine-successor',generation='new-gen');owner.update(actor='genuine-successor',epoch=4);s.update(pid=510,process_creation_filetime=5100)
                current_hash[0]='9'*64
                h.observe_live()
                self.assertEqual(requests.call_args.args[2]['baseline']['profile_sha256'],'9'*64)
                observer.close.assert_called_once()
if __name__=='__main__':unittest.main()
