"""Bounded, read-only OpenCode message usage. No prompts, parts or credentials."""
import datetime as dt
import math
import pathlib
import sqlite3
import time

SOURCE = 'opencode-message-reported'
DB_REL = '.local/opencode-isolated/opencode/opencode.db'
HOME_DB_REL = '.local/share/opencode/opencode.db'

def default_home_db():
    return pathlib.Path.home()/HOME_DB_REL
FIELDS = ('total_tokens','input_tokens','output_tokens','reasoning_output_tokens','cached_input_tokens','cache_write_tokens','reported_cost')

def number(value):
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 else None

def read_usage(root, assignments, interval_start_ms, *, max_sessions=128, max_messages=50000, deadline_seconds=2, home_db=None):
    """Exact registered conversations plus DB parent-linked children, counted once.

    Assignments are {conversation_id,team_id,tag}. Conflicting owners are unassigned.
    The fixed owned DB must not be a symlink outside root. Rescanning PK rows means
    late completion updates replace prior values, never append/double-count them.
    The user home store is observed too (same attribution rule: session directory
    must resolve inside root). Cross-store duplicates reconcile deterministically:
    completed over pending, latest completed/created time, larger totals, then the
    owned store wins ties, so one message kept in both stores counts once with the
    freshest values. A missing store is skipped.
    """
    root=pathlib.Path(root).resolve(); path=root/DB_REL
    home=pathlib.Path(home_db) if home_db is not None else default_home_db()
    result={'source':SOURCE,'interval_start':dt.datetime.fromtimestamp(interval_start_ms/1000,dt.timezone.utc).isoformat(),'observed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'unknown','sessions':[],'by_model':[],'by_team':{},'stores':[],'limits':['Stored provider totals include cached processing and are not unique text or money spent.','Raw output/reasoning categories are shown separately; total is authoritative and never recomputed by adding reasoning.','Reported cost is OpenCode/provider estimate, not subscription billing.','Interval uses message creation time; late completion updates may backfill earlier messages.','Only exact registered conversation IDs and same-directory DB parent-linked children are attributed.','Cross-store duplicates reconcile to one record: completed over pending, latest completed/created time, larger totals, owned store on full ties.']}
    try:
        stores=[]
        if path.is_file() and root in path.resolve().parents:stores.append(('owned',path))
        elif path.is_file():result['stores'].append({'role':'owned','path':str(path),'status':'outside-root-skipped','assistant_rows':0})
        else:result['stores'].append({'role':'owned','path':str(path),'status':'missing-skipped','assistant_rows':0})
        if home.is_file():stores.append(('home',home))
        else:result['stores'].append({'role':'home','path':str(home),'status':'missing-skipped','assistant_rows':0})
        if not stores:return result
        owners={}
        for a in assignments:
            sid=a.get('conversation_id')
            if isinstance(sid,str) and sid.startswith('ses_'):
                owners.setdefault(sid,set()).add((a.get('team_id'),a.get('tag')))
        if not owners:return result
        if len(owners)>max_sessions:raise ValueError('session bound')
        deadline=time.monotonic()+deadline_seconds
        admitted=set();all_rows=[]
        for role,dbpath in stores:
            try:
                store_admitted,rows=_query_store(dbpath,root,owners,max_sessions,max_messages,deadline)
            except (sqlite3.Error,OSError,ValueError,TypeError,OverflowError):
                result['stores'].append({'role':role,'path':str(dbpath),'status':'unavailable-skipped','assistant_rows':0});continue
            result['stores'].append({'role':role,'path':str(dbpath),'status':'queried','assistant_rows':len(rows)})
            admitted.update(store_admitted)
            if len(admitted)>max_sessions:raise ValueError('session bound')
            all_rows.extend([(*r,role) for r in rows])
        if not admitted:return result
        if len(all_rows)>max_messages:raise ValueError('message bound')
        winners=list(_reconcile(all_rows).values())
        winners.sort(key=lambda r:(r[1],r[0]))
        groups={};seen=set()
        for mid,sid,created,provider,model,completed,*rest in winners:
            values,role=rest[:-1],rest[-1]
            key=(provider,sid,mid)
            if key in seen:continue
            seen.add(key)
            group=groups.setdefault(sid,{'conversation_id':sid,'owners':sorted([{'team_id':t,'tag':g} for t,g in owners[sid]],key=lambda x:str(x)),'models':{}})
            model_key=(provider or 'unknown',model or 'unknown')
            bucket=group['models'].setdefault(model_key,{'provider':model_key[0],'model':model_key[1],'cumulative':empty(),'interval':empty()})
            for name,eligible in [('cumulative',True),('interval',created>=interval_start_ms)]:
                if not eligible:continue
                totals=bucket[name];totals['assistant_records']+=1
                valid=number(completed) is not None and number(values[0]) is not None
                if not valid:totals['pending_or_missing_records']+=1;continue
                totals['records_with_total']+=1
                for field,value in zip(FIELDS,values):
                    value=number(value)
                    if value is None:totals['missing_fields'][field]+=1
                    else:totals[field]+=value;totals['known_fields'][field]+=1
                totals['first_message_ms']=created if totals['first_message_ms'] is None else min(created,totals['first_message_ms'])
                totals['last_message_ms']=created if totals['last_message_ms'] is None else max(created,totals['last_message_ms'])
        global_models={};teams={}
        for sid,group in groups.items():
            group['models']=list(group['models'].values()); owner_set=owners[sid]
            team_ids={t for t,g in owner_set}
            team=next(iter(team_ids)) if len(team_ids)==1 else 'unassigned-conflicting-ownership'
            group['team_id']=team
            for b in group['models']:
                key=(b['provider'],b['model']); target=global_models.setdefault(key,{'provider':key[0],'model':key[1],'interval':empty()})
                merge(target['interval'],b['interval']);merge(teams.setdefault(team or 'unassigned',empty()),b['interval'])
            group['cumulative']=empty();group['interval']=empty()
            for b in group['models']:
                merge(group['cumulative'],b['cumulative']);merge(group['interval'],b['interval'])
            for b in group['models']:
                finish(b['cumulative']);finish(b['interval'])
            finish(group['cumulative']);finish(group['interval']);result['sessions'].append(group)
        for b in global_models.values():finish(b['interval'])
        for b in teams.values():finish(b)
        result.update(status='observed',by_model=list(global_models.values()),by_team=teams,queried_assistant_records=len(all_rows),unique_assistant_records=len(seen),registered_conversations=len(assignments),attributed_conversations=len(admitted))
    except (sqlite3.Error,OSError,ValueError,TypeError,OverflowError):
        result.update(status='unavailable-or-bound-exceeded',sessions=[],by_model=[],by_team={})
    return result

def _score(row):
    mid,sid,created,provider,model,completed,total,input_v,output_v,reasoning_v,read_v,write_v,cost_v,role=row
    done=number(completed) is not None
    stamp=completed if done else created
    total_n=number(total)
    return (done,stamp if isinstance(stamp,(int,float)) else -1,total_n if total_n is not None else -1,role=='owned')

def _reconcile(rows):
    """One winner per (provider,sid,mid): completed first, then latest stamp,
    then larger total, then owned store. Owned is queried first so full ties
    keep it by strict-greater replacement."""
    best={}
    for r in rows:
        key=(r[3],r[1],r[0])
        cur=best.get(key)
        if cur is None or _score(r)>_score(cur):best[key]=r
    return best

def _query_store(dbpath, root, owners, max_sessions, max_messages, deadline):
    """Read-only WAL snapshot of one store. Admission is strictly per-store:
    only session IDs present in THIS store with directory==root, plus children
    parent-linked within THIS store. Returns (admitted, rows)."""
    con=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True,timeout=.2)
    try:
        con.execute('PRAGMA query_only=ON');con.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
        con.execute('BEGIN') # one consistent WAL snapshot; never immutable=1
        ids=list(owners); placeholders=','.join('?' for _ in ids)
        # Do not infer an owner from a human-readable title.
        catalog=con.execute(f'SELECT id,parent_id,directory FROM session WHERE id IN ({placeholders})',ids).fetchall()
        admitted={sid for sid,parent,directory in catalog if pathlib.Path(directory).resolve()==root}
        if len(admitted)>max_sessions:raise ValueError('session bound')
        frontier=list(admitted)
        while frontier:
            p=','.join('?' for _ in frontier)
            rows=con.execute(f'SELECT id,parent_id,directory FROM session WHERE parent_id IN ({p}) LIMIT ?',frontier+[max_sessions+1]).fetchall()
            frontier=[]
            for sid,parent,directory in rows:
                if pathlib.Path(directory).resolve()!=root or sid in admitted:continue
                admitted.add(sid);owners.setdefault(sid,set()).update(owners[parent]);frontier.append(sid)
                if len(admitted)>max_sessions:raise ValueError('session bound')
        if not admitted:return admitted,[]
        ids=sorted(admitted); p=','.join('?' for _ in ids)
        return admitted,con.execute(f'''SELECT id,session_id,time_created,
            json_extract(data,'$.providerID'),json_extract(data,'$.modelID'),
            json_extract(data,'$.time.completed'),json_extract(data,'$.tokens.total'),
            json_extract(data,'$.tokens.input'),json_extract(data,'$.tokens.output'),
            json_extract(data,'$.tokens.reasoning'),json_extract(data,'$.tokens.cache.read'),
            json_extract(data,'$.tokens.cache.write'),json_extract(data,'$.cost')
            FROM message WHERE session_id IN ({p}) AND json_extract(data,'$.role')='assistant'
            ORDER BY session_id,id LIMIT ?''',ids+[max_messages+1]).fetchall()
    finally:con.close()

def empty():
    return {**{f:0 for f in FIELDS},'assistant_records':0,'records_with_total':0,'pending_or_missing_records':0,'known_fields':{f:0 for f in FIELDS},'missing_fields':{f:0 for f in FIELDS},'first_message_ms':None,'last_message_ms':None}

def merge(to,other):
    for f in FIELDS:to[f]+=other[f];to['known_fields'][f]+=other['known_fields'][f];to['missing_fields'][f]+=other['missing_fields'][f]
    for f in ('assistant_records','records_with_total','pending_or_missing_records'):to[f]+=other[f]
    for f,fn in [('first_message_ms',min),('last_message_ms',max)]:
        if other[f] is not None:to[f]=other[f] if to[f] is None else fn(to[f],other[f])

def finish(bucket):
    for f in FIELDS:
        if not bucket['known_fields'][f]:bucket[f]=None
    bucket['coverage']='partial' if bucket['pending_or_missing_records'] or any(bucket['missing_fields'].values()) else ('observed' if bucket['records_with_total'] else 'unknown')
