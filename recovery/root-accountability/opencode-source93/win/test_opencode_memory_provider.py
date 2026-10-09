import json,unittest
from opencode_memory_provider import MemoryProvider,native_slot,NATIVE_ORIGIN,CODING_ORIGIN,ENV_KEY,PROVIDER,MODEL

class MemoryProviderTests(unittest.TestCase):
    def source(self,key='owned-fixture-key'):return {'provider':{PROVIDER:{'options':{'baseURL':NATIVE_ORIGIN,'apiKey':key}}}}
    def test_exact_machine_slot(self):self.assertEqual(native_slot(self.source()),'owned-fixture-key')
    def test_regular_provider_cannot_substitute(self):
        with self.assertRaises(ValueError):native_slot({'provider':{'zai':self.source()['provider'][PROVIDER]}})
    def test_route_drift_denied(self):
        for url in ('https://api.z.ai/api/paas/v4',NATIVE_ORIGIN+'/',NATIVE_ORIGIN+'?x=1','http://api.z.ai/api/anthropic'):
            with self.subTest(url=url):
                source=self.source();source['provider'][PROVIDER]['options']['baseURL']=url
                with self.assertRaises(ValueError):native_slot(source)
    def test_bad_key_denied(self):
        for key in (None,False,'',' ','bad\nkey'):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):native_slot(self.source(key))
    def test_secret_absent_config_and_repr(self):
        p=MemoryProvider('owned-fixture-key');self.assertNotIn('owned-fixture-key',json.dumps(p.config())+repr(p))
        self.assertEqual(p.config()['provider'][PROVIDER]['options']['apiKey'],'{env:'+ENV_KEY+'}')
    def test_fixed_endpoint_model_and_no_tools(self):
        c=MemoryProvider('owned-fixture-key').config()
        self.assertEqual(c['provider'][PROVIDER]['options']['baseURL'],CODING_ORIGIN)
        self.assertEqual(set(c['provider'][PROVIDER]['models']),{MODEL})
        self.assertEqual(c['permission'],{'*':'deny'});self.assertEqual(c['mcp'],{});self.assertEqual(c['plugin'],[])
    def test_environment_scrubs_other_credentials(self):
        env=MemoryProvider('owned-fixture-key').private_environment({'PATH':'fixture','OPENAI_API_KEY':'forbidden','HTTP_PROXY':'forbidden','OPENCODE_CONFIG_CONTENT':'forbidden'})
        self.assertEqual(env[ENV_KEY],'owned-fixture-key');self.assertNotIn('forbidden',json.dumps(env))
        self.assertNotIn('owned-fixture-key',env['OPENCODE_CONFIG_CONTENT'])
    def test_binding_matches_own_monitor_domain(self):
        import hashlib
        self.assertEqual(MemoryProvider('owned-fixture-key').account_binding_sha256,hashlib.sha256(b'own-ZCode-CodingPlan:owned-fixture-key').hexdigest())

if __name__=='__main__':unittest.main()
