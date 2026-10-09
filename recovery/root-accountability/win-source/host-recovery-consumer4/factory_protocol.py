"""One authenticated death permit, one fixed native factory attempt.

Stores/native functions are the pinned Guardian implementation, never RPC caller
callbacks. This state machine neither terminates processes nor starts a model.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import hashlib,json,copy
class Held(RuntimeError):pass
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def validate_permit(permit,expected):
    if (set(permit)!=set(('v','operation','challenge','owner','profile_sha256'))
        or type(permit['v']) is not int or permit['v']!=1
        or permit['operation']!='fixed-native-factory'
        or permit['challenge']!=expected['challenge'] or permit['owner']!=expected['owner']
        or permit['profile_sha256']!=expected['profile_sha256']):raise Held('fixed authenticated death permit mismatch')

def perform(permit,expected,store,prepare_holding,spawn_fixed,reconcile_fixed):
    validate_permit(permit,expected)
    record=store.read()
    if record is None:
        record=dict(v=1,phase='holding-write-pending',permit_sha256=digest(permit),owner=expected['owner'],challenge=expected['challenge'])
        store.write(record)
    if (not isinstance(record,dict) or record.get('v')!=1 or record.get('permit_sha256')!=digest(permit)
        or record.get('owner')!=expected['owner'] or record.get('challenge')!=expected['challenge']
        or record.get('phase') not in ('holding-write-pending','factory-ready','factory-pending-reconcile-only','completed')):
        raise Held('unknown/foreign factory journal; preserve')
    if record['phase']=='holding-write-pending':
        # Idempotent exact before/after profile hash and private-state checks.
        holding=prepare_holding(permit)
        record.update(phase='factory-ready',holding=holding);store.write(record)
    if record['phase']=='factory-ready':
        record['phase']='factory-pending-reconcile-only';store.write(record)
        # Once this boundary is persisted, no exception can authorize a retry.
        response=spawn_fixed(record['holding'])
        record['native_response']=response;store.write(record)
    if record['phase']=='factory-pending-reconcile-only':
        # Reconcile actual catalog/WHOAMI/kernel leaf. Never call spawn again.
        leaf=reconcile_fixed(record['holding'],record.get('native_response'))
        if not isinstance(leaf,dict) or not leaf.get('actual_leaf_verified'):raise Held('uncertain native factory; no replay')
        record.update(phase='completed',successor=leaf);store.write(record)
    return copy.deepcopy(record['successor'])
