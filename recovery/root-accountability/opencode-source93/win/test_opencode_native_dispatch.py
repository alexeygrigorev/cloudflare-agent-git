import copy,hashlib,unittest,threading
from opencode_native_dispatch import NativeDispatch,digest

class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.saved=None;self.posts=[];self.now=101;self.history=[]
        self.owner={'role':'root','actor':'genuine-source-fixture'}
        self.selected={'body':'Server fixed meaningful input','input_sha256':hashlib.sha256(b'Server fixed meaningful input').hexdigest(),
            'challenge':'nonce','envelope':'server-envelope','issued_at':100,'deadline':220}
        self.gate={'provider':'zai-coding-plan','model':'glm-5.3-flash','account_binding':'own','launch_allowed':True,
            'physical_allowed':True,'source_ref':'provider-fixture','resource_ref':'physical-fixture','observed_at':100,'valid_until':105}
        self.d=NativeDispatch(self.owner,'ses_actualFixture','own',lambda:copy.deepcopy(self.saved),self.save,
            lambda:self.history,self.post,lambda:self.gate,lambda *a:None,lambda:self.now)
    def save(self,value):self.saved=copy.deepcopy(value)
    def post(self,*args):self.posts.append(args);return {'status':204}
    def test_durable_intent_precedes_post_no_completion_claim(self):
        def post(*args):
            self.assertEqual(self.saved['phase'],'dispatch-pending');return self.post(*args)
        self.d.post=post;r=self.d.dispatch(self.selected)
        self.assertFalse(r['model_completed']);self.assertFalse(r['authority_effect'])
        self.assertEqual(self.posts[0][0],'/session/ses_actualFixture/prompt_async')
    def test_lost_response_never_resends(self):
        self.d.post=lambda *a:(_ for _ in ()).throw(TimeoutError('fixture'))
        with self.assertRaises(TimeoutError):self.d.dispatch(self.selected)
        self.d.post=self.post
        with self.assertRaises(RuntimeError):self.d.dispatch(self.selected)
        self.assertFalse(self.posts);self.assertEqual(self.saved['phase'],'dispatch-pending')
    def test_actual_unique_user_reconciles_without_second_post(self):
        self.d.dispatch(self.selected)
        self.history=[{'info':{'role':'user','id':'msg_actual','sessionID':'ses_actualFixture','time':{'created':101000}},
                       'parts':[{'type':'text','text':self.selected['body']}]}]
        r=self.d.dispatch(self.selected)
        self.assertEqual(r['user_message_id'],'msg_actual');self.assertEqual(len(self.posts),1)
        self.assertFalse(r['model_completed'])
    def test_unknown_foreign_denied_expired_gate_has_no_post(self):
        for key,value in (('account_binding','foreign'),('launch_allowed',False),('physical_allowed',False),('valid_until',101)):
            gate=copy.deepcopy(self.gate);gate[key]=value;self.d.admission=lambda:gate
            with self.assertRaises(RuntimeError):self.d.dispatch(self.selected)
        self.assertFalse(self.posts);self.assertIsNone(self.saved)
    def test_pending_different_input_or_duplicate_user_holds(self):
        self.d.dispatch(self.selected)
        with self.assertRaises(RuntimeError):self.d.dispatch(dict(self.selected,envelope='foreign'))
        item={'info':{'role':'user','id':'msg_same','sessionID':'ses_actualFixture','time':{'created':101000}},
              'parts':[{'type':'text','text':self.selected['body']}]}
        self.history=[item,item]
        with self.assertRaises(RuntimeError):self.d.dispatch(self.selected)
        self.assertEqual(len(self.posts),1)
    def test_concurrent_admission_only_one_native_post(self):
        barrier=threading.Barrier(2);errors=[]
        def admission():barrier.wait(1);return self.gate
        self.d.admission=admission
        def run():
            try:self.d.dispatch(self.selected)
            except RuntimeError as exc:errors.append(exc)
        workers=[threading.Thread(target=run) for _ in range(2)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(2)
        self.assertEqual(len(self.posts),1);self.assertEqual(len(errors),1)
    def prepare_release(self):
        self.d.dispatch(self.selected)
        self.history=[{'info':{'role':'user','id':'msg_actual','sessionID':'ses_actualFixture','time':{'created':101000}},
                       'parts':[{'type':'text','text':self.selected['body']}]}]
        self.d.reconcile(self.selected);self.archive=[]
        self.completion={'owner':self.owner,'session_id':'ses_actualFixture','envelope':'server-envelope',
            'challenge':'nonce','input_sha256':self.selected['input_sha256'],'response_completed':True,
            'native_reply_receipt_ref':'actual-server-source-fixture','completed_at':102}
        self.d.completed_reply_reader=lambda p:self.completion
        def archive(value):self.archive.append(copy.deepcopy(value));return digest(value)
        self.d.archive=archive;self.d.archive_reader=lambda key:next(v for v in self.archive if digest(v)==key)
        self.d.quiescent=lambda s:True
    def test_prior_release_archives_actual_reply_before_next_dispatch(self):
        self.prepare_release();r=self.d.release_prior()
        self.assertFalse(r['check_completed']);self.assertEqual(len(self.archive),1);self.assertEqual(self.saved['phase'],'released')
        self.d.dispatch(dict(self.selected,envelope='next-server-envelope'))
        self.assertEqual(len(self.posts),2)
    def test_helper_only_foreign_or_busy_reply_cannot_release(self):
        self.prepare_release()
        for key,value in (('response_completed',False),('envelope','foreign'),('native_reply_receipt_ref',''),('completed_at',221)):
            old=self.completion[key];self.completion[key]=value
            with self.assertRaises(RuntimeError):self.d.release_prior()
            self.completion[key]=old
        self.d.quiescent=lambda s:False
        with self.assertRaises(RuntimeError):self.d.release_prior()
        self.assertFalse(self.archive);self.assertIsNotNone(self.saved)

if __name__=='__main__':unittest.main()
