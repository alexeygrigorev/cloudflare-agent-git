import copy,hashlib,unittest
from opencode_controller_gate import ControllerGate,ref
class GateTests(unittest.TestCase):
    def setUp(self):
        self.owner={'project':'own','role':'root','actor':'own-native','generation':'own-generation','epoch':12};self.requests=[]
        self.response={'v':1,'owner':self.owner,'owner_ref':ref(self.owner),'helper_allowed':True,'model_launch_allowed':False,'authority_effect':False,
            'activation_pending':True,'role_gate_ref':'actual-server-ref','issued_at':100,'valid_until':105,'instructions_sha256':'a'*64}
        def post(path,body):self.requests.append((path,body));return copy.deepcopy(self.response)
        self.gate=ControllerGate(self.owner,{'identity_id':'own','token':'sentinel-only'},'a'*64,post,clock=lambda:101)
    def test_own_unactivated_gate_only_not_launch(self):
        result=self.gate({'owner':self.owner},'root_ack_instructions');self.assertTrue(result['activation_pending'])
        path,body=self.requests[0];self.assertEqual(path,'/v1/host-recovery');self.assertEqual(set(body),{'v','credential','op'})
        self.assertNotIn('sentinel',repr(self.gate))
    def test_wrong_owner_stale_or_granted_launch_held(self):
        for key,value in [('owner_ref','foreign'),('valid_until',100),('helper_allowed',False),('model_launch_allowed',True),('authority_effect',True)]:
            original=copy.deepcopy(self.response);self.response[key]=value
            with self.assertRaises(RuntimeError):self.gate({'owner':self.owner},'root_oversight_snapshot')
            self.response=original
    def test_input_body_binding_and_no_completed_replay(self):
        body='Fixed actual server input';self.response={'v':1,'owner_ref':ref(self.owner),'challenge':'fixed-nonce','envelope':'fixed-envelope',
            'body':body,'input_sha256':hashlib.sha256(body.encode()).hexdigest(),'issued_at':100,'deadline':220,'response_completed':False,'check_completed':False,'model_launch_allowed':False}
        self.assertEqual(self.gate.initial_input()['challenge'],'fixed-nonce')
        self.response['response_completed']=True
        with self.assertRaises(RuntimeError):self.gate.initial_input()
        self.response['response_completed']=False;self.response['body']='changed'
        with self.assertRaises(RuntimeError):self.gate.initial_input()
if __name__=='__main__':unittest.main()
