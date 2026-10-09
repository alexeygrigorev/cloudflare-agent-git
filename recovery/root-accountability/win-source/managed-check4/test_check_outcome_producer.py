import unittest,copy,hashlib
from check_outcome_producer import CheckOutcomeProducer

class Outcome(unittest.TestCase):
    def setUp(self):
        self.state={'conversation_id':'parent','provider_turn_id':'check-turn','provider_turn_state':'busy','thread_owner':{'epoch':13}}
        self.check={'owner':{'epoch':13},'thread_id':'parent','turn_id':'check-turn','envelope':'fixed-server-envelope'}
        self.result={'owner':{'epoch':13},'child_thread_id':'child','child_turn_id':'child-turn',
            'own_result':'Principal owns the unresolved coverage remedy; request its changed action and receipt.',
            'required_reads_completed':True,'wait_event_id':'actual-wait','parent_wait_status':'completed'}
        self.writes=[]
        self.producer=CheckOutcomeProducer(lambda:copy.deepcopy(self.state),lambda c:copy.deepcopy(self.result),
            lambda:copy.deepcopy(self.check),lambda k,r:self.writes.append((k,copy.deepcopy(r))),clock=lambda:123.0,
            helper=lambda s,q,c,r:dict(exit_code=0,owner=s['thread_owner'],thread_id=q['params']['threadId'],
                turn_id=q['params']['turnId'],call_id=q['params']['callId'],helper_kernel={'pid':12,'creation_filetime':123}))
        self.q={'id':9,'method':'item/tool/call','params':{'threadId':'parent','turnId':'check-turn','callId':'accept-event','tool':'root_check_result',
            'arguments':{'check_envelope':'fixed-server-envelope','child_thread_id':'child','child_turn_id':'child-turn',
                'result_sha256':hashlib.sha256(self.result['own_result'].encode()).hexdigest(),
                'next_action':'Request the principal changed continuation remedy.','checkpoint':'Verify its actual owner receipt in fifteen minutes.'}}}

    def test_handled_helper_is_not_completed_model_proof(self):
        response=self.producer.handle(self.q)
        with self.assertRaises(RuntimeError):self.producer.proof('fixed-server-envelope','parent')
        event={'method':'item/completed','params':{'threadId':'parent','turnId':'check-turn','item':{
            'id':'accept-event','type':'dynamicToolCall','tool':'root_check_result','status':'completed','success':True,
            'arguments':self.q['params']['arguments'],'contentItems':response['contentItems']}}}
        self.producer.observe(event)
        proof=self.producer.proof('fixed-server-envelope','parent')['check_result']
        self.assertEqual(proof['parent_accept_event']['id'],'accept-event')
        self.assertEqual(proof['source_event_at'],123.0)

    def test_wrong_envelope_child_hash_turn_no_wait_hold_before_persistence(self):
        for field,value in (('check_envelope','foreign'),('child_thread_id','foreign'),('child_turn_id','other'),('result_sha256','fake')):
            q=copy.deepcopy(self.q);q['params']['arguments'][field]=value
            with self.assertRaises(RuntimeError):self.producer.handle(q)
        self.result['wait_event_id']=None
        with self.assertRaises(RuntimeError):self.producer.handle(self.q)
        self.assertEqual(self.writes,[])

    def test_old_child_or_replayed_call_cannot_accept_parent_result(self):
        q=copy.deepcopy(self.q);q['params']['threadId']='child'
        with self.assertRaises(RuntimeError):self.producer.handle(q)
        self.producer.handle(self.q)
        with self.assertRaises(RuntimeError):self.producer.handle(self.q)
        self.assertEqual(len(self.writes),1)

    def test_result_inspection_returns_actual_final_hash_after_wait(self):
        q=copy.deepcopy(self.q);q['params'].update(tool='root_check_inspect',arguments={'child_thread_id':'child'})
        value=self.producer.handle(q)
        self.assertIn(self.q['params']['arguments']['result_sha256'],value['contentItems'][0]['text'])

if __name__=='__main__':unittest.main()
