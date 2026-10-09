"""Fixed privileged route candidate. No model proof upload or new listener.

Constructor callbacks must be installed/pinned trusted producers. Missing seams
fail closed. Network and model work is outside authority transactions.
"""
import json
from opencode_native75 import NativeObservation, digest
from held_luna75 import owner_ref

class Gateway:
    OPS = {'opencode-observe', 'opencode-activate', 'opencode-reply', 'root-luna-hold'}
    def __init__(self, authority, verifier, authenticate, selected_owner, instructions_sha256,
                 reply_recorder=None, oversight_verifier=None):
        self.a=authority;self.verifier=verifier;self.authenticate=authenticate
        self.selected_owner=selected_owner;self.instructions_sha256=instructions_sha256
        self.reply_recorder=reply_recorder;self.oversight_verifier=oversight_verifier

    @staticmethod
    def schema(db):
        db.execute('''CREATE TABLE IF NOT EXISTS opencode_native_observations(
          event_ref TEXT PRIMARY KEY, owner_ref TEXT NOT NULL,
          tool TEXT NOT NULL, observed_at REAL NOT NULL, observation TEXT NOT NULL)''')

    def handle(self, request):
        if type(request) is not dict or set(request) != {'v','credential','op'} or type(request['v']) is not int or request['v'] != 1 or request['op'] not in self.OPS:
            raise ValueError('fixed privileged request; no proof or owner upload')
        if not callable(self.authenticate) or not self.authenticate(request['credential'],scope='fixed-host-caretaker'):
            raise ValueError('fixed scoped credential required')
        if not callable(self.selected_owner):raise ValueError('server owner resolver missing')
        selected=self.selected_owner()
        if type(selected) is not tuple or len(selected)!=5:raise ValueError('server-selected owner tuple')
        project,role,actor,generation,epoch=selected
        if role!='root':raise ValueError('root-only gateway')
        ref=owner_ref(*selected)
        # Authenticated own history/RPC may block; do not hold SQLite transaction.
        obs=self.verifier.observe()
        if type(obs) is not NativeObservation or obs.owner_ref!=ref:raise ValueError('selected native owner mismatch')
        if self.selected_owner()!=selected:raise ValueError('owner changed across observation')
        event_ref=digest([obs.session_id,obs.user_message_id,obs.assistant_message_id,obs.part_id,obs.call_id])
        with self.a._tx() as db:
            row=self.a._valid(db,*selected)
            self.schema(db)
            payload=json.dumps(obs.__dict__,sort_keys=True)
            old=db.execute('SELECT observation FROM opencode_native_observations WHERE event_ref=?',(event_ref,)).fetchone()
            if old and old['observation']!=payload:raise ValueError('conflicting native event')
            db.execute('INSERT OR IGNORE INTO opencode_native_observations VALUES(?,?,?,?,?)',
                       (event_ref,ref,obs.tool,self.a.clock(),payload))
            if request['op']=='opencode-observe':
                return {'discriminator':'opencode-native-v1','receipt_ref':event_ref,'tool':obs.tool,
                        'owner_ref':ref,'source_sha256':obs.source_sha256,'completed_at':obs.completed_at,'authority_effect':False}
            if request['op']=='opencode-activate':
                if obs.tool!='root_oversight_snapshot' or not callable(self.oversight_verifier) or not self.oversight_verifier(obs):
                    raise ValueError('genuine current oversight output/source required')
                ack=None
                for found in db.execute("SELECT event_ref,observation FROM opencode_native_observations WHERE owner_ref=? AND tool='root_ack_instructions'",(ref,)):
                    item=json.loads(found['observation'])
                    if (item['session_id']==obs.session_id and json.loads(item['args_json'])=={'instructions_sha256':self.instructions_sha256}
                        and item['completed_at']<=obs.completed_at):ack=found['event_ref']
                if not ack:raise ValueError('own exact instruction ACK required')
                old=db.execute('SELECT * FROM activation_receipts WHERE project=? AND role=? AND epoch=?',(project,role,epoch)).fetchone()
                if old and (old['role_ack'],old['first_action'])!=(ack,event_ref):raise ValueError('conflicting activation')
                db.execute('INSERT OR IGNORE INTO activation_receipts VALUES(?,?,?,?,?)',(project,role,epoch,ack,event_ref))
                if not old:self.a._event(db,project,role,'opencode_native_activation',epoch,{'role_ack':ack,'first_action':event_ref})
                return {'activated':True,'owner_ref':ref,'role_ack_ref':ack,'first_action_ref':event_ref,'check_completed':False}
            if request['op']=='opencode-reply':
                if obs.tool!='root_role_reply' or not callable(self.reply_recorder):raise ValueError('fixed issued-response recorder missing')
                # Must validate current persisted nonce and retire it atomically,
                # not infer health from this observation or mechanical heartbeat.
                return self.reply_recorder(db,row,obs,event_ref)
            if obs.tool!='root_luna_hold' or self.a.hold_policy is None:raise ValueError('fixed hold policy missing')
            if not callable(self.reply_recorder):raise ValueError('issued-response recorder missing')
            response=self.reply_recorder(db,row,obs,event_ref)
            activated=db.execute('SELECT 1 FROM activation_receipts WHERE project=? AND role=? AND epoch=?',(project,role,epoch)).fetchone()
            result=self.a.hold_policy.record(db,row,ref,obs,activated=bool(activated))
            result['response_receipt_ref']=response['receipt_ref']
            if not result['replayed']:self.a._event(db,project,role,'luna_dependency_held',epoch,result)
            return result
