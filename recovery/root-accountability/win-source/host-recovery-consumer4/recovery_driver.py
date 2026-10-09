"""Existing Guardian orchestration; no root/model identity is invented here.

Hooks are the fixed pinned Windows/runtime adapter. A server-derived nonce and
permit are required; ambiguous factory state is always reconciled, never replayed.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import copy
class Held(RuntimeError):pass

class Driver:
    def __init__(self,hooks):self.hooks=hooks
    def step(self):
        h=self.hooks
        pending=h.read_recovery()
        if pending is not None:
            if not isinstance(pending,dict) or pending.get('phase') not in ('factory-authorized','factory-completed','credential-write-pending','completed'):
                raise Held('unknown recovery phase; preserve')
            if pending['phase']=='completed':
                # Current live successor remains an ordinary keeper task.
                if h.successor_live(pending['successor']):
                    h.supervise_recover();h.observe_live();return 'current-successor-supervised'
                # A new predecessor can recover only through a NEW server nonce.
                h.archive_completed(pending)
                return 'completed-history-archived'
            return self.resume(pending)
        profile=h.current_profile()
        if h.native_alive(profile):
            h.supervise_recover();h.observe_live();return 'live-custody-supervised'
        # Does not equate missing/unknown state with death. Fixed hook reads every
        # exact native/backend incarnation plus retained Job/provider checkpoint.
        challenge=h.server_challenge()
        evidence=h.observe_death(challenge)
        authorized=h.server_reconcile(challenge,evidence)
        permit=authorized.get('permit')
        if not isinstance(permit,dict):raise Held('server did not authorize fixed factory')
        pending=dict(phase='factory-authorized',permit=permit,expected=authorized['expected'])
        h.write_recovery(pending) # Before any local profile/factory effects.
        return self.resume(pending)
    def resume(self,pending):
        h=self.hooks
        if pending['phase']=='factory-authorized':
            successor=h.perform_factory(pending['permit'],pending['expected'])
            pending.update(phase='factory-completed',successor=successor);h.write_recovery(pending)
        if pending['phase']=='factory-completed':
            handoff=h.server_enroll(pending['permit']['challenge'],pending['successor'])
            merge=h.prepare_credential_merge(handoff,pending['successor'])
            pending.update(phase='credential-write-pending',merge=merge);h.write_recovery(pending)
        if pending['phase']=='credential-write-pending':
            # Exact holding/after hash only; a lost response cannot replay spawn.
            h.complete_credential_merge(pending['merge'],pending['successor'])
            pending['phase']='completed';h.write_recovery(pending)
        h.supervise_recover();h.observe_live()
        return 'genuine-successor-held-and-supervised'
