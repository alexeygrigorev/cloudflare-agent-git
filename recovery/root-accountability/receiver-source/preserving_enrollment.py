"""Preserving nonce -> genuine successor -> existing held enrollment gate.

There is deliberately no drain/death call on this path. Ambiguous enrollment
intent is held, not replayed; the current holder can never be overwritten.
"""
import hashlib,json,uuid
from operational_receiver import CheckFenced,digest
from host_recovery_adapter import OwnerBaseline,VerifiedSuccessor

class PreservingEnrollment:
    def __init__(self, wire, *, factory_sha256):
        self.wire=wire;self.host=wire.host;self.authority=wire.authority
        if not isinstance(factory_sha256,str) or len(factory_sha256)!=64 or any(c not in '0123456789abcdef' for c in factory_sha256):raise CheckFenced('installed preserving factory pin required')
        self.factory=factory_sha256
        with self.authority._tx() as db:db.execute('CREATE TABLE IF NOT EXISTS preserving_enrollments(nonce TEXT PRIMARY KEY,successor_digest TEXT NOT NULL,phase TEXT NOT NULL,binding_digest TEXT)')

    def enroll(self, nonce, successor):
        with self.host._lock:
            with self.authority._tx() as db:
                attempt=db.execute('SELECT * FROM preserving_attempts WHERE nonce=?',(nonce,)).fetchone()
            if not attempt:raise CheckFenced('server preserving nonce absent')
            permit=json.loads(attempt['permit']);owner=permit['owner']
            # Revalidate the actual preserved family against the immutable
            # permit baseline immediately before any new enrollment effect.
            result=self.wire.receiver.challenge(owner)
            if result['permit']!=permit:raise CheckFenced('preserving permit changed')
            if not isinstance(successor,dict):raise CheckFenced('actual new native leaf required')
            actor=successor.get('actor');who=successor.get('whoami',{})
            try:canonical=str(uuid.UUID(actor))
            except (ValueError,TypeError,AttributeError):raise CheckFenced('canonical native UUID required')
            kernel=self.host._process(successor.get('kernel'))
            generation='win32:'+str(kernel['pid'])+':'+str(kernel['creation_filetime'])
            suffix=hashlib.sha256(nonce.encode()).hexdigest()
            binding=self.host._config()['bindings'][owner['actor']]
            if (actor!=canonical or actor==owner['actor'] or successor.get('generation')!=generation
                or who.get('id')!=actor or who.get('tag')!=successor.get('root_tag')
                or successor.get('root_tag')!='win35-root-capsule-api-recovery-'+suffix[:16]
                or successor.get('state_dir','').replace(chr(92),'/')!=self.host.plan['win_state_root'].rstrip('/')+'/recovery-'+suffix
                or successor.get('host')!=binding['host']
                or who.get('workspace','').replace(chr(92),'/').lower()!=self.host.plan['win_workspace'].lower()
                or successor.get('actual_leaf_verified') is not True
                or type(successor.get('api_port')) is not int or successor['api_port']!=permit['new_api_port']):raise CheckFenced('fixed nonce/host/kernel/factory/opposite port leaf mismatch')
            for field in ('leaf_sha256','holding_profile_sha256'):
                sha=successor.get(field)
                if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise CheckFenced('actual leaf/profile digest required')
            reference=digest(successor)
            baseline=OwnerBaseline(owner['project'],'root',owner['actor'],owner['generation'],owner['epoch'],attempt['baseline'])
            proof=VerifiedSuccessor(baseline,nonce,reference,actor,generation,digest(kernel),self.factory,self.authority.clock())
            with self.authority._tx() as db:
                old=db.execute('SELECT * FROM preserving_enrollments WHERE nonce=?',(nonce,)).fetchone()
                if old:
                    if old['successor_digest']!=reference:raise CheckFenced('different preserving leaf replay')
                    if old['phase']=='completed':return self.host._read_handoff(nonce,old['binding_digest'])
                    raise CheckFenced('uncertain held enrollment; controlled reconciliation required')
                current=self.authority._get(db,owner['project'],'root')
                if current['holder'] is not None or current['epoch']!=owner['epoch']+1:raise CheckFenced('reserved preserving vacant epoch required')
                db.execute('INSERT INTO preserving_enrollments VALUES(?,?,?,NULL)',(nonce,reference,'enrollment-pending'))
            # Existing sole profile/install locks + exact DB vacant CAS + native
            # registry checks are executed by the maintained privileged gate.
            output=self.host._held_enrollment(proof,successor)
            with self.authority._tx() as db:
                db.execute("UPDATE preserving_enrollments SET phase='completed',binding_digest=? WHERE nonce=? AND phase='enrollment-pending'",(output['binding_digest'],nonce))
            return self.host._read_handoff(nonce,output['binding_digest'])
