"""Single fixed read operation on the existing authenticated NativeChannels.

No role effects, model launch, arbitrary paths or caller proof fields. Every
projection is derived during one pinned controller observation/revision.
"""
import copy,hashlib,json,time

OP='opencode-native-observation'
def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class ObservationChannel:
    def __init__(self,native,owner,source_sha256,context_reader,history_reader,kernel_reader,command_guard,clock=time.time,batch_reader=None):
        self.native=copy.deepcopy(native);self.owner=copy.deepcopy(owner);self.source_sha256=source_sha256
        self.context_reader=context_reader;self.history_reader=history_reader;self.kernel_reader=kernel_reader
        self.command_guard=command_guard;self.clock=clock
        if not callable(batch_reader):raise ValueError('fixed atomic helper-batch reader required')
        self.batch_reader=batch_reader
    def execute(self,command):
        if (type(command) is not dict or command.get('operation')!=OP or command.get('payload')!={}
            or command.get('owner')!=self.owner or type(command.get('key')) is not str or not command['key']):
            raise RuntimeError('fixed authenticated observation command required')
        self.command_guard(command) # existing authenticated source/sink command
        batch=self.batch_reader();context=batch['context'];before=self.kernel_reader()
        if (set(batch)!={'revision','context','helper_contexts'} or type(batch['helper_contexts']) is not list
            or not batch['helper_contexts'] or context!=batch['helper_contexts'][-1]
            or any(h.get('revision')!=batch['revision'] or h.get('owner_ref')!=context.get('owner_ref')
                or h.get('session_id')!=context.get('session_id') or h.get('user_message_id')!=context.get('user_message_id')
                or h.get('profile_sha256')!=context.get('profile_sha256') for h in batch['helper_contexts'])):
            raise RuntimeError('single selected-input helper batch required')
        if not self.bound(context,before):raise RuntimeError('current owner/native kernel/profile binding absent')
        history=self.history_reader(context)
        after=self.kernel_reader();latest_batch=self.batch_reader();latest=self.context_reader()
        if batch!=latest_batch or context!=latest or before!=after or not self.bound(latest,after):
            raise RuntimeError('native observation changed across fixed read')
        self.command_guard(command)
        evidence={'v':1,'discriminator':'opencode-native-v1','source_sha256':self.source_sha256,
            'observed_at':self.clock(),'revision':context['revision'],'context':context,'helper_contexts':batch['helper_contexts'],'history':history,
            'kernel_before':before,'kernel_after':after,'authority_effect':False}
        evidence['projection_sha256']=sha(evidence)
        return {'v':1,'key':command['key'],'owner':self.owner,'operation':OP,'payload':{},
            'state':'completed','native_actor':self.native,'evidence':evidence}
    def bound(self,context,kernel):
        expected=sha([self.owner[k] for k in ('project','role','actor','generation','epoch')])
        return (type(context) is dict and type(kernel) is dict and context.get('owner_ref')==expected
            and kernel.get('native_actor')==self.native and kernel.get('owner')==self.owner
            and kernel.get('profile_sha256')==context.get('profile_sha256')
            and kernel.get('kernel_ref')==context.get('kernel_ref') and kernel.get('session_id')==context.get('session_id')
            and kernel.get('job',{}).get('queried') is True
            and type(kernel.get('job',{}).get('active_processes')) is int and kernel['job']['active_processes']>0
            and type(kernel.get('processes')) is list and len(kernel['processes'])>=4
            and all(type(p) is dict and type(p.get('pid')) is int and p['pid']>0
                and type(p.get('creation_filetime')) is int and p['creation_filetime']>0
                and p.get('session_id')==2 and p.get('state')=='alive' for p in kernel['processes']))
