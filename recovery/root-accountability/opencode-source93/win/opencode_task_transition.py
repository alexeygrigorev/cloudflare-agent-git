"""One existing Task cutover, preserving a living expired managed root.

The concrete Windows hooks must prove protected family/history custody and the
old outside Guardian's absence of child work before every mechanical effect.
No model start, role acquire, root family termination or source installation is
performed here. An uncertain start is reconcile-only, including minute triggers.
"""
class Held(RuntimeError):pass

def transition(h):
    h.verify_plan_and_source();h.verify_protected_family()
    journal=h.read()
    if journal is None:
        h.verify_old_task_and_quiescence()
        journal={'v':1,'plan_sha256':h.plan_sha256,'phase':'disable-intent'}
        h.save(journal)
    if (type(journal) is not dict or journal.get('v')!=1 or journal.get('plan_sha256')!=h.plan_sha256
        or journal.get('phase') not in ('disable-intent','retire-intent','action-intent','plan-intent','start-intent','completed')):
        raise Held('unknown or foreign mechanical transition')
    if journal['phase']=='completed':
        h.verify_new_task();h.reconcile_guardian();h.verify_protected_family();return journal
    if journal['phase']=='disable-intent':
        h.disable_exact_task_reconcile();h.verify_protected_family()
        journal['phase']='retire-intent';h.save(journal)
    if journal['phase']=='retire-intent':
        h.retire_exact_outside_guardian();h.verify_protected_family()
        journal['phase']='action-intent';h.save(journal)
    if journal['phase']=='action-intent':
        h.rebind_only_arguments_reconcile();h.verify_protected_family()
        journal['phase']='plan-intent';h.save(journal)
    if journal['phase']=='plan-intent':
        h.persist_exact_runtime_plan();h.verify_protected_family()
        journal['phase']='start-intent';h.save(journal)
        fresh=True
    else:fresh=False
    if journal['phase']=='start-intent':
        if fresh:
            h.enable_exact_task()
            # Persisted start intent precedes enabling, since the existing
            # minute trigger may start it before this own observation.
            if not h.actual_one_instance():h.start_once()
        receipt=h.reconcile_guardian()
        h.verify_new_task();h.verify_protected_family()
        journal.update(phase='completed',guardian=receipt);h.save(journal)
    return journal
