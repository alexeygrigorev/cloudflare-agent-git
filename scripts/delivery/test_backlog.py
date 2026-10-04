import unittest
from validate_backlog import audit
class ContractTests(unittest.TestCase):
 def records(self):return ({'tasks':[{'id':'t','project_id':'agent-branches','status':'queued','next_action':'implement'}]},{'human_sources':[{'id':'h','task_ids':['t'],'requirement_summary':'ask','disposition':'deliverable'}]},{'projects':[{'id':x} for x in ['agent-branches','agent-dashboard','quota-launcher','agent-coordination']]})
 def test_dangling_ask_is_error(self):
  t,b,r=self.records();b['human_sources'][0]['task_ids']=['lost'];self.assertTrue(audit(t,b,r)['errors'])
 def test_false_done_rejected(self):
  t,b,r=self.records();t['tasks'][0]['status']='done';self.assertTrue(audit(t,b,r)['errors'])
 def test_running_requires_receipt(self):
  t,b,r=self.records();t['tasks'][0]['status']='running';self.assertTrue(audit(t,b,r)['warnings']);t['tasks'][0]['first_action']={'path':'artifact','at':'actual-time'};self.assertFalse(audit(t,b,r)['warnings'])
if __name__=='__main__':unittest.main()
