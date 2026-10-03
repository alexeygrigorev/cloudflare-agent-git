"""Read exact native ACK evidence without issuing ACK/delivery or changing cursors."""
import fcntl, hashlib, json, os, pathlib, stat, uuid

LIMIT = 1024 * 1024

def read_json(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            raise ValueError('nonregular or oversized native evidence')
        raw = handle.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('oversized native evidence')
    return json.loads(raw), hashlib.sha256(raw).hexdigest()

def native_state_root():
    if os.environ.get('APLEXER_STATE_DIR'):
        return pathlib.Path(os.environ['APLEXER_STATE_DIR']).absolute()
    if os.environ.get('XDG_STATE_HOME'):
        return pathlib.Path(os.environ['XDG_STATE_HOME']) / 'aplexer'
    return pathlib.Path.home() / '.local/state/aplexer'

def exact_ack(pending, recipient_id, tag, workspace, state_root=None):
    """Missing/pruned/legacy-only/locked/inconsistent evidence remains unresolved.

    Original sender may differ from this service, but must match the persisted
    envelope. Require its original resolved recipient and exact cursor entry.
    No tag inheritance, high-water guessing, mailbox scans or inbox inference.
    """
    try:
        mid = str(uuid.UUID(pending['id']))
        sender = str(uuid.UUID(pending['sender_id']))
        recipient = str(uuid.UUID(recipient_id))
        root = pathlib.Path(state_root) if state_root is not None else native_state_root()
        workspace = str(pathlib.Path(workspace).resolve())
        box = root / 'messages' / hashlib.sha256(os.fsencode(workspace)).hexdigest()[:32]
        # Existing native lock only; read-only nonblocking lease respects mailbox
        # append/GC and cursor writers. Never creates or mutates native state.
        fd = os.open(box / '.mailbox.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                return None
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            meta, _ = read_json(box / 'workspace.json')
            envelope, envelope_sha = read_json(box / 'msgs' / (mid + '.json'))
            cursor, cursor_sha = read_json(box / 'cursors' / (recipient + '.json'))
            if (meta.get('workspace') != workspace or envelope.get('workspace') != workspace
                    or envelope.get('id') != mid or envelope.get('schema_version') != 1
                    or envelope.get('from', {}).get('session_id') != sender
                    or envelope.get('from', {}).get('workspace') != workspace
                    or envelope.get('from', {}).get('tag') != 'experiment-supervision'
                    or envelope.get('to') != {'session_id': recipient, 'tag': tag}):
                return None
            ids = cursor.get('exceptions')
            if not isinstance(ids, list) or mid not in ids:
                return None
            return {'message_id': mid, 'original_sender_id': sender,
                    'recipient_id': recipient, 'source': 'native-exact-consumer-cursor',
                    'envelope_sha256': envelope_sha, 'cursor_sha256': cursor_sha,
                    'mailbox_key': box.name, 'read_only': True}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
