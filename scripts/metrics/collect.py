#!/usr/bin/env python3
"""Private experiment observation. Never dispatches agents or changes hook state."""
import argparse, datetime as dt, fcntl, json, logging, os, pathlib, subprocess, threading, time, hashlib, http.server, signal, warnings
logger = logging.getLogger('collect')
ROOT=pathlib.Path(__file__).resolve().parents[2]
STORE=ROOT/'.local/metrics'
STORE.mkdir(parents=True,exist_ok=True); os.chmod(STORE,0o700)
from adapters import quotas, temporal, archive_history
from opencode_usage import read_usage as read_opencode_usage, SOURCE as OPENCODE_SOURCE
COUNT_ROLES={'principal','head','executor','subagent'}
APLEXER_STATE=pathlib.Path.home()/'.local/state/aplexer/sessions'

def read_json(p,default=None):
    try: return json.loads(pathlib.Path(p).read_text())
    except (OSError,ValueError): return default

def atomic(p,obj):
    tmp=pathlib.Path(str(p)+'.tmp'); tmp.write_text(json.dumps(obj,ensure_ascii=False)); os.chmod(tmp,0o600); tmp.replace(p)

def disk_session(session_id,workspace=None):
    """Completed sessions pruned from the live aplexer catalog persist on disk.
    Only an exact id+workspace identity match is accepted, and liveness fields
    are dropped so a reused PID can never make a completed session look alive."""
    base=APLEXER_STATE/str(session_id)
    for name in ('session.json','session_record.json'):
        row=read_json(base/name)
        if not isinstance(row,dict) or not row.get('id'): continue
        if str(row.get('id'))!=str(session_id): continue
        record_workspace=row.get('workspace') or row.get('cwd')
        if workspace and record_workspace!=workspace: continue
        row.pop('workload_pid',None)
        row.setdefault('workspace',record_workspace or str(ROOT))
        return row
    return None

def native_usage(session):
    """Codex cumulative native usage: cache categories already INCLUDED in input."""
    binding=read_json(APLEXER_STATE/session['id']/'transcript.json',{})
    path=pathlib.Path(binding.get('path','/nonexistent'))
    if not path.is_file(): return None
    if binding.get('engine') not in ('codex','zcodex'): return None
    try:
        with path.open('rb') as f:
            size=path.stat().st_size; offset=max(0,size-2*1024*1024); f.seek(offset)
            if offset: f.readline()
            data=f.read(2*1024*1024).decode('utf-8',errors='replace')
        result=None
        for line in data.splitlines():
            try: row=json.loads(line)
            except ValueError: continue
            payload=row.get('payload',{})
            if row.get('type')=='event_msg' and payload.get('type')=='token_count':
                total=(payload.get('info') or {}).get('total_token_usage')
                if total:
                    result={'conversation_id':binding.get('engine_session_id'),'source':'codex-native-cumulative','scope':'Conversation cumulative; may include pre-observer history. NOT experiment expenditure.','input_tokens':total.get('input_tokens'),'output_tokens':total.get('output_tokens'),'total_tokens':total.get('total_tokens'),'cached_input_tokens':total.get('cached_input_tokens'),'reasoning_output_tokens':total.get('reasoning_output_tokens'),'cost_usd':None,'cost_basis':None,'observed_at':row.get('timestamp')}
        return result
    except OSError: return None

def rollout_tele_path(tele):
    """Saved rollout file path from telemetry; DB paths are never rollouts."""
    kind=tele.get('type') or ''; path=tele.get('path')
    if not isinstance(path,str) or not path: return None
    if kind.endswith('rollout'): return path
    name=pathlib.PurePath(path).name
    return path if name.endswith('.jsonl') and 'rollout' in name else None

