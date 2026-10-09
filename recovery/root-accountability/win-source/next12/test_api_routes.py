"""Mock-only route negatives; no provider, native actor, process or role is launched."""
import contextlib,copy,json,pathlib,tempfile,unittest
from unittest.mock import MagicMock,patch
import win35_root_host as host
import win35_root_control as control
from api_root_custody import observe,validate_latest_history,dispatch_clear

class ApiRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=pathlib.Path(self.tmp.name)
        self.owner=dict(project='fixture',role='root',actor='fixture-native',generation='win32:10:20',epoch=3)
        self.profile=dict(runtime_mode='api-root',owner=self.owner,actor=self.owner['actor'],generation=self.owner['generation'],state_dir=self.tmp.name,workspace=self.tmp.name)
        self.state=dict(runtime_mode='api-root',highest_epoch=3,fence_owner=self.owner,thread_owner=self.owner,pid=30,process_creation_filetime=40,
            guardian_binding=dict(pid=10,creation_filetime=20),conversation_id='fixture-cid',native_session_id='fixture-session',initial_turn_submitted=True,
            initial_turn_receipt={'turn':{'id':'fixture-turn'}},native_policy={'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'},
            provider_turn_id='fixture-turn',provider_turn_state='busy',provider_pending_tools={},api_history_validated=True,model_launch_complete=True,launched_epoch=3)
        self.runtime=host.RootRuntime(self.profile,{'id':'fixture-native'},smoke_only=False)
        self.runtime.process=MagicMock(pid=30,creation_filetime=40);self.runtime.process.poll.return_value=None
        self.runtime.job=MagicMock();self.runtime.rpc=MagicMock();self.runtime.final_guard=MagicMock();self.runtime.check_deadline=MagicMock()
        self.thread=dict(id='fixture-cid',sessionId='fixture-session',modelProvider='openai',cwd=self.tmp.name,historyMode='legacy',turns=[{'id':'fixture-turn','status':'completed'}])
        self.runtime.rpc.call.return_value={'thread':self.thread}
    def write(self):
        (self.directory/'root-runtime.json').write_text(json.dumps(self.state))
        (self.directory/'control-journal.private.json').write_text(json.dumps({'owner':self.owner,'active':True,'pending':{'fixture':'uncertain'}}))
    def test_busy_pending_and_unknown_history_deny_all_native_effect_routes(self):
        for state_kind in ('busy','tool-pending','history-unknown'):
            for operation in ('root-check','root-standup-ping','root-writeup-ping','root-stop','root-test-kill'):
                with self.subTest(state=state_kind,operation=operation):
                    self.state['provider_turn_state']='busy' if state_kind=='busy' else 'completed'
                    self.state['provider_pending_tools']={'tool':True} if state_kind=='tool-pending' else {}
                    self.thread['turns']=[{'id':'wrong-turn','status':'completed'}] if state_kind=='history-unknown' else [{'id':'fixture-turn','status':'inProgress' if state_kind=='busy' else 'completed'}]
                    self.write();self.runtime.rpc.reset_mock();self.runtime.process.reset_mock();self.runtime.job.reset_mock()
                    command=dict(owner=self.owner,key='fixture-'+operation,operation=operation,payload={})
                    with patch.object(host,'callback_request',return_value={'key':command['key'],'epoch':3}),patch.object(host,'recorded_process_state',return_value='alive'):
                        with self.assertRaises(RuntimeError):self.runtime.execute_locked(command)
                    self.runtime.process.kill.assert_not_called();self.runtime.job.kill.assert_not_called()
                    self.assertTrue(all(call.args[0]=='thread/read' for call in self.runtime.rpc.call.call_args_list))
    def test_control_busy_gate_never_calls_authority_execute(self):
        self.write();(self.directory/'control-journal.private.json').write_text(json.dumps({'owner':self.owner,'active':True}))
        for mode in ('Check','Standup','Writeup','Stop','TestKill'):
            (self.directory/'control-journal.private.json').write_text(json.dumps({'owner':self.owner,'active':True}))
            calls=[]
            def load(path):return self.profile if pathlib.Path(path)==control.PROFILE else self.state
            def request(profile,body):calls.append(body['op']);return {'result':{'admission':'held'}}
            with patch.object(control,'scheduled_slot',return_value=None),patch.object(control,'load_private_profile',side_effect=load),patch.object(control,'recorded_process_state',return_value='alive'),patch.object(control,'request',side_effect=request),patch.object(control,'journal_lock',return_value=contextlib.nullcontext()):
                with self.assertRaises(RuntimeError) as error:control.run(mode)
            self.assertEqual(calls,['renew','admission_refresh'],(mode,str(error.exception)))
    def test_later_turn_uses_observed_connection_and_requires_its_completion_history(self):
        self.state.update(provider_turn_state='completed',provider_pending_tools={},api_history_validated=True)
        self.profile['check_prompt']='fixture bounded check'
        self.write();self.runtime.fresh_admission=MagicMock(return_value=(True,{}))
        def call(method,params):
            if method=='thread/read':return {'thread':self.thread}
            self.assertEqual(method,'turn/start')
            current=json.loads((self.directory/'root-runtime.json').read_text())
            self.assertFalse(current['api_history_validated'])
            observe(current,{'method':'turn/started','params':{'threadId':'fixture-cid','turn':{'id':'next-turn'}}})
            host.save(self.directory/'root-runtime.json',current)
            return {'turn':{'id':'next-turn'}}
        self.runtime.rpc.call.side_effect=call
        command=dict(owner=self.owner,key='fixture-check',operation='root-check',payload={})
        with patch.object(host,'callback_request',return_value={'key':command['key'],'epoch':3}),patch.object(host,'recorded_process_state',return_value='alive'),patch.object(host,'load_private_profile',return_value={'token':'fixture'}),patch.object(host,'AppServerRPC') as other:
            receipt=self.runtime.execute_locked(command)
        other.assert_not_called();self.assertTrue(receipt['evidence']['native_turn_submitted'])
        current=json.loads((self.directory/'root-runtime.json').read_text())
        self.assertFalse(dispatch_clear(current));self.assertEqual(current['provider_turn_id'],'next-turn')
        observe(current,{'method':'turn/completed','params':{'threadId':'fixture-cid','turn':{'id':'next-turn','status':'completed'}}})
        self.assertFalse(validate_latest_history(current,self.thread))
        self.thread['turns'].append({'id':'next-turn','status':'completed'})
        self.assertTrue(validate_latest_history(current,self.thread));self.assertTrue(dispatch_clear(current))
    def test_active_keeper_preserves_uncertain_effect_and_renews_busy_custody(self):
        self.write();calls=[]
        def load(path):return self.profile if pathlib.Path(path)==control.PROFILE else self.state
        def request(profile,body):calls.append(body['op']);return {'result':{'admission':'held'}}
        with patch.object(control,'load_private_profile',side_effect=load),patch.object(control,'recorded_process_state',return_value='alive'),patch.object(control,'request',side_effect=request),patch.object(control,'journal_lock',return_value=contextlib.nullcontext()):
            result=control.run('Recover')
        self.assertEqual(calls,['renew','admission_refresh']);self.assertTrue(result['pending_effect_preserved']);self.assertFalse(result['dispatch_ready'])

if __name__=='__main__':unittest.main()
