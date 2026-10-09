import types,unittest
from opencode_backend_api import BackendAPI

class BackendAPITests(unittest.TestCase):
    def test_prompt_guard_is_mandatory_and_fixed_provider_before_kernel(self):
        api=BackendAPI(None,lambda:(_ for _ in ()).throw(AssertionError('guard called')))
        payload={'model':{'providerID':'zai-coding-plan','modelID':'glm-5.3-flash'},'agent':'root_contingency',
                 'parts':[{'type':'text','text':'fixed source'}]}
        with self.assertRaises(RuntimeError):api.prompt_async(None,None,8815,'sentinel','ses_owned',payload,None)
        payload['model']['providerID']='zai'
        with self.assertRaises(RuntimeError):api.prompt_async(None,None,8815,'sentinel','ses_owned',payload,lambda:None)
    def test_config_prompt_or_foreign_slot_denied_before_kernel_or_auth(self):
        api=BackendAPI(None,lambda:(_ for _ in ()).throw(AssertionError('guard called')))
        for port,method,path,body in ((8815,'GET','/config',None),(8816,'POST','/session/ses_x/prompt_async',{}),
            (8801,'POST','/session',{}),(8815,'POST','/session',{'model':'anything'})):
            with self.assertRaises(RuntimeError):api.request(None,None,port,'sentinel',method,path,body)
    def test_new_session_is_once_and_actual_empty_history_required(self):
        api=BackendAPI(None,lambda:None);calls=[]
        def request(*args):
            method,path=args[4:6];calls.append((method,path))
            if path=='/global/health':return {'healthy':True}
            if path=='/session':return {'id':'ses_actualfixture'}
            return []
        api.request=request
        result=api(None,None,8815,'sentinel','create-session',{})
        self.assertEqual(result['initial_message_count'],0)
        self.assertEqual(calls.count(('POST','/session')),1)
    def test_uncertain_session_response_is_never_retried(self):
        api=BackendAPI(None,lambda:None);calls=[]
        def request(*args):
            method,path=args[4:6];calls.append((method,path))
            if path=='/global/health':return {'healthy':True}
            raise RuntimeError('lost response')
        api.request=request
        with self.assertRaises(RuntimeError):api(None,None,8815,'sentinel','create-session',{})
        self.assertEqual(calls.count(('POST','/session')),1)

if __name__=='__main__':unittest.main()