def rollout_usage(path,conversation_id=None):
    """Codex/zcodex saved rollout JSONL: cumulative counters, cost stays unknown.
    A bounded head read recovers session_meta even when the 2MiB tail window no
    longer holds it; a missing or mismatched native conversation id stays unknown
    and is never substituted with the aplexer session UUID."""
    p=pathlib.Path(path).expanduser()
    if not p.is_file(): return None
    try:
        meta_id=None
        try:
            with p.open('rb') as hf: head=hf.read(256*1024).decode('utf-8',errors='replace')
        except OSError:
            head=''
        for line in head.splitlines():
            try: row=json.loads(line)
            except ValueError: continue
            if row.get('type')=='session_meta':
                payload=row.get('payload') or {}
                meta_id=payload.get('id') or payload.get('session_id') or meta_id
                break
        with p.open('rb') as f:
            size=p.stat().st_size; offset=max(0,size-2*1024*1024); f.seek(offset)
            if offset: f.readline()
            data=f.read(2*1024*1024).decode('utf-8',errors='replace')
        result=None
        for line in data.splitlines():
            try: row=json.loads(line)
            except ValueError: continue
            payload=row.get('payload') or {}
            if row.get('type')=='event_msg' and payload.get('type')=='token_count':
                total=(payload.get('info') or {}).get('total_token_usage')
                if total:
                    result={'conversation_id':meta_id,'source':'codex-rollout','scope':'Saved rollout cumulative; may include pre-observer history. NOT experiment expenditure.','input_tokens':total.get('input_tokens'),'output_tokens':total.get('output_tokens'),'total_tokens':total.get('total_tokens'),'cached_input_tokens':total.get('cached_input_tokens'),'reasoning_output_tokens':total.get('reasoning_output_tokens'),'cost_usd':None,'cost_basis':None,'observed_at':row.get('timestamp'),'rollout_path':str(p)}
        if result:
            if conversation_id and meta_id and conversation_id!=meta_id:
                result['conversation_id']=None
                result['scope']+=' Saved telemetry and rollout head disagree on the native conversation id; treated as unknown.'
            elif result['conversation_id'] is None and conversation_id:
                result['conversation_id']=conversation_id
            elif result['conversation_id'] is None:
                result['scope']+=' Native conversation id outside the bounded head/tail window; unknown and excluded from conversation totals.'
        return result
    except OSError: return None

def opencode_sid(item,tele):
    """Exact saved native conversation id; DB titles never establish identity."""
    if tele.get('type')=='opencode-db':
        candidates=[tele.get('conversation_id'),item.get('opencode_session_id'),item.get('resumed_conversation'),item.get('conversation')]
    else:
        candidates=[item.get('opencode_session_id'),item.get('resumed_conversation'),item.get('conversation')]
    return next((c for c in candidates if isinstance(c,str) and c.startswith('ses_')),None)

def proc(pid):
    try:
        raw=pathlib.Path(f'/proc/{pid}/stat').read_text(); fields=raw[raw.rfind(')')+2:].split()
        if fields[0]=='Z': return {'alive':False}
        hz=os.sysconf('SC_CLK_TCK'); pages=os.sysconf('SC_PAGE_SIZE')
        return {'alive':True,'cpu_seconds':(int(fields[11])+int(fields[12]))/hz,'rss_bytes':int(fields[21])*pages,'start_ticks':int(fields[19])}
    except (OSError,ValueError,IndexError,TypeError): return {'alive':False}

def count_status(rows):
    return {key:sum(bool(r.get(key)) for r in rows) for key in ['pid_live','hook_working','stale_hook','unregistered']}

