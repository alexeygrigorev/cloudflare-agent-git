"""Server-owned reply obligations over the maintained authority's existing database.

Opaque receipt refs are untrusted input. Only constructor-installed native verifiers
may resolve them to these bound facts. No RPC may replace verifiers or policy.
"""
import json
import math
import secrets
from dataclasses import dataclass

@dataclass(frozen=True)
class Challenge:
    project: str
    role: str
    actor: str
    generation: str
    epoch: int
    nonce: str
    body: str
    created: float

@dataclass(frozen=True)
class VerifiedDelivery:
    challenge: Challenge
    envelope: str
    proof_ref: str
    event_time: float

@dataclass(frozen=True)
class VerifiedModelReply:
    challenge: Challenge
    envelope: str
    proof_ref: str
    event_time: float
    native_completed_event: str
    next_action: str
    checkpoint: str

class RootReplyPolicy:
    def __init__(self, authority, *, verify_delivery=None, verify_reply=None, deadline=120):
        if type(deadline) not in (int,float) or not math.isfinite(deadline) or not 1<=deadline<=600:
            raise ValueError('server reply deadline must be finite 1..600 seconds')
        self.authority=authority
        self._deadline=float(deadline)
        self._delivery=verify_delivery or (lambda reference,expected: None)
        self._reply=verify_reply or (lambda reference,expected,envelope: None)

    @staticmethod
    def _challenge(row):
        return Challenge(row['project'],row['role'],row['actor'],row['generation'],row['epoch'],row['nonce'],row['body'],row['created'])

    @staticmethod
    def _reference(value):
        if not isinstance(value,str) or not value.strip() or len(value)>4096:
            raise ValueError('opaque receipt reference required')

    def issue(self, project, role, *, key, body):
        self._reference(key)
        canonical=json.dumps(body,sort_keys=True,allow_nan=False,separators=(',',':'))
        with self.authority._tx() as db:
            row=self.authority._get(db,project,role)
            if not row['holder']:
                raise ValueError('no current holder')
            self.authority._valid(db,project,role,row['holder'],row['generation'],row['epoch'])
            existing=db.execute('SELECT * FROM reply_obligations WHERE key=?',(key,)).fetchone()
            identity=(project,role,row['holder'],row['generation'],row['epoch'],canonical)
            if existing:
                if tuple(existing[k] for k in ('project','role','actor','generation','epoch','body'))!=identity:
                    raise ValueError('challenge idempotency conflict')
                return self._challenge(existing)
            now=float(self.authority.clock())
            db.execute('INSERT INTO reply_obligations(key,nonce,project,role,actor,generation,epoch,body,created,deadline,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (key,secrets.token_hex(24),*identity,now,now+self._deadline,'pending'))
            return self._challenge(db.execute('SELECT * FROM reply_obligations WHERE key=?',(key,)).fetchone())

    def _read(self, nonce):
        self._reference(nonce)
        with self.authority._tx() as db:
            row=db.execute('SELECT * FROM reply_obligations WHERE nonce=?',(nonce,)).fetchone()
            if row is None:
                raise ValueError('unknown challenge')
            return dict(row)

    @staticmethod
    def _time(event_time, expected, now):
        if type(event_time) not in (int,float) or not math.isfinite(event_time) or not expected.created<=event_time<=now:
            raise ValueError('invalid completed native event time')

    def delivered(self, nonce, receipt_ref):
        self._reference(receipt_ref)
        before=self._read(nonce)
        expected=self._challenge(before)
        proof=self._delivery(receipt_ref,expected)  # Fixed server resolver; no caller JSON facts.
        if type(proof) is not VerifiedDelivery or proof.challenge!=expected or proof.proof_ref!=receipt_ref:
            raise ValueError('unverified or misbound delivery')
        self._reference(proof.envelope)
        self._time(proof.event_time,expected,self.authority.clock())
        with self.authority._tx() as db:
            row=db.execute('SELECT * FROM reply_obligations WHERE nonce=?',(nonce,)).fetchone()
            if row['state']!='pending':
                if row['state'] in ('delivered','replied') and (row['delivery_ref'],row['envelope'],row['delivered'])==(receipt_ref,proof.envelope,proof.event_time):
                    return dict(row)
                raise ValueError('conflicting or revoked delivery')
            self.authority._valid(db,expected.project,expected.role,expected.actor,expected.generation,expected.epoch)
            self._time(proof.event_time,expected,self.authority.clock())
            if db.execute('SELECT 1 FROM reply_obligations WHERE delivery_ref=? OR envelope=?',(receipt_ref,proof.envelope)).fetchone():
                raise ValueError('delivery proof reused')
            db.execute("UPDATE reply_obligations SET state='delivered',delivered=?,envelope=?,delivery_ref=? WHERE nonce=? AND state='pending'",
                (proof.event_time,proof.envelope,receipt_ref,nonce))
        # Publish the proven obligation before safety prelude handles an already due receipt.
        return self._read(nonce)

    def replied(self, nonce, receipt_ref):
        self._reference(receipt_ref)
        before=self._read(nonce)
        if before['state'] not in ('delivered','replied'):
            raise ValueError('challenge not delivered or permanently revoked')
        expected=self._challenge(before)
        proof=self._reply(receipt_ref,expected,before['envelope'])
        if type(proof) is not VerifiedModelReply or proof.challenge!=expected or proof.envelope!=before['envelope'] or proof.proof_ref!=receipt_ref:
            raise ValueError('unverified or misbound model reply')
        for value in (proof.native_completed_event,proof.next_action,proof.checkpoint):
            self._reference(value)
        self._time(proof.event_time,expected,self.authority.clock())
        with self.authority._tx() as db:
            row=db.execute('SELECT * FROM reply_obligations WHERE nonce=?',(nonce,)).fetchone()
            if row['state']=='replied':
                if (row['reply_ref'],row['reply_event'],row['reply_native_event'],row['next_action'],row['checkpoint'])!=(receipt_ref,proof.event_time,proof.native_completed_event,proof.next_action,proof.checkpoint):
                    raise ValueError('conflicting reply replay')
                return dict(row)
            if row['state']!='delivered':
                raise ValueError('challenge permanently revoked')
            self.authority._valid(db,expected.project,expected.role,expected.actor,expected.generation,expected.epoch)
            if self.authority.clock()>=row['deadline'] or not row['delivered']<=proof.event_time<row['deadline']:
                raise ValueError('reply outside fixed response deadline')
            if db.execute('SELECT 1 FROM reply_obligations WHERE reply_ref=? OR reply_native_event=?',(receipt_ref,proof.native_completed_event)).fetchone():
                raise ValueError('model proof reused')
            db.execute("UPDATE reply_obligations SET state='replied',reply_ref=?,reply_event=?,reply_native_event=?,next_action=?,checkpoint=? WHERE nonce=? AND state='delivered'",
                (receipt_ref,proof.event_time,proof.native_completed_event,proof.next_action,proof.checkpoint,nonce))
            return dict(db.execute('SELECT * FROM reply_obligations WHERE nonce=?',(nonce,)).fetchone())
