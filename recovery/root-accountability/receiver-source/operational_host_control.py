"""Bound outside-root caretaker probes on the existing service, no new timer."""
from operational_receiver import CheckFenced,owner_values

class OperationalHostControl:
    def __init__(self, host_wire, root_receiver):
        self.host=host_wire;self.root=root_receiver;self.authority=host_wire.authority

    def handle(self, request, fingerprint):
        self.host.authenticate(request.get('credential'),fingerprint)
        if set(request)!={'v','credential','op'} or request.get('v')!=1 or request.get('op')!='reply-probe':raise CheckFenced('fixed privileged reply probe required')
        # Source selected by actual role/check deadline, never caller supplied
        # nonce, owner, body, input reference, proof or requested model turn.
        with self.authority._tx() as db:
            row=self.authority._get(db,self.host.plan['project'],'root')
            owner=self.host._owner(row)
            self.authority._valid(db,*owner_values(owner))
            due=row['check_due']
        key='custody-response:'+owner['actor']+':'+owner['generation']+':'+str(owner['epoch'])+':'+repr(due)
        policy=self.root.replies.policy
        challenge=policy.issue(owner['project'],'root',key=key,body={'request':'Confirm this current custody challenge with a genuine root_role_reply, meaningful response, next action and checkpoint. A delegated check may remain unfinished; do not claim its acceptance.'})
        current=policy._read(challenge.nonce)
        if current['state']=='pending':
            current=self.root.replies.deliver(challenge)
        if current['state']=='delivered':
            try:current=self.root.replies.collect_reply(challenge.nonce)
            except (CheckFenced,TimeoutError,ConnectionError):
                # Re-read runs authority expiry prelude. Pending delivery/model
                # is explicitly not healthy custody; old key is not forgotten.
                current=policy._read(challenge.nonce)
        return {'status':current['state'],'nonce':challenge.nonce,'owner':owner,'reply_due_at':current['deadline'],'current_model_reply':current['state']=='replied','check_outcome_not_implied':True}
