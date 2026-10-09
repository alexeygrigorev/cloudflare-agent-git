import copy,json,unittest
from opencode_native_proof import completed_tool,text_sha,fixed_reader_context
from opencode_root_tools import FixedRootTools

class RootProducerTests(unittest.TestCase):
    def setUp(self):
        self.context={'owner':{'project':'fixture-project','role':'ROOT','actor':'owned-fixture','generation':'owned-generation','epoch':1},'kernel':{'pid':123,'creation_filetime':456},
            'session_id':'ses_fixture','user_message_id':'msg_user','user_input_sha256':text_sha('owned input'),
            'provider_id':'zai-coding-plan','model_id':'glm-5.3-flash','agent':'root_contingency',
            'nonce':'fixed-nonce','envelope':'fixed-envelope','body':'fixed challenge','challenge_ref':'server-owned',
            'issued_at_ms':900,'deadline_ms':120900,'input_accepted_at_ms':1000,'profile_sha256':'a'*64,'kernel_ref':'private-source-ref','revision':1}
        self.journal=[];self.effects=[]
        def helper(c,n,a):
            self.effects.append(n);return {'helper_exit_code':0,'receipt_ref':'ref_'+str(len(self.effects))}
        self.tools=FixedRootTools(lambda:copy.deepcopy(self.context),lambda c,n:None,
            lambda c:{'helper_exit_code':0,'receipt_ref':'read-ref','instructions_sha256':'fixed-digest'},
            lambda c:{'helper_exit_code':0,'receipt_ref':'snapshot-ref','source_kind':'operator-audit','principal_authored':False},
            helper,lambda k,v:self.journal.append((k,copy.deepcopy(v))),clock=lambda:1.8)
    def call(self,name='root_role_reply',args=None):
        args=args if args is not None else {'body':'fixed challenge','next_action':'verify current principal','checkpoint':'next genuine result'}
        return self.tools.call({'jsonrpc':'2.0','id':7,'method':'tools/call','params':{'name':name,'arguments':args}})
    def proof_inputs(self):
        self.call();handled=self.journal[-1][1]
        user={'info':{'id':'msg_user','role':'user','sessionID':'ses_fixture','time':{'created':1000}},'parts':[{'type':'text','text':'owned input'}]}
        assistant={'info':{'id':'msg_assistant','role':'assistant','sessionID':'ses_fixture','parentID':'msg_user',
            'providerID':'zai-coding-plan','modelID':'glm-5.3-flash','agent':'root_contingency','time':{'created':1000,'completed':2000}},
            'parts':[{'type':'tool','id':'prt_tool','callID':'provider-call','sessionID':'ses_fixture','messageID':'msg_assistant',
            'tool':'root_gateway_root_role_reply','state':{'status':'completed','input':handled['arguments'],'output':handled['output'],'time':{'start':1200,'end':1900}}}]}
        return [user,assistant],handled
    def test_journal_precedes_mcp_return(self):
        output=self.call();self.assertEqual(len(self.journal),2)
        self.assertTrue(self.journal[0][0].startswith('helper-intent:'))
        self.assertEqual(output['content'][0]['text'],self.journal[-1][1]['output'])
        self.assertNotIn('native_completed',self.journal[-1][1])
    def test_model_cannot_supply_context(self):
        args={'body':'fixed challenge','next_action':'action','checkpoint':'check','owner':{'actor':'foreign'}}
        with self.assertRaises(RuntimeError):self.call(args=args)
        self.assertEqual(self.effects,[])
    def test_generic_tool_denied(self):
        for name in ('write','bash','task','root_check_completed'):
            with self.assertRaises(RuntimeError):self.call(name,{})
        self.assertEqual(self.journal,[])
    def test_reply_requires_trusted_current_challenge(self):
        self.context.pop('nonce')
        with self.assertRaises(RuntimeError):self.call()
        self.assertEqual(self.effects,[])
    def test_ack_exact_bundle(self):
        with self.assertRaises(RuntimeError):self.call('root_ack_instructions',{'instructions_sha256':'wrong'})
        self.assertEqual(self.effects,[])
    def test_replay_no_second_helper(self):
        self.call()
        with self.assertRaises(RuntimeError):self.call()
        self.assertEqual(len(self.effects),1)
    def test_native_completed_identifiers_preserved(self):
        history,h=self.proof_inputs();p=completed_tool(history,self.context,h,clock=lambda:2.5)
        self.assertEqual(p['proof_kind'],'opencode-native-v1');self.assertEqual(p['tool_part_id'],'prt_tool')
        self.assertEqual(p['call_id'],'provider-call');self.assertNotIn('turnId',p)
    def test_foreign_native_provider_message_denied(self):
        history,h=self.proof_inputs()
        for key,value in [('providerID','zai'),('modelID','other'),('sessionID','foreign'),('parentID','old'),('agent','general')]:
            with self.subTest(key=key):
                changed=copy.deepcopy(history);changed[-1]['info'][key]=value
                with self.assertRaises(RuntimeError):completed_tool(changed,self.context,h,clock=lambda:2.5)
    def test_wrong_native_input_or_pending_event_denied(self):
        history,h=self.proof_inputs()
        changed=copy.deepcopy(history);changed[0]['parts'][0]['text']='different'
        with self.assertRaises(RuntimeError):completed_tool(changed,self.context,h,clock=lambda:2.5)
        changed=copy.deepcopy(history);changed[-1]['parts'][0]['state']['status']='running'
        with self.assertRaises(RuntimeError):completed_tool(changed,self.context,h,clock=lambda:2.5)
    def test_boolean_helper_exit_and_reused_event_denied(self):
        history,h=self.proof_inputs();bad=dict(h,helper_exit_code=False)
        with self.assertRaises(RuntimeError):completed_tool(history,self.context,bad,clock=lambda:2.5)
        changed=copy.deepcopy(history);changed.append(copy.deepcopy(history[-1]))
        with self.assertRaises(RuntimeError):completed_tool(changed,self.context,h,clock=lambda:2.5)
    def test_native_output_and_raw_arguments_match(self):
        history,h=self.proof_inputs()
        for field,value in [('output','foreign receipt'),('input',{})]:
            changed=copy.deepcopy(history);changed[-1]['parts'][0]['state'][field]=value
            with self.assertRaises(RuntimeError):completed_tool(changed,self.context,h,clock=lambda:2.5)
    def test_stale_event_or_missing_challenge_denied(self):
        history,h=self.proof_inputs()
        with self.assertRaises(RuntimeError):completed_tool(history,self.context,h,clock=lambda:100)
        c=dict(self.context);c.pop('challenge_ref')
        with self.assertRaises(RuntimeError):completed_tool(history,c,h,clock=lambda:2.5)
    def test_completed_tool_does_not_require_or_claim_assistant_final(self):
        history,h=self.proof_inputs();history[-1]['info']['time'].pop('completed')
        result=completed_tool(history,self.context,h,clock=lambda:2.5)
        self.assertIsNone(result['message_completed_at']);self.assertFalse(result['task_or_check_completed'])
    def test_privileged_reader_exact_schema(self):
        history,h=self.proof_inputs();r=fixed_reader_context(self.context,h)
        self.assertEqual(set(r),{'owner_ref','profile_sha256','kernel_ref','session_id','user_message_id','input_sha256','challenge','envelope','issued_at','deadline','provider_id','model_id','helper','revision'})
        self.assertEqual(r['helper']['recorded_at'],1.8);self.assertEqual(r['challenge'],'fixed-nonce')
    def test_helper_secret_never_enters_mcp_return(self):
        self.tools.helper=lambda c,n,a:{'helper_exit_code':0,'receipt_ref':'fixed','nested':{'apiKey':'owned-secret-fixture'}}
        with self.assertRaises(RuntimeError):self.call()
        self.assertEqual(len(self.journal),1) # intent retained, no result/return

if __name__=='__main__':unittest.main()
