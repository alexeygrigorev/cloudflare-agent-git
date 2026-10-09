"""Short durable provider-state transactions; never lock across an RPC."""
import contextlib
import copy
import json
import os
import pathlib
import threading

_lock = threading.RLock()
FIELDS = ('provider_turn_id', 'provider_turn_state', 'provider_pending_tools', 'provider_terminal_turns', 'provider_event_conflict',
          'api_history_validated', 'api_history_receipt_sha256', '_api_event_revision')

def revision(state):
    value = state.get('_api_event_revision', 0)
    if type(value) is not int or value < 0:
        raise RuntimeError('invalid provider-state revision')
    return value

def binding(state):
    return state.get('conversation_id'), state.get('thread_owner')

@contextlib.contextmanager
def transaction(path):
    with _lock:
        with pathlib.Path(str(path)+'.provider-lock').open('a+b') as stream:
            stream.seek(0)
            if not stream.read(1):
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

def merge(current, proposed):
    result = copy.deepcopy(proposed)
    old, new = revision(current), revision(proposed)
    if current.get('conversation_id') and binding(current) != binding(proposed):
        raise RuntimeError('provider-state owner/CID changed')
    if new > old:
        raise RuntimeError('only native provider transaction may advance revision')
    if old > new:
        for field in FIELDS:
            result.pop(field, None)
            if field in current:
                result[field] = copy.deepcopy(current[field])
    return result

def persist(path, proposed, writer):
    with transaction(path):
        current = json.loads(path.read_text()) if path.exists() else {}
        value = merge(current, proposed) if current.get('runtime_mode') == 'api-root' else copy.deepcopy(proposed)
        writer(path, value)
        proposed.clear(); proposed.update(value)

def event(path, expected_binding, message, observer, writer):
    with transaction(path):
        current = json.loads(path.read_text())
        if binding(current) != expected_binding:
            raise RuntimeError('provider event cannot update successor')
        before = copy.deepcopy(current)
        observer(current, message)
        if current != before:
            current['_api_event_revision'] = revision(before)+1
            writer(path, current)

def history(path, expected_binding, thread, validator, writer, receipt_writer):
    with transaction(path):
        current = json.loads(path.read_text())
        if binding(current) != expected_binding:
            raise RuntimeError('history cannot update successor')
        # The authenticated latest legacy turn is a separate native completion
        # source. It cannot clear pending tools or supersede a newer turn.
        turns = thread.get('turns', [])
        if (isinstance(turns, list) and turns and
            turns[-1].get('id') == current.get('provider_turn_id') and
            turns[-1].get('status') == 'completed' and
            current.get('provider_pending_tools') == {} and
            current.get('provider_turn_state') in ('busy','unknown','completed') and
            thread.get('id') == current.get('conversation_id') and
            thread.get('historyMode') == 'legacy'):
            current['provider_turn_state'] = 'completed'
            current.setdefault('provider_terminal_turns',{})[current['provider_turn_id']]=True
        validator(current, thread)
        current['_api_event_revision'] = revision(current)+1
        if current.get('api_history_validated'):
            current['api_history_receipt_sha256'] = receipt_writer(current)
        else:
            current.pop('api_history_receipt_sha256', None)
        writer(path, current)
        return current
