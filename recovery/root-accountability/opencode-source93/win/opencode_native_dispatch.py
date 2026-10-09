"""One durable server-selected input dispatch on the fixed owned native session.

Uses supported OpenCode prompt_async (204, no completed-model claim). A lost
response is reconcile-only against authenticated own history, NEVER a resend.
No model selects provider/session/body or supplies admission proof.
"""
import copy,hashlib,time,threading,json,re

PROVIDER='zai-coding-plan';MODEL='glm-5.3-flash';AGENT='root_contingency'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class NativeDispatch:
    def __init__(self,owner,session_id,account_binding,read,save,owned_history,native_post,
                 admission,current_guard,clock=time.time,completed_reply_reader=None,archive=None,quiescent=None,archive_reader=None):
        if owner.get('role')!='root' or type(session_id) is not str or not re.fullmatch(r'ses_[A-Za-z0-9]+',session_id):
            raise ValueError('genuine selected root native session required')
        self.owner=copy.deepcopy(owner);self.session_id=session_id;self.account_binding=account_binding
        self.read=read;self.save=save;self.history=owned_history;self.post=native_post
        self.admission=admission;self.guard=current_guard;self.clock=clock
        self.lock=threading.Lock() # one owned controller; no RPC under this lock
        self.completed_reply_reader=completed_reply_reader;self.archive=archive;self.quiescent=quiescent
        self.archive_reader=archive_reader
    def validate_input(self,selected):
        if (type(selected) is not dict or type(selected.get('body')) is not str or not selected['body']
            or hashlib.sha256(selected['body'].encode()).hexdigest()!=selected.get('input_sha256')
            or not selected.get('challenge') or not selected.get('envelope')
            or type(selected.get('issued_at')) not in (int,float)
            or type(selected.get('deadline')) not in (int,float)
            or not selected['issued_at']-1<=self.clock()<selected['deadline']
            or not 0<selected['deadline']-selected['issued_at']<=120):
            raise RuntimeError('fresh fixed server input required')
        self.guard(self.owner,self.session_id,selected)
    def dispatch(self,selected):
        self.validate_input(selected)
        previous=self.read()
        if previous is not None:
            if type(previous) is not dict:raise RuntimeError('malformed present native dispatch held')
            if previous.get('phase')=='released':
                if (previous.get('owner')!=self.owner or previous.get('session_id')!=self.session_id
                    or not callable(self.archive_reader)):
                    raise RuntimeError('durable authenticated release archive required')
                archived=self.archive_reader(previous.get('archive_sha256'))
                if (digest(archived)!=previous.get('archive_sha256')
                    or archived.get('completion',{}).get('native_reply_receipt_ref')!=previous.get('native_reply_receipt_ref')
                    or archived.get('dispatch',{}).get('owner')!=self.owner
                    or archived.get('dispatch',{}).get('session_id')!=self.session_id):
                    raise RuntimeError('released record archive binding differs')
            else:
                if (type(previous) is not dict or previous.get('phase') not in ('dispatch-pending','accepted')
                    or previous.get('owner')!=self.owner or previous.get('session_id')!=self.session_id
                    or previous.get('selected')!=selected):
                    raise RuntimeError('unknown or other native input intent held')
                return self.reconcile(selected) # never invoke native_post again
        gate=self.admission()
        if (type(gate) is not dict or gate.get('provider')!=PROVIDER or gate.get('model')!=MODEL
            or gate.get('account_binding')!=self.account_binding or gate.get('launch_allowed') is not True
            or gate.get('physical_allowed') is not True or not gate.get('source_ref')
            or not gate.get('resource_ref') or type(gate.get('observed_at')) not in (int,float)
            or type(gate.get('valid_until')) not in (int,float)
            or not gate['observed_at']<=self.clock()<gate['valid_until']<=gate['observed_at']+30):
            raise RuntimeError('fresh own provider and physical pre-effect admission denied')
        self.validate_input(selected)
        intent={'v':1,'phase':'dispatch-pending','owner':self.owner,'session_id':self.session_id,
                'selected':copy.deepcopy(selected),'provider_gate_ref':gate['source_ref'],
                'resource_gate_ref':gate['resource_ref'],'recorded_at':self.clock()}
        with self.lock:
            if self.read()!=previous:raise RuntimeError('concurrent native dispatch already reserved')
            self.save(intent) # durable before model effect; crash/timeout holds
        # Recheck freshness after durable save immediately before POST/spend.
        self.validate_input(selected)
        if not self.clock()<gate['valid_until']:raise RuntimeError('admission expired before native dispatch')
        result=self.post('/session/'+self.session_id+'/prompt_async',
            {'model':{'providerID':PROVIDER,'modelID':MODEL},'agent':AGENT,
             'parts':[{'type':'text','text':selected['body']}]})
        if result!={'status':204}:raise RuntimeError('native input response uncertain; reconcile only')
        with self.lock:
            latest=self.read()
            if (type(latest) is not dict or latest.get('owner')!=self.owner
                or latest.get('selected')!=selected or latest.get('phase') not in ('dispatch-pending','accepted')):
                raise RuntimeError('native dispatch record changed; reconcile only')
            self.save(dict(latest,phase='accepted',native_accepted_at=self.clock(),model_completed=False))
        return {'input_accepted':True,'model_completed':False,'authority_effect':False}
    def reconcile(self,selected):
        self.validate_input(selected)
        users=[]
        for item in self.history():
            info=item.get('info',{})
            if info.get('role')!='user':continue
            text=''.join(p.get('text','') for p in item.get('parts',[]) if p.get('type')=='text')
            if hashlib.sha256(text.encode()).hexdigest()==selected['input_sha256']:
                if (info.get('sessionID')!=self.session_id or not info.get('id')
                    or type(info.get('time',{}).get('created')) not in (int,float)
                    or not selected['issued_at']-1<=info['time']['created']/1000<selected['deadline']):
                    raise RuntimeError('native selected user event binding held')
                users.append(info)
        if len(users)!=1:raise RuntimeError('actual unique native input acceptance not yet reconciled')
        self.guard(self.owner,self.session_id,selected)
        with self.lock:
            previous=self.read()
            if (type(previous) is not dict or previous.get('selected')!=selected
                or previous.get('owner')!=self.owner or previous.get('session_id')!=self.session_id
                or previous.get('phase') not in ('dispatch-pending','accepted')
                or previous.get('native_user_message_id',users[0]['id'])!=users[0]['id']):
                raise RuntimeError('native dispatch intent changed')
            self.save(dict(previous,phase='accepted',native_user_message_id=users[0]['id'],
                           native_input_at_ms=users[0]['time']['created'],model_completed=False))
        return {'input_accepted':True,'user_message_id':users[0]['id'],
                'input_accepted_at_ms':users[0]['time']['created'],'model_completed':False,'authority_effect':False}
    def release_prior(self):
        """Outside controller only, from authentic completed SERVER reply receipt.

        A helper return/204 never qualifies. Archive precedes clearing; an
        interrupted archive is immutable/replayable only for the identical
        record. No network/native read takes place under the writer lock.
        """
        previous=self.read()
        if (type(previous) is not dict or previous.get('phase')!='accepted'
            or previous.get('owner')!=self.owner or previous.get('session_id')!=self.session_id
            or not previous.get('native_user_message_id')
            or not all(callable(f) for f in (self.completed_reply_reader,self.archive,self.quiescent))):
            raise RuntimeError('owned accepted input and fixed completion collectors required')
        selected=previous['selected']
        self.guard(self.owner,self.session_id,selected)
        completion=self.completed_reply_reader(copy.deepcopy(previous))
        if (type(completion) is not dict or completion.get('owner')!=self.owner
            or completion.get('session_id')!=self.session_id or completion.get('envelope')!=selected['envelope']
            or completion.get('challenge')!=selected['challenge']
            or completion.get('input_sha256')!=selected['input_sha256']
            or completion.get('response_completed') is not True
            or not completion.get('native_reply_receipt_ref')
            or type(completion.get('completed_at')) not in (int,float)
            or not selected['issued_at']<=completion['completed_at']<selected['deadline']):
            raise RuntimeError('actual current-owner completed reply binding absent')
        if self.quiescent(self.session_id) is not True:
            raise RuntimeError('native productive turn/pending helper must be preserved')
        self.guard(self.owner,self.session_id,selected)
        with self.lock:
            if self.read()!=previous:raise RuntimeError('prior input changed during authenticated collection')
            archived={'v':1,'dispatch':previous,'completion':completion}
            archive_sha=digest(archived)
            if self.archive(archived)!=archive_sha:raise RuntimeError('immutable release archive readback required')
            self.save({'v':1,'phase':'released','owner':self.owner,'session_id':self.session_id,
                       'archive_sha256':archive_sha,'native_reply_receipt_ref':completion['native_reply_receipt_ref']})
        return {'released':True,'native_reply_receipt_ref':completion['native_reply_receipt_ref'],
                'envelope':selected['envelope'],'authority_effect':False,'check_completed':False}
