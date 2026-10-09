import copy,unittest
from opencode_keeper import Keeper
from opencode_controller_gate import ref

class KeeperTests(unittest.TestCase):
    def setUp(self):
        self.state=None;self.calls=[];self.fail=None;self.ordinal=1;self.completed=False
        self.candidate=dict(project='fixture',role='root',actor='native',generation='gen',epoch=1)
        def request(body):
            self.calls.append(copy.deepcopy(body))
            if body['op']==self.fail:raise RuntimeError('uncertain')
            result=dict(read_only=False,holder='native',generation='gen',epoch=12) if body['op']=='acquire' else {}
            if body['op'] in ('bootstrap_start','renew'):
                owner=dict(self.candidate,epoch=12)
                result['root_control']=dict(v=1,owner=owner,ordinal=self.ordinal,envelope='fixture:'+str(self.ordinal),
                    input_sha256='a'*64,issued_at=100,deadline=220,operation='root-check',payload={},
                    key='opencode-control:'+ref(owner)+':'+str(self.ordinal),response_completed=self.completed,check_completed=False)
            return dict(v=1,status='ok',result=result)
        self.keeper=Keeper(self.candidate,request,lambda:copy.deepcopy(self.state),
            lambda v:setattr(self,'state',copy.deepcopy(v)),lambda:None,lambda:100)
    def test_actual_acquire_epoch_then_existing_fence_start_and_check(self):
        receipt=self.keeper.step()
        self.assertEqual(receipt['owner']['epoch'],12)
        self.assertEqual([c['op'] for c in self.calls],['admission_refresh','acquire','first_action','bootstrap_start','admission_refresh','execute','renew'])
        self.assertFalse(receipt['activated_claimed'])
        self.assertFalse(receipt['check_completed'])
        self.keeper.step()
        self.assertEqual(self.calls[-1]['op'],'renew')
    def test_lost_root_start_response_reuses_same_request_and_no_other_effect(self):
        self.fail='bootstrap_start'
        with self.assertRaises(RuntimeError):self.keeper.step()
        pending=copy.deepcopy(self.state['pending'])
        self.fail=None;self.keeper.step()
        starts=[c for c in self.calls if c['op']=='bootstrap_start']
        self.assertEqual(starts,[pending['body'],pending['body']])
        self.assertEqual(len([c for c in self.calls if c['op']=='first_action']),1)
    def test_unknown_journal_never_runs_request(self):
        self.state={}
        with self.assertRaises(RuntimeError):self.keeper.step()
        self.assertEqual(self.calls,[])
    def test_lost_acquire_reconciles_without_new_admission_request(self):
        self.fail='acquire'
        with self.assertRaises(RuntimeError):self.keeper.step()
        self.fail=None;self.keeper.step()
        self.assertEqual(len([c for c in self.calls if c['op']=='admission_refresh']),2)
    def test_second_ordinal_dispatches_once_and_same_ordinal_never_repeats(self):
        self.keeper.step();self.ordinal=2;self.keeper.step();self.keeper.step()
        calls=[c for c in self.calls if c['op']=='execute']
        self.assertEqual(len(calls),2)
        self.assertEqual(len([c for c in self.calls if c['op']=='admission_refresh']),3)
        self.assertTrue(calls[0]['key'].endswith(':1'));self.assertTrue(calls[1]['key'].endswith(':2'))
    def test_completed_old_control_does_not_create_a_model_input(self):
        self.completed=True;self.keeper.step()
        self.assertEqual([c for c in self.calls if c['op']=='execute'],[])
    def test_uncertain_second_ordinal_reconciles_exact_key_before_next_renew(self):
        self.keeper.step();self.ordinal=2;self.fail='execute'
        with self.assertRaises(RuntimeError):self.keeper.step()
        pending=copy.deepcopy(self.state['pending']);self.fail=None;self.keeper.step()
        repeated=[c for c in self.calls if c['op']=='execute' and c['key'].endswith(':2')]
        self.assertEqual(repeated,[pending['body'],pending['body']])

if __name__=='__main__':unittest.main()
