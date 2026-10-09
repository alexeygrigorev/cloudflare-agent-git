import copy,unittest
from unittest.mock import patch
import api_root_custody as api
import win35_root_control as control

class ApiCustodyTests(unittest.TestCase):
    def setUp(self):
        self.owner=dict(project='test',role='root',actor='native-fixture',generation='win32:10:20',epoch=3)
        self.profile=dict(runtime_mode='api-root',actor='native-fixture',generation='win32:10:20',state_dir='fixture')
        self.state=dict(runtime_mode='api-root',fence_owner=self.owner,thread_owner=self.owner,conversation_id='new-model-fixture',native_session_id='provider-fixture',
                        guardian_binding=dict(pid=10,creation_filetime=20),pid=30,process_creation_filetime=40,initial_turn_submitted=True,initial_turn_receipt={'turn':{'id':'real-response-fixture'}},
                        native_policy={'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'},provider_pending_tools={})
        self.live=lambda pid,stamp:'alive'
    def test_recorded_owned_api_without_frontend(self):
        self.assertTrue(api.recorded_api_custody(self.profile,self.state,self.owner,self.live))
    def test_absent_ui_never_admits_foreign_or_unknown(self):
        for key,value in [('runtime_mode',None),('conversation_id',None),('thread_owner',dict(self.owner,epoch=2)),('frontend_pid',999),('frontend_attempt_pending','uncertain'),('native_policy',{})]:
            with self.subTest(key=key):
                state=copy.deepcopy(self.state);state[key]=value
                self.assertFalse(api.recorded_api_custody(self.profile,state,self.owner,self.live))
        self.assertFalse(api.recorded_api_custody(self.profile,self.state,self.owner,lambda p,t:'unknown'))
    def test_native_generation_must_match(self):
        state=copy.deepcopy(self.state);state['guardian_binding']['creation_filetime']=21
        self.assertFalse(api.recorded_api_custody(self.profile,state,self.owner,self.live))
    def test_busy_tools_and_other_thread_not_dispatch_clear(self):
        api.observe(self.state,{'method':'turn/started','params':{'threadId':'new-model-fixture','turn':{'id':'turn'}}})
        self.assertFalse(api.dispatch_clear(self.state))
        api.observe(self.state,{'method':'item/tool/call','params':{'threadId':'new-model-fixture','callId':'tool'}})
        api.observe(self.state,{'method':'turn/completed','params':{'threadId':'another-thread','turn':{'id':'turn','status':'completed'}}})
        self.assertEqual(self.state['provider_turn_state'],'busy')
        api.observe(self.state,{'method':'turn/completed','params':{'threadId':'new-model-fixture','turn':{'id':'turn','status':'completed'}}})
        self.state['api_history_validated']=True
        self.assertFalse(api.dispatch_clear(self.state))
        api.observe(self.state,{'method':'item/completed','params':{'threadId':'new-model-fixture','item':{'id':'tool'}}})
        self.assertTrue(api.dispatch_clear(self.state))
    def test_expired_tuple_is_not_active(self):
        role=dict(holder=self.owner['actor'],generation=self.owner['generation'],epoch=3,lease_fresh=False,activation_due=False)
        self.assertFalse(api.valid_lease_tuple(role,self.owner))
        role['lease_fresh']=True;self.assertTrue(api.valid_lease_tuple(role,self.owner))
        del role['lease_fresh'];self.assertFalse(api.valid_lease_tuple(role,self.owner))
    def test_custody_renew_precedes_held_admission(self):
        calls=[]
        def request(profile,body):
            calls.append(body['op'])
            if body['op']=='admission_refresh':raise RuntimeError('protected or quota-held fixture')
        with patch.object(control,'load_private_profile',return_value=self.state),patch.object(control,'recorded_process_state',self.live),patch.object(control,'request',side_effect=request):
            with self.assertRaises(RuntimeError):control.refresh_owned(self.profile,self.owner)
        self.assertEqual(calls,['renew','admission_refresh'])
    def test_expired_renew_does_not_admit_or_revive(self):
        calls=[]
        def request(profile,body):calls.append(body['op']);raise RuntimeError('expired authority fixture')
        with patch.object(control,'load_private_profile',return_value=self.state),patch.object(control,'recorded_process_state',self.live),patch.object(control,'request',side_effect=request):
            with self.assertRaises(RuntimeError):control.refresh_owned(self.profile,self.owner)
        self.assertEqual(calls,['renew'])

if __name__=='__main__':unittest.main()
