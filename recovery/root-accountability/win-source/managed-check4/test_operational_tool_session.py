import unittest,copy
from operational_tool_session import OperationalToolSession

class Session(unittest.TestCase):
    def setUp(self):
        self.state={'conversation_id':'parent','provider_turn_id':'turn',
                    'provider_turn_state':'busy','thread_owner':{'epoch':11}}
        self.effects=[]
        self.session=OperationalToolSession(lambda:copy.deepcopy(self.state),
            lambda *a:self.fail('unexpected SDK lookup'),lambda *a:self.fail('unexpected raw lookup'),
            lambda:None,lambda *a:None,
            lambda s,r:(self.effects.append((s,r)) or {'success':True}))
        self.request={'id':900,'method':'item/tool/call','params':{'threadId':'parent','turnId':'turn',
            'callId':'actual-call','tool':'root_role_ack','arguments':{'accept_custody':True}}}

    def test_scoped_initial_busy_ack_is_allowed_not_new_dispatch(self):
        self.assertTrue(self.session.authorize(self.request));self.session.handle(self.request)
        self.assertEqual(len(self.effects),1)

    def test_owner_turn_or_tool_changes_hold_before_parent_helper(self):
        for changes in ({'provider_turn_id':'new'}, {'provider_turn_state':'completed'}, {'thread_owner':None}):
            saved=copy.deepcopy(self.state);self.state.update(changes)
            with self.assertRaises(RuntimeError):self.session.handle(self.request)
            self.state=saved
        self.request['params']['tool']='root_recover'
        with self.assertRaises(RuntimeError):self.session.handle(self.request)
        self.assertEqual(self.effects,[])

    def test_child_cannot_borrow_parent_ack(self):
        self.request['params']['threadId']='child'
        with self.assertRaises(RuntimeError):self.session.handle(self.request)
        self.assertEqual(self.effects,[])

if __name__=='__main__':unittest.main()
