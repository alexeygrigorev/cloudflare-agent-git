import copy,datetime,time,unittest
from managed_check_gate_client import FixedManagedAdmission
from win35_quota_gate import account_fingerprint

class RPC:
    def __init__(self):self.calls=[];self.used=84
    def call(self,method,args):
        self.calls.append(method)
        if method=='account/read':return {'account':{'type':'chatgpt','email':'fixture@example.invalid'}}
        return {'rateLimits':{'primary':{'usedPercent':self.used},'secondary':None}}

class Gate(unittest.TestCase):
    def setUp(self):
        self.state={'owner':{'project':'fixture','role':'root','actor':'A','generation':'G','epoch':11},
                    'thread_id':'own-CID','turn_id':'own-turn','activated':True,'lease_fresh':True}
        self.sent=[];self.saved=[];self.rpc=RPC()
        self.resources={'physical_source':'Windows CIM','disk_after_promised_growth_above_floor':True,
            'scratch_within_limit':True,'measured_ram':True,
            'measured_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        def request(body):
            self.sent.append(body);now=time.time()
            return {'v':1,'status':'ok','result':{'owner':copy.deepcopy(self.state['owner']),
                'thread_id':'own-CID','parent_turn_id':'own-turn','check_envelope':'envelope',
                'phase':body['phase'],'observed_at':now,'valid_until':now+5,
                'role_gate_ref':'server-owned:'+body['phase'],'current_activated':True,
                'proof_kind':'server-authority-gate'}}
        self.client=FixedManagedAdmission(lambda:copy.deepcopy(self.state),request,self.rpc,
            lambda:copy.deepcopy(self.resources),lambda k,v:self.saved.append((k,v)),
            account_fingerprint({'type':'chatgpt','email':'fixture@example.invalid'}))

    def test_actual_fixed_request_has_no_model_or_caller_proof(self):
        result=self.client.admission(self.state,'turn-start','envelope')
        self.assertEqual(result['remaining_percent'],16)
        self.assertEqual(self.rpc.calls,['account/read','account/rateLimits/read'])
        self.assertEqual(set(self.sent[0]),set(self.state['owner'])|{'v','op','check_envelope','parent_turn_id','phase'})
        self.assertEqual(self.sent[0]['v'],1)
        self.assertEqual(self.sent[0]['op'],'root_check_gate')
        self.assertEqual(len(self.saved),2)

    def test_actual_reserve_denial_never_requests_role_gate(self):
        self.rpc.used=85
        with self.assertRaises(RuntimeError):self.client.admission(self.state,'thread-start','envelope')
        self.assertEqual(self.sent,[])

    def test_wrong_account_or_physical_stale_denied(self):
        self.client.expected_account='wrong'
        with self.assertRaises(RuntimeError):self.client.admission(self.state,'thread-start','envelope')
        self.assertEqual(self.sent,[])
        self.setUp();self.resources['measured_at']='2000-01-01T00:00:00+00:00'
        with self.assertRaises(RuntimeError):self.client.admission(self.state,'thread-start','envelope')
        self.assertEqual(self.rpc.calls,[])

    def test_server_unknown_or_changed_binding_denied(self):
        self.client.request=lambda b:{'v':1,'status':'held'}
        with self.assertRaises(RuntimeError):self.client.admission(self.state,'thread-start','envelope')
        self.setUp();wrong=copy.deepcopy(self.state);wrong['turn_id']='old'
        with self.assertRaises(RuntimeError):self.client.admission(wrong,'thread-start','envelope')
        self.assertEqual(self.sent,[])

if __name__=='__main__':unittest.main()
