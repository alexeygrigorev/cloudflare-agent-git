"""Private aggregate adapters; quota is never converted into tokens or cost."""
import argparse, collections, concurrent.futures, datetime as dt, gzip, hashlib, json, os, pathlib, subprocess, time

def quotas(store):
    path=store/'quotas.json'
    try: old=json.loads(path.read_text())
    except (OSError,ValueError): old={}
    if time.time()-old.get('observed_unix',0)<300:return old
    def one(provider):
        try:
            p=subprocess.run(['quse',provider,'--json'],capture_output=True,text=True,timeout=30)
            if p.returncode: return provider,{'status':'error','error':'provider query failed','windows':{}}
            x=json.loads(p.stdout).get(provider,{})
            return provider,{'status':x.get('status','unknown'),'error':x.get('error'),'windows':x.get('windows',{}),'limit_reached':x.get('details',{}).get('limit_reached')}
        except (OSError,ValueError,subprocess.TimeoutExpired):return provider,{'status':'error','error':'unavailable/timeout','windows':{}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: values=dict(pool.map(one,['codex','claude','zai','gemini','go']))
    result={'observed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'observed_unix':time.time(),'providers':values,'limits':'Provider account quota windows; never agent tokens, subscription cost, or permission to launch.'}
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result));tmp.chmod(0o600);tmp.replace(path);return result

def temporal(store,observations,tasks,at):
    path=store/'observation-state.json'
    try: state=json.loads(path.read_text())
    except (OSError,ValueError):state={'first_observed_at':at,'conversations':{},'agents':{},'task_states':{},'task_observed_seconds':{},'last_unix':time.time()}
    now=time.time(); elapsed=min(120,max(0,now-state.get('last_unix',now)))
    # A conversation reused in multiple PTYs is still a single cumulative stream.
    grouped={}
    for r in observations:
        u=r.get('usage')
        if u and u.get('conversation_id'):
            key=u['source']+':'+u['conversation_id']
            if key not in grouped or (u.get('total_tokens') or 0)>(grouped[key].get('total_tokens') or 0):grouped[key]=u
    for key,u in grouped.items():
        current=u.get('total_tokens')
        if current is None:continue
        item=state['conversations'].setdefault(key,{'first_at':at,'first_cumulative_tokens':current,'latest_cumulative_tokens':current,'source':u['source'],'conversation_id':u['conversation_id']})
        item['latest_cumulative_tokens']=max(current,item['latest_cumulative_tokens']);item['tokens_since_observer']=item['latest_cumulative_tokens']-item['first_cumulative_tokens']
    for r in observations:
        identity=r.get('id') or r.get('harness_conversation_id') or ('missing:'+str(r.get('tag')))
        agent=state['agents'].setdefault(identity,{
            'tag':r.get('tag'),
            'team_id':r.get('team_id'),
            'parent_session':r.get('parent_session'),
            'parent_tag':r.get('parent_tag'),
            'harness_conversation_id':r.get('harness_conversation_id'),
            'role':r.get('role'),
            'responsibility':r.get('responsibility'),
            'first_seen_at':at,
            'pid_live_seconds':0,
            'hook_working_seconds':0,
            'hook_idle_seconds':0,
            'cpu_observed_delta_seconds':0,
            'previous_cpu':None,
            'previous_start':None,
            'idle_since_unix':None
        })
        if r.get('parent_session') and not agent.get('parent_session'):
            agent['parent_session']=r.get('parent_session')
        if r.get('parent_tag') and not agent.get('parent_tag'):
            agent['parent_tag']=r.get('parent_tag')
        if r.get('harness_conversation_id') and not agent.get('harness_conversation_id'):
            agent['harness_conversation_id']=r.get('harness_conversation_id')
        if r.get('responsibility') and not agent.get('responsibility'):
            agent['responsibility']=r.get('responsibility')
        if r['pid_live']:agent['pid_live_seconds']+=elapsed
        state_now=r.get('reported_state')
        if r['pid_live'] and not r['stale_hook']:
            if state_now=='working':agent['hook_working_seconds']+=elapsed
            elif state_now in ('idle','waiting'):agent['hook_idle_seconds']+=elapsed
        if r['pid_live'] and state_now in ('idle','waiting'):
            if agent['idle_since_unix'] is None:agent['idle_since_unix']=now
        else:agent['idle_since_unix']=None
        old=agent.get('previous_cpu');cur=r.get('cpu_seconds')
        if old is not None and cur is not None and agent['previous_start']==r.get('proc_start_ticks'):agent['cpu_observed_delta_seconds']+=max(0,cur-old)
        agent['previous_cpu']=cur;agent['previous_start']=r.get('proc_start_ticks')
        r['observed_idle_seconds']=max(0,now-agent['idle_since_unix']) if agent['idle_since_unix'] is not None else None
        if r.get('usage'):
            key=r['usage']['source']+':'+str(r['usage'].get('conversation_id'));base=state['conversations'].get(key,{})
            r['usage']['first_observed_cumulative_tokens']=base.get('first_cumulative_tokens');r['usage']['tokens_since_observer']=base.get('tokens_since_observer')
    events=[]
    for t in tasks:
        tid=t.get('id');new=t.get('status');previous=state['task_states'].get(tid)
        if previous is not None:state['task_observed_seconds'].setdefault(tid,{})[previous]=state['task_observed_seconds'].get(tid,{}).get(previous,0)+elapsed
        if new!=previous:events.append({'at':at,'task_id':tid,'owner_tag':t.get('owner_tag'),'from_status':previous,'to_status':new,'start_before_observer':'unknown' if previous is None else False})
        state['task_states'][tid]=new
    if events:
        with (store/'task-transitions.jsonl').open('a') as f:
            for event in events:f.write(json.dumps(event)+'\n')
        (store/'task-transitions.jsonl').chmod(0o600)
    state['last_unix']=now;tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.chmod(0o600);tmp.replace(path)
    return {'first_observed_at':state['first_observed_at'],'conversations':list(state['conversations'].values()),'tokens_since_observer_known':sum(v.get('tokens_since_observer',0) for v in state['conversations'].values()),'task_observed_seconds':state['task_observed_seconds'],'task_transitions_this_sample':events,'limits':'Sampling estimates; state start before observer is unknown; token change covers observer interval, not total experiment expenditure.'}

