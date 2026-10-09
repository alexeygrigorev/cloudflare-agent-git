import json,pathlib,tempfile,unittest
from unittest import mock
import win35_root_host as host
import win35_root_control as control

class BootstrapDraft(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.owner={'project':'test','role':'root','actor':'genuine-fixture','generation':'kernel-fixture','epoch':1}
        self.runtime=host.RootRuntime({'state_dir':self.tmp.name},{'id':'genuine-fixture'})
        self.runtime.process=mock.Mock(pid=10,creation_filetime=20)
        self.runtime.process.poll.return_value=None
        self.runtime.job=mock.Mock()
        self.binding={'pid':30,'creation_filetime':40}
        self.state={'pid':10,'process_creation_filetime':20,'initial_turn_submitted':True,
            'frontend_pending':True,'model_launch_complete':False,'launch_pending':None,
            'conversation_id':'actual-cid','native_session_id':'actual-native-session',
            'thread_owner':self.owner,'fence_owner':self.owner,'guardian_binding':self.binding,
            'initial_turn_receipt':{'turn':{'id':'actual-turn'}},
            'native_policy':{'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'}}
    def test_intentional_no_frontend_has_no_composer(self):
        with mock.patch.object(host,'recorded_process_state',return_value='alive'),mock.patch.object(host,'current_process_binding',return_value=self.binding):
            self.assertFalse(self.runtime.protected_draft(self.state))
        self.runtime.job.query.assert_called_once()
    def test_missing_or_foreign_bootstrap_identity_is_unknown(self):
        for key in ('native_session_id','conversation_id','initial_turn_receipt','native_policy','guardian_binding'):
            state=dict(self.state);state.pop(key)
            with mock.patch.object(host,'recorded_process_state',return_value='alive'),mock.patch.object(host,'current_process_binding',return_value=self.binding):
                with self.assertRaises(RuntimeError):self.runtime.protected_draft(state)
    def test_recorded_or_dead_frontend_is_not_admitted(self):
        for values in ({'frontend_pid':99},{'viewer_pid':99},{'frontend_attempt_pending':'uncertain-attach'}, {'process_creation_filetime':21},{'initial_turn_submitted':False}):
            state=dict(self.state,**values)
            with mock.patch.object(host,'recorded_process_state',return_value='alive'),mock.patch.object(host,'current_process_binding',return_value=self.binding):
                with self.assertRaises(RuntimeError):self.runtime.protected_draft(state)
    def test_uncertain_attach_is_not_retried(self):
        state=dict(self.state,frontend_attempt_pending='exact-prior-key')
        self.runtime.rpc=mock.Mock()
        self.runtime.final_guard=mock.Mock()
        with self.assertRaisesRegex(RuntimeError,'uncertain prior frontend'):
            self.runtime.attach_materialized_frontend(state,pathlib.Path(self.tmp.name)/'state.json',{'owner':self.owner})
        self.runtime.rpc.call.assert_not_called()
        self.runtime.job.start.assert_not_called()

class BootstrapRenewal(unittest.TestCase):
    def test_observation_and_pending_renew_precede_model_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            owner={'project':'test','role':'root','actor':'native','generation':'win32:10:20','epoch':1}
            profile={'runtime_mode':'api-root','actor':'native','generation':owner['generation'],'owner':owner,'state_dir':directory}
            state={'runtime_mode':'api-root','thread_owner':owner,'fence_owner':owner,'conversation_id':'fixture-cid','native_session_id':'fixture-session',
                   'initial_turn_submitted':True,'initial_turn_receipt':{'turn':{'id':'fixture-turn'}},'guardian_binding':{'pid':10,'creation_filetime':20},'pid':30,'process_creation_filetime':40,
                   'native_policy':{'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'},'provider_turn_state':'completed','provider_pending_tools':{}}
            proof={'owner':owner,'model':{'first_tool':{'event_id':'provider-event','ack_message_id':'actual-bus-id'}}}
            pathlib.Path(directory,'model-evidence.private.json').write_text(json.dumps(proof))
            calls=[]
            def request(profile,body):
                calls.append(body['op'])
                if body['op']=='acquire':return {'result':{'holder':'native','generation':owner['generation'],'epoch':1,'read_only':False}}
                if body['op']=='first_action':return {'result':{'first_action_key':'fixed-key'}}
                return {'result':{}}
            with mock.patch.object(control,'request',side_effect=request),mock.patch.object(control,'load_private_profile',return_value=state),mock.patch.object(control,'recorded_process_state',return_value='alive'):
                control.bootstrap(profile,{},pathlib.Path(directory,'journal.json'))
            at=calls.index('model_evidence')
            self.assertEqual(calls[at-2:at],['renew','admission_refresh'])
            self.assertEqual(calls[-1],'activate')

if __name__=='__main__':unittest.main()
