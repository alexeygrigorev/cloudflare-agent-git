import copy,hashlib,json,types,unittest
from opencode_root_start import RootStart

class RootStartTests(unittest.TestCase):
    def setUp(self):
        self.owner=dict(project='fixture',role='root',actor='native',generation='gen',epoch=12)
        self.native=dict(id='native',tag='fixture',engine='shell',workspace='fixture')
        self.command=dict(owner=self.owner,operation='root-start',payload={},key='owned')
        self.state=None;self.receipt=None;self.starts=0;self.history=[]
        self.profile=dict(owner=self.owner,session_id='ses_new')
        pin=hashlib.sha256(json.dumps(self.profile).encode()).hexdigest()
        self.kernel=dict(owner=self.owner,native_actor=self.native,profile_sha256=pin,
                         session_id='ses_new',kernel_ref='kernel',job=dict(queried=True,active_processes=1))
        def start(command):
            self.starts+=1
            self.state=dict(phase='native-session-ready',owner=self.owner,key='owned',session_id='ses_new',model_turn_submitted=False)
        self.factory=types.SimpleNamespace(profile={},read=lambda:copy.deepcopy(self.state),start=start,backend=object(),job=object())
        writer=types.SimpleNamespace(write=lambda *args:dict(profile_sha256=pin))
        self.adapter=RootStart(self.factory,lambda:dict(owner=self.owner,native=self.native,holding_profile_sha256='b'*64),lambda:{},writer,
            lambda:copy.deepcopy(self.profile),lambda *args:lambda:copy.deepcopy(self.kernel),
            lambda old:copy.deepcopy(self.history),lambda:copy.deepcopy(self.receipt),
            lambda v:setattr(self,'receipt',copy.deepcopy(v)),lambda c:None,'a'*64,lambda:100)
    def test_first_start_actual_empty_session_receipt_and_replay_no_new_start(self):
        proof=self.adapter.start(self.command)
        self.assertEqual(proof['owner'],self.owner)
        self.assertEqual(proof['session_id'],'ses_new')
        self.assertTrue(proof['history_empty'])
        self.assertFalse(proof['model_turn_submitted'])
        self.assertEqual(proof['kernel_before'],proof['kernel_after'])
        self.assertEqual(self.adapter.start(self.command),proof)
        self.assertEqual(self.starts,1)
    def test_existing_uncertain_intent_never_restarts(self):
        self.state=dict(phase='start-pending')
        with self.assertRaises(RuntimeError):self.adapter.start(self.command)
        self.assertEqual(self.starts,0)
    def test_replay_requires_fresh_empty_history(self):
        self.adapter.start(self.command);self.history=[dict(info=dict(role='user'))]
        with self.assertRaises(RuntimeError):self.adapter.start(self.command)
        self.assertEqual(self.starts,1)
    def test_wrong_owner_or_profile_never_accepted(self):
        with self.assertRaises(RuntimeError):self.adapter.start(dict(self.command,owner=dict(self.owner,epoch=1)))
        self.profile['session_id']='ses_foreign'
        with self.assertRaises(RuntimeError):self.adapter.start(self.command)
    def test_kernel_change_during_history_holds_without_receipt(self):
        def history(old):
            self.kernel['kernel_ref']='different';return []
        self.adapter.history_reader=history
        with self.assertRaises(RuntimeError):self.adapter.start(self.command)
        self.assertIsNone(self.receipt)

if __name__=='__main__':unittest.main()