def archive_history(store,dayfile,max_active_bytes=192*1024*1024,floor_active_bytes=160*1024*1024):
    def digest(handle):
        h=hashlib.sha256();size=0
        while chunk:=handle.read(65536):h.update(chunk);size+=len(chunk)
        return size,h.hexdigest()
    try:previous={r['file']:r for r in json.loads((store/'retention-manifest.json').read_text()).get('archives',[])}
    except (OSError,ValueError):previous={}
    hashes={}
    for p in store.glob('snapshots-*.jsonl'):
        if p!=dayfile or p.stat().st_size>=2*1024*1024:
            target=store/(p.name+'.'+str(time.time_ns())+'.gz');pending=store/('.archive-'+target.name+'.pending')
            with p.open('rb') as src,gzip.open(pending,'wb',compresslevel=6) as dst:
                while chunk:=src.read(65536):dst.write(chunk)
            pending.chmod(0o600)
            with p.open('rb') as source:source_size,source_sha=digest(source)
            with gzip.open(pending,'rb') as decoded:decoded_size,decoded_sha=digest(decoded)
            if (source_size,source_sha)!=(decoded_size,decoded_sha):raise OSError('archive SHA256 verification failed; original and pending archive retained')
            pending.replace(target)
            with target.open('rb') as compressed:_,compressed_sha=digest(compressed)
            hashes[target.name]={'uncompressed_sha256':source_sha,'uncompressed_bytes':source_size,'sha256':compressed_sha}
            p.unlink() # only verified metrics-owned original; all sample bytes survive in archive

    active_files=[p for p in store.glob('snapshots-*') if p.is_file()]
    current_active_bytes=sum(p.stat().st_size for p in active_files)
    if current_active_bytes>max_active_bytes:
        prefix=dayfile.name.replace('.jsonl','')
        candidates=sorted([p for p in active_files if p.name.endswith('.gz') and not p.name.startswith(prefix) and not p.name.startswith(dayfile.name)],key=lambda p:p.name)
        archive_dir=store/'archive'
        archive_dir.mkdir(parents=True,exist_ok=True)
        try:os.chmod(archive_dir,0o700)
        except OSError:pass
        archive_manifest_path=archive_dir/'manifest.json'
        try:
            archive_manifest=json.loads(archive_manifest_path.read_text())
            if not isinstance(archive_manifest,dict):raise ValueError('invalid manifest')
            if 'archives' not in archive_manifest or not isinstance(archive_manifest['archives'],list):archive_manifest['archives']=[]
        except (OSError,ValueError):
            archive_manifest={'schema_version':1,'archives':[],'policy':'Preserved private archive of closed daily snapshot gzip chunks to maintain active metrics store below 256 MiB cap. Mode 0700/0600 enforced. Zero historical bytes deleted.'}
        manifest_index={r['file']:idx for idx,r in enumerate(archive_manifest['archives']) if isinstance(r,dict) and 'file' in r}
        for p in candidates:
            if current_active_bytes<=floor_active_bytes:break
            with p.open('rb') as src:size,sha=digest(src)
            dest=archive_dir/p.name
            p.replace(dest)
            try:os.chmod(dest,0o600)
            except OSError:pass
            entry={'file':p.name,'bytes':size,'sha256':sha,'mtime_ns':dest.stat().st_mtime_ns,'relocated_at':dt.datetime.now(dt.timezone.utc).isoformat()}
            if p.name in manifest_index:archive_manifest['archives'][manifest_index[p.name]]=entry
            else:
                manifest_index[p.name]=len(archive_manifest['archives'])
                archive_manifest['archives'].append(entry)
            current_active_bytes-=size
        archive_manifest['total_bytes']=sum(r['bytes'] for r in archive_manifest['archives'])
        archive_manifest['file_count']=len(archive_manifest['archives'])
        manifest_tmp=archive_dir/'manifest.tmp'
        manifest_tmp.write_text(json.dumps(archive_manifest,indent=2))
        try:os.chmod(manifest_tmp,0o600)
        except OSError:pass
        manifest_tmp.replace(archive_manifest_path)

    archives=[]
    for p in sorted(store.glob('snapshots-*')):
        if not p.is_file():continue
        st=p.stat();cached=previous.get(p.name,{})
        if p.name in hashes:record=hashes[p.name]
        elif cached.get('bytes')==st.st_size and cached.get('mtime_ns')==st.st_mtime_ns:record={k:cached[k] for k in ['sha256','uncompressed_sha256','uncompressed_bytes'] if k in cached}
        else:
            with p.open('rb') as file:_,sha=digest(file)
            record={'sha256':sha}
        archives.append({'file':p.name,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,**record})
    manifest={'archives':archives,'total_bytes':sum(r['bytes'] for r in archives),'policy':'All samples retained; original and decompressed archive SHA256+length must match before replacing owned original. Pending failed archives excluded from export. 256MiB cap preserves existing data.'}
    temp=store/'retention-manifest.tmp';temp.write_text(json.dumps(manifest));temp.chmod(0o600);temp.replace(store/'retention-manifest.json');return manifest

