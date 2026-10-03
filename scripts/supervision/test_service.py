import importlib.util,pathlib,unittest,tempfile,json
spec=importlib.util.spec_from_file_location('service',pathlib.Path(__file__).with_name('service.py'))
service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)
class Safety(unittest.TestCase):
 def test_codex_placeholder(self):
  self.assertEqual(service.composer('Done\n› Ask Codex to do anything\n  GPT-6 Context 50%\n  ? for shortcuts','codex-principal'),'empty')
 def test_claude_draft(self):
  self.assertEqual(service.composer('❯ go ahead and deploy the zcodex fix\n────','claude-principal'),'draft')
 def test_claude_feedback(self):
  self.assertEqual(service.composer('How is Claude doing\n❯\n────','claude-principal'),'menu-or-draft')
 def test_working(self):
  self.assertEqual(service.composer('• Working (5m • esc to interrupt)\n› Ask Codex to do anything','codex-principal'),'busy')
 def test_multiline_unknown(self):
  self.assertEqual(service.composer('❯\n deployment human draft','claude-principal'),'unknown')
 def test_reported_busy_denies(self):
  count,reason=service.eligible({'alive':True,'reported_state':'working'},'› Ask Codex to do anything','codex-principal',{})
  self.assertEqual(count,0)
 def test_quota_denies(self):
  self.assertFalse(service.quota_allowed({'codex':{'status':'ok','windows':{'7d':{'percent_remaining':15}}}}))
  self.assertFalse(service.quota_allowed({}))
 def test_two_same_session(self):
  state={'alive':True,'reported_state':'idle','session_id':'a'}
  screen='› Ask Codex to do anything'
  self.assertEqual(service.eligible(state,screen,'codex-principal',{})[0],1)
  self.assertEqual(service.eligible(state,screen,'codex-principal',{'session_id':'a','ready_snapshot_count':1})[0],2)
  self.assertEqual(service.eligible(state,screen,'codex-principal',{'session_id':'b','ready_snapshot_count':1})[0],1)
 def test_completed_no_busywork(self):
  self.assertEqual(service.task_event([{'id':'x','status':'completed'}])[0],[])
 def test_idle_slo_unchanged_work(self):
  self.assertTrue(service.idle_episode([{'id':'x'}],True,{'idle_since':0},301)[1])
  self.assertFalse(service.idle_episode([{'id':'x'}],False,{'idle_since':0},301)[1])
  self.assertFalse(service.idle_episode([],True,{'idle_since':0},301)[1])
  self.assertFalse(service.idle_episode([{'id':'x'}],True,{'idle_since':0,'pending':{'id':'y'}},301)[1])
 def test_timestamp_only_not_revision(self):
  a=service.task_event([{'id':'x','status':'ready','updated_at':'a'}])[1]
  b=service.task_event([{'id':'x','status':'ready','updated_at':'b'}])[1]
  self.assertEqual(a,b)
 def test_no_native_key_send_crash(self):
  with tempfile.TemporaryDirectory() as folder:
   calls=[]
   def fail(args):
    calls.append(args);raise RuntimeError('response lost')
   spool=pathlib.Path(folder)
   one=service.recorded_send('binary','peer','key','body',spool,'sender',False,fail)
   two=service.recorded_send('binary','peer','key','body',spool,'sender',False,fail)
   self.assertEqual(len(calls),1);self.assertEqual(two['delivery'],'send-uncertain')
   self.assertNotIn('--idempotency-key',calls[0])
 def test_no_native_key_receipt_reuse(self):
  with tempfile.TemporaryDirectory() as folder:
   calls=[]
   def send(args):
    calls.append(args);return json.dumps({'id':'message','delivery':'inbox'})
   spool=pathlib.Path(folder)
   service.recorded_send('binary','peer','key','body',spool,'sender',False,send)
   result=service.recorded_send('binary','peer','key','body',spool,'sender',False,send)
   self.assertEqual(len(calls),1);self.assertEqual(result['id'],'message')
 def test_foreign_sender_no_delivery(self):
  self.assertFalse(service.may_deliver({'id':'x','sender_id':'old','delivery':'inbox'},'new'))
  self.assertFalse(service.may_deliver({'id':'x','delivery':'inbox'},'new'))
  self.assertTrue(service.may_deliver({'id':'x','sender_id':'new','delivery':'inbox'},'new'))
 def test_busy_then_success(self):
  real_run,real_time=service.subprocess.run,service.time
  seq=[{'rc':1,'err':'workspace mailbox lock is busy, retry'},
       {'rc':1,'err':'Resource temporarily unavailable'},
       {'rc':0,'out':'{"messages":[]}'}]
  slept=[]
  class R:
   def __init__(self,e):self.returncode=e['rc'];self.stdout=e.get('out','');self.stderr=e.get('err','')
  service.subprocess.run=lambda a,**k:R(seq.pop(0))
  service.time=type('T',(),{'sleep':staticmethod(lambda s:slept.append(s))})()
  try:self.assertEqual(service.command(['aplexer','message','inbox','--json']),'{"messages":[]}')
  finally:service.subprocess.run,service.time=real_run,real_time
  self.assertEqual(slept,[0.2,0.4])
 def test_busy_exhausted_raises_mailboxbusy(self):
  real_run,real_time=service.subprocess.run,service.time
  calls=[];slept=[]
  class R:
   returncode=1;stdout='';stderr='mailbox lock is busy, retry later'
  def always_busy(a,**k):calls.append(a);return R()
  service.subprocess.run=always_busy
  service.time=type('T',(),{'sleep':staticmethod(lambda s:slept.append(s))})()
  try:
   with self.assertRaises(service.MailboxBusy) as ctx:service.command([service.BINARY,'message','inbox','--json'])
  finally:service.subprocess.run,service.time=real_run,real_time
  self.assertEqual(len(calls),6);self.assertEqual(slept,[0.2,0.4,0.8,1.6,3.2])
  self.assertIn('mailbox busy after 5 retries',str(ctx.exception))
 def test_nonbusy_failure_raises_immediately(self):
  real_run=service.subprocess.run;calls=[]
  class R:
   returncode=1;stdout='';stderr='unknown flag --nope'
  def bad(a,**k):calls.append(a);return R()
  service.subprocess.run=bad
  try:
   with self.assertRaises(RuntimeError) as ctx:service.command([service.BINARY,'whoami','--json'])
  finally:service.subprocess.run=real_run
  self.assertEqual(len(calls),1)
  self.assertIn('rc=1',str(ctx.exception));self.assertIn('unknown flag --nope',str(ctx.exception))
if __name__=='__main__':unittest.main()
