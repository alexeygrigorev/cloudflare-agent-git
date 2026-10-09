"""Fixed owner role-control transport used by the one external Guardian.

This is control of its own enrolled native binding, not agents-bus messaging.
Only maintained admission/acquire/fence/start/check/renew/inspect requests exist.
"""
import hashlib,http.client,json,pathlib,ssl
from urllib.parse import urlsplit

OPS={'admission_refresh','acquire','first_action','bootstrap_start','execute','renew','inspect'}

class RoleTransport:
    def __init__(self,profile,source_guard,server_certificate_sha256):
        self.profile=profile;self.guard=source_guard;self.server_pin=server_certificate_sha256
    def __call__(self,body):
        p=self.profile;self.guard()
        if (type(body) is not dict or body.get('op') not in OPS
            or body.get('project')!=p['project'] or body.get('role')!='root'
            or body.get('actor')!=p['actor'] or body.get('generation')!=p['generation']
            or type(body.get('epoch')) is not int or body['epoch']<1):
            raise RuntimeError('fixed own native role request differs')
        fields={'project','role','actor','generation','epoch','op'}
        op=body['op']
        expected=fields|({'operation','payload'} if op in ('first_action','bootstrap_start') else
            {'operation','payload','key'} if op=='execute' else {'ttl'} if op=='renew' else set())
        if set(body)!=expected:raise RuntimeError('unknown role request fields held')
        if op in ('first_action','bootstrap_start','execute'):
            operation={'first_action':'root-fence-activate','bootstrap_start':'root-start','execute':'root-check'}[op]
            if body['operation']!=operation or body['payload']!={}:raise RuntimeError('fixed native role operation required')
        if op=='renew' and (type(body['ttl']) is not int or body['ttl']!=180):raise RuntimeError('fixed renewal TTL required')
        origin=urlsplit(p['authority_url'])
        if (origin.scheme!='https' or origin.port!=8801 or not origin.hostname or origin.path not in ('','/')
            or origin.username or origin.password or origin.query or origin.fragment):
            raise RuntimeError('fixed same authority origin required')
        context=ssl.create_default_context(cafile=p['ca_certificate'])
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(p['client_certificate'],p['client_key'])
        connection=http.client.HTTPSConnection(origin.hostname,8801,context=context,timeout=30)
        try:
            connection.connect()
            if hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()!=self.server_pin:
                raise RuntimeError('fixed authority peer changed')
            self.guard()
            connection.request('POST','/v1/role-control',body=json.dumps(dict(body,v=1,credential=p['credential'])).encode(),
                headers={'Content-Type':'application/json','Accept':'application/json'})
            response=connection.getresponse();raw=response.read(262145)
            if response.status!=200 or len(raw)>262144:raise RuntimeError('role request held')
            result=json.loads(raw)
            if type(result) is not dict or result.get('v')!=1 or type(result['v']) is not int or result.get('status')!='ok':
                raise RuntimeError('role receipt malformed')
            self.guard();return result
        except Exception:raise RuntimeError('fixed native role request refused or uncertain') from None
        finally:connection.close()