def cli_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Metrics rolling archive retention trigger')
    root = pathlib.Path(__file__).resolve().parents[2]
    default_store = root / '.local/metrics' if (root / '.local/metrics').is_dir() else pathlib.Path('.local/metrics')
    parser.add_argument('--store', default=str(default_store), help="path to metrics store (default: ROOT / '.local/metrics' or current directory '.local/metrics')")
    parser.add_argument('--dayfile', default=None, help="optional explicit path to today's active dayfile (default: store / ('snapshots-' + dt.date.today().isoformat() + '.jsonl'))")
    parser.add_argument('--max-active-bytes', type=int, default=192 * 1024 * 1024, help='ceiling in bytes (default: 192*1024*1024)')
    parser.add_argument('--floor-active-bytes', type=int, default=160 * 1024 * 1024, help='floor target in bytes (default: 160*1024*1024)')
    parser.add_argument('--force', action='store_true', help='temporarily sets max_active_bytes to 0 so all candidate closed archives from previous days are relocated')
    parser.add_argument('--dry-run', action='store_true', help='computes what would be moved without mutating files or manifests')
    parser.add_argument('--json', action='store_true', help='emit machine-readable JSON output')

    args = parser.parse_args(argv)
    store = pathlib.Path(args.store)
    dayfile = pathlib.Path(args.dayfile) if args.dayfile else (store / ('snapshots-' + dt.date.today().isoformat() + '.jsonl'))
    max_active_bytes = 0 if args.force else args.max_active_bytes
    floor_active_bytes = 0 if args.force else args.floor_active_bytes

    if args.dry_run:
        active_files = [p for p in store.glob('snapshots-*') if p.is_file()] if store.exists() else []
        current_active_bytes = sum(p.stat().st_size for p in active_files)
        prefix = dayfile.name.replace('.jsonl', '')
        candidates = sorted([p for p in active_files if p.name.endswith('.gz') and not p.name.startswith(prefix) and not p.name.startswith(dayfile.name)], key=lambda p: p.name)
        candidate_bytes = sum(p.stat().st_size for p in candidates)
        would_relocate = []
        would_relocate_bytes = 0
        if current_active_bytes > max_active_bytes:
            simulated_bytes = current_active_bytes
            for p in candidates:
                if simulated_bytes <= floor_active_bytes:
                    break
                would_relocate.append(p.name)
                sz = p.stat().st_size
                simulated_bytes -= sz
                would_relocate_bytes += sz
        if args.json:
            print(json.dumps({
                'status': 'ok',
                'dry_run': True,
                'active_bytes': current_active_bytes,
                'active_files': len(active_files),
                'candidate_files': [p.name for p in candidates],
                'candidate_bytes': candidate_bytes,
                'candidates': [p.name for p in candidates],
                'would_relocate': would_relocate,
                'would_relocate_files': would_relocate,
                'would_relocate_bytes': would_relocate_bytes,
                'manifest_path': str(store / 'retention-manifest.json'),
            }))
        else:
            print(f"Dry run: {len(candidates)} candidate files ({candidate_bytes} bytes). Active files: {len(active_files)} ({current_active_bytes} bytes). Would relocate: {len(would_relocate)} files ({would_relocate_bytes} bytes).")
        return 0

    manifest = archive_history(store, dayfile, max_active_bytes=max_active_bytes, floor_active_bytes=floor_active_bytes)
    if args.json:
        print(json.dumps({'status': 'ok', 'active_bytes': manifest['total_bytes'], 'active_files': len(manifest['archives']), 'manifest_path': str(store / 'retention-manifest.json')}))
    else:
        print(f"Active store: {manifest['total_bytes']} bytes across {len(manifest['archives'])} files. Manifest: {store / 'retention-manifest.json'}")
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(cli_main())
