"""Trusted controller seam; never an HTTP proof-upload verifier or admission gate."""
import hashlib
import json
import math
from dataclasses import dataclass

TOOLS = frozenset({'root_read_instructions', 'root_ack_instructions',
                   'root_oversight_snapshot', 'root_role_reply', 'root_luna_hold'})

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def meaningful(args):
    return (type(args) is dict and set(args) == {'body', 'next_action', 'checkpoint'}
            and all(type(args[k]) is str and 8 <= len(args[k].strip()) <= 4000 for k in args))

@dataclass(frozen=True)
class NativeObservation:
    owner_ref: str
    profile_sha256: str
    session_id: str
    user_message_id: str
    assistant_message_id: str
    part_id: str
    call_id: str
    tool: str
    args_json: str
    challenge: str
    envelope: str
    issued_at: float
    completed_at: float
    source_sha256: str
    receipt_ref: str
    discriminator: str = 'opencode-native-v1'
    native_tool: str = ''

class NativeVerifier:
    """Dependencies are fixed authenticated controller readers, not model callbacks.

    observe() takes no owner, proof JSON, history, receipt or session parameters.
    context supplies source-selected dispatch/helper records; reader supplies own
    authenticated native history; binding verifies current actual kernel/profile.
    This module alone does not authenticate a callback or authorize role effects.
    """
    def __init__(self, context_reader, history_reader, binding_reader, clock, *, mcp_prefix='root_gateway_'):
        if mcp_prefix != 'root_gateway_':
            raise ValueError('fixed installed MCP namespace')
        self.mcp_prefix = mcp_prefix
        self.context_reader = context_reader
        self.history_reader = history_reader
        self.binding_reader = binding_reader
        self.clock = clock

    def observe(self):
        if not all(callable(x) for x in (self.context_reader, self.history_reader, self.binding_reader, self.clock)):
            raise ValueError('trusted controller dependency missing')
        before = self.context_reader()
        required = {'owner_ref', 'profile_sha256', 'kernel_ref', 'session_id', 'user_message_id',
                    'input_sha256', 'challenge', 'envelope', 'issued_at', 'deadline',
                    'provider_id', 'model_id', 'helper', 'revision'}
        if type(before) is not dict or set(before) != required:
            raise ValueError('fixed context schema')
        if before['provider_id'] != 'zai-coding-plan' or before['model_id'] != 'glm-5.3-flash':
            raise ValueError('production provider binding')
        now = self.clock()
        if not all(finite(x) for x in (now, before['issued_at'], before['deadline'])):
            raise ValueError('finite source time')
        if not 0 < before['deadline'] - before['issued_at'] <= 120 or not before['issued_at'] <= now <= before['deadline']:
            raise ValueError('expired response window')
        if not self.binding_reader(before):
            raise ValueError('current kernel profile owner binding')
        history = self.history_reader(before)
        after = self.context_reader()
        if digest(before) != digest(after) or not self.binding_reader(after):
            raise ValueError('context changed across native read')
        if type(history) is not list:
            raise ValueError('native history schema')
        relevant = []
        user = None
        seen_ids = set()
        for record in history:
            info = record.get('info', {})
            if info.get('sessionID') != before['session_id']:
                raise ValueError('foreign native session')
            rid = info.get('id')
            if type(rid) is not str or not rid or rid in seen_ids:
                raise ValueError('duplicate native message')
            seen_ids.add(rid)
            if info.get('role') == 'user' and rid == before['user_message_id']:
                user = record
            if info.get('role') == 'assistant' and info.get('parentID') == before['user_message_id']:
                relevant.append(record)
        if user is None or not relevant:
            raise ValueError('selected actual input missing')
        # Hash exact selected text parts, not a model-provided envelope argument.
        text = ''.join(p['text'] for p in user.get('parts', []) if p.get('type') == 'text' and type(p.get('text')) is str)
        if hashlib.sha256(text.encode()).hexdigest() != before['input_sha256']:
            raise ValueError('actual input body mismatch')
        def source_time(value):
            if not finite(value):
                raise ValueError('native millisecond time missing')
            seconds = value / 1000
            if not before['issued_at'] - 1 <= seconds <= min(now + 1, before['deadline']):
                raise ValueError('stale future native event')
            return seconds
        source_time(user['info'].get('time', {}).get('created'))
        helper = before['helper']
        if type(helper) is not dict or set(helper) != {'tool', 'args', 'output', 'receipt_ref', 'recorded_at'}:
            raise ValueError('fixed helper schema')
        if helper['tool'] not in TOOLS or not finite(helper['recorded_at']):
            raise ValueError('helper binding')
        matches = []
        part_ids, call_ids = set(), set()
        for record in relevant:
            info = record['info']
            if (info.get('providerID'), info.get('modelID')) != (before['provider_id'], before['model_id']):
                raise ValueError('native execution provider')
            created = source_time(info.get('time', {}).get('created'))
            native_completed = info.get('time', {}).get('completed')
            completed = source_time(native_completed) if native_completed is not None else now + 1
            if completed < created:
                raise ValueError('native message ordering')
            for part in record.get('parts', []):
                if part.get('type') != 'tool':
                    continue
                native_tool = part.get('tool')
                tool_map = {self.mcp_prefix + name: name for name in TOOLS}
                if native_tool not in tool_map:
                    raise ValueError('unapproved native tool')
                if (part.get('sessionID'), part.get('messageID')) != (before['session_id'], info['id']):
                    raise ValueError('native part correlation')
                pid, cid = part.get('id'), part.get('callID')
                if not all(type(x) is str and x for x in (pid, cid)) or pid in part_ids or cid in call_ids:
                    raise ValueError('native call identity')
                part_ids.add(pid); call_ids.add(cid)
                state = part.get('state', {})
                if state.get('status') != 'completed':
                    raise ValueError('pending or failed native tool')
                start = source_time(state.get('time', {}).get('start'))
                end = source_time(state.get('time', {}).get('end'))
                if not created <= start <= end <= completed:
                    raise ValueError('native tool time ordering')
                if tool_map[native_tool] == helper['tool'] and state.get('input') == helper['args'] and state.get('output') == helper['output']:
                    if not start <= helper['recorded_at'] <= end:
                        raise ValueError('helper receipt not before completion')
                    matches.append((info, part, end))
        if len(matches) != 1:
            raise ValueError('unique genuine completed helper tool required')
        # A genuine completed native tool response can precede the final model
        # message. Do not confuse prompt responsiveness with task completion.
        if helper['tool'] in ('root_role_reply', 'root_luna_hold') and not meaningful(helper['args']):
            raise ValueError('meaningful model response required')
        if helper['tool'] in ('root_read_instructions', 'root_oversight_snapshot') and helper['args'] != {}:
            raise ValueError('fixed read arguments')
        if helper['tool'] == 'root_ack_instructions' and (type(helper['args']) is not dict or set(helper['args']) != {'instructions_sha256'} or len(helper['args']['instructions_sha256']) != 64):
            raise ValueError('instruction ACK schema')
        info, part, end = matches[0]
        return NativeObservation(before['owner_ref'], before['profile_sha256'], before['session_id'],
             before['user_message_id'], info['id'], part['id'], part['callID'], helper['tool'],
             json.dumps(helper['args'],sort_keys=True), before['challenge'], before['envelope'],
             before['issued_at'], end, digest(history), helper['receipt_ref'], native_tool=part['tool'])
