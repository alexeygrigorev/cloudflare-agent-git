"""Same existing Task, explicit mechanical transition, no root/model kill."""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires isolated startup')
class Held(RuntimeError):pass
def transition(hooks):
    h=hooks;h.verify_all_source_and_private_inputs();h.assert_legacy_and_dead_predecessor()
    journal=h.read_journal()
    if journal is None:
        h.assert_exact_old_task_and_quiescence()
        journal={'phase':'disable-pending','plan_sha256':h.plan_sha256}
        h.save(journal)
    if not isinstance(journal,dict) or journal.get('plan_sha256')!=h.plan_sha256 or journal.get('phase') not in ('disable-pending','retire-pending','action-pending','deployment-pending','start-intent','completed'):
        raise Held('unknown/foreign adoption intent')
    if journal['phase']=='disable-pending':
        h.disable_only_exact_old_task()
        journal['phase']='retire-pending';h.save(journal)
    if journal['phase']=='retire-pending':
        # No process/PID fallback: only the exact owned mechanical task is
        # stopped; its old Guardian must independently exit before proceeding.
        h.stop_exact_mechanical_task_and_wait_dead()
        h.assert_legacy_and_dead_predecessor()
        journal['phase']='action-pending';h.save(journal)
    if journal['phase']=='action-pending':
        h.rebind_only_action_and_readback()
        journal['phase']='deployment-pending';h.save(journal)
    if journal['phase']=='deployment-pending':
        h.write_exact_private_deployment_after_task_readback()
        journal['phase']='start-intent';h.save(journal) # BEFORE enabling minute trigger.
        fresh=True
    else:fresh=False
    if journal['phase']=='start-intent':
        if fresh:
            h.enable_exact_task()
            if not h.actual_one_instance():h.start_exact_task_once()
        # A resumed start intent never enables or starts again. Trigger/explicit
        # start ambiguity needs a genuine new fixed Guardian receipt/kernel.
        receipt=h.reconcile_actual_guardian()
        journal.update(phase='completed',guardian=receipt);h.save(journal)
    return journal
