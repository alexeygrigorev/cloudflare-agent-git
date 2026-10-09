"""Server-selected preserving disposition in the existing authority DB.

Only an installed trusted caretaker verifier supplies VerifiedPreservedFamily;
no HTTP caller may upload it or select ports, nonce, history or proof flags.
"""
import json,secrets,math
from dataclasses import dataclass
from operational_receiver import owner_values,CheckFenced,digest

@dataclass(frozen=True)
class VerifiedPreservedFamily:
 owner:dict
 profile_sha256:str
 thread_id:str
 api_port:int
 opposite_free:bool
 native_kernel_ref:str
 retained_job_ref:str
 source_receipt_ref:str
 observed_at:float

class PreservingReceiver:
 def __init__(self,authority,*,bindings,verify_family):
  self.authority=authority;self.bindings=bindings;self.verify_family=verify_family
  with authority._tx() as db:db.execute('CREATE TABLE IF NOT EXISTS preserving_attempts(owner TEXT PRIMARY KEY,nonce TEXT UNIQUE NOT NULL,permit TEXT NOT NULL,baseline TEXT NOT NULL,created REAL NOT NULL)')
 def challenge(self,owner):
  owner_values(owner);binding=self.bindings.get(owner['actor'])
  if not binding or binding.get('owner')!=owner or binding.get('api_port') not in (8813,8814) or type(binding.get('api_port')) is not int:raise CheckFenced('fixed preserving owner binding absent')
  # Native kernel/history/Job/port observation outside all authority DB locks.
  proof=self.verify_family(owner,binding)
  now=float(self.authority.clock())
  if type(proof) is not VerifiedPreservedFamily or proof.owner!=owner or proof.profile_sha256!=binding.get('profile_sha256') or proof.thread_id!=binding.get('thread_id') or proof.api_port!=binding['api_port'] or proof.opposite_free is not True:raise CheckFenced('trusted exact preserved family/opposite free slot required')
  if type(proof.observed_at) not in (float,int) or not math.isfinite(proof.observed_at) or not now-30<=proof.observed_at<=now+1:raise CheckFenced('fresh trusted family observation required')
  if any(not isinstance(x,str) or not x for x in (proof.native_kernel_ref,proof.retained_job_ref,proof.source_receipt_ref)):raise CheckFenced('actual retained live family proof missing')
  encoded=json.dumps(owner,sort_keys=True);baseline=digest({k:v for k,v in proof.__dict__.items() if k!='observed_at'})
  with self.authority._tx() as db:
   row=self.authority._get(db,owner['project'],'root')
   previous=db.execute('SELECT * FROM preserving_attempts WHERE owner=?',(encoded,)).fetchone()
   if previous:
    # Replay is only the exact reserved vacant epoch, never a fresh permission
    # after another root acquires authority or changes predecessor identity.
    if row['holder'] is not None or row['epoch']!=owner['epoch']+1:raise CheckFenced('preserving attempt already superseded')
    permit=json.loads(previous['permit'])
    if previous['baseline']!=baseline:raise CheckFenced('preserving family/source baseline changed')
    return {'permit':permit,'expected':permit.copy()}
   obligation=db.execute("SELECT * FROM reply_obligations WHERE project=? AND role='root' AND actor=? AND generation=? AND epoch=? AND state='revoked' AND deadline<=? ORDER BY created DESC LIMIT 1",(owner['project'],owner['actor'],owner['generation'],owner['epoch'],now)).fetchone()
   tombstone=db.execute('SELECT 1 FROM reply_tombstones WHERE actor=? AND generation=?',(owner['actor'],owner['generation'])).fetchone()
   if obligation and tombstone:
    if row['holder'] is not None or row['epoch']!=owner['epoch']+1:raise CheckFenced('reply disposition changed by other owner')
    reason='reply_deadline';ref='reply:'+obligation['nonce']
   else:
    if (row['holder'],row['generation'],row['epoch'])!=(owner['actor'],owner['generation'],owner['epoch']):raise CheckFenced('exact incumbent disposition required')
    if not row['check_due']+120<=now or not row['expires']<=now:raise CheckFenced('expired missed-check custody required')
    activation=db.execute('SELECT first_action FROM activation_receipts WHERE project=? AND role=? AND epoch=?',(owner['project'],'root',owner['epoch'])).fetchone()
    if not activation or activation['first_action']!=binding.get('activation_ref'):raise CheckFenced('exact completed model activation required')
    changed=db.execute('UPDATE roles SET holder=NULL,generation=NULL,epoch=epoch+1,expires=0,activation_due=0,suspect_since=NULL WHERE project=? AND role=? AND holder=? AND generation=? AND epoch=?',(owner['project'],'root',owner['actor'],owner['generation'],owner['epoch'])).rowcount
    if changed!=1:raise CheckFenced('preserving disposition CAS lost')
    db.execute('INSERT OR IGNORE INTO reply_tombstones VALUES(?,?,?)',(owner['actor'],owner['generation'],now))
    reason='missed_periodic_check';ref='preserving:'+secrets.token_hex(24)
    self.authority._event(db,owner['project'],'root','preserving_disposition',owner['epoch']+1,{'reason':reason,'retired_owner':owner,'source_receipt_ref':proof.source_receipt_ref,'preserve_family':True})
   nonce=secrets.token_hex(24)
   permit={'v':1,'operation':'fixed-preserving-successor','mode':'revoked-alive','challenge':nonce,'owner':owner,'profile_sha256':proof.profile_sha256,'predecessor_api_port':proof.api_port,'new_api_port':8814 if proof.api_port==8813 else 8813,'revocation_receipt_ref':ref}
   db.execute('INSERT INTO preserving_attempts VALUES(?,?,?,?,?)',(encoded,nonce,json.dumps(permit,sort_keys=True),baseline,now))
   return {'permit':permit,'expected':permit.copy()}
