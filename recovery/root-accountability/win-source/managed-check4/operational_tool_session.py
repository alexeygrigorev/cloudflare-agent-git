"""Off-reader root/child routing on the existing observed native RPC.

The host installs fixed producers. No model-supplied paths, ancestry or identity
can enter them. Child ancestry checks stay in the independently reviewed router.
"""
import copy
from check_tool_router import CheckToolRouter

class OperationalToolSession:
    def __init__(self,current_state,read_thread,read_rollout,instructions,reports,parent_handler,check=None,persist=None,helper=None,managed=None):
        self.current_state=current_state;self.parent_handler=parent_handler
        self.router=CheckToolRouter(current_state,read_thread,read_rollout,instructions,reports)
        self.managed=managed
        self.outcome=None
        if check is not None and persist is not None:
            from check_outcome_producer import CheckOutcomeProducer
            self.outcome=CheckOutcomeProducer(current_state,
                managed.supervised if managed is not None else self.router.supervised,check,persist,helper=helper)

    def is_parent(self,request):
        s=self.current_state();p=request.get('params',{})
        if p.get('threadId')!=s.get('conversation_id'):return False
        if (request.get('method')!='item/tool/call' or not p.get('callId')
            or p.get('turnId')!=s.get('provider_turn_id')
            or p.get('namespace') not in (None,'')
            or not s.get('thread_owner') or s.get('provider_turn_state')!='busy'):
            raise RuntimeError('parent request has no exact current owned busy turn')
        if not ((p.get('tool')=='root_read_instructions' and p.get('arguments')=={})
                or (p.get('tool')=='root_role_ack' and p.get('arguments')=={'accept_custody':True})
                or self.managed is not None and p.get('tool') in ('root_spawn_check','root_wait_check') and self.managed.authorize(request)
                or self.outcome is not None and p.get('tool') in ('root_check_inspect','root_check_result') and self.outcome.authorize(request)):
            raise RuntimeError('unapproved parent tool')
        return True

    def authorize(self,request):
        return True if self.is_parent(request) else (self.managed.authorize(request) if self.managed is not None else self.router.authorize(request))

    def handle(self,request):
        if self.is_parent(request):
            if self.managed is not None and request['params']['tool'] in ('root_spawn_check','root_wait_check'):
                return self.managed.handle_parent(request)
            if self.outcome is not None and request['params']['tool'] in ('root_check_inspect','root_check_result'):
                return self.outcome.handle(request)
            state=copy.deepcopy(self.current_state())
            return self.parent_handler(state,request)
        return self.managed.child_read(request) if self.managed is not None else self.router.handle(request)

    def observe(self,message):
        if self.managed is not None:self.managed.observe(message)
        else:self.router.observe(message)
        return self.outcome.observe(message) if self.outcome is not None else False
    def supervised(self,child):return self.managed.supervised(child) if self.managed is not None else self.router.supervised(child)
