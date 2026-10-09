import copy
import unittest,time
from managed_check_session import ManagedCheckSession


class RPC:
    def __init__(self): self.calls=[];self.final=None
    def call(self, method, args):
        self.calls.append((method,args))
        if method=='thread/start':return {'sandbox':{'type':'readOnly','networkAccess':False},
            'approvalPolicy':'never','thread':{'id':'child','forkedFromId':None,
            'parentThreadId':None,'modelProvider':'openai','model':'gpt-6-luna',
            'reasoningEffort':'max','turns':[]}}
        if method=='thread/read':return {'thread':{'id':'child','turns':[self.final]}}
        return {'turn':{'id':'child-turn'}}


class Managed(unittest.TestCase):
    def setUp(self):
        self.state={'owner':{'actor':'root','epoch':11},'thread_id':'parent','turn_id':'parent-turn',
                    'activated':True,'lease_fresh':True}
        self.gate={'launch_allowed':True,'fresh':True,'provider':'openai',
                   'physical_allowed':True,'remaining_percent':16,
                   'role_gate_ref':'role-proof','quota_gate_ref':'fresh-api-proof','resource_gate_ref':'host-proof'}
        self.rpc=RPC();self.saved=[];self.gates=0
        def admit(state,phase,envelope):
            self.gates+=1;value=copy.deepcopy(self.gate);now=time.time()
            value['role_gate_ref'] += ':'+phase
            value['role_gate']={'v':1,'owner':copy.deepcopy(state['owner']),
                'thread_id':state['thread_id'],'parent_turn_id':state['turn_id'],
                'check_envelope':envelope,'phase':phase,'observed_at':now,'valid_until':now+5,
                'role_gate_ref':value['role_gate_ref'],'current_activated':True,'proof_kind':'server-authority-gate'}
            return value
        self.session=ManagedCheckSession(lambda:copy.deepcopy(self.state),admit,self.rpc,
            lambda r:self.saved.append(r),lambda:{'fixed':'instructions'},lambda:{'fixed':'reports'},
            'server-envelope','owned-workspace',lambda r:None)
        self.request={'method':'item/tool/call','params':{'threadId':'parent','turnId':'parent-turn',
            'callId':'parent-call','tool':'root_spawn_check','arguments':{}}}

    def test_real_launch_arguments_fixed_fresh_and_two_pre_effect_gates(self):
        r=self.session.spawn(self.request)
        self.assertEqual(self.gates,2);self.assertEqual(self.saved[0]['phase'],'context-pending')
        first=self.rpc.calls[0][1]
        self.assertEqual(first['model'],'gpt-6-luna');self.assertEqual(first['config']['model_reasoning_effort'],'max')
        self.assertNotIn('threadId',first);self.assertNotIn('forkedFromId',first)
        self.assertEqual(r['kind'],'managed-sdk-check');self.assertEqual(r['context_mode'],'new-thread-no-history')

    def test_denied_admission_has_zero_rpc(self):
        for change in ({'remaining_percent':15},{'remaining_percent':True},{'fresh':False},
                       {'physical_allowed':False},{'launch_allowed':False},{'provider':'fake'}):
            with self.subTest(change=change):
                self.setUp();self.gate.update(change)
                with self.assertRaises(RuntimeError):self.session.spawn(self.request)
                self.assertEqual(self.rpc.calls,[]);self.assertEqual(self.saved,[])

    def test_foreign_current_owner_or_arguments_denied_before_context(self):
        for change in ({'threadId':'foreign'},{'turnId':'old'},{'arguments':{'model':'other'}}):
            with self.subTest(change=change):
                req=copy.deepcopy(self.request);req['params'].update(change)
                with self.assertRaises(RuntimeError):self.session.spawn(req)
        self.assertEqual(self.rpc.calls,[])

    def test_expired_parent_never_spawns(self):
        self.state['lease_fresh']=False
        with self.assertRaises(RuntimeError):self.session.spawn(self.request)
        self.assertEqual(self.rpc.calls,[])

    def test_durable_attempt_is_not_replayed(self):
        self.session.spawn(self.request)
        with self.assertRaises(RuntimeError):self.session.spawn(self.request)
        self.assertEqual(len(self.rpc.calls),2)

    def test_gate_changes_after_context_no_model_turn(self):
        original=self.session.fresh_admission
        def admit(state,phase,envelope):
            value=original(state,phase,envelope)
            value['launch_allowed']=self.gates==1
            return value
        self.session.fresh_admission=admit
        with self.assertRaises(RuntimeError):self.session.spawn(self.request)
        self.assertEqual([m for m,a in self.rpc.calls],['thread/start'])
        self.assertEqual(self.saved[-1]['phase'],'context-created')

    def test_wrong_stale_or_forged_role_gate_has_zero_native_effect(self):
        for change in ({'phase':'wrong'},{'valid_until':0},{'thread_id':'foreign'},
                       {'current_activated':False},{'proof_kind':'model-asserted'},
                       {'observed_at':True},{'check_envelope':'foreign'}):
            with self.subTest(change=change):
                self.setUp();original=self.session.fresh_admission
                def bad(state,phase,envelope):
                    value=original(state,phase,envelope);value['role_gate'].update(change);return value
                self.session.fresh_admission=bad
                with self.assertRaises(RuntimeError):self.session.spawn(self.request)
                self.assertEqual(self.rpc.calls,[])

    def test_child_parent_tools_and_replay_denied(self):
        self.session.spawn(self.request)
        req={'method':'item/tool/call','params':{'threadId':'child','turnId':'child-turn',
            'callId':'child-call','tool':'root_role_ack','arguments':{}}}
        with self.assertRaises(RuntimeError):self.session.child_read(req)
        req['params']['tool']='root_read_instructions'
        self.assertEqual(self.session.child_read(req),{'fixed':'instructions'})
        with self.assertRaises(RuntimeError):self.session.child_read(req)

    def test_changed_owner_denies_child_reads(self):
        self.session.spawn(self.request);self.state['owner']['epoch']=12
        req={'method':'item/tool/call','params':{'threadId':'child','turnId':'child-turn',
            'callId':'child-call','tool':'root_check_reports','arguments':{}}}
        with self.assertRaises(RuntimeError):self.session.child_read(req)

    def test_actual_completed_custom_events_required_for_parent_wait_and_result(self):
        import hashlib,json
        response=self.session.handle_parent(self.request)
        def completed(thread,turn,call,tool,response):
            return {'method':'item/completed','params':{'threadId':thread,'turnId':turn,'item':{
                'id':call,'type':'dynamicToolCall','tool':tool,'arguments':{},'status':'completed',
                'success':True,'contentItems':response['contentItems']}}}
        wait=copy.deepcopy(self.request);wait['params'].update(tool='root_wait_check',callId='wait-call')
        with self.assertRaises(RuntimeError):self.session.wait(wait)
        self.session.observe(completed('parent','parent-turn','parent-call','root_spawn_check',response))
        fixed={'contentItems':[{'type':'inputText','text':'Fixed labelled evidence'}],'success':True}
        self.session.instructions=lambda:fixed;self.session.reports=lambda:fixed
        for tool in ('root_read_instructions','root_check_reports'):
            req={'method':'item/tool/call','params':{'threadId':'child','turnId':'child-turn',
                'callId':tool+'-call','tool':tool,'arguments':{}}}
            value=self.session.child_read(req)
            self.session.observe(completed('child','child-turn',tool+'-call',tool,value))
        self.rpc.final={'id':'child-turn','status':'completed','items':[{
            'type':'agentMessage','text':'Principal outcome unresolved; require actual owner action and checkpoint.'}]}
        self.session.verify_context=lambda r:{'model':'gpt-6-luna','effort':'max','turn_id':'child-turn',
            'approval_policy':'never','sandbox_policy':{'type':'read-only'},'owned_rollout_receipt_sha256':'a'*64}
        wait_response=self.session.handle_parent(wait)
        with self.assertRaises(RuntimeError):self.session.supervised('child')
        self.session.observe(completed('parent','parent-turn','wait-call','root_wait_check',wait_response))
        result=self.session.supervised('child')
        self.produced_result=copy.deepcopy(result)
        self.assertEqual(result['check_method'],'managed-sdk-fresh-v1')
        self.assertEqual(result['managed_launch']['initial_turn_count'],0)
        self.assertIsInstance(result['managed_launch']['native_start_at'],float)
        self.assertIsInstance(result['managed_launch']['native_turn_at'],float)
        self.assertNotIn('native_context_start_at',result['managed_launch'])
        self.assertNotIn('native_turn_ref',result['managed_launch'])
        self.assertEqual(result['launch_method'],'managed-sdk-fresh-v1')
        self.assertEqual(result['parent_thread_id'],result['managed_launch']['parent_thread_id'])
        self.assertEqual(result['spawn_event_id'],result['parent_spawn_event']['id'])
        self.assertEqual(set(result['actual_execution_context']),{'thread_id','turn_id','model','effort','sandbox_policy','approval_policy'})
        self.assertTrue(result['child_completed_event'].startswith('managed-owned-record:'))
        self.assertNotIn('raw_fork_mode',result)
        self.assertEqual(result['wait_event_id'],'wait-call')
        self.rpc.final['items'][0]['text']='newer unaccepted result'
        with self.assertRaises(RuntimeError):self.session.supervised('child')


if __name__=='__main__':unittest.main()
