import json,pathlib,tempfile,types,unittest
from unittest.mock import patch
from opencode_native_factory import NativeFactory,sha

class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name);self.profile=self.root/'api-runtime.private.json'
        self.source=self.root/'source';self.source.mkdir()
        self.old=dict(runtime_mode='api-root',actor='old',generation='gen',api_port=8813,
            project='fixture',authority_url='https://fixture:8801',ca_certificate='fixed',client_certificate='fixed',
            client_key='fixed',python_exe='fixed',python_sha256='a'*64,aplexer_exe='fixed',aplexer_sha256='b'*64,
            workspace='fixed',expected_host='fixed',controller_credential={'token':'old-secret'})
        self.profile.write_text(json.dumps(self.old));self.effects=[]
        self.plan=dict(native_shell_sha256='c'*64,controller_source_manifest_sha256='d'*64,
            execution_plan_sha256='e'*64,provider_account_binding='account')
        self.factory=NativeFactory(self.profile,self.source,self.plan,lambda p:json.loads(p.read_bytes()),
            lambda p,v:p.write_text(json.dumps(v)),lambda p:p.mkdir(parents=True,exist_ok=True),lambda pid:{},lambda:None,lambda:{'pid':1})
        self.permit=dict(operation='fixed-preserving-successor',challenge='nonce',owner={'actor':'old','generation':'gen'},
            profile_sha256=sha(self.profile),predecessor_api_port=8813,new_api_port=8814)
    def fake_startup(self):
        return patch('opencode_full_startup.FullStartup',return_value=types.SimpleNamespace(documents=lambda:[],entries=[]))
    def test_holding_clears_predecessor_credentials_and_binds_both_native_slots(self):
        with self.fake_startup(),patch('opencode_native_factory.free_pair') as ports:
            result=self.factory.prepare(self.permit)
            new=json.loads(self.profile.read_bytes())
            self.assertEqual((new['api_port'],new['native_port']),(8814,8816))
            self.assertNotIn('controller_credential',new)
            self.assertIsNone(new['credential']);self.assertIsNone(new['owner'])
            self.assertEqual(new['root_runtime_kind'],'opencode-native-v1')
            self.assertEqual(pathlib.Path(result['state_dir']).name,'preserving-'+__import__('hashlib').sha256(b'nonce').hexdigest())
            self.assertEqual(self.factory.prepare(self.permit),result)
    def test_occupied_slot_denies_before_profile_write(self):
        before=self.profile.read_bytes()
        with patch('opencode_native_factory.free_pair',side_effect=RuntimeError('occupied')):
            with self.assertRaises(RuntimeError):self.factory.prepare(self.permit)
        self.assertEqual(self.profile.read_bytes(),before)
    def test_wrong_predecessor_profile_is_preserved(self):
        before=self.profile.read_bytes();self.permit['profile_sha256']='f'*64
        with self.assertRaises(RuntimeError):self.factory.prepare(self.permit)
        self.assertEqual(self.profile.read_bytes(),before)

if __name__=='__main__':unittest.main()
