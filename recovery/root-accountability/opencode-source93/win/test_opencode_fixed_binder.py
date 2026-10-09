import copy,json,pathlib,unittest
from opencode_fixed_binder import FixedBinder,INSTRUCTIONS_SHA
from opencode_controller_gate import ref

class Journal:
    def __init__(self):self.records=[]
    def write(self,key,value):self.records.append((key,copy.deepcopy(value)))
class BinderTests(unittest.TestCase):
    def setUp(self):
        self.base=pathlib.Path(__file__).parent
        if not (self.base/'startup-doc67').exists():self.base=self.base.parent
        self.owner={'project':'owned-source-fixture','role':'root','actor':'fixture','generation':'fixture','epoch':1}
        self.context={'owner':self.owner,'kernel':{'pid':1,'creation_filetime':2},'session_id':'ses_fixture',
            'user_message_id':'msg_fixture','user_input_sha256':'b'*64,'nonce':'fixture-nonce','envelope':'fixture-envelope'}
        self.journal=Journal();self.denial={'provider':'openai-codex','launch_allowed':False,'actual_upstream_read':True,
            'account_binding':'f'*64,'source_ref':'fixture-only-not-real-denial','status':'RESERVE_DENIED',
            'observed_at':100,'valid_until':160,'next_trigger':'source-fixture-only'}
        def post(path,body):return {'v':1,'owner':self.owner,'owner_ref':ref(self.owner),'helper_allowed':True,
            'model_launch_allowed':False,'authority_effect':False,'activation_pending':True,'role_gate_ref':'fixture-source-only',
            'issued_at':100,'valid_until':105,'instructions_sha256':INSTRUCTIONS_SHA}
        self.b=FixedBinder(self.owner,{'identity_id':'fixture','token':'sentinel-only'},post,lambda:copy.deepcopy(self.context),self.journal,
            self.base/'startup-doc67',self.base/'principal-observation-20261009T043726Z.private.json',
            '0d30c9782f01e5331532f8b33bef6033927b395803b0fae71f16dd244ed76135',lambda:copy.deepcopy(self.denial),clock=lambda:101)
    def test_reads_actual_pinned_approved_docs(self):
        result=self.b.instructions(self.context)
        self.assertEqual(result['instructions_sha256'],INSTRUCTIONS_SHA)
        self.assertEqual(len(result['documents']),3);self.assertFalse(result['authority_effect'])
        self.assertTrue(all(d['body'] for d in result['documents']))
    def test_actual_labelled_audit_does_not_become_current_principal(self):
        result=self.b.snapshot(self.context)
        self.assertFalse(result['principal_authored']);self.assertEqual(result['source_kind'],'operator-audit')
        self.assertEqual(result['facts']['goal']['current_saved_state'],'UNKNOWN')
    def test_local_reply_is_not_delivery_or_completed_response(self):
        r=self.b.helper(self.context,'root_role_reply',{'body':'Substantive fixture response','next_action':'Verify genuine principal custody','checkpoint':'Require accepted source evidence'})
        self.assertFalse(r['response_completed']);self.assertFalse(r['check_completed']);self.assertFalse(r['authority_effect'])
        self.assertIn('pending',r['delivery'])
    def test_real_denial_required_hold_never_completes_check(self):
        result=self.b.helper(self.context,'root_luna_hold',{'body':'source-only fixture','next_action':'no model dispatch','checkpoint':'next actual gate'})
        self.assertFalse(result['check_completed']);self.denial['actual_upstream_read']=False
        with self.assertRaises(RuntimeError):self.b.helper(self.context,'root_luna_hold',{})
    def test_unknown_or_expired_projection_never_becomes_hold(self):
        self.denial['status']='READ_UNKNOWN'
        with self.assertRaises(RuntimeError):self.b.helper(self.context,'root_luna_hold',{})
        self.denial['status']='RESERVE_DENIED';self.denial['valid_until']=101
        with self.assertRaises(RuntimeError):self.b.helper(self.context,'root_luna_hold',{})
if __name__=='__main__':unittest.main()
