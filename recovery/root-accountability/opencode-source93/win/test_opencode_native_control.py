import copy,types,unittest,datetime
from opencode_native_control import NativeControl

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.state=[None];self.effects=[]
        self.owner={'project':'fixture','role':'root','actor':'native','generation':'gen','epoch':12}
        self.command={'owner':self.owner,'operation':'root-start','payload':{},'key':'owned','deadline':130}
        self.control=NativeControl({'project':'fixture','generation':'gen','host':'fixture'},{'id':'native'},
            lambda:copy.deepcopy(self.state[0]),lambda v:self.state.__setitem__(0,copy.deepcopy(v)),
            lambda:None,lambda:None,lambda c:self.effects.append('proof'),lambda:{},
            types.SimpleNamespace(read=lambda:None,start=lambda c:self.effects.append('launch') or {'model_turn_submitted':False}),
            None,lambda:100)
    def test_start_without_real_native_fence_denied_before_launch(self):
        with self.assertRaises(RuntimeError):self.control.execute(self.command)
        self.assertEqual(self.effects,[])
    def test_fence_then_start_requires_actual_final_guard(self):
        result=self.control.execute(dict(self.command,operation='root-fence-activate'))
        self.assertFalse(result['evidence']['model_started'])
        self.assertEqual(result['evidence']['fence_activation'],self.owner)
        self.assertNotIn('native_fence_owner',result['evidence'])
        self.control.execute(self.command)
        self.assertEqual(self.effects,['proof','proof','launch'])
    def test_foreign_or_expired_command_denied(self):
        for value in (dict(self.command,deadline=99),dict(self.command,owner=dict(self.owner,actor='other')),
                      dict(self.command,payload={'model':'other'})):
            with self.assertRaises(RuntimeError):self.control.execute(value)
        self.assertEqual(self.effects,[])
    def test_preacquire_admission_unknown_is_not_ready_or_model(self):
        receipt=self.control.execute(dict(self.command,operation='root-admission'))
        self.assertFalse(receipt['evidence']['admission']['ready'])
        self.assertFalse(receipt['evidence']['admission']['model_started'])
        self.assertEqual(self.effects,[])
        observed=receipt['evidence']['admission']['observed_at']
        self.assertEqual(datetime.datetime.fromisoformat(observed.replace('Z','+00:00')).timestamp(),100)
    def post_started(self):
        self.control.binding['provider_account_binding']='a'*64
        self.control.admission=lambda:dict(provider='zai-coding-plan',model='glm-5.3-flash',launch_allowed=True,
            physical_allowed=True,account_binding='a'*64,source_ref='own-fixture-monitor',resource_ref='own-fixture-resource',observed_at=100,valid_until=125)
        self.control.factory.read=lambda:{'phase':'completed'}
        self.state[0]=dict(phase='native-fence-active',owner=self.owner)
    def test_post_start_actual_authenticated_quiescence_allows_ready_without_model_effect(self):
        self.post_started();self.control.post_start_ready=lambda command:True
        r=self.control.execute(dict(self.command,operation='root-admission'))['evidence']['admission']
        self.assertTrue(r['ready']);self.assertFalse(r['draft']);self.assertFalse(r['model_started'])
        self.assertEqual(self.effects,[])
    def test_busy_or_unknown_history_holds_post_start_admission(self):
        self.post_started()
        for callback in (lambda command:False,lambda command:(_ for _ in ()).throw(RuntimeError('unknown own history'))):
            self.control.post_start_ready=callback
            r=self.control.execute(dict(self.command,operation='root-admission'))['evidence']['admission']
            self.assertFalse(r['ready']);self.assertTrue(r['draft'])
    def test_stale_owner_never_invokes_post_start_history_callback(self):
        self.post_started();self.state[0]['owner']=dict(self.owner,epoch=11)
        self.control.post_start_ready=lambda command:(_ for _ in ()).throw(AssertionError('must not use other owner history'))
        r=self.control.execute(dict(self.command,operation='root-admission'))['evidence']['admission']
        self.assertFalse(r['ready'])

if __name__=='__main__':unittest.main()
