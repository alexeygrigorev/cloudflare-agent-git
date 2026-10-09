"""Fixed five-tool MCP producer seam; no generic HTTP/upload/launch API.

All callbacks are installed-controller bindings requiring source/plan review.
This source candidate itself provides no runtime adapter or authority effects.
"""
import copy,hashlib,json,threading,time

TOOLS={
 'root_read_instructions':(),
 'root_ack_instructions':('instructions_sha256',),
 'root_oversight_snapshot':(),
 'root_role_reply':('body','next_action','checkpoint'),
 'root_luna_hold':('body','next_action','checkpoint')}

def reject_secret_fields(value):
    if type(value) is dict:
        for k,v in value.items():
            if str(k).casefold().replace('_','') in ('token','credential','credentials','apikey','authorization','password','privatekey'):
                raise RuntimeError('private helper fields cannot enter native/model output')
            reject_secret_fields(v)
    elif type(value) is list:
        for item in value:reject_secret_fields(item)

class FixedRootTools:
    def __init__(self,context,current_gate,instructions,snapshot,helper,write,clock=time.time):
        self.context=context;self.current_gate=current_gate;self.instructions=instructions
        self.snapshot=snapshot;self.helper=helper;self.write=write;self.clock=clock;self.lock=threading.Lock();self.seen={}
    def call(self,request):
        if request.get('method')!='tools/call' or type(request.get('params')) is not dict:
            raise RuntimeError('not a fixed MCP request')
        p=request['params'];name=p.get('name');args=p.get('arguments',{})
        if name not in TOOLS or type(args) is not dict or set(args)!=set(TOOLS[name]):
            raise RuntimeError('unknown tool or model-selected context')
        if any(type(v) is not str or not v.strip() or len(v)>8192 for v in args.values()):
            raise RuntimeError('invalid bounded tool argument')
        context=copy.deepcopy(self.context());self.current_gate(context,name)
        for k in ('owner','kernel','session_id','user_message_id','user_input_sha256'):
            if not context.get(k):raise RuntimeError('current owned native input absent')
        # MCP request id and provider callID are separate native identifiers.
        key=hashlib.sha256(json.dumps([context['owner'],context['session_id'],context['user_message_id'],request.get('id'),name,args],sort_keys=True).encode()).hexdigest()
        with self.lock:
            if key in self.seen:raise RuntimeError('replayed MCP handling held')
            self.seen[key]='pending'
        self.write('helper-intent:'+key,dict(phase='pending-reconcile-only',context=context,tool=name,arguments=args,mcp_request_id=request.get('id')))
        if name=='root_read_instructions':result=self.instructions(context)
        elif name=='root_oversight_snapshot':result=self.snapshot(context)
        else:
            if name=='root_ack_instructions' and args['instructions_sha256']!=self.instructions(context)['instructions_sha256']:
                raise RuntimeError('wrong actually pinned instruction digest')
            if name=='root_role_reply' and (not context.get('nonce') or not context.get('envelope')):
                raise RuntimeError('no exact trusted post-challenge reply context')
            # The fixed controller invokes actual source-pinned helper/gates.
            # Luna hold must resolve fresh denial; never complete_check here.
            self.current_gate(context,name)
            result=self.helper(context,name,args)
        if (type(result) is not dict or type(result.get('helper_exit_code')) is not int
            or result['helper_exit_code']!=0 or not result.get('receipt_ref')):
            raise RuntimeError('actual fixed helper receipt unavailable')
        reject_secret_fields(result)
        self.current_gate(context,name)
        if self.context()!=context:raise RuntimeError('native context changed during handling')
        output=json.dumps(result,sort_keys=True,separators=(',',':'))
        handled=dict(owner=context['owner'],kernel=context['kernel'],session_id=context['session_id'],
            user_message_id=context['user_message_id'],tool=name,arguments=args,
            helper_exit_code=0,receipt_ref=result['receipt_ref'],output=output,mcp_request_id=request.get('id'),handled_at_ms=self.clock()*1000)
        self.write('helper-result:'+key,handled) # durable before MCP completion
        with self.lock:self.seen[key]='returned-not-native-completed'
        return {'content':[{'type':'text','text':output}]}
