import copy,unittest
from opencode_task_transition import transition,Held

class Hooks:
    plan_sha256='a'*64
    def __init__(self):self.journal=None;self.effects=[];self.instances=False;self.fail_start=False;self.protected=True
    def verify_plan_and_source(self):pass
    def verify_protected_family(self):
        if not self.protected:raise Held('protected family changed')
    def verify_old_task_and_quiescence(self):pass
    def read(self):return copy.deepcopy(self.journal)
    def save(self,v):self.journal=copy.deepcopy(v)
    def verify_new_task(self):pass
    def disable_exact_task_reconcile(self):self.effects.append('disable')
    def retire_exact_outside_guardian(self):self.effects.append('outside-guardian-retire')
    def rebind_only_arguments_reconcile(self):self.effects.append('arguments-only')
    def persist_exact_runtime_plan(self):self.effects.append('immutable-plan')
    def enable_exact_task(self):self.effects.append('enable')
    def actual_one_instance(self):return self.instances
    def start_once(self):self.effects.append('start-once');self.instances=True
    def reconcile_guardian(self):
        if self.fail_start:raise Held('actual Guardian absent, no replay')
        return {'source_sha256':'b'*64,'pid':123,'creation_filetime':456}

class Tests(unittest.TestCase):
    def test_order_has_no_root_family_or_role_effect(self):
        h=Hooks();r=transition(h)
        self.assertEqual(r['phase'],'completed')
        self.assertEqual(h.effects,['disable','outside-guardian-retire','arguments-only','immutable-plan','enable','start-once'])
    def test_lost_start_receipt_never_reenables_or_restarts(self):
        h=Hooks();h.fail_start=True
        with self.assertRaises(Held):transition(h)
        effects=list(h.effects);self.assertEqual(h.journal['phase'],'start-intent')
        h.fail_start=False;transition(h);self.assertEqual(h.effects,effects)
    def test_existing_minute_instance_avoids_explicit_start(self):
        h=Hooks();h.instances=True;transition(h);self.assertNotIn('start-once',h.effects)
    def test_foreign_or_unknown_journal_prevents_effects(self):
        for j in ({'v':1,'plan_sha256':'foreign','phase':'disable-intent'},{'v':1,'plan_sha256':'a'*64,'phase':'unknown'}):
            h=Hooks();h.journal=j
            with self.assertRaises(Held):transition(h)
            self.assertEqual(h.effects,[])
    def test_protected_change_prevents_first_effect(self):
        h=Hooks();h.protected=False
        with self.assertRaises(Held):transition(h)
        self.assertEqual(h.effects,[])

if __name__=='__main__':unittest.main()
