"""Existing outbound native channel transport, fixed enrolled shell only."""
import hashlib,json,pathlib,socket,ssl
from urllib.parse import urlsplit

def channel(profile,native,runtime,source_guard):
    source_guard()
    endpoint=urlsplit(profile['authority_url'])
    if (endpoint.scheme!='https' or not endpoint.hostname or endpoint.port!=8801
        or endpoint.username or endpoint.password or endpoint.path not in ('','/')
        or endpoint.query or endpoint.fragment):raise RuntimeError('fixed authority8801 origin required')
    if native['id']!=profile['actor'] or profile['root_runtime_kind']!='opencode-native-v1':
        raise RuntimeError('actual enrolled OpenCode shell binding required')
    context=ssl.create_default_context(cafile=profile['ca_certificate'])
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(profile['client_certificate'],profile['client_key'])
    body=json.dumps({'v':1,'op':'inspect','project':profile['project'],'role':'root',
        'actor':native['id'],'generation':profile['generation'],'credential':profile['credential']}).encode()
    raw=socket.create_connection((endpoint.hostname,8801),timeout=10)
    with context.wrap_socket(raw,server_hostname=endpoint.hostname) as connection:
        source_guard()
        header=('POST /v1/native-channel HTTP/1.1\r\nHost: '+endpoint.netloc+
            '\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body))+'\r\n\r\n').encode()
        connection.sendall(header+body)
        stream=connection.makefile('rwb')
        if not stream.readline(4096).startswith(b'HTTP/1.1 101 '):raise RuntimeError('native channel unavailable')
        total=0
        while True:
            line=stream.readline(4096);total+=len(line)
            if not line or total>16384:raise RuntimeError('native channel response header held')
            if line==b'\r\n':break
        connection.settimeout(90)
        while True:
            line=stream.readline(16385)
            if not line or len(line)>16384:raise RuntimeError('native channel disconnected/bounds exceeded')
            command=json.loads(line);source_guard()
            try:receipt=runtime.execute(command)
            except Exception:
                receipt={'v':1,'key':command.get('key'),'owner':command.get('owner'),
                    'operation':command.get('operation'),'payload':command.get('payload',{}),
                    'state':'uncertain','native_actor':native,
                    'evidence':{'reconcile_required':True,'model_success_claimed':False}}
            stream.write(json.dumps(receipt).encode()+b'\n');stream.flush()
