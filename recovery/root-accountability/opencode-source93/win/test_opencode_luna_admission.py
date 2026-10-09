import unittest
from types import SimpleNamespace
from opencode_luna_admission import LunaAdmission,OP

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.cache=[];self.calls=[];self.now=100
        self.quota=SimpleNamespace(read_limits=lambda exe:({'rateLimits':{'primary':{'resetsAt':1000}}},{'type':'chatgpt'}),
            account_fingerprint=lambda a:'own',decision=lambda l,a:(False,'reserve gate'))
        self.a=LunaAdmission({'id':'native'},{'actor':'root'},'fixed.exe','pin','own',self.quota,
            lambda:'pin',lambda c:self.calls.append(c),self.cache.append,lambda:self.now)
        self.command={'operation':OP,'payload':{},'owner':{'actor':'root'},'key':'fixed'}
    def test_real_projection_cached_and_redacted(self):
        r=self.a.execute(self.command)
        self.assertEqual(r['v'],1);self.assertEqual(r['evidence']['status'],'RESERVE_DENIED')
        self.assertEqual(r['evidence']['next_trigger'],1000)
        self.assertEqual(self.cache,[r['evidence']]);self.assertNotIn('limits',r['evidence'])
        self.assertEqual(len(self.calls),2)
    def test_unknown_is_not_denial(self):
        self.quota.decision=lambda l,a:(False,'missing limits')
        self.assertEqual(self.a.execute(self.command)['evidence']['status'],'READ_UNKNOWN')
    def test_foreign_account_or_binary_holds(self):
        self.quota.account_fingerprint=lambda a:'foreign'
        self.assertEqual(self.a.execute(self.command)['evidence']['status'],'READ_UNKNOWN')
        self.assertIsNone(self.cache[-1]['source_ref'])
    def test_model_cannot_supply_fields_or_read(self):
        self.command['payload']={'account':'foreign'}
        with self.assertRaises(RuntimeError):self.a.execute(self.command)
        self.assertFalse(self.cache);self.assertFalse(self.calls)
    def test_provider_denial_distinct_from_allowed(self):
        self.quota.decision=lambda l,a:(False,'account limit reached')
        self.assertEqual(self.a.execute(self.command)['evidence']['status'],'PROVIDER_DENIED')
        self.quota.decision=lambda l,a:(True,'fresh known windows above reserve')
        self.assertTrue(self.a.execute(self.command)['evidence']['launch_allowed'])
    def test_actual_ordinary_usage_refusal_dominates_reserve(self):
        self.quota.read_limits=lambda exe:({'ordinaryUsageAllowed':False,'rateLimits':{'primary':{'resetsAt':1000}}},{'type':'chatgpt'})
        self.quota.decision=lambda l,a:(True,'fresh known windows above reserve')
        r=self.a.execute(self.command)['evidence']
        self.assertEqual(r['status'],'PROVIDER_DENIED');self.assertFalse(r['launch_allowed'])

if __name__=='__main__':unittest.main()
