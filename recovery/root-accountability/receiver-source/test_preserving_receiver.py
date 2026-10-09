import sqlite3,copy
import pytest
from test_operational_receiver import setup
from preserving_receiver import PreservingReceiver,VerifiedPreservedFamily
from operational_receiver import CheckFenced
from coordination.role_failover import Fenced

def receiver(a,c,o,mutate=lambda p:p):
 binding={'owner':o,'profile_sha256':'fixed-profile','thread_id':'parent','api_port':8813,'activation_ref':'first-action'}
 with a._tx() as db:db.execute('INSERT INTO activation_receipts VALUES(?,?,?,?,?)',('p','root',o['epoch'],'own-ack','first-action'))
 def verify(owner,binding):
  # Prove native kernel observation isn't under the SQL write lock.
  with sqlite3.connect(a.path,timeout=.1) as db:db.execute('BEGIN IMMEDIATE');db.rollback()
  return mutate(VerifiedPreservedFamily(o,'fixed-profile','parent',8813,True,'kernel-proof','retained-job','fixed-receipt',c[0]))
 return PreservingReceiver(a,bindings={'actor':binding},verify_family=verify)

def test_expired_completed_check_disposition_preserves_family_and_exact_replay(setup):
 a,c,o,p,r=setup;s=receiver(a,c,o);c[0]=5000
 first=s.challenge(o);assert first['permit']['new_api_port']==8814;assert first['permit']['mode']=='revoked-alive';assert 'job_zero' not in first
 assert s.challenge(o)==first
 with sqlite3.connect(a.path) as db:
  assert db.execute('SELECT holder,epoch FROM roles').fetchone()==(None,o['epoch']+1)
  assert db.execute('SELECT COUNT(*) FROM reply_tombstones').fetchone()[0]==1
  assert 'missed_periodic_check' in db.execute("SELECT payload FROM events WHERE kind='preserving_disposition'").fetchone()[0]
 with pytest.raises(Fenced):a.renew('p','root','actor','g',o['epoch'])

def test_lease_expiry_alone_is_not_missed_check_or_vacancy(setup):
 a,c,o,p,r=setup;s=receiver(a,c,o);c[0]=2001
 with pytest.raises(CheckFenced):s.challenge(o)

def test_caller_dictionary_cannot_authorize_family(setup):
 a,c,o,p,r=setup;s=receiver(a,c,o,lambda p:p.__dict__);c[0]=5000
 with pytest.raises(CheckFenced):s.challenge(o)

@pytest.mark.parametrize('field,value',[('opposite_free',False),('thread_id','foreign'),('api_port',8803),('source_receipt_ref',''),('observed_at',1.)])
def test_typed_proof_negatives_preserve_incumbent(setup,field,value):
 a,c,o,p,r=setup
 def mutate(proof):
  args=proof.__dict__.copy();args[field]=value;return VerifiedPreservedFamily(**args)
 s=receiver(a,c,o,mutate);c[0]=5000
 with pytest.raises(CheckFenced):s.challenge(o)
 with sqlite3.connect(a.path) as db:assert db.execute('SELECT holder FROM roles').fetchone()[0]=='actor'

def test_changed_epoch_or_foreign_binding_cannot_reuse_permit(setup):
 a,c,o,p,r=setup;s=receiver(a,c,o);c[0]=5000;s.challenge(o)
 with a._tx() as db:db.execute('UPDATE roles SET epoch=epoch+1')
 with pytest.raises(CheckFenced):s.challenge(o)

def test_absent_or_other_activation_is_not_completed_custody(setup):
 a,c,o,p,r=setup;s=receiver(a,c,o)
 with a._tx() as db:db.execute("UPDATE activation_receipts SET first_action='other-proof'")
 c[0]=5000
 with pytest.raises(CheckFenced):s.challenge(o)

@pytest.mark.parametrize('field,value',[('native_kernel_ref','other-kernel'),('retained_job_ref','other-job'),('source_receipt_ref','other-source')])
def test_replayed_family_identity_change_is_denied(setup,field,value):
 a,c,o,p,r=setup;change=[False]
 def mutate(proof):
  args=proof.__dict__.copy()
  if change[0]:args[field]=value
  return VerifiedPreservedFamily(**args)
 s=receiver(a,c,o,mutate);c[0]=5000;s.challenge(o);change[0]=True
 with pytest.raises(CheckFenced):s.challenge(o)

def test_fresh_observation_time_does_not_change_same_family_permit(setup):
 a,c,o,p,r=setup;s=receiver(a,c,o);c[0]=5000;first=s.challenge(o);c[0]+=1;assert s.challenge(o)==first
