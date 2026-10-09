import copy,hashlib,pathlib,unittest
from unittest.mock import patch
import opencode_runtime_profile as module
from opencode_controller_gate import ref
from opencode_controller_journal import ControllerJournal

class RuntimeProfileTests(unittest.TestCase):
    def setUp(self):
        self.dir=module.BASE/('preserving-'+'a'*64)
        self.owner={'project':'fixture','role':'root','actor':'native','generation':'win32:1:2','epoch':12}
        self.profile={'v':1,'runtime_mode':'opencode-native-v1','state_dir':str(self.dir),'source_manifest_sha256':'b'*64,
            'owner':self.owner,'native':{'id':'native','engine':'shell','workspace':'C:/Users/User/git/cloudflare-agent-git'},
            'controller_credential':{'scope':'fixed-root-controller','identity_id':'new-own','token':'sentinel-only'},
            'api_port':8814,'native_port':8816,'session_id':'ses_fixture','native_password':'x'*32,
            'provider':'zai-coding-plan','model':'glm-5.3-flash','agent':'root_contingency'}
    def test_candidate_profile_preserves_own_enrolled_identity(self):
        result=module.validate_profile(self.profile,self.dir,'b'*64)
        self.assertEqual(result,self.profile);self.assertIsNot(result,self.profile)
    def test_caretaker_old_identity_source_or_slot_cannot_bind(self):
        for key,value in (('controller_credential',dict(self.profile['controller_credential'],scope='fixed-host-caretaker')),
                          ('native',dict(self.profile['native'],id='old-actor')),('native_port',8815),
                          ('source_manifest_sha256','c'*64)):
            with self.assertRaises(RuntimeError):module.validate_profile(dict(self.profile,**{key:value}),self.dir,'b'*64)
    def test_actual_native_user_is_selected_not_caller_id(self):
        state=[None];selected={'body':'Fixed server prompt','input_sha256':hashlib.sha256(b'Fixed server prompt').hexdigest(),
            'owner_ref':ref(self.owner),'challenge':'nonce','envelope':'envelope','issued_at':100,'deadline':220}
        dispatch={'phase':'accepted','owner':self.owner,'session_id':'ses_fixture','selected':selected}
        kernel={'owner':self.owner,'native_actor':self.profile['native'],'session_id':'ses_fixture',
                'profile_sha256':'b'*64,'kernel_ref':'fixed-kernel'}
        journal=ControllerJournal(lambda:copy.deepcopy(state[0]),lambda v:state.__setitem__(0,copy.deepcopy(v)),lambda c:True)
        history=[{'info':{'role':'user','id':'msg_NATIVE','sessionID':'ses_fixture','time':{'created':101000}},
                  'parts':[{'type':'text','text':'Fixed server prompt'}]}]
        selector=module.ControllerInput(self.profile,lambda:copy.deepcopy(dispatch),journal,
            lambda:copy.deepcopy(kernel),lambda c:history,lambda:101)
        result=selector.current();self.assertEqual(result['user_message_id'],'msg_NATIVE')
        self.assertEqual(state[0]['context']['user_message_id'],'msg_NATIVE')
        self.assertEqual(selector.current(),result)
    def test_duplicate_or_foreign_user_never_seeds_context(self):
        self.test_actual_native_user_is_selected_not_caller_id()
        # Strict same-session/history uniqueness is exercised in the dispatcher
        # and native reader; profile rejects injected session paths pretransport.
        with self.assertRaises(RuntimeError):module.validate_profile(dict(self.profile,session_id='ses_bad/../config'),self.dir,'b'*64)

if __name__=='__main__':unittest.main()
