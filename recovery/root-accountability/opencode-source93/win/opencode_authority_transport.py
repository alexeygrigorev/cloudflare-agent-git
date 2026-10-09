"""Fixed own-root mTLS helper transport; no URLs/credentials selected by tools.

Constructor values come only from the separately reviewed private incarnation
profile. Generic proxy/redirect handlers are deliberately absent. This transport
never treats helper gates as provider admission or native completion.
"""
import hashlib,http.client,json,ssl
from urllib.parse import urlsplit

OPS=frozenset(('opencode-controller-gate','opencode-input','opencode-reply-receipt'))

class AuthorityTransport:
    def __init__(self,origin,credential,certificate_paths,certificate_pins,guard,connection_factory=None):
        parsed=urlsplit(origin)
        if (parsed.scheme!='https' or not parsed.hostname or parsed.port!=8801
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('','/')):
            raise ValueError('fixed existing authority8801 origin required')
        if set(certificate_paths)!= {'ca','certificate','key'} or set(certificate_pins)!=set(certificate_paths):
            raise ValueError('fixed mTLS material bindings required')
        self.host=parsed.hostname;self.credential=credential
        self.paths=certificate_paths;self.pins=certificate_pins;self.guard=guard
        self.connection_factory=connection_factory
    def __repr__(self):return '<AuthorityTransport fixed8801 own-root mTLS; credentials private>'
    def verify_files(self):
        for name,path in self.paths.items():
            if (not path.is_file() or path.stat().st_size>1048576
                or any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (path,*path.parents))
                or hashlib.sha256(path.read_bytes()).hexdigest()!=self.pins[name]):
                raise RuntimeError('fixed mTLS source binding unavailable')
    def __call__(self,path,body):
        if (path!='/v1/host-recovery' or type(body) is not dict
            or set(body)!= {'v','credential','op'} or body['v']!=1
            or body['op'] not in OPS or body['credential']!=self.credential):
            raise RuntimeError('fixed own-root helper request required')
        self.guard();self.verify_files()
        connection=None
        try:
            if self.connection_factory:
                connection=self.connection_factory()
            else:
                context=ssl.create_default_context(cafile=str(self.paths['ca']))
                context.minimum_version=ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(str(self.paths['certificate']),str(self.paths['key']))
                connection=http.client.HTTPSConnection(self.host,8801,context=context,timeout=10)
            connection.request('POST','/v1/host-recovery',body=json.dumps(body).encode(),
                               headers={'Content-Type':'application/json','Accept':'application/json'})
            response=connection.getresponse()
            if response.status!=200:raise RuntimeError('helper gate held')
            raw=response.read(131073)
            if len(raw)>131072:raise RuntimeError('helper response bound')
            envelope=json.loads(raw)
            if (type(envelope) is not dict or set(envelope)!= {'v','status','result'}
                or type(envelope['v']) is not int or envelope['v']!=1
                or envelope['status']!='ok' or type(envelope['result']) is not dict):
                raise RuntimeError('exact existing HTTP authority envelope required')
            result=envelope['result']
            self.verify_files();self.guard()
            return result
        except Exception:
            raise RuntimeError('fixed authenticated helper request held') from None
        finally:
            if connection is not None:connection.close()