def authentic_conversation_id(s, item):
    """Determine the session's authentic conversation ID.
    Checks:
    1. Live session engine_session_id or conversation_id from live record `s`
    2. Disk session binding (transcript.json or session record on disk)
    3. item.get('harness_conversation_id') or item.get('conversation_id')
    4. item telemetry conversation_id or s telemetry conversation_id
    """
    if not isinstance(item, dict): item = {}
    if not isinstance(s, dict): s = {}

    for val in (s.get('engine_session_id'),
                s.get('conversation_id')):
        if isinstance(val, str) and val.strip():
            return val.strip()

    sid = s.get('id') or item.get('session_id')
    if sid:
        binding = read_json(APLEXER_STATE/str(sid)/'transcript.json', {}) or {}
        for val in (binding.get('engine_session_id'), binding.get('conversation_id')):
            if isinstance(val, str) and val.strip():
                return val.strip()
        disk = disk_session(sid, item.get('workspace', str(ROOT)))
        if disk:
            for val in (disk.get('engine_session_id'), disk.get('conversation_id')):
                if isinstance(val, str) and val.strip():
                    return val.strip()

    for val in (item.get('harness_conversation_id'),
                item.get('conversation_id')):
        if isinstance(val, str) and val.strip():
            return val.strip()

    for val in (item.get('telemetry', {}).get('conversation_id') if isinstance(item.get('telemetry'), dict) else None,
                s.get('telemetry', {}).get('conversation_id') if isinstance(s.get('telemetry'), dict) else None):
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None

def parse_entry_timestamp(entry):
    if not isinstance(entry, dict): return 0.0
    ts = entry.get('observed_at') or entry.get('at') or entry.get('timestamp')
    if ts is None: return 0.0
    if isinstance(ts, (int, float)): return float(ts)
    if isinstance(ts, str):
        try: return dt.datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
        except ValueError: return 0.0
    return 0.0

