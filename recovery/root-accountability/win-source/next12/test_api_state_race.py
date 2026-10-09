import copy
import json
import pathlib
import tempfile
import subprocess
import sys
import unittest
from api_root_state import persist,event,history
from api_root_custody import observe,validate_latest_history
from win35_root_sink import save

class StateRace(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=pathlib.Path(self.tmp.name)/'root-runtime.json'
        self.state={'runtime_mode':'api-root','conversation_id':'cid','thread_owner':{'actor':'a','epoch':7},'provider_turn_id':'t','provider_turn_state':'busy','provider_pending_tools':{},'api_history_validated':False}
        save(self.path,self.state)
    def read(self):return json.loads(self.path.read_text())
    def event(self,method,params):event(self.path,('cid',self.state['thread_owner']),{'method':method,'params':dict(threadId='cid',**params)},observe,save)
    def test_completed_survives_late_callback(self):
        stale=copy.deepcopy(self.state)
        self.event('turn/completed',{'turn':{'id':'t','status':'completed'}})
        stale['initial_turn_submitted']=True
        persist(self.path,stale,save)
        self.assertEqual(self.read()['provider_turn_state'],'completed')
        self.assertTrue(stale['initial_turn_submitted'])
    def history(self,turn='t'):
        return history(self.path,('cid',self.state['thread_owner']),{'id':'cid','historyMode':'legacy','turns':[{'id':turn,'status':'completed'}]},validate_latest_history,save,lambda state:'receipt')
    def test_authenticated_history_recovers_lost_completion(self):
        self.assertTrue(self.history()['api_history_validated'])
        self.assertEqual(self.read()['provider_turn_state'],'completed')
    def test_new_turn_dominates_old_history(self):
        stale=self.history()
        starting=self.read();starting['provider_turn_state']='starting';starting['api_history_validated']=False;persist(self.path,starting,save)
        self.event('turn/started',{'turn':{'id':'new'}})
        persist(self.path,stale,save)
        self.assertEqual(self.read()['provider_turn_id'],'new')
        self.assertFalse(self.read()['api_history_validated'])
        self.assertFalse(self.history()['api_history_validated'])
    def test_pending_not_cleared_by_completed_history(self):
        self.event('item/tool/call',{'callId':'tool'})
        self.assertFalse(self.history()['api_history_validated'])
        self.assertEqual(self.read()['provider_pending_tools'],{'tool':True})
    def test_foreign_binding_denied(self):
        for field,value in [('conversation_id','foreign'),('thread_owner',{'actor':'foreign'})]:
            proposed=self.read();proposed[field]=value
            with self.assertRaises(RuntimeError):persist(self.path,proposed,save)
        self.assertEqual(self.read(),self.state)
    def test_revision_forgery_denied(self):
        for value in [True,-1,1,'0']:
            proposed=self.read();proposed['_api_event_revision']=value
            with self.assertRaises(RuntimeError):persist(self.path,proposed,save)
    def test_restart_preserves_event_revision(self):
        stale=self.read();self.event('turn/completed',{'turn':{'id':'t','status':'completed'}})
        # New caller has no in-memory lock/event cache after restart.
        persist(self.path,stale,save)
        self.assertEqual(self.read()['_api_event_revision'],1)
        self.assertEqual(self.read()['provider_turn_state'],'completed')
    def test_starting_submission_is_not_old_history_completion(self):
        state=self.read();state['provider_turn_state']='starting';save(self.path,state)
        self.assertFalse(self.history()['api_history_validated'])
        self.assertEqual(self.read()['provider_turn_state'],'starting')
    def test_foreign_or_old_history_cannot_recover(self):
        for thread in [{'id':'foreign','historyMode':'legacy','turns':[{'id':'t','status':'completed'}]},
                       {'id':'cid','historyMode':'legacy','turns':[{'id':'old','status':'completed'}]}]:
            value=history(self.path,('cid',self.state['thread_owner']),thread,validate_latest_history,save,lambda state:'receipt')
            self.assertFalse(value['api_history_validated'])
            self.assertEqual(value['provider_turn_state'],'busy')
    def test_real_second_process_cannot_overwrite_completion(self):
        self.event('turn/completed',{'turn':{'id':'t','status':'completed'}})
        code="import sys,json,pathlib;sys.path.insert(0,sys.argv[1]);from api_root_state import persist;from win35_root_sink import save;persist(pathlib.Path(sys.argv[2]),json.loads(sys.argv[3]),save)"
        result=subprocess.run([sys.executable,'-I','-S','-c',code,str(pathlib.Path(__file__).parent),str(self.path),json.dumps(self.state)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.read()['provider_turn_state'],'completed')
    def test_interrupted_temp_write_preserves_atomic_old_then_resume(self):
        def interrupted(path,value):
            path.with_suffix('.tmp').write_text('{')
            raise RuntimeError('injected before replacement')
        with self.assertRaises(RuntimeError):
            event(self.path,('cid',self.state['thread_owner']),{'method':'turn/completed','params':{'threadId':'cid','turn':{'id':'t','status':'completed'}}},observe,interrupted)
        self.assertEqual(self.read(),self.state)
        self.event('turn/completed',{'turn':{'id':'t','status':'completed'}})
        self.assertEqual(self.read()['provider_turn_state'],'completed')
    def test_duplicate_started_cannot_downgrade_completed_turn(self):
        self.history();before=self.read()
        self.event('turn/started',{'turn':{'id':'t'}})
        self.assertEqual(self.read(),before)
    def test_late_old_started_cannot_replace_new_busy_turn(self):
        self.history();starting=self.read();starting.update(provider_turn_state='starting',api_history_validated=False);persist(self.path,starting,save)
        self.event('turn/started',{'turn':{'id':'new'}});before=self.read()
        self.event('turn/started',{'turn':{'id':'t'}})
        self.assertEqual(self.read(),before)
    def test_unrequested_turn_holds_without_replacing_current(self):
        self.history();self.event('turn/started',{'turn':{'id':'foreign'}})
        self.assertEqual(self.read()['provider_turn_id'],'t')
        self.assertTrue(self.read()['provider_event_conflict'])
        self.assertFalse(self.history()['api_history_validated'])

if __name__=='__main__':unittest.main()
