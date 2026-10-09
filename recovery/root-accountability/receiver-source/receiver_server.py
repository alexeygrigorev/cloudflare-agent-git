"""Installed-only integration for existing authenticated role-control/native channel.

The HTTP handler must first apply its existing certificate/native scope and Bus
authentication. This module supplies no public registration or proof-upload API.
"""
import json, sqlite3, uuid
from pathlib import Path
from types import SimpleNamespace
from operational_receiver import CompletedCheckReceiver,CheckFenced,owner_values
from root_reply_receiver import NativeReplyReceiver
from principal_snapshot import fixed_snapshot

def activated_model(config,owner):
 owner_values(owner)
 with sqlite3.connect(Path(config['authority_db']).as_uri()+'?mode=ro',uri=True) as db:
  row=db.execute('SELECT first_action FROM activation_receipts WHERE project=? AND role=? AND epoch=?',(owner['project'],owner['role'],owner['epoch'])).fetchone()
 if not row:raise CheckFenced('exact activated model absent')
 with sqlite3.connect(Path(config['sink_journal']).as_uri()+'?mode=ro',uri=True) as db:
  saved=db.execute('SELECT body,result FROM sink_receipts WHERE key=?',(row[0],)).fetchone()
 if not saved or not saved[1]:raise CheckFenced('completed fixed activation sink absent')
 intent,result=map(json.loads,saved);model=result.get('evidence',{}).get('model',{})
 if (intent.get('owner')!=owner or intent.get('operation')!='root-model-evidence' or result.get('state') not in ('ok','completed') or model.get('native_actor')!=owner['actor'] or not isinstance(model.get('thread_id'),str) or not 1<=len(model['thread_id'])<=128 or type(model.get('first_tool',{}).get('exit_code')) is not int or model['first_tool']['exit_code']!=0):raise CheckFenced('actual exact model/tool activation required')
 return {'owner':dict(owner),'thread_id':model['thread_id']}

class OperationalReceiver:
 def __init__(self,authority,config,channels,*,config_getter=None):
  self.config=config;self.authority=authority;self.channels=channels;self._config_getter=config_getter
  self.replies=NativeReplyReceiver(authority,model_binding=lambda owner:activated_model(self.current_config(),owner),dispatch=self._dispatch)
  self.checks=CompletedCheckReceiver(authority,model_binding=lambda owner:activated_model(self.current_config(),owner),dispatch=self._dispatch,clock=authority.clock,method=config.get("operational_receiver",{}).get("check_method","native-direct-v1"))
 def current_config(self):
  current=self._config_getter() if self._config_getter is not None else self.config
  if any(current.get(k)!=self.config.get(k) for k in ('authority_db','sink_journal','operational_receiver','operational_http')):raise CheckFenced('cold-installed source/database plan changed')
  return current
 def _dispatch(self,owner,command,timeout):
  # Existing NativeChannels selects authenticated actor/generation channel and
  # rechecks its exact pending command receipt. No HTTP caller supplies proof.
  return self.channels.dispatch(SimpleNamespace(**owner),command,timeout)
 def handle_authenticated(self,request):
  owner={k:request[k] for k in ('project','role','actor','generation','epoch')};owner_values(owner)
  config=self.current_config();binding=config['bindings'].get(owner['actor'])
  if not binding or binding.get('retired') or (binding['generation'],binding['role'],binding['project'])!=(owner['generation'],'root',owner['project']):raise CheckFenced('current managed actor required')
  if any(k in request for k in ('evidence','receipt','proof','check_result','model','source','thread_id','child_thread_id')):raise CheckFenced('client proof upload forbidden')
  if request['op']=='root_check_gate':
   if set(request)!={'v','op','project','role','actor','generation','epoch','credential','check_envelope','parent_turn_id','phase'}:raise CheckFenced('fixed native pre-effect gate request required')
   if type(request['v']) is not int or request['v']!=1:raise CheckFenced('fixed protocol version required')
   for field in ('check_envelope','parent_turn_id'):
    if not isinstance(request[field],str) or not 1<=len(request[field])<=128:raise CheckFenced('bounded native correlation required')
   if request['phase'] not in ('thread-start','turn-start'):raise CheckFenced('fixed managed effect phase required')
   model=activated_model(config,owner)
   with self.authority._tx() as db:
    row=self.authority._valid(db,*owner_values(owner));now=self.authority.clock()
    valid_until=min(row['expires'],now+5)
    if valid_until<=now:raise CheckFenced('current authority required before effect')
    db.execute('CREATE TABLE IF NOT EXISTS native_check_gates(ref TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)')
    ref='check-gate:'+str(uuid.uuid4())
    body={'owner':owner,'thread_id':model['thread_id'],'parent_turn_id':request['parent_turn_id'],'check_envelope':request['check_envelope'],'phase':request['phase'],'observed_at':now,'valid_until':valid_until,'role_gate_ref':ref,'current_activated':True,'proof_kind':'server-authority-gate'}
    db.execute('INSERT INTO native_check_gates VALUES(?,?,?)',(ref,json.dumps(owner,sort_keys=True),json.dumps(body,sort_keys=True)))
   return body
  if request['op']=='principal_snapshot':
   with self.authority._tx() as db:self.authority._valid(db,*owner_values(owner))
   activated_model(config,owner)
   return fixed_snapshot(config['principal_snapshot'],owner,self.authority.clock())
  if request['op']=='check_result_collect':
   return self.checks.collect(owner,key=request['key'],check_envelope=request['check_envelope'])
  if request['op']=='complete_check':return self.checks.complete_check(owner,request['receipt_ref'])
  raise CheckFenced('fixed operational receiver operation required')