def match_usage_event(events_path, tag, team_id, session_cid=None):
    """Match usage event from usage-events.jsonl.
    - If session_cid is known: require entry.conversation_id == session_cid. Mismatched IDs NEVER bind.
    - If session_cid is None and event has no conversation_id: legacy fallback to (tag, team_id).
    - If multiple events match: deterministically reconcile by timestamp to select latest cumulative record.
    Returns (found_entry, is_fallback).
    """
    p = pathlib.Path(events_path)
    if not p.is_file() or p.stat().st_size > 16*1024*1024:
        return None, False

    if session_cid:
        session_cid = session_cid.strip() if session_cid else None
    if not session_cid:
        session_cid = None

    matches = []
    has_fallback = False
    try:
        with p.open('r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    entry = json.loads(line_str)
                except (json.JSONDecodeError, ValueError) as exc:
                    logger.warning("Skipping corrupted line in %s: %s", events_path, exc)
                    warnings.warn(f"Skipping corrupted line in {events_path}: {exc}", UserWarning)
                    continue
                if not isinstance(entry, dict):
                    logger.warning("Skipping non-dict JSON entry in %s: %r", events_path, entry)
                    warnings.warn(f"Skipping non-dict JSON entry in {events_path}: {entry}", UserWarning)
                    continue
                if entry.get('tag') != tag or entry.get('team_id') != team_id:
                    continue
                entry_cid = entry.get('conversation_id')
                if entry_cid:
                    entry_cid = entry_cid.strip() if isinstance(entry_cid, str) else None
                if not entry_cid:
                    entry_cid = None
                    if 'conversation_id' in entry:
                        entry['conversation_id'] = None
                if session_cid:
                    if entry_cid == session_cid:
                        matches.append(entry)
                else:
                    if not entry_cid:
                        matches.append(entry)
                        has_fallback = True
    except OSError:
        return None, False

    if not matches:
        return None, False

    matches.sort(key=lambda e: (parse_entry_timestamp(e), e.get('total_tokens', 0)))
    return matches[-1], has_fallback

def _collect():
    now=time.time(); errors=[]
    try:
        p=subprocess.run(['aplexer','list','--all','--json'],cwd=ROOT,capture_output=True,text=True,timeout=15)
        if p.returncode: raise ValueError('aplexer list failed')
        catalog=json.loads(p.stdout)
        if not isinstance(catalog,list): raise ValueError('unexpected session schema')
    except (ValueError,OSError,subprocess.TimeoutExpired) as e:
        catalog=[]; errors.append(str(e))
    registry=read_json(ROOT/'coordination/TEAM-REGISTRY.json',{}) or {}
    tasks_obj=read_json(ROOT/'coordination/TASKS.json',{}) or {}
    tasks=tasks_obj.get('tasks',[]) if isinstance(tasks_obj,dict) else tasks_obj
    teams=registry.get('teams',[]) if isinstance(registry,dict) else []
    declared=[]
    seen_team_tags=set()
    seen_team_cids=set()
    seen_team_sids=set()
    for team in teams:
        tid=team.get('id')
        for item in team.get('agents',[]):
            tag=item.get('tag')
            declared.append((tid,item))
            if tag: seen_team_tags.add(tag)
            cid=item.get('harness_conversation_id') or item.get('conversation_id')
            if cid: seen_team_cids.add(cid)
            sid=item.get('session_id')
            if sid: seen_team_sids.add(sid)
    # Also accept top-level agent list, including principals, monitors and private services.
    for item in registry.get('agents',[]):
        tag=item.get('tag')
        cid=item.get('harness_conversation_id') or item.get('conversation_id')
        sid=item.get('session_id')
        is_distinct = (tag not in seen_team_tags) or (cid and cid not in seen_team_cids) or (sid and sid not in seen_team_sids)
        if is_distinct:
            declared.append((item.get('team_id','oversight'),item))
    selected=[]; seen=set()
    for team_id,item in declared:
        tag=item.get('tag')
        matches=[s for s in catalog if s.get('tag')==tag and s.get('workspace')==item.get('workspace',str(ROOT))]
        exact=[s for s in matches if s.get('id')==item.get('session_id')]
        matches.sort(key=lambda s:s.get('created_at_ms',0),reverse=True)
        live=[s for s in matches if proc(s.get('workload_pid')).get('alive')]
        if exact and proc(exact[0].get('workload_pid')).get('alive'): choice=exact[0]; resolution='registered exact session'
        elif len(live)==1: choice=live[0]; resolution='single live same-workspace tag'
        elif len(live)>1: choice=None; resolution='ambiguous live tag'
        elif exact: choice=exact[0]; resolution='registered dead session'
        else: choice=matches[0] if matches else None; resolution='latest dead tag' if matches else 'missing'
        # Disk fallback only for tags with no catalog presence at all: an ambiguous
        # live tag keeps its own resolution instead of gaining a duplicate identity.
        if resolution=='missing' and item.get('session_id'):
            disk=disk_session(item['session_id'],item.get('workspace',str(ROOT)))
            if disk: choice=disk; resolution='registered completed session on disk'
        if choice: seen.add(choice['id'])
        selected.append((choice,team_id,item,resolution))
    for s in catalog:
        if s.get('workspace')==str(ROOT) and s['id'] not in seen and proc(s.get('workload_pid')).get('alive'):
            selected.append((s,'unregistered',{'tag':s.get('tag'),'role':'unknown'},'unregistered; launch parent does not imply team'))
    # Explicit saved native IDs; DB human-readable titles never establish identity.
    opencode_assignments=[]
    for team_id,item in declared:
        tag=item.get('tag')
        sid=opencode_sid(item,item.get('telemetry',{}))
        if sid and item.get('workspace',str(ROOT))==str(ROOT):
            opencode_assignments.append({'conversation_id':sid,'tag':tag,'team_id':team_id})
    observer=read_json(STORE/'observation-state.json',{}) or {}
    try: interval_ms=int(dt.datetime.fromisoformat(observer['first_observed_at'].replace('Z','+00:00')).timestamp()*1000)
    except (KeyError,ValueError,TypeError): interval_ms=int(now*1000)
    opencode=read_opencode_usage(ROOT,opencode_assignments,interval_ms)
    opencode_by_id={r['conversation_id']:r for r in opencode['sessions']}
    def opencode_counter(row):
        counters=row['cumulative']
        return {**counters,'source':OPENCODE_SOURCE,'conversation_id':row['conversation_id'],'scope':'Stored conversation cumulative; includes pre-observer history, NOT experiment spending.','cost_usd':counters.get('reported_cost'),'cost_basis':'OpenCode/provider reported estimate, not subscription billing','models':row['models'],'interval':row['interval']}
    observations=[]
    for s,team_id,item,resolution in selected:
        s=s or {}; usage=native_usage(s) if s.get('id') else None
        tele=item.get('telemetry',{}); sid=opencode_sid(item,tele)
        if sid in opencode_by_id: usage=opencode_counter(opencode_by_id[sid])
        if usage is None:
            rp=rollout_tele_path(tele)
            # Only an exact saved native id may seed attribution; the aplexer
            # session UUID is never substituted when rollout metadata is absent.
            if rp: usage=rollout_usage(rp,tele.get('conversation_id'))
        if usage is None:
            sess_cid=authentic_conversation_id(s,item)
            found,is_fallback=match_usage_event(STORE/'usage-events.jsonl',item.get('tag'),team_id,sess_cid)
            if found:
                scope=('Fallback tag-matched owner counters without conversation binding, not independent telemetry verification'
                       if is_fallback else
                       'Exact owner-registered cumulative counters, not independent telemetry verification')
                usage={**found,'source':'owner-metadata-'+found.get('provider','unknown')+'-'+found.get('model','unknown'),'scope':scope}
        telemetry=item.get('telemetry',{})
        if telemetry.get('type')=='claude-result':
            source=read_json(ROOT/telemetry.get('path',''),{}) or {}
            model_usage=source.get('modelUsage',{})
            # Per-model result belongs to ONE native conversation, not each resumed PTY.
            if model_usage:
                usage={'conversation_id':source.get('session_id'),'source':'claude-result-modelUsage','scope':'completed writer result; list-price estimate is not a bill','models':model_usage,'input_tokens':sum(v.get('inputTokens',0)+v.get('cacheReadInputTokens',0)+v.get('cacheCreationInputTokens',0) for v in model_usage.values()),'output_tokens':sum(v.get('outputTokens',0) for v in model_usage.values()),'cost_usd':source.get('total_cost_usd'),'cost_basis':'provider-reported list-price estimate, not actual subscription spend'}
                usage['total_tokens']=usage['input_tokens']+usage['output_tokens']
        ps=proc(s.get('workload_pid')); state=s.get('reported_state'); stamp=s.get('reported_state_at_ms',s.get('state_reported_at_ms'))
        if not stamp: stamp=s.get('last_activity_ms') # proxy only; labeled explicitly
        age=max(0,now-stamp/1000) if isinstance(stamp,(int,float)) else None
        owned=[t for t in tasks if t.get('owner_tag')==item.get('tag')]
        role=item.get('role','unknown'); evidence=[]
        registered_paths=sorted({rel for task in owned for rel in task.get('evidence_paths',[])})
        coverage={'registered_distinct_paths':len(registered_paths),'missing_paths':[],'unsupported_directory_paths':[],'out_of_scope_paths':[],'scope':'Registered file metadata only, not accepted outcomes or authorship'}
        seen_paths=set()
        for rel in registered_paths:
            path=(ROOT/rel).resolve()
            if ROOT not in path.parents:coverage['out_of_scope_paths'].append(rel)
            elif path.is_file():
                if str(path) not in seen_paths:
                    st=path.stat(); evidence.append({'path':rel,'bytes':st.st_size,'mtime':st.st_mtime});seen_paths.add(str(path))
            elif path.is_dir():coverage['unsupported_directory_paths'].append(rel)
            else:coverage['missing_paths'].append(rel)
        coverage['observed_distinct_files']=len(evidence)
        coverage['status']='unregistered' if not registered_paths else ('partial' if coverage['missing_paths'] or coverage['unsupported_directory_paths'] or coverage['out_of_scope_paths'] else 'observed')
        observations.append({'id':s.get('id'),'tag':item.get('tag'),'team_id':team_id,'role':role,'counted_as_agent':role in COUNT_ROLES,'unregistered':team_id=='unregistered','resolution':resolution,'parent_session':s.get('parent_session'),'engine':s.get('engine'),'pid_live':ps['alive'],'phase':s.get('phase'),'reported_state':state,'hook_age_seconds':age,'hook_age_basis':'reported_state timestamp if present; otherwise PTY activity proxy','hook_working':ps['alive'] and state=='working','stale_hook':state is not None and (age is None or age>300),'cpu_seconds':ps.get('cpu_seconds'),'rss_bytes':ps.get('rss_bytes'),'proc_start_ticks':ps.get('start_ticks'),'usage':usage,'tasks':[{'id':t.get('id'),'status':t.get('status'),'updated_at':t.get('updated_at'),'blocked_on':t.get('blocked_on',[]),'next_action':t.get('next_action')} for t in owned],'evidence':evidence,'evidence_coverage':coverage})
    counted=[s for s in observations if s['counted_as_agent']]; unique_usage={}
    for row in observations:
        u=row.get('usage')
        if u and u.get('conversation_id'):
            # Codex native and rollout records describe the same conversation lineage:
            # dedup by conversation id so a resumed rollout never double counts.
            codex_native=u.get('source') in ('codex-native-cumulative','codex-rollout')
            key=u['conversation_id'] if codex_native else u['source']+':'+u['conversation_id']
            previous=unique_usage.get(key)
            if previous is None or (u.get('total_tokens') or 0)>(previous.get('total_tokens') or 0): unique_usage[key]=u
    # DB parent-linked native subagents are separate conversations, never hidden in head totals.
    for row in opencode['sessions']:
        usage=opencode_counter(row); unique_usage[OPENCODE_SOURCE+':'+row['conversation_id']]=usage
    observed_totals=[u['total_tokens'] for u in unique_usage.values() if u.get('total_tokens') is not None]
    known_total=sum(observed_totals) if observed_totals else None
    aggregate={'registered_agents':len(counted),'services_and_writers':sum(r['role'] in ('service','observer','writer','scribe') for r in observations),'agents_pid_live':sum(r['pid_live'] for r in counted),'agents_hook_working':sum(r['hook_working'] for r in counted),'unregistered_live':sum(r['unregistered'] and r['pid_live'] for r in observations),'known_conversation_tokens':known_total if unique_usage else None,'usage_observed_conversations':len(unique_usage),'agents_without_token_observation':sum(r['usage'] is None for r in counted),'tasks_by_status':{status:sum(t.get('status')==status for t in tasks) for status in sorted(set(('queued','ready','running','review','blocked','done','cancelled'))|{t.get('status','unknown') for t in tasks})}}
    aggregate['roles']={role:{'registered':sum(r['role']==role for r in observations),'pid_live':sum(r['role']==role and r['pid_live'] for r in observations),'reported_working':sum(r['role']==role and r['hook_working'] for r in observations)} for role in ['principal','head','executor','subagent']}
    aggregate['reported_idle']=sum(r['pid_live'] and r['reported_state'] in ('idle','waiting') for r in counted)
    aggregate['stale_hook']=sum(r['stale_hook'] for r in counted)
    aggregate['state_unknown']=sum(r['pid_live'] and r['reported_state'] is None for r in counted)
    aggregate['fresh_hook_working']=sum(r['hook_working'] and not r['stale_hook'] for r in counted)
    observation=temporal(STORE,observations,tasks,dt.datetime.now(dt.timezone.utc).isoformat())
    aggregate['tokens_since_observer_known']=observation['tokens_since_observer_known']
    aggregate['longest_observed_idle_seconds']=max((r['observed_idle_seconds'] or 0 for r in counted),default=0)
    disks={}
    for name,path in [('root','/'),('tmp','/tmp')]:
        v=os.statvfs(path); disks[name]={'free_bytes':v.f_bavail*v.f_frsize,'total_bytes':v.f_blocks*v.f_frsize}
    snap={'schema_version':1,'at':dt.datetime.now(dt.timezone.utc).isoformat(),'aggregate':aggregate,'teams':{tid:count_status([r for r in counted if r['team_id']==tid]) for tid in sorted(set(r['team_id'] for r in observations))},'sessions':observations,'tasks':tasks,'observation':observation,'opencode_usage':opencode,'quota':quotas(STORE),'supervision':read_json(ROOT/'.local/supervision/status.json',{}),'host':{'load_average':os.getloadavg(),'disks':disks},'errors':errors,'limits':['PID live and hook working are observations, never proof of useful work.','Missing token/cost telemetry remains null; known token total is a partial lower bound.','Completed sessions pruned from the live catalog are attributed from on-disk aplexer records or saved rollout telemetry when available; otherwise they stay null.','Cumulative native conversation usage deduplicated across resumed session IDs, rollout files and nested subagents with separate native identity.','CPU/RSS currently workload root process only, excludes descendants.','Services/writers excluded from agent execution totals.','No market/productivity conclusion from agent count, tokens or commits.']}
    with (STORE/'collector.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        daily=STORE/('snapshots-'+dt.date.today().isoformat()+'.jsonl')
        retention=archive_history(STORE,daily)
        if retention['total_bytes']>256*1024*1024: errors.append('daily snapshot cap reached; latest continues, history paused')
        else:
            history={'at':snap['at'],'aggregate':snap['aggregate'],'teams':snap['teams'],'opencode_usage':opencode,'errors':snap['errors'],'sessions':[{k:r.get(k) for k in ['id','tag','team_id','role','pid_live','reported_state','hook_age_seconds','stale_hook','cpu_seconds','rss_bytes','proc_start_ticks','usage','observed_idle_seconds','evidence','evidence_coverage','tasks']} for r in observations],'tasks':[{key:t.get(key) for key in ['id','status','owner_tag','team_id','next_action','acceptance','acceptance_status','reviewer_tag','evidence_paths','blocked_on','assignment_ack','updated_at']} for t in tasks]};
            with daily.open('a') as f: f.write(json.dumps(history)+'\n')
            os.chmod(daily,0o600)
        atomic(STORE/'latest.json',snap)
    return snap

def collect():
    with (STORE/'sample.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _collect()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/api/latest','/api/tasks'):
            value=read_json(STORE/'latest.json',{})
            if self.path=='/api/tasks': value=value.get('tasks',[])
            data=json.dumps(value).encode(); kind='application/json'
        elif self.path=='/': data=(pathlib.Path(__file__).parent/'dashboard.html').read_bytes(); kind='text/html; charset=utf-8'
        else: self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type',kind); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'"); self.end_headers(); self.wfile.write(data)
    def log_message(self,*args): pass

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--loop',action='store_true'); ap.add_argument('--interval',type=int,default=60); ap.add_argument('--serve',action='store_true'); ap.add_argument('--port',type=int,default=8766); args=ap.parse_args()
    if not args.loop:
        snap=collect(); print(json.dumps({'at':snap['at'],'aggregate':snap['aggregate'],'errors':snap['errors']})); return
    with (STORE/'service.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit('metrics service already running')
        if args.serve:
            server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
        stopping=threading.Event()
        signal.signal(signal.SIGTERM,lambda *_:stopping.set())
        signal.signal(signal.SIGINT,lambda *_:stopping.set())
        while not stopping.is_set():
            try: collect()
            except Exception as exc: atomic(STORE/'service-error.json',{'at':time.time(),'error_type':type(exc).__name__})
            stopping.wait(max(30,args.interval))
if __name__=='__main__': main()
