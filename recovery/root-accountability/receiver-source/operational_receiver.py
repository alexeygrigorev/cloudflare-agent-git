"""Fixed native completed-check receiver. No remote caller installs a verifier.

Only a bound NativeChannels command response enters record_check. Ordinary RPC
callers submit the opaque server key to complete_check, never evidence JSON.
"""
import hashlib,json,math,sqlite3,time
from dataclasses import dataclass

FIELDS=('project','role','actor','generation','epoch')
class CheckFenced(PermissionError):pass

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def owner_values(owner):
 if not isinstance(owner,dict) or set(owner)!=set(FIELDS) or owner.get('role')!='root' or type(owner.get('epoch')) is not int or owner['epoch']<1 or any(not isinstance(owner[k],str) or not owner[k] for k in FIELDS[:-1]):raise CheckFenced('exact root owner required')
 return tuple(owner[k] for k in FIELDS)

def text(value):
 if not isinstance(value,str) or not value.strip() or len(value)>8192:raise CheckFenced('meaningful fixed evidence required')
 return value

class CompletedCheckReceiver:
 def __init__(self,authority,*,model_binding,dispatch,clock=time.time,method="native-direct-v1"):
  if method not in ("native-direct-v1","managed-sdk-fresh-v1"):raise CheckFenced("cold-installed check method required")
  self.method=method
  self.authority=authority;self._binding=model_binding;self._dispatch=dispatch;self.clock=clock
  with authority._tx() as db:
   db.execute('CREATE TABLE IF NOT EXISTS native_check_receipts(key TEXT PRIMARY KEY,owner TEXT NOT NULL,command TEXT NOT NULL,receipt TEXT NOT NULL,observed REAL NOT NULL,native_event TEXT UNIQUE NOT NULL,completed INTEGER NOT NULL DEFAULT 0)')
 def _valid(self,owner):
  values=owner_values(owner)
  with self.authority._tx() as db:self.authority._valid(db,*values)
 def collect(self,owner,*,key,check_envelope):
  # Binding producer is fixed server code reading exact activation/sink proof,
  # never caller-provided model metadata. RPC/model work occurs outside tx.
  self._valid(owner);key=text(key);envelope=text(check_envelope);binding=self._binding(owner)
  if not isinstance(binding,dict) or binding.get('owner')!=owner:raise CheckFenced('actual activated native model binding absent')
  cid=text(binding.get('thread_id'))
  command={'v':1,'key':key,'owner':dict(owner),'operation':'root-check-proof','payload':{'check_envelope':envelope,'thread_id':cid}}
  wrapped=self._dispatch(owner,command,30)
  return self.record_check(command,wrapped,binding)
 def record_check(self,command,wrapped,binding):
  # This method is internal only, attached after NativeChannel's exact pending
  # wrapper check; it is deliberately absent from the remote route allowlist.
  owner=command['owner'];self._valid(owner)
  for k in ('v','key','owner','operation','payload'):
   if wrapped.get(k)!=command[k]:raise CheckFenced('native pending command mismatch')
  if command.get('operation')!='root-check-proof' or wrapped.get('state')!='completed':raise CheckFenced('native proof incomplete')
  proof=wrapped.get('evidence',{});result=proof.get('check_result',{});binding_owner=binding.get('owner');cid=binding.get('thread_id')
  if binding_owner!=owner or result.get('owner')!=owner or result.get('parent_thread_id')!=cid or command['payload'].get('thread_id')!=cid:raise CheckFenced('foreign owner/CID')
  parent_turn=text(result.get('parent_turn_id'));child=text(result.get('child_thread_id'));child_turn=text(result.get('child_turn_id'))
  if child==cid or result.get('model')!='gpt-6-luna' or result.get('effort')!='max':raise CheckFenced('fresh Luna-max child execution proof absent')
  if self.method=='native-direct-v1':
   if result.get('launch_method') not in (None,'native-direct-v1') or result.get('raw_fork_mode')!='none':raise CheckFenced('actual native direct child/no fork proof absent')
  else:
   from managed_check_binding import validate_managed,validate_server_gates
   validate_managed(result,owner,cid,parent_turn,child,child_turn,command['payload']['check_envelope'])
   validate_server_gates(self.authority,result,owner,cid,parent_turn,command['payload']['check_envelope'])
  if result.get('actual_execution_context')!={'thread_id':child,'turn_id':child_turn,'model':'gpt-6-luna','effort':'max','sandbox_policy':{'type':'read-only'},'approval_policy':'never'}:raise CheckFenced('configured metadata is not actual execution context')
  for k in ('spawn_event_id','wait_event_id','child_completed_event','instruction_completed_event','report_completed_event','owned_rollout_receipt_sha256'):text(result.get(k))
  if result.get('required_reads_completed') is not True or result.get('child_status')!='completed' or result.get('parent_wait_status')!='completed':raise CheckFenced('submission or helper success is not completed check')
  final=text(result.get('own_result'));result_sha=hashlib.sha256(final.encode()).hexdigest()
  if result.get('result_sha256')!=result_sha:raise CheckFenced('own latest child result changed')
  item=result.get('parent_accept_event',{})
  args=item.get('arguments',{})
  if (item.get('type')!='dynamicToolCall' or item.get('tool')!='root_check_result' or item.get('namespace') not in (None,'') or item.get('status')!='completed' or item.get('success') is not True or not item.get('id') or result.get('parent_accept_thread_id')!=cid or result.get('parent_accept_turn_id')!=parent_turn or type(result.get('helper_exit_code')) is not int or result['helper_exit_code']!=0):raise CheckFenced('actual new parent model outcome acceptance missing')
  if args.get('check_envelope')!=command['payload']['check_envelope'] or args.get('child_thread_id')!=child or args.get('child_turn_id')!=child_turn or args.get('result_sha256')!=result_sha:raise CheckFenced('parent accepted other result/request')
  text(args.get('next_action'));text(args.get('checkpoint'))
  event_time=result.get('source_event_at');now=self.clock()
  if type(event_time) not in (float,int) or not math.isfinite(event_time) or not now-120<=event_time<=now+1:raise CheckFenced('stale/future check proof')
  # Caller cannot use freshly received stale report as current fact. The fixed
  # native producer checks report provenance; result retains its receipt digest.
  with self.authority._tx() as db:
   self.authority._valid(db,*owner_values(owner))
   old=db.execute('SELECT * FROM native_check_receipts WHERE key=?',(command['key'],)).fetchone()
   native_event=digest([owner,cid,parent_turn,item['id']])
   event_owner=db.execute('SELECT key FROM native_check_receipts WHERE native_event=?',(native_event,)).fetchone()
   if event_owner and event_owner['key']!=command['key']:raise CheckFenced('completed model event reused under another key')
   payload=(json.dumps(owner,sort_keys=True),json.dumps(command,sort_keys=True),json.dumps(wrapped,sort_keys=True))
   if old:
    if (old['owner'],old['command'],old['receipt'])!=payload:raise CheckFenced('changed native check receipt replay')
   else:db.execute('INSERT INTO native_check_receipts(key,owner,command,receipt,observed,native_event) VALUES(?,?,?,?,?,?)',(command['key'],*payload,now,native_event))
  return {'receipt_ref':command['key'],'result_sha256':result_sha,'owner':owner,'observed_at':now}
 def complete_check(self,owner,receipt_ref):
  self._valid(owner);text(receipt_ref)
  with self.authority._tx() as db:
   row=db.execute('SELECT * FROM native_check_receipts WHERE key=?',(receipt_ref,)).fetchone()
   if row is None or json.loads(row['owner'])!=owner or not self.clock()-120<=row['observed']<=self.clock():raise CheckFenced('opaque native accepted check receipt unavailable/stale')
   wrapped=json.loads(row['receipt']);result=wrapped['evidence']['check_result']
   # One authoritative transaction: duplicate completion never extends the
   # deadline, even when concurrent callers or process restart reuse the key.
   if row['completed']:
    return {'completed':True,'replayed':True,'receipt_ref':receipt_ref}
   self.authority._valid(db,*owner_values(owner))
   db.execute('UPDATE roles SET check_due=? WHERE project=? AND role=? AND holder=? AND generation=? AND epoch=?',
     (row['observed']+1800,owner['project'],owner['role'],owner['actor'],owner['generation'],owner['epoch']))
   self.authority._event(db,owner['project'],owner['role'],'check_completed',owner['epoch'],{'evidence':'native-check:'+receipt_ref})
   db.execute('UPDATE native_check_receipts SET completed=1 WHERE key=? AND completed=0',(receipt_ref,))
   return {'completed':True,'replayed':False,'receipt_ref':receipt_ref}
