#!/usr/bin/env python3
"""Bound native aplexer mailbox, read through SSH by the desktop orchestrator."""
import json, os, pathlib, subprocess, time
root=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
os.chdir(root)
local=root/'.local'
def call(args):
    return subprocess.run(['aplexer', *args], capture_output=True, text=True, timeout=30, check=True)
while not (local/'orchestrator-channel.stop').exists():
    try:
        inbox=call(['message','inbox','--json'])
        parsed=json.loads(inbox.stdout)
        temp=local/'orchestrator-inbox.tmp'
        temp.write_text(json.dumps(parsed,indent=2))
        temp.replace(local/'orchestrator-inbox.json')
        for request in sorted((local/'orchestrator-outbox').glob('*.json')):
            req=json.loads(request.read_text())
            token=req['token']
            if not token or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):
                continue
            receipt=local/'orchestrator-sent'/f'{token}.json'
            if receipt.exists():
                continue
            replies=[]
            for tag in req['recipients']:
                sent=call(['message','send','--to',tag,'--json',req['body']])
                replies.append(json.loads(sent.stdout))
            receipt.write_text(json.dumps({'token':token,'receipts':replies},indent=2))
        # ACK only IDs explicitly reviewed by the desktop; never ACK merely on polling.
        ackfile=local/'orchestrator-ack.json'
        if ackfile.exists():
            ids=json.loads(ackfile.read_text())
            for ident in ids:
                call(['message','ack',ident,'--json'])
            ackfile.unlink()
    except Exception as exc:
        (local/'orchestrator-channel-error.txt').write_text(type(exc).__name__)
    time.sleep(20)
