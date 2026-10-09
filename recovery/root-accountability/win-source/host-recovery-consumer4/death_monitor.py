"""Pinned caretaker observations; dependency-injected kernel APIs, no effects.

The Guardian holds the same Job query handle across native/model death. Missing
objects or incomplete provider history are holds, never zero-process evidence.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import copy,time

class Held(RuntimeError):pass

class DeathMonitor:
    def __init__(self,baseline,query_job,process_state,current_guardian,outside_job,checkpoint,factory_attempt):
        self.baseline=copy.deepcopy(baseline)
        self.query_job=query_job;self.process_state=process_state
        self.current_guardian=current_guardian;self.outside_job=outside_job
        self.checkpoint=checkpoint;self.factory_attempt=factory_attempt
    def observe(self,challenge):
        b=self.baseline
        if challenge.get('owner')!=b['owner'] or not isinstance(challenge.get('nonce'),str) or not challenge['nonce']:
            raise Held('server challenge owner/nonce mismatch')
        guardian=self.current_guardian()
        if any(guardian.get(k)!=b['guardian'][k] for k in ('pid','creation_filetime','session_id','user_sid','source_sha256','task_action_sha256')):
            raise Held('current caretaker incarnation/custody mismatch')
        owned=[b['native'][n] for n in ('worker','workload','host_process')]+[b['model']['backend']]
        if guardian['pid'] in {x['pid'] for x in owned} or guardian['session_id']!=b['model']['job']['session_id']:
            raise Held('caretaker overlaps root boundary/session')
        if self.process_state(guardian['pid'],guardian['creation_filetime'])!='alive' or self.outside_job() is not True:
            raise Held('caretaker liveness/Job boundary unknown')
        native=dict(id=b['native']['id'])
        for n in ('worker','workload','host_process'):
            x=b['native'][n];observed=self.process_state(x['pid'],x['creation_filetime'])
            if observed not in ('exited','original-exited-pid-reused'):raise Held('owned native is alive/unknown')
            native[n]=dict(x,state='dead')
        backend=b['model']['backend']
        if self.process_state(backend['pid'],backend['creation_filetime']) not in ('exited','original-exited-pid-reused'):
            raise Held('model backend is alive/unknown')
        accounting=self.query_job() # Must query retained exact native Job handle.
        if type(accounting.get('active_processes')) is not int or accounting['active_processes']!=0 or accounting.get('source')!='QueryInformationJobObject':
            raise Held('exact Job is not drained')
        checkpoint=self.checkpoint()
        if (checkpoint.get('thread_id')!=b['checkpoint']['thread_id']
            or checkpoint.get('history_receipt_sha256')!=b['checkpoint']['history_receipt_sha256']
            or checkpoint.get('provider_turn_state')!='completed'
            or type(checkpoint.get('pending_tool_count')) is not int or checkpoint['pending_tool_count']!=0
            or checkpoint.get('protected_state')!='clear'):
            raise Held('provider/history checkpoint protected or unknown')
        attempt=self.factory_attempt() # An actual durable-journal read, not omitted metadata.
        if attempt is not None:raise Held('factory intent already exists; reconcile only')
        return dict(v=1,challenge=challenge['nonce'],owner=b['owner'],host=b['host'],observed_at=time.time(),
            guardian=dict(guardian,state='alive',outside_owned_jobs=True),native=native,
            model=dict(owner=b['owner'],backend=dict(backend,state='dead'),job=dict(b['model']['job'],queried=True,active_processes=0)),
            checkpoint=checkpoint,factory_attempt=None)
