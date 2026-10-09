"""Candidate fixed per-incarnation MCP/controller profile and input binding.

No global predecessor profile or caretaker credential alias. The reviewed cold
factory must write this private profile after genuine successor enrollment.
This module does not launch, enroll, acquire, or infer model completion.
"""
import copy,hashlib,pathlib,re
from opencode_controller_store import BASE,INCARNATION
from opencode_controller_gate import ref

HEX=re.compile(r'[0-9a-f]{64}\Z')
def validate_profile(profile,directory,expected_source_sha256):
    directory=pathlib.Path(directory)
    if directory.parent!=BASE or not INCARNATION.fullmatch(directory.name):
        raise RuntimeError('fixed native incarnation directory required')
    if (type(profile) is not dict or profile.get('v')!=1
        or profile.get('runtime_mode')!='opencode-native-v1'
        or profile.get('state_dir')!=str(directory)
        or profile.get('source_manifest_sha256')!=expected_source_sha256
        or type(expected_source_sha256) is not str or not HEX.fullmatch(expected_source_sha256)):
        raise RuntimeError('source-pinned own controller profile required')
    owner=profile.get('owner');native=profile.get('native');credential=profile.get('controller_credential')
    if (type(owner) is not dict or set(owner)!= {'project','role','actor','generation','epoch'}
        or owner['role']!='root' or type(owner['epoch']) is not int or owner['epoch']<1
        or any(type(owner[k]) is not str or not owner[k] for k in ('project','actor','generation'))
        or type(native) is not dict or native.get('id')!=owner['actor']
        or native.get('engine')!='shell' or native.get('workspace')!='C:/Users/User/git/cloudflare-agent-git'
        or type(credential) is not dict or set(credential)!= {'scope','identity_id','token'}
        or credential['scope']!='fixed-root-controller' or not credential['identity_id'] or not credential['token']):
        raise RuntimeError('new enrolled native owner/controller credential required')
    if (profile.get('api_port'),profile.get('native_port')) not in ((8813,8815),(8814,8816)):
        raise RuntimeError('fixed outer/inner native slot pair required')
    if (type(profile.get('session_id')) is not str or not re.fullmatch(r'ses_[A-Za-z0-9]+',profile['session_id'])
        or type(profile.get('native_password')) is not str or len(profile['native_password'])<32
        or profile.get('provider')!='zai-coding-plan' or profile.get('model')!='glm-5.3-flash'
        or profile.get('agent')!='root_contingency'):
        raise RuntimeError('fixed own authenticated native session/provider required')
    return copy.deepcopy(profile)

class ControllerInput:
    def __init__(self,profile,dispatch_read,journal,kernel_reader,history_reader,clock):
        self.profile=profile;self.dispatch_read=dispatch_read;self.journal=journal
        self.kernel=kernel_reader;self.history=history_reader;self.clock=clock
    def current(self):
        dispatch=self.dispatch_read();owner=self.profile['owner'];sid=self.profile['session_id']
        if (type(dispatch) is not dict or dispatch.get('phase') not in ('dispatch-pending','accepted')
            or dispatch.get('owner')!=owner or dispatch.get('session_id')!=sid):
            raise RuntimeError('own durable server input dispatch absent')
        selected=dispatch['selected'];kernel=self.kernel()
        if (type(selected) is not dict or type(selected.get('body')) is not str
            or hashlib.sha256(selected['body'].encode()).hexdigest()!=selected.get('input_sha256')
            or selected.get('owner_ref')!=ref(owner) or kernel.get('owner')!=owner
            or kernel.get('native_actor')!=self.profile['native']
            or kernel.get('session_id')!=sid):
            raise RuntimeError('same owner/session/kernel/server input required')
        previous=self.journal.read()
        if previous is not None and previous.get('context',{}).get('envelope')==selected['envelope']:
            context=previous['context']
            if (context.get('owner')!=owner or context.get('session_id')!=sid
                or context.get('kernel_ref')!=kernel['kernel_ref']
                or context.get('user_input_sha256')!=selected['input_sha256']):
                raise RuntimeError('selected durable input differs from current native source')
            return copy.deepcopy(context)
        base={'owner':owner,'kernel':kernel,'session_id':sid,'user_message_id':None,
            'user_input_sha256':selected['input_sha256'],'provider_id':self.profile['provider'],
            'model_id':self.profile['model'],'agent':self.profile['agent'],
            'nonce':selected['challenge'],'envelope':selected['envelope'],
            'challenge_ref':selected['challenge'],'issued_at_ms':selected['issued_at']*1000,
            'deadline_ms':selected['deadline']*1000,'profile_sha256':kernel['profile_sha256'],
            'kernel_ref':kernel['kernel_ref'],'revision':1}
        users=[]
        for item in self.history(base):
            info=item.get('info',{})
            if info.get('role')!='user':continue
            text=''.join(p.get('text','') for p in item.get('parts',[]) if p.get('type')=='text')
            if hashlib.sha256(text.encode()).hexdigest()==selected['input_sha256']:users.append(info)
        if (len(users)!=1 or users[0].get('sessionID')!=sid or not users[0].get('id')
            or type(users[0].get('time',{}).get('created')) not in (int,float)
            or not selected['issued_at']-1<=users[0]['time']['created']/1000<selected['deadline']):
            raise RuntimeError('actual unique native selected user event required')
        if self.kernel()!=kernel or self.dispatch_read()!=dispatch:
            raise RuntimeError('native source changed while selecting actual user event')
        base.update(user_message_id=users[0]['id'],input_accepted_at_ms=users[0]['time']['created'])
        self.journal.select_input(base)
        return base
