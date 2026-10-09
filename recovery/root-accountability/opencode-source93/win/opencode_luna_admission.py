"""Fixed nonpaid native admission read; no model, role effect or caller identity.

The production constructor binds the reviewed native quota module, pinned binary,
expected own account fingerprint and private durable cache writer. RPC occurs
outside authority transactions. Unknown is never evidence of a reserve denial.
"""
import hashlib,json,math,time

OP='opencode-luna-admission'
def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class LunaAdmission:
    def __init__(self,native,owner,executable,executable_sha256,account_binding,quota_module,
                 binary_digest,command_guard,persist,clock=time.time):
        self.native=native;self.owner=owner;self.executable=executable
        self.executable_sha256=executable_sha256;self.account_binding=account_binding
        self.quota=quota_module;self.binary_digest=binary_digest;self.command_guard=command_guard
        self.persist=persist;self.clock=clock
    def execute(self,command):
        if (type(command) is not dict or command.get('operation')!=OP
            or command.get('payload')!={} or command.get('owner')!=self.owner
            or type(command.get('key')) is not str or not command['key']):
            raise RuntimeError('fixed authenticated admission read required')
        self.command_guard(command)
        started=self.clock();status='READ_UNKNOWN';next_trigger=None;source=None
        try:
            if self.binary_digest()!=self.executable_sha256:raise ValueError('binary pin')
            limits,account=self.quota.read_limits(self.executable)
            if self.quota.account_fingerprint(account)!=self.account_binding:raise ValueError('account binding')
            allowed,reason=self.quota.decision(limits,account.get('type'))
            if self.binary_digest()!=self.executable_sha256:raise ValueError('binary changed')
            if limits.get('ordinaryUsageAllowed') is False:status='PROVIDER_DENIED'
            elif reason=='reserve gate':status='RESERVE_DENIED'
            elif reason=='account limit reached':status='PROVIDER_DENIED'
            elif allowed and reason=='fresh known windows above reserve':status='ALLOWED'
            buckets=limits.get('rateLimitsByLimitId')
            if buckets is None:buckets={'legacy':limits.get('rateLimits')}
            resets=[w['resetsAt'] for b in buckets.values() if type(b) is dict
                    for n in ('primary','secondary') for w in [b.get(n)]
                    if type(w) is dict and type(w.get('resetsAt')) in (int,float)
                    and math.isfinite(w['resetsAt']) and w['resetsAt']>self.clock()]
            next_trigger=min(resets) if resets else None
            source=sha({'account_binding':self.account_binding,'limits':limits,
                        'binary_sha256':self.executable_sha256,'started_at':started})
        except Exception:
            status='READ_UNKNOWN';source=None;next_trigger=None
        observed=self.clock()
        if observed-started>60 or observed<started:status='READ_UNKNOWN';source=None
        projection={'v':1,'provider':'openai-codex','status':status,
            'launch_allowed':status=='ALLOWED','account_binding':self.account_binding,
            'source_ref':source,'observed_at':observed,'valid_until':observed+60,
            'actual_upstream_read':source is not None and status!='READ_UNKNOWN',
            'next_trigger':next_trigger,'model_started':False,'authority_effect':False}
        self.command_guard(command)
        self.persist(projection) # private cache before any server SQL consumption
        return {'v':1,'key':command['key'],'owner':self.owner,'operation':OP,
                'payload':{},'state':'completed','native_actor':self.native,'evidence':projection}
