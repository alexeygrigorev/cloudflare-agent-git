"""Finite fixed Win stdio tool composition; launches no model or authority role.

The existing native controller supplies current context, kernel-bound journal,
own-root mTLS post and a trusted denial reader. No model selects those bindings.
"""
import hashlib,json,time
from opencode_controller_gate import ControllerGate
from opencode_root_tools import FixedRootTools
from opencode_mcp_protocol import FixedMCPProtocol

COMMIT='47b5933c0f12eb403aeaad9e5b7c9c9277c79aa0'
DOCS={'_docs/team/02-root.md':'da4aa091bf6cc3d2dccd759a34090567a91bbbaef545326ca2ee49f6a070a539',
    '_docs/05-recovery.md':'259a4e380efd385b5aaab84094959c67b8ddb69931e7ed1df07eb2ba65c51f7c',
    'recovery/README.md':'e5c4854562ad78e6033ed92d87b97ec5a7fa27cc111a53ac587862d36bb1324f'}
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
INSTRUCTIONS_SHA=digest({'commit':COMMIT,'documents':DOCS})

class FixedBinder:
    def __init__(self,owner,credential,post,context,journal,docs_root,snapshot_path,snapshot_sha256,denial_reader,clock=time.time,startup_bundle=None):
        if owner.get('role')!='root':raise RuntimeError('genuine selected root owner required')
        self.context=context;self.journal=journal;self.docs_root=docs_root;self.snapshot_path=snapshot_path
        self.snapshot_sha256=snapshot_sha256;self.denial_reader=denial_reader;self.clock=clock
        self.startup_bundle=startup_bundle
        self.instructions_sha256=startup_bundle.instructions_sha256 if startup_bundle is not None else INSTRUCTIONS_SHA
        self.gate=ControllerGate(owner,credential,self.instructions_sha256,post,clock)
        self.tools=FixedRootTools(context,self.gate,self.instructions,self.snapshot,self.helper,journal.write,clock)
        self.protocol=FixedMCPProtocol(self.tools)
    def result(self,context,tool,args,fields):
        receipt=digest({'owner':context['owner'],'kernel':context['kernel'],'session_id':context['session_id'],
            'user_message_id':context['user_message_id'],'tool':tool,'args':args,'source_fields':fields,'recorded_at':self.clock()})
        return dict(fields,helper_exit_code=0,receipt_ref=receipt,authority_effect=False)
    def instructions(self,context):
        if self.startup_bundle is not None:
            return self.result(context,'root_read_instructions',{},
                {'instructions_sha256':self.instructions_sha256,
                 'startup_manifest_sha256':self.startup_bundle.manifest_sha256,
                 'documents':self.startup_bundle.documents(),
                 'runtime_claim':'actual pinned startup bytes; source review and operating acceptance remain separate'})
        documents=[]
        for name,expected in DOCS.items():
            path=self.docs_root/name
            if self.reparse(path) or not path.is_file() or path.stat().st_size>131072:
                raise RuntimeError('fixed approved startup document unavailable')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=expected:raise RuntimeError('approved startup bytes changed')
            documents.append({'name':name,'sha256':expected,'body':data.decode('utf-8')})
        return self.result(context,'root_read_instructions',{},
            {'instructions_sha256':INSTRUCTIONS_SHA,'source_commit':COMMIT,'documents':documents,
             'runtime_claim':'instruction bytes only; current provider trial contract is separately pinned'})
    def snapshot(self,context):
        p=self.snapshot_path
        if self.reparse(p) or not p.is_file() or p.stat().st_size>65536:raise RuntimeError('fixed labelled oversight snapshot absent')
        data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=self.snapshot_sha256:raise RuntimeError('fixed oversight source changed')
        v=json.loads(data)
        if v.get('source_kind') not in ('operator-audit','head-verified-snapshot') or v.get('principal_authored') is not False:
            raise RuntimeError('unverified principal provenance denied')
        return self.result(context,'root_oversight_snapshot',{},
            {'source_kind':v['source_kind'],'principal_authored':False,'source_receipt_sha256':self.snapshot_sha256,
             'received_at':self.clock(),'facts':v,'limitation':'actual fact ages retained; no current principal health or delivery inferred'})
    def helper(self,context,name,args):
        if name=='root_ack_instructions':
            if args!={'instructions_sha256':self.instructions_sha256}:raise RuntimeError('approved actual instruction ACK mismatch')
            self.instructions(context) # recheck exact bytes before local handling
            fields={'instructions_sha256':self.instructions_sha256,'role_ack':'pending-completed-native-verification'}
        elif name=='root_role_reply':
            fields={'response_completed':False,'check_completed':False,'delivery':'pending-genuine-native-and-fixed-recipient-route'}
        elif name=='root_luna_hold':
            denial=self.denial_reader()
            if (type(denial) is not dict or denial.get('provider')!='openai-codex' or denial.get('launch_allowed') is not False
                or denial.get('status') not in ('RESERVE_DENIED','PROVIDER_DENIED')
                or denial.get('actual_upstream_read') is not True or not denial.get('account_binding')
                or not denial.get('source_ref') or type(denial.get('observed_at')) not in (int,float)
                or type(denial.get('valid_until')) not in (int,float)
                or not denial['observed_at']<=self.clock()<denial['valid_until']<=denial['observed_at']+60
                or not 0<=self.clock()-denial['observed_at']<=30 or not denial.get('next_trigger')):
                raise RuntimeError('fresh trusted actual Luna denial unavailable')
            fields={'dependency':'HELD-PENDING-NATIVE-ACCEPTANCE','check_completed':False,
                'denial_receipt_ref':denial['source_ref'],'next_trigger':denial['next_trigger']}
        else:raise RuntimeError('fixed local helper only')
        return self.result(context,name,args,fields)
    def run_stdio(self,input_stream,output_stream):
        self.protocol.run(input_stream,output_stream)
    @staticmethod
    def reparse(path):
        return any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (path,*path.parents))
