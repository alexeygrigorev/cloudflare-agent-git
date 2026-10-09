"""Current registered native action sink-proof on the existing authority8801."""
import http.client,json,ssl,time
from urllib.parse import urlsplit

class RoleProof:
    def __init__(self,profile,source_guard,clock=time.time):
        self.profile=profile;self.guard=source_guard;self.clock=clock
    def __call__(self,command):
        self.guard();profile=self.profile
        owner=command['owner']
        if (owner['actor']!=profile['actor'] or owner['generation']!=profile['generation']
            or owner['project']!=profile['project'] or owner['role']!='root'
            or command.get('payload')!={} or command['operation'] not in ('root-fence-activate','root-start')):
            raise RuntimeError('fixed native role action differs')
        endpoint=urlsplit(profile['authority_url'])
        if endpoint.scheme!='https' or endpoint.port!=8801 or not endpoint.hostname or endpoint.path not in ('','/'):
            raise RuntimeError('fixed authority endpoint required')
        context=ssl.create_default_context(cafile=profile['ca_certificate'])
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(profile['client_certificate'],profile['client_key'])
        connection=http.client.HTTPSConnection(endpoint.hostname,8801,context=context,timeout=10)
        try:
            body=dict(owner,v=1,op='sink-proof',key=command['key'],operation=command['operation'],payload={},credential=profile['credential'])
            connection.request('POST','/v1/sink-proof',body=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            response=connection.getresponse();raw=response.read(65537)
            if response.status!=200 or len(raw)>65536:raise RuntimeError('current role proof unavailable')
            proof=json.loads(raw)
            if proof.get('v')!=1 or type(proof['v']) is not int or proof.get('status')!='ok':
                raise RuntimeError('current role fenced')
            for key in ('owner','key','operation','payload'):
                if proof.get(key)!=command[key]:raise RuntimeError('exact current sink proof differs')
            self.guard()
            if not 0<command['deadline']-self.clock()<=60:raise RuntimeError('authority command expired')
            return proof
        except Exception:raise RuntimeError('fixed current role proof held') from None
        finally:connection.close()
