"""Factory-only immutable controller profile/binding, before first prompt.

All values are constructor-owned native/enrollment/plan records. No caller/model
upload, manufactured credential, predecessor alias or global profile overwrite.
"""
import copy,hashlib,json,pathlib,re

def encoded(value):return json.dumps(value).encode()

class ProfileWriter:
    def __init__(self,directory,load,save,verify_private,identity_guard,kernel_reader,plan_reader):
        self.directory=pathlib.Path(directory);self.load=load;self.save=save;self.verify=verify_private
        self.identity=identity_guard;self.kernel=kernel_reader;self.plan=plan_reader
    def write(self,enrolled,backend,controller_credential):
        self.verify(self.directory);self.identity(enrolled)
        if (type(controller_credential) is not dict or set(controller_credential)!= {'scope','identity_id','token'}
            or controller_credential.get('scope')!='fixed-root-controller'
            or not controller_credential.get('identity_id') or not controller_credential.get('token')):
            raise RuntimeError('genuine own enrolled fixed-root-controller credential missing')
        if (backend.get('owner')!=enrolled.get('owner') or backend.get('model_turn_submitted') is not False
            or not re.fullmatch('ses_[A-Za-z0-9]+',backend.get('session_id',''))):
            raise RuntimeError('actual same-owner empty native session required')
        plan=self.plan();kernel=self.kernel()
        if (plan.get('controller_source_manifest_sha256')!=enrolled.get('controller_source_manifest_sha256')
            or kernel.get('owner')!=enrolled['owner'] or kernel.get('native_actor')!=enrolled['native']
            or kernel.get('backend')!=backend.get('backend') or kernel.get('job_name')!=backend.get('job_name')):
            raise RuntimeError('fixed accepted source/current native kernel mismatch')
        profile={'v':1,'runtime_mode':'opencode-native-v1','state_dir':str(self.directory),
            'source_manifest_sha256':enrolled['controller_source_manifest_sha256'],
            'execution_plan_sha256':enrolled['execution_plan_sha256'],
            'owner':enrolled['owner'],'native':enrolled['native'],'controller_credential':controller_credential,
            'api_port':enrolled['api_port'],'native_port':enrolled['native_port'],
            'session_id':backend['session_id'],'native_password':backend['native_password'],
            'provider':'zai-coding-plan','model':'glm-5.3-flash','agent':'root_contingency',
            'kernel':kernel,'authority':plan['authority'],'snapshot_sha256':plan['snapshot_sha256']}
        profile_path=self.directory/'opencode-controller.private.json'
        binding_path=self.directory/'opencode-controller-binding.private.json'
        intent_path=self.directory/'opencode-controller-profile-intent.private.json'
        profile_sha=hashlib.sha256(encoded(profile)).hexdigest()
        binding={'v':1,'state_dir':str(self.directory),'source_manifest_sha256':profile['source_manifest_sha256'],
                 'profile_sha256':profile_sha}
        intent={'v':1,'owner':profile['owner'],'phase':'profile-write-pending',
                'profile_sha256':profile_sha,'binding':binding}
        if intent_path.exists():
            previous=self.load(intent_path)
            if (type(previous) is not dict or previous.get('phase') not in ('profile-write-pending','completed')
                or dict(previous,phase='profile-write-pending')!=intent):
                raise RuntimeError('unknown or different profile intent held')
        else:self.save(intent_path,intent)
        self.identity(enrolled)
        if self.kernel()!=kernel:raise RuntimeError('kernel changed before controller profile write')
        for path,value in ((profile_path,profile),(binding_path,binding)):
            if path.exists():
                if self.load(path)!=value:raise RuntimeError('immutable private controller file differs')
            else:self.save(path,value)
            self.verify(path)
            if self.load(path)!=value:raise RuntimeError('private controller write/readback differs')
        if hashlib.sha256(profile_path.read_bytes()).hexdigest()!=profile_sha:
            raise RuntimeError('private controller serialized profile pin differs')
        self.save(intent_path,dict(intent,phase='completed'))
        if self.load(intent_path)!=dict(intent,phase='completed'):
            raise RuntimeError('controller profile completion readback differs')
        return {'profile_sha256':profile_sha,'source_manifest_sha256':profile['source_manifest_sha256'],
                'model_turn_submitted':False,'authority_effect':False}
