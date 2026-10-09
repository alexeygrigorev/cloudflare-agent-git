"""Durable controller-selected MCP receipts, never caller proof uploads.

The cold plan supplies the reviewed owner-private save/read implementation and
fixed incarnation path. This module does not provision directories or launch.
"""
import copy,hashlib,json,threading
from opencode_native_proof import fixed_reader_context

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class ControllerJournal:
    def __init__(self,read,save,binding):
        self.read=read;self.save=save;self.binding=binding;self.lock=threading.Lock()
    def select_input(self,context):
        """Only trusted controller after actual native accepted input receipt."""
        if not self.binding(context):raise RuntimeError('selected native input binding unavailable')
        with self.lock:
            previous=self.read()
            if previous is not None:
                if type(previous) is not dict or previous.get('phase') not in ('selected','handled'):
                    raise RuntimeError('unknown controller journal held')
                if previous['context'].get('owner')!=context.get('owner'):
                    raise RuntimeError('foreign incarnation journal held')
                if previous['context'].get('user_message_id')==context.get('user_message_id'):
                    if digest(previous['context'])!=digest(context):raise RuntimeError('native input selection conflict')
                    return
                # No pending helper may disappear merely because a new input
                # arrives. Outside controller must explicitly reconcile first.
                if any(v.get('phase')=='pending-reconcile-only' for v in previous.get('records',{}).values()):
                    raise RuntimeError('pending helper blocks new input')
            self.save({'v':1,'phase':'selected','context':copy.deepcopy(context),'records':{},'selected_helper':None,'journal_revision':0})
    def write(self,key,value):
        if type(key) is not str or not key.startswith(('helper-intent:','helper-result:')):
            raise RuntimeError('fixed helper journal key required')
        with self.lock:
            state=self.read()
            if type(state) is not dict or state.get('phase') not in ('selected','handled'):
                raise RuntimeError('selected controller input absent')
            context=state['context']
            if not self.binding(context):raise RuntimeError('native input/kernel no longer current')
            if key in state['records']:
                stored=dict(state['records'][key]);stored.pop('journal_sequence',None)
                if digest(stored)!=digest(value):raise RuntimeError('conflicting immutable helper receipt')
                return
            suffix=key.split(':',1)[1]
            if key.startswith('helper-result:'):
                intent=state['records'].get('helper-intent:'+suffix)
                if type(intent) is not dict or intent.get('context')!=context:
                    raise RuntimeError('actual helper intent absent')
                if (value.get('owner')!=context['owner'] or value.get('kernel')!=context['kernel']
                    or value.get('session_id')!=context['session_id'] or value.get('user_message_id')!=context['user_message_id']
                    or value.get('tool')!=intent['tool'] or value.get('arguments')!=intent['arguments']):
                    raise RuntimeError('helper result differs from selected intent')
                previous_helpers=[v for k,v in state['records'].items() if k.startswith('helper-result:')]
                if previous_helpers and value['handled_at_ms']<max(h['handled_at_ms'] for h in previous_helpers):
                    raise RuntimeError('native helper clock moved backward')
                state['records']['helper-intent:'+suffix]=dict(intent,phase='handled-not-native-completed')
                state['selected_helper']=key;state['phase']='handled'
            elif value.get('context')!=context or value.get('phase')!='pending-reconcile-only':
                raise RuntimeError('helper intent not selected current input')
            state['journal_revision']=state.get('journal_revision',0)+1
            state['records'][key]=copy.deepcopy(value)
            if key.startswith('helper-result:'):state['records'][key]['journal_sequence']=state['journal_revision']
            self.save(state) # reviewed private save; durable before MCP response
    def selected_context(self):
        return self.selected_observation()['context']
    def selected_observation(self):
        with self.lock:
            state=self.read()
            if type(state) is not dict or state.get('phase')!='handled' or not state.get('selected_helper'):
                raise RuntimeError('completed local helper selection absent')
            context=state['context'];handled=state['records'][state['selected_helper']]
            if not self.binding(context):raise RuntimeError('selected current native membership unavailable')
            revision=state.get('journal_revision')
            if type(revision) is not int or revision<1:raise RuntimeError('durable helper batch revision absent')
            current=dict(context,revision=revision)
            helpers=[v for key,v in state['records'].items() if key.startswith('helper-result:')]
            helpers.sort(key=lambda v:v['journal_sequence'])
            if not helpers or helpers[-1]!=handled:raise RuntimeError('latest immutable helper sequence mismatch')
            return {'revision':revision,'context':fixed_reader_context(current,handled),
                'helper_contexts':[fixed_reader_context(current,h) for h in helpers]}
