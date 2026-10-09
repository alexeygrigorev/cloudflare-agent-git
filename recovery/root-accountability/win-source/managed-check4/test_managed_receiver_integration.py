"""One isolated source-to-receiver fixture; no model/provider/runtime effects.

Run with the exact independently frozen receiver directory as argv[1]. The
fixture persists its server-issued two-phase gate rows before native RPC
fixtures, then passes real producer functions' result and completed acceptance
event to the receiver. It is not a genuine live provider check.
"""
import contextlib,copy,hashlib,json,pathlib,sqlite3,sys,time,unittest
if len(sys.argv)!=2:raise SystemExit('requires exact owned receiver directory')
sys.path.insert(0,str(pathlib.Path(sys.argv.pop()).resolve()))
from operational_receiver import CompletedCheckReceiver,CheckFenced
from test_managed_check_session import Managed
from check_outcome_producer import CheckOutcomeProducer

class Authority:
    def __init__(self,owner):
        self.owner=owner;self.clock=time.time;self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE native_check_gates(ref TEXT PRIMARY KEY,owner TEXT,body TEXT)')
    @contextlib.contextmanager
    def _tx(self):
        with self.db:yield self.db
    def _valid(self,db,*owner):
        if tuple(self.owner[k] for k in ('project','role','actor','generation','epoch'))!=owner:
            raise CheckFenced('fixture foreign owner')

class Integration(unittest.TestCase):
    def test_supervised_completed_acceptance_into_fixed_receiver(self):
        f=Managed();f.setUp()
        owner={'project':'isolated-fixture','role':'root','actor':'fixture-root','generation':'fixture-gen','epoch':11}
        f.state['owner']=owner;authority=Authority(owner)
        original=f.session.fresh_admission
        def issue(state,phase,envelope):
            gate=original(state,phase,envelope)
            authority.db.execute('INSERT INTO native_check_gates VALUES(?,?,?)',
                (gate['role_gate_ref'],json.dumps(owner),json.dumps(gate['role_gate'])))
            return gate
        f.session.fresh_admission=issue
        f.test_actual_completed_custom_events_required_for_parent_wait_and_result()
        result=f.produced_result
        parent={'thread_owner':owner,'conversation_id':'parent','provider_turn_id':'parent-turn','provider_turn_state':'busy'}
        check={'owner':owner,'thread_id':'parent','turn_id':'parent-turn','envelope':'server-envelope'}
        producer=CheckOutcomeProducer(lambda:copy.deepcopy(parent),lambda child:copy.deepcopy(result),
            lambda:check,lambda key,record:None,
            helper=lambda s,q,c,r:{'exit_code':0,'owner':owner,'thread_id':'parent','turn_id':'parent-turn',
                'call_id':q['params']['callId'],'helper_kernel':{'pid':12,'creation_filetime':123}})
        args={'check_envelope':'server-envelope','child_thread_id':'child','child_turn_id':'child-turn',
              'result_sha256':hashlib.sha256(result['own_result'].encode()).hexdigest(),
              'next_action':'Require principal owner and executed remedy evidence.',
              'checkpoint':'Verify genuine owner action receipt at next bounded check.'}
        request={'method':'item/tool/call','params':{'threadId':'parent','turnId':'parent-turn',
                 'callId':'accept-fixture','tool':'root_check_result','arguments':args}}
        response=producer.handle(request)
        with self.assertRaises(RuntimeError):producer.proof('server-envelope','parent')
        producer.observe({'method':'item/completed','params':{'threadId':'parent','turnId':'parent-turn','item':{
            'type':'dynamicToolCall','tool':'root_check_result','id':'accept-fixture','arguments':args,
            'status':'completed','success':True,'contentItems':response['contentItems']}}})
        proof=producer.proof('server-envelope','parent')
        command={'v':1,'key':'fixture-only-key','owner':owner,'operation':'root-check-proof',
                 'payload':{'check_envelope':'server-envelope','thread_id':'parent'}}
        wrapped=dict(command,state='completed',evidence=proof)
        receiver=CompletedCheckReceiver(authority,model_binding=lambda o:None,dispatch=lambda *a:None,
                                        method='managed-sdk-fresh-v1')
        accepted=receiver.record_check(command,wrapped,{'owner':owner,'thread_id':'parent'})
        self.assertEqual(accepted['receipt_ref'],'fixture-only-key')
        forged=copy.deepcopy(wrapped);forged['evidence']['check_result']['managed_launch']['turn_role_gate_ref']='invented'
        with self.assertRaises(CheckFenced):receiver.record_check(command,forged,{'owner':owner,'thread_id':'parent'})

if __name__=='__main__':unittest.main()
