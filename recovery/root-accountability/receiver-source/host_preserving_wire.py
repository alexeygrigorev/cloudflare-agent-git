"""Privileged same-service caretaker observation; model credentials cannot enter.

This reuses HostRecoveryWire's pinned producer/task/device authentication and
kernel schema. It does not grant arbitrary OS actors or caller proof flags trust.
"""
import json,math
from preserving_receiver import PreservingReceiver,VerifiedPreservedFamily
from operational_receiver import CheckFenced,owner_values,digest
from receiver_server import activated_model

class HostPreservingWire:
 def __init__(self,host_wire,*,bindings,preserving_factory_sha256=None):
  self.host=host_wire;self.authority=host_wire.authority;self.bindings=bindings;self.enrollment=None
  if preserving_factory_sha256 is not None:
   from preserving_enrollment import PreservingEnrollment
   self.enrollment=PreservingEnrollment(self,factory_sha256=preserving_factory_sha256)
  with self.authority._tx() as db:db.execute('CREATE TABLE IF NOT EXISTS preserving_observations(owner TEXT PRIMARY KEY,receipt TEXT NOT NULL,received REAL NOT NULL)')
  self.receiver=PreservingReceiver(self.authority,bindings=bindings,verify_family=self._saved_family)
 def _verify(self,r):
  fields={'baseline','observed_at','native_alive','job','api_port','opposite_slot','source_receipt_ref','owned_sdk'}
  if not isinstance(r,dict) or set(r)!=fields:raise CheckFenced('strict privileged preserving receipt required')
  b=r['baseline'];owner=b.get('owner');owner_values(owner);binding=self.bindings.get(owner['actor'])
  if not binding or binding['owner']!=owner:raise CheckFenced('installed preserving binding absent')
  self.host._guardian(b.get('guardian'))
  config=self.host._config();native_binding=config['bindings'].get(owner['actor'])
  if not native_binding or native_binding.get('generation')!=owner['generation'] or b.get('host')!=native_binding['host']:raise CheckFenced('exact managed native host required')
  if b.get('profile_sha256')!=binding['profile_sha256'] or r['api_port']!=binding['api_port'] or type(r['api_port']) is not int:raise CheckFenced('fixed current predecessor profile/port required')
  sdk=r['owned_sdk'];cid=activated_model(config,owner)['thread_id']
  if (not isinstance(sdk,dict) or set(sdk)!={'thread_id','turn_id','status','pending_tool_count','history_receipt_sha256'} or sdk['thread_id']!=cid or sdk['thread_id']!=binding['thread_id'] or not isinstance(sdk['turn_id'],str) or not sdk['turn_id'] or sdk['status']!='completed' or type(sdk['pending_tool_count']) is not int or sdk['pending_tool_count']!=0):raise CheckFenced('fresh owned completed SDK history required')
  self.host._checkpoint(b.get('checkpoint'))
  if b['checkpoint']['thread_id']!=cid or b['checkpoint']['history_receipt_sha256']!=sdk['history_receipt_sha256']:raise CheckFenced('current owned provider checkpoint mismatch')
  n=b['native'];m=b['model']
  if n.get('id')!=owner['actor'] or m.get('owner')!=owner:raise CheckFenced('native/model owner mismatch')
  kernels=[self.host._process(n[k]) for k in ('worker','workload','host_process')]+[self.host._process(m['backend'])]
  if owner['generation']!='win32:'+str(kernels[2]['pid'])+':'+str(kernels[2]['creation_filetime']):raise CheckFenced('actual native kernel generation required')
  if r['native_alive']!=[dict(k,state='alive') for k in kernels]:raise CheckFenced('exact whole preserved family alive observations required')
  if b['guardian']['pid'] in {x['pid'] for x in kernels} or m['job'].get('session_id')!=2 or not m['job'].get('name'):raise CheckFenced('outside-root Guardian/actual Job boundary required')
  job=r['job']
  if not isinstance(job,dict) or set(job)!={'queried','retained_handle_ref','active_processes'} or job['queried'] is not True or type(job['active_processes']) is not int or job['active_processes']<1 or not isinstance(job['retained_handle_ref'],str) or not job['retained_handle_ref']:raise CheckFenced('fresh retained live Job query required; never zero/death')
  opposite=8814 if binding['api_port']==8813 else 8813
  if r['opposite_slot']!={'port':opposite,'free':True}:raise CheckFenced('fixed free opposite slot required')
  now=self.authority.clock();observed=r['observed_at']
  if type(observed) not in (int,float) or not math.isfinite(observed) or not now-30<=observed<=now+1:raise CheckFenced('fresh privileged observation required')
  for sha in (sdk['history_receipt_sha256'],r['source_receipt_ref']):
   if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise CheckFenced('fixed source/history digest required')
  return VerifiedPreservedFamily(owner,binding['profile_sha256'],cid,binding['api_port'],True,digest(kernels),job['retained_handle_ref'],r['source_receipt_ref'],observed)
 def observe(self,receipt):
  proof=self._verify(receipt)
  with self.authority._tx() as db:
   row=self.authority._get(db,proof.owner['project'],'root')
   if self.host._owner(row)!=proof.owner:raise CheckFenced('current expired holder required before disposition')
   db.execute('INSERT OR REPLACE INTO preserving_observations VALUES(?,?,?)',(json.dumps(proof.owner,sort_keys=True),json.dumps(receipt,sort_keys=True),self.authority.clock()))
  return {'status':'preserving-observation-recorded','receipt_sha256':digest(receipt)}
 def _saved_family(self,owner,binding):
  with self.authority._tx() as db:row=db.execute('SELECT receipt FROM preserving_observations WHERE owner=?',(json.dumps(owner,sort_keys=True),)).fetchone()
  if not row:raise CheckFenced('fresh privileged family observation absent')
  return self._verify(json.loads(row['receipt']))
 def handle(self,request,fingerprint):
  self.host.authenticate(request.get('credential'),fingerprint)
  if request.get('v')!=1 or set(request)-{'v','credential','op','receipt','challenge','successor'}:raise CheckFenced('fixed caretaker preserving operation required')
  if request['op']=='preserving-reconcile':
   if set(request)!={'v','credential','op','challenge','successor'} or self.enrollment is None:raise CheckFenced('paired preserving enrollment not installed')
   return self.enrollment.enroll(request['challenge'],request['successor'])
  if 'challenge' in request or 'successor' in request:raise CheckFenced('foreign preserving operation fields')
  if request['op']=='preserving-observe':return self.observe(request['receipt'])
  if request['op']=='preserving-challenge':
   with self.authority._tx() as db:
    row=self.authority._get(db,self.host.plan['project'],'root');owner=self.host._owner(row)
    if row['holder']:
     # A healthy current root never needs a preserving replacement. This does
     # not mistake caller process/lease heartbeat for healthy genuine custody.
     from coordination.role_failover import Fenced
     try:self.authority._valid(db,*owner_values(owner))
     except Fenced:pass
     else:return {'status':'no-preserving-permit'}
   if not owner['actor']:
    # Fixed initial binding selects its already-reserved vacant replay only.
    matches=[b['owner'] for b in self.bindings.values() if b['owner']['epoch']+1==row['epoch']]
    if len(matches)!=1:raise CheckFenced('preserving disposition owner unknown')
    owner=matches[0]
   return self.receiver.challenge(owner)
  raise CheckFenced('fixed preserving host operation required')
