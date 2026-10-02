#!/usr/bin/env python3
"""Genuinely bound desktop mailbox worker; SSH transports requests, not identities."""
import json,pathlib,subprocess,time,os
root=pathlib.Path('/home/alexey/git/cloudflare-agent-git');os.chdir(root)
local=root/'.local'
patched='/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer'
def call(args,binary='aplexer'):
 return subprocess.run([binary,*args],capture_output=True,text=True,timeout=30,check=True)
def save(path,obj):
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(obj,indent=2));temp.replace(path)
identity=json.loads(call(['whoami','--json']).stdout)
assert identity['workspace']==str(root) and identity['tag']=='desktop-orchestrator',identity
save(local/'orchestrator-channel-identity.json',{k:identity[k] for k in ['id','tag','workspace']})
while not (local/'orchestrator-channel.stop').exists():
 try:save(local/'orchestrator-inbox.json',json.loads(call(['message','inbox','--json']).stdout))
 except Exception as exc:save(local/'orchestrator-channel-error.json',{'stage':'inbox','error':type(exc).__name__})
 for request in sorted((local/'orchestrator-outbox').glob('*.json')):
  try:
   req=json.loads(request.read_text());token=req['token']
   if not token or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):continue
   receipt=local/'orchestrator-sent'/f'{token}.json'
   if receipt.exists():continue
   op=req.get('op','send');assert op in ['send','reply']
   targets=req['recipients'] if op=='send' else [req['reply_to']]
   replies=[];errors=[]
   for target in targets:
    part=local/'orchestrator-sent'/f'{token}-{target}.json'
    if part.exists():replies.append(json.loads(part.read_text()));continue
    args=['message','send','--to',target,'--json'] if op=='send' else ['message','reply',target,'--json']
    binary='aplexer'
    if req.get('idempotency_key'):
     binary=patched;args+=['--idempotency-key',req['idempotency_key']+('-'+target if op=='send' else '')]
    try:
     item=json.loads(call(args+[req['body']],binary).stdout);save(part,item);replies.append(item)
    except Exception as exc:
     # One stale recipient must not block all other requests or reviewed ACKs.
     errors.append({'target':target,'error':type(exc).__name__})
   if not errors:save(receipt,{'token':token,'receipts':replies})
   else:save(local/'orchestrator-sent'/f'{token}-errors.json',errors)
  except Exception as exc:save(local/'orchestrator-channel-error.json',{'stage':'request','file':request.name,'error':type(exc).__name__})
 ackfile=local/'orchestrator-ack.json'
 if ackfile.exists():
  try:
   ids=json.loads(ackfile.read_text());remaining=[]
   for ident in ids:
    try:call(['message','ack',ident,'--json'])
    except Exception:remaining.append(ident)
   # Avoid consuming an ACK file replaced concurrently by the desktop.
   if json.loads(ackfile.read_text())==ids:
    if remaining:save(ackfile,remaining)
    else:ackfile.unlink()
  except Exception as exc:save(local/'orchestrator-channel-error.json',{'stage':'ack','error':type(exc).__name__})
 time.sleep(5)
