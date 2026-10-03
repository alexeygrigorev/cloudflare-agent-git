"""Lossless private archives; storage exhaustion pauses work instead of erasing evidence."""
import gzip,hashlib,json,os,pathlib,time

SOFT_BYTES = 128 * 1024 * 1024
HARD_BYTES = 256 * 1024 * 1024

class StorageFull(RuntimeError):
    pass

def sync_dir(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def storage_usage(spool):
    return sum(path.stat().st_size for path in spool.rglob('*') if path.is_file())

def storage_guard(spool, soft=SOFT_BYTES, hard=HARD_BYTES):
    used = storage_usage(spool)
    return {'used_bytes':used,'soft_bytes':soft,'hard_bytes':hard,
            'state':'paused-hard-limit' if used >= hard else 'soft-limit-warning' if used >= soft else 'ok',
            'policy':'preserve all archives and unresolved evidence; pause at hard limit'}

def archive_verified(source, spool, hard=HARD_BYTES):
    """Unlink source only after durable gzip, digest roundtrip and persisted manifest."""
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    packed = gzip.compress(data,mtime=0)
    if storage_usage(spool) + len(packed) + 4096 >= hard:
        raise StorageFull('archive would exceed storage hard limit; original evidence preserved')
    archive_dir = spool / 'archives'
    archive_dir.mkdir(exist_ok=True)
    target = archive_dir / f'{time.time_ns()}-{source.name}-{digest}.gz'
    with target.open('xb') as handle:
        handle.write(packed);handle.flush();os.fsync(handle.fileno())
    sync_dir(archive_dir)
    restored = gzip.decompress(target.read_bytes())
    if restored != data or hashlib.sha256(restored).hexdigest() != digest:
        raise RuntimeError('archive verification failed; original evidence preserved')
    record = {'source_name':source.name,'archive':str(target.relative_to(spool)),
              'sha256':digest,'archive_sha256':hashlib.sha256(packed).hexdigest(),
              'original_bytes':len(data),'compressed_bytes':len(packed),'created_at_ns':time.time_ns()}
    manifest = archive_dir / 'manifest.jsonl'
    with manifest.open('a') as handle:
        handle.write(json.dumps(record)+'\n');handle.flush();os.fsync(handle.fileno())
    sync_dir(archive_dir)
    # Record identifies original bytes; concurrent append/replacement stays live for next archive.
    if source.read_bytes() == data:
        source.unlink()
        sync_dir(spool)
    return record

def read_archived(spool,name):
    candidates = sorted((spool/'archives').glob(f'*-{name}-*.gz'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    if not candidates:
        return None
    target = candidates[0]
    data = gzip.decompress(target.read_bytes())
    expected = target.name.rsplit('-',1)[1][:-3]
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('archived receipt digest mismatch; no send authorized')
    return json.loads(data)

def archive_operational(spool,protected,keep=2048,hard=HARD_BYTES):
    files = sorted([*spool.glob('receipt-*.json'),*spool.glob('reply-*.json'),*spool.glob('delivery-*.json')],key=lambda p:p.stat().st_mtime,reverse=True)
    count = 0
    for source in files[keep:]:
        if any(value and value in source.name for value in protected):
            continue
        archive_verified(source,spool,hard);count += 1
    return count
