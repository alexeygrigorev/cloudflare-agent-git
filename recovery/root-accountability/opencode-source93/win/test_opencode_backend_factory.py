import types,unittest
from opencode_backend_factory import BackendFactory

class BackendFactoryTests(unittest.TestCase):
    def factory(self,gate,stored=None):
        self.calls=[]
        owner={'project':'fixture','role':'root','actor':'genuine-fixture','generation':'fixture','epoch':12}
        profile={'owner':owner,'provider_account_binding':'account'}
        def forbidden(*args):self.calls.append('effect');raise AssertionError('pre-effect denial failed')
        factory=BackendFactory(profile,'b'*64,lambda:stored,forbidden,lambda:None,lambda p:None,
            lambda c:None,lambda:gate,forbidden,forbidden,forbidden,forbidden,lambda:100)
        return factory,{'operation':'root-start','payload':{},'owner':owner,'key':'owned-key'}
    def test_unknown_admission_denies_before_key_or_process_or_journal(self):
        factory,command=self.factory({'provider':'zai-coding-plan','launch_allowed':False})
        with self.assertRaises(RuntimeError):factory.start(command)
        self.assertEqual(self.calls,[])
    def test_existing_intent_is_reconcile_only_before_new_effect(self):
        factory,command=self.factory({},stored={'phase':'start-pending'})
        with self.assertRaisesRegex(RuntimeError,'reconcile only'):factory.start(command)
        self.assertEqual(self.calls,[])
    def test_foreign_owner_or_model_payload_cannot_select_launch(self):
        factory,command=self.factory({})
        for update in ({'payload':{'model':'other'}},{'owner':{'actor':'other'}},{'operation':'opencode-controller-gate'}):
            with self.assertRaises(RuntimeError):factory.start(dict(command,**update))
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
