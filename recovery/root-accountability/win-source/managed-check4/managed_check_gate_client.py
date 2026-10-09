"""Fixed pre-spend client for a managed SDK check.

The host supplies authenticated RPC/HTTPS, private bound state, native custody,
physical measurement and private receipt persistence. No model arguments enter
this class. It cannot weaken the server role gate or choose a provider/model.
"""
import copy,hashlib,json,time,datetime
from win35_quota_gate import decision,account_fingerprint


class FixedManagedAdmission:
    def __init__(self, binding, request, rpc, physical, persist, expected_account):
        self.binding=binding;self.request=request;self.rpc=rpc
        self.physical=physical;self.persist=persist;self.expected_account=expected_account

    def _gate(self, state, phase, envelope):
        if (phase not in ('thread-start','turn-start') or not isinstance(envelope,str) or not envelope
                or self.binding()!=state):
            raise RuntimeError('managed admission binding changed')
        response=self.request(dict(state['owner'],v=1,op='root_check_gate',check_envelope=envelope,
                                   parent_turn_id=state['turn_id'],phase=phase))
        if response.get('v')!=1 or response.get('status')!='ok' or not isinstance(response.get('result'),dict):
            raise RuntimeError('authenticated server gate unavailable')
        gate=copy.deepcopy(response['result']);gate['v']=response['v']
        now=time.time()
        if (gate.get('owner')!=state['owner'] or gate.get('thread_id')!=state['thread_id']
                or gate.get('parent_turn_id')!=state['turn_id'] or gate.get('phase')!=phase
                or gate.get('check_envelope')!=envelope or gate.get('current_activated') is not True
                or gate.get('proof_kind')!='server-authority-gate'
                or not isinstance(gate.get('role_gate_ref'),str) or not gate['role_gate_ref']
                or type(gate.get('observed_at')) not in (int,float)
                or type(gate.get('valid_until')) not in (int,float)
                or not -1<=now-gate['observed_at']<=5 or not now<gate['valid_until']
                or not 0<=gate['valid_until']-gate['observed_at']<=5
                or self.binding()!=state):
            raise RuntimeError('server gate is stale/foreign/malformed')
        return gate

    def admission(self, state, phase, envelope):
        resources=self.physical()  # Fixed native producer, before final role gate.
        if (not isinstance(resources,dict) or resources.get('physical_source')!='Windows CIM'
                or resources.get('disk_after_promised_growth_above_floor') is not True
                or resources.get('scratch_within_limit') is not True
                or resources.get('measured_ram') is not True):
            raise RuntimeError('actual physical admission unknown/denied')
        try: measured=datetime.datetime.fromisoformat(resources['measured_at']).timestamp()
        except (KeyError,TypeError,ValueError):raise RuntimeError('physical observation timestamp missing')
        if not -1<=time.time()-measured<=30:raise RuntimeError('physical observation stale')
        account=self.rpc.call('account/read',{'refreshToken':False}).get('account')
        if account_fingerprint(account)!=self.expected_account:
            raise RuntimeError('native account binding differs')
        limits=self.rpc.call('account/rateLimits/read',{})
        allowed,reason=decision(limits,account.get('type'))
        if allowed is not True:raise RuntimeError('actual API admission denied: '+reason)
        buckets=limits.get('rateLimitsByLimitId')
        if buckets is None:buckets={'legacy':limits['rateLimits']}
        remaining=min(100-b[name]['usedPercent'] for b in buckets.values()
                      for name in ('primary','secondary') if b.get(name) is not None)
        now=time.time()
        quota={'source':'owned-native-account-rateLimits-read','observed_at':now,
               'account_fingerprint':self.expected_account,'remaining_percent':remaining,
               'actual_limit_denied':False,'reserve_percent':15,'launch_allowed':True}
        def receipt(kind,value):
            ref=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
            self.persist(kind+':'+ref,value)
            return ref
        quota_ref=receipt('managed-quota',quota)
        resource_ref=receipt('managed-resources',resources)
        gate=self._gate(state,phase,envelope)  # Last, fresh <=5s; no lease extension.
        if time.time()-now>30 or time.time()-measured>30:
            raise RuntimeError('account/resource observation expired before effect')
        return {'launch_allowed':True,'fresh':True,'provider':'openai','physical_allowed':True,
                'remaining_percent':remaining,'role_gate_ref':gate['role_gate_ref'],
                'quota_gate_ref':quota_ref,'resource_gate_ref':resource_ref,'role_gate':gate}
