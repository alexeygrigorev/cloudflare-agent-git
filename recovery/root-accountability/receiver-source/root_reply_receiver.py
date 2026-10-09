"""Fixed native input and genuine current-model reply resolver, not proof upload."""
import json,math,re
from root_reply_deadline import RootReplyPolicy, VerifiedDelivery, VerifiedModelReply
from operational_receiver import CheckFenced, owner_values, text, digest

class NativeReplyReceiver:
    def __init__(self, authority, *, model_binding, dispatch, deadline=120):
        self.authority=authority; self.binding=model_binding; self.dispatch=dispatch
        with authority._tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS native_reply_receipts(ref TEXT PRIMARY KEY,kind TEXT NOT NULL,nonce TEXT NOT NULL,body TEXT NOT NULL)')
        self.policy=RootReplyPolicy(authority,verify_delivery=self.delivery,verify_reply=self.reply,deadline=deadline)

    @staticmethod
    def owner(challenge):
        return {k:getattr(challenge,k) for k in ('project','role','actor','generation','epoch')}

    def save(self, ref, kind, nonce, body):
        text(ref)
        encoded=json.dumps(body,sort_keys=True)
        with self.authority._tx() as db:
            old=db.execute('SELECT kind,nonce,body FROM native_reply_receipts WHERE ref=?',(ref,)).fetchone()
            if old and tuple(old)!=(kind,nonce,encoded):raise CheckFenced('conflicting native proof reference')
            db.execute('INSERT OR IGNORE INTO native_reply_receipts VALUES(?,?,?,?)',(ref,kind,nonce,encoded))

    def saved(self, ref, kind, challenge):
        with self.authority._tx() as db:
            row=db.execute('SELECT body FROM native_reply_receipts WHERE ref=? AND kind=? AND nonce=?',(ref,kind,challenge.nonce)).fetchone()
        if row is None:raise CheckFenced('fixed native receipt absent')
        return json.loads(row['body'])

    def checked_dispatch(self, owner, command):
        with self.authority._tx() as db:self.authority._valid(db,*owner_values(owner))
        wrapped=self.dispatch(owner,command,30) # Never hold SQL tx during native RPC.
        if any(wrapped.get(k)!=command[k] for k in ('v','key','owner','operation','payload')) or wrapped.get('state')!='completed':raise CheckFenced('exact completed native command required')
        with self.authority._tx() as db:self.authority._valid(db,*owner_values(owner))
        return wrapped['evidence']

    def received_event(self, proof, challenge, ref, kind):
        raw=proof.get('source_event_at');now=self.authority.clock()
        if type(raw) not in (float,int) or not math.isfinite(raw) or not challenge.created-1<=raw<=now+1:raise CheckFenced('fresh genuine source event required with bounded clock skew')
        # The policy deadline is authority receipt time. Preserve the raw
        # source timestamp separately; a future-skewed source cannot extend it.
        with self.authority._tx() as db:
            old=db.execute('SELECT body FROM native_reply_receipts WHERE ref=? AND kind=? AND nonce=?',(ref,kind,challenge.nonce)).fetchone()
        if old:
            prior=json.loads(old['body']);raw_prior={k:v for k,v in prior.items() if k!='authority_received_at'}
            if raw_prior!=proof:raise CheckFenced('conflicting completed native receipt replay')
            return prior
        return dict(proof,authority_received_at=now)

    def deliver(self, challenge):
        owner=self.owner(challenge);binding=self.binding(owner)
        if binding.get('owner')!=owner:raise CheckFenced('actual current activated model required')
        envelope='root-reply:'+challenge.nonce
        with self.authority._tx() as db:
            due=db.execute('SELECT deadline FROM reply_obligations WHERE nonce=?',(challenge.nonce,)).fetchone()['deadline']
        command={'v':1,'key':'reply-input:'+challenge.nonce,'owner':owner,'operation':'root-reply-evidence','payload':{'nonce':challenge.nonce,'envelope':envelope,'thread_id':binding['thread_id'],'body':challenge.body,'issued_at':challenge.created,'reply_due_at':due}}
        proof=self.checked_dispatch(owner,command).get('reply_input',{})
        if (proof.get('owner')!=owner or proof.get('thread_id')!=binding['thread_id'] or proof.get('nonce')!=challenge.nonce or proof.get('envelope')!=envelope or proof.get('method') not in ('turn-start','turn-steer') or proof.get('accepted') is not True):raise CheckFenced('actual matching SDK input acceptance absent')
        for key in ('turn_id','input_receipt_ref'):text(proof.get(key))
        proof=self.received_event(proof,challenge,command['key'],'input')
        self.save(command['key'],'input',challenge.nonce,proof)
        return self.policy.delivered(challenge.nonce,command['key'])

    def delivery(self, ref, challenge):
        proof=self.saved(ref,'input',challenge)
        return VerifiedDelivery(challenge,proof['envelope'],ref,proof['authority_received_at'])

    def collect_reply(self, nonce):
        row=self.policy._read(nonce);challenge=self.policy._challenge(row);owner=self.owner(challenge)
        if row['state']!='delivered':raise CheckFenced('delivered current obligation required')
        prior=self.saved(row['delivery_ref'],'input',challenge);binding=self.binding(owner)
        if binding.get('owner')!=owner or binding.get('thread_id')!=prior['thread_id']:raise CheckFenced('activated model changed')
        command={'v':1,'key':'reply-proof:'+nonce,'owner':owner,'operation':'root-reply-proof','payload':{'nonce':nonce,'envelope':row['envelope'],'input_receipt_ref':prior['input_receipt_ref'],'thread_id':prior['thread_id'],'turn_id':prior['turn_id']}}
        proof=self.checked_dispatch(owner,command).get('reply_result',{})
        event=proof.get('model_event',{});args=event.get('arguments',{})
        if (proof.get('owner')!=owner or proof.get('thread_id')!=prior['thread_id'] or proof.get('turn_id')!=prior['turn_id'] or proof.get('input_receipt_ref')!=prior['input_receipt_ref'] or type(proof.get('helper_exit_code')) is not int or proof['helper_exit_code']!=0 or event.get('type')!='dynamicToolCall' or event.get('tool')!='root_role_reply' or event.get('namespace') not in ('',None) or event.get('status')!='completed' or event.get('success') is not True):raise CheckFenced('genuine current parent model reply absent')
        for key in ('id',):text(event.get(key))
        if args.get('nonce')!=nonce or args.get('envelope')!=row['envelope']:raise CheckFenced('other challenge reply')
        for key in ('body','next_action','checkpoint'):text(args.get(key))
        if not isinstance(proof.get('owned_rollout_receipt_sha256'),str) or not re.fullmatch('[0-9a-f]{64}',proof['owned_rollout_receipt_sha256']):raise CheckFenced('owned native rollout digest required')
        proof=self.received_event(proof,challenge,command['key'],'reply')
        if proof['source_event_at']<prior['source_event_at']:raise CheckFenced('reply predates actual input')
        self.save(command['key'],'reply',nonce,proof)
        return self.policy.replied(nonce,command['key'])

    def reply(self, ref, challenge, envelope):
        proof=self.saved(ref,'reply',challenge);args=proof['model_event']['arguments']
        native_event=digest([self.owner(challenge),proof['thread_id'],proof['turn_id'],proof['model_event']['id']])
        return VerifiedModelReply(challenge,envelope,ref,proof['authority_received_at'],native_event,args['next_action'],args['checkpoint'])
