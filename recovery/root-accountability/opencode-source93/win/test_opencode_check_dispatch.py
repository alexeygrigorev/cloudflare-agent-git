import unittest
from opencode_check_dispatch import quiescent,CheckDispatch

class DispatchTests(unittest.TestCase):
    def test_real_current_history_quiescence_requires_assistant_completion(self):
        info=dict(role='assistant',sessionID='ses_owned',time=dict(completed=1000))
        self.assertTrue(quiescent([dict(info=info,parts=[])],'ses_owned'))
        self.assertFalse(quiescent([dict(info=dict(info,role='user'),parts=[])],'ses_owned'))
        self.assertFalse(quiescent([dict(info=info,parts=[dict(type='tool',state=dict(status='running'))])],'ses_owned'))
        self.assertFalse(quiescent([dict(info=dict(info,sessionID='ses_other'),parts=[])],'ses_owned'))
    def test_foreign_check_denied_before_authority_or_native(self):
        effects=[];owner=dict(project='fixture',role='root',actor='a',generation='g',epoch=12)
        check=CheckDispatch(owner,'ses_owned','account',{},'a'*64,
            lambda *args:effects.append('authority'),lambda:None,lambda v:None,lambda:[],
            lambda *args:effects.append('native'),lambda:{},lambda c:None,lambda:None,
            lambda v:'archive',lambda pin:{})
        with self.assertRaises(RuntimeError):check(dict(owner=owner,operation='root-check',payload={'body':'chosen'}))
        self.assertEqual(effects,[])

if __name__=='__main__':unittest.main()
