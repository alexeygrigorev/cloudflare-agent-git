import copy,unittest
from opencode_controller_journal import ControllerJournal
import test_opencode_root_producer as fixture_module

class JournalTests(unittest.TestCase):
    def setUp(self):
        fixture=fixture_module.RootProducerTests();fixture.setUp();self.context=fixture.context
        self.state=None;self.saves=[]
        def save(v):self.state=copy.deepcopy(v);self.saves.append(copy.deepcopy(v))
        self.j=ControllerJournal(lambda:copy.deepcopy(self.state),save,lambda c:True)
        self.j.select_input(self.context)
    def intent(self):return {'phase':'pending-reconcile-only','context':copy.deepcopy(self.context),'tool':'root_role_reply','arguments':{'body':'actual useful response','next_action':'verify current principal','checkpoint':'next genuine result'}}
    def result(self):return {'owner':self.context['owner'],'kernel':self.context['kernel'],'session_id':self.context['session_id'],'user_message_id':self.context['user_message_id'],
        'tool':'root_role_reply','arguments':self.intent()['arguments'],'output':'bounded-result','receipt_ref':'fixed-receipt','handled_at_ms':1800,'helper_exit_code':0}
    def test_selected_context_only_after_durable_intent_and_result(self):
        with self.assertRaises(RuntimeError):self.j.selected_context()
        self.j.write('helper-intent:fixed',self.intent());self.j.write('helper-result:fixed',self.result())
        selected=self.j.selected_context();self.assertEqual(selected['helper']['tool'],'root_role_reply')
        self.assertEqual(selected['helper']['recorded_at'],1.8)
        self.assertEqual(self.state['records']['helper-intent:fixed']['phase'],'handled-not-native-completed')
    def test_pending_input_cannot_be_replaced(self):
        self.j.write('helper-intent:fixed',self.intent())
        with self.assertRaises(RuntimeError):self.j.select_input(dict(self.context,user_message_id='msg_new'))
    def test_result_requires_real_matching_intent(self):
        with self.assertRaises(RuntimeError):self.j.write('helper-result:fixed',self.result())
        self.j.write('helper-intent:fixed',self.intent())
        with self.assertRaises(RuntimeError):self.j.write('helper-result:fixed',dict(self.result(),session_id='ses_foreign'))
    def test_unknown_and_foreign_journal_hold(self):
        self.state['phase']='unknown'
        with self.assertRaises(RuntimeError):self.j.select_input(self.context)
        self.state['phase']='selected';self.state['context']['owner']['actor']='foreign'
        with self.assertRaises(RuntimeError):self.j.select_input(self.context)
    def test_context_recheck_denies_old_kernel(self):
        self.j.write('helper-intent:fixed',self.intent());self.j.write('helper-result:fixed',self.result())
        self.j.binding=lambda c:False
        with self.assertRaises(RuntimeError):self.j.selected_context()
    def test_earlier_ack_and_snapshot_not_lost_before_latest_reply(self):
        for index,tool in enumerate(('root_ack_instructions','root_oversight_snapshot','root_role_reply')):
            intent=self.intent();intent['tool']=tool
            result=self.result();result['tool']=tool;result['receipt_ref']='receipt-'+str(index);result['handled_at_ms']=1800+index
            self.j.write('helper-intent:'+str(index),intent);self.j.write('helper-result:'+str(index),result)
        batch=self.j.selected_observation()
        self.assertEqual([c['helper']['tool'] for c in batch['helper_contexts']],['root_ack_instructions','root_oversight_snapshot','root_role_reply'])
        self.assertEqual(batch['context']['helper']['tool'],'root_role_reply')
        self.assertTrue(all(c['revision']==batch['revision'] for c in batch['helper_contexts']))
    def test_tied_native_times_preserve_durable_sequence(self):
        for index,receipt in enumerate(('z-first','a-latest')):
            self.j.write('helper-intent:'+str(index),self.intent())
            result=self.result();result['receipt_ref']=receipt
            self.j.write('helper-result:'+str(index),result)
        batch=self.j.selected_observation()
        self.assertEqual([c['helper']['receipt_ref'] for c in batch['helper_contexts']],['z-first','a-latest'])
        self.assertEqual(batch['context'],batch['helper_contexts'][-1])
    def test_backward_helper_time_is_held(self):
        self.j.write('helper-intent:1',self.intent());self.j.write('helper-result:1',self.result())
        self.j.write('helper-intent:2',self.intent())
        with self.assertRaises(RuntimeError):self.j.write('helper-result:2',dict(self.result(),handled_at_ms=1700))
if __name__=='__main__':unittest.main()
