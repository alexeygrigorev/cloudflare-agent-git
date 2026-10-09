"""Fixed root-check {} channel command, outside readers and writer locks.

Input and prior completed reply are selected by the authority's authenticated
own-root routes. Prompt 204/input acceptance never claims completed check.
"""
import copy,hashlib,json,re
from opencode_native_dispatch import NativeDispatch,digest
from opencode_controller_gate import ControllerGate

def quiescent(history,session_id):
    if type(history) is not list or not history:return False
    if any(type(h) is not dict or h.get('info',{}).get('sessionID')!=session_id for h in history):return False
    newest=history[-1]
    info=newest.get('info',{})
    if info.get('role')!='assistant' or type(info.get('time',{}).get('completed')) not in (int,float):return False
    for item in history:
        for part in item.get('parts',[]):
            if part.get('type')=='tool' and part.get('state',{}).get('status') not in ('completed','error'):
                return False
    return True

class CheckDispatch:
    def __init__(self,owner,session_id,account_binding,credential,instructions_sha256,
                 authority_post,read,save,history,native_post,admission,command_guard,kernel_guard,
                 archive,archive_reader):
        self.owner=copy.deepcopy(owner);self.session_id=session_id;self.credential=credential
        self.post=authority_post;self.guard=command_guard;self.read=read
        self.gate=ControllerGate(owner,credential,instructions_sha256,authority_post)
        def current(owner,sid,selected):
            if owner!=self.owner or sid!=self.session_id:raise RuntimeError('fixed paid dispatcher owner differs')
            kernel_guard()
            self.gate({'owner':owner},'root-check')
            kernel_guard()
        def completion(previous):
            return self.post('/v1/host-recovery',{'v':1,'credential':credential,'op':'opencode-reply-receipt'})
        self.dispatcher=NativeDispatch(owner,session_id,account_binding,read,save,history,native_post,
            admission,current,completed_reply_reader=completion,archive=archive,
            quiescent=lambda sid:quiescent(history(),sid),archive_reader=archive_reader)
    def __call__(self,command):
        self.guard(command)
        if command.get('operation')!='root-check' or command.get('payload')!={} or command.get('owner')!=self.owner:
            raise RuntimeError('existing fixed root-check required')
        source=self.gate.initial_input()
        selected={k:source[k] for k in ('body','input_sha256','challenge','envelope','issued_at','deadline','owner_ref')}
        previous=self.read()
        if previous is not None and previous.get('phase')!='released' and previous.get('selected')!=selected:
            self.dispatcher.release_prior()
        result=self.dispatcher.dispatch(selected)
        # POST204 cannot stand in for the authenticated native user event.
        reconciled=self.dispatcher.reconcile(selected)
        self.guard(command)
        return dict(reconciled,check_completed=False,authority_effect=False)
