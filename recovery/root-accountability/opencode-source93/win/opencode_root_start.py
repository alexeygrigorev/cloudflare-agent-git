"""Existing root-start evidence, collected before any model input.

This adapter consumes only its retained factory/native readers. A journal is
an intent, never proof of live custody or empty history. Replay reconciles the
same session and handles without invoking backend/session creation again.
"""
import copy,hashlib,json,re,threading,time

def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class RootStart:
    def __init__(self,factory,enrolled,credential,profile_writer,profile_reader,
                 custody_factory,history_reader,read,save,command_guard,source_sha256,
                 clock=time.time):
        self.factory=factory;self.enrolled=enrolled;self.credential=credential
        self.writer=profile_writer;self.profile_reader=profile_reader
        self.custody_factory=custody_factory;self.history_reader=history_reader
        self.read_receipt=read;self.save=save;self.guard=command_guard
        self.source=source_sha256;self.clock=clock;self.lock=threading.Lock()
    def read(self):return self.factory.read()
    def start(self,command):
        with self.lock:
            self.guard(command)
            selected=copy.deepcopy(self.enrolled())
            if (command.get('operation')!='root-start' or command.get('payload')!={}
                or selected.get('owner')!=command.get('owner')
                or not re.fullmatch('[0-9a-f]{64}',selected.get('holding_profile_sha256',''))
                or not re.fullmatch('[0-9a-f]{64}',self.source)):
                raise RuntimeError('fixed elected root-start/source required')
            old=self.factory.read()
            if old is None:
                # Owner came from the authenticated fence, not enrollment epoch1.
                self.factory.profile.update(owner=copy.deepcopy(command['owner']))
                self.factory.start(command)
                old=self.factory.read()
            if (type(old) is not dict or old.get('phase')!='native-session-ready'
                or old.get('owner')!=command['owner'] or old.get('key')!=command['key']
                or old.get('model_turn_submitted') is not False
                or self.factory.backend is None or self.factory.job is None):
                raise RuntimeError('uncertain previous start requires retained-handle reconciliation')
            written=self.writer.write(selected,old,self.credential())
            profile=self.profile_reader()
            if (profile.get('owner')!=command['owner'] or profile.get('session_id')!=old['session_id']
                or sha_source_profile(profile)!=written['profile_sha256']):
                raise RuntimeError('immutable controller profile differs')
            custody=self.custody_factory(profile,written['profile_sha256'])
            before=custody();history=self.history_reader(old);after=custody()
            if (history!=[] or before!=after or before.get('owner')!=command['owner']
                or before.get('native_actor')!=selected['native']
                or before.get('profile_sha256')!=written['profile_sha256']
                or before.get('session_id')!=old['session_id']
                or before.get('job',{}).get('queried') is not True
                or type(before['job'].get('active_processes')) is not int
                or before['job']['active_processes']<1
                or not before.get('kernel_ref')):
                raise RuntimeError('fresh same-profile/session empty-history custody required')
            self.guard(command)
            identity={'v':1,'discriminator':'opencode-native-v1','source_sha256':self.source,
                'owner':copy.deepcopy(command['owner']),'native_actor':copy.deepcopy(selected['native']),
                'profile_sha256':written['profile_sha256'],'kernel_ref':before['kernel_ref'],
                'holding_profile_sha256':selected['holding_profile_sha256'],
                'session_id':old['session_id'],'provider_id':'zai-coding-plan','model_id':'glm-5.3-flash',
                'revision':1,'history_empty':True,'initial_message_count':0,
                'history_receipt_sha256':sha(history),'kernel_before':before,'kernel_after':after,
                'model_turn_submitted':False,'authority_effect':False}
            previous=self.read_receipt()
            if previous is not None:
                if (type(previous) is not dict or previous.get('key')!=command['key']
                    or previous.get('phase')!='completed' or previous.get('identity_sha256')!=sha(identity)):
                    raise RuntimeError('conflicting root-start receipt preserved')
                return copy.deepcopy(previous['evidence'])
            evidence=dict(identity,observed_at=self.clock())
            record={'v':1,'phase':'completed','key':command['key'],
                'identity_sha256':sha(identity),'evidence':evidence}
            self.save(record)
            if self.read_receipt()!=record:raise RuntimeError('root-start receipt readback differs')
            return evidence

def sha_source_profile(profile):
    # Matches the pinned private_writer/ProfileWriter serialization exactly.
    return hashlib.sha256(json.dumps(profile).encode()).hexdigest()
