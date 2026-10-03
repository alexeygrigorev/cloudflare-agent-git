import importlib.util,pathlib,unittest,tempfile,json,os
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
 def test_read_only_allowlist(self):
  self.assertTrue(service.read_only(['aplexer','whoami','--json']))
  self.assertTrue(service.read_only(['aplexer','list','--json']))
  self.assertTrue(service.read_only(['aplexer','capture','session-id','--screen','--plain']))
  self.assertTrue(service.read_only([service.BINARY,'message','inbox','--json']))
  self.assertTrue(service.read_only([service.BINARY,'message','log','--json']))
  self.assertTrue(service.read_only([service.BINARY,'message','show','id-1','--json']))
  self.assertTrue(service.read_only([service.BINARY,'message','send','--help']))
  self.assertFalse(service.read_only([service.BINARY,'message','send','--to','inbox','--json','body text']))
  self.assertFalse(service.read_only([service.BINARY,'message','reply','id-1','--json','body']))
  self.assertFalse(service.read_only([service.BINARY,'message','deliver','id-1','--json']))
  self.assertFalse(service.read_only([service.BINARY,'message','ack','id-1','--json']))
  self.assertFalse(service.read_only([service.BINARY,'state-report','--json']))
  self.assertFalse(service.read_only(['quse','codex','--json']))
 def test_busy_send_one_call_uncertain_degraded_no_second_id(self):
  real_run=service.subprocess.run;persisted=[]
  BUSY='a: mailbox /home/alexey/git/cloudflare-agent-git is busy, retry: Resource temporarily unavailable (os error 11)'
  class R:
   returncode=1;stdout='';stderr=BUSY
  def fake(a,**k):persisted.append(a);return R()
  service.subprocess.run=fake
  try:
   with self.assertRaises(service.DeliveryUncertain) as ctx:
    service.command([service.BINARY,'message','send','--to','claude-principal','--json','body'])
   self.assertEqual(len(persisted),1)
   self.assertIn(BUSY[:60],ctx.exception.stderr)
   report={'timestamp':'t','identity':'x','principals':{},'errors':[],'actions':[],'degraded':False}
   service.record_cycle_failure(report,ctx.exception)
   self.assertTrue(report['degraded'])
   self.assertEqual(report['observation'],'incomplete-cycle: DeliveryUncertain')
   self.assertEqual(report['uncertain_outcome']['outcome'],'UNKNOWN')
   self.assertIn('message',report['uncertain_outcome']['cmd'])
   with tempfile.TemporaryDirectory() as folder:
    spool=pathlib.Path(folder)
    with self.assertRaises(service.DeliveryUncertain):
     service.recorded_send(service.BINARY,'claude-principal','ev-key','body',spool,'sender',True)
    self.assertEqual(len(persisted),2)
    frozen=service.recorded_send(service.BINARY,'claude-principal','ev-key','body',spool,'sender',True)
    self.assertEqual(len(persisted),2)
    self.assertEqual(frozen['delivery'],'send-uncertain');self.assertIsNone(frozen['id'])
  finally:service.subprocess.run=real_run
 def test_busy_inbox_byte_exact_stderr_retries_then_success(self):
  real_run,real_time=service.subprocess.run,service.time
  BUSY='a: mailbox /home/alexey/git/cloudflare-agent-git is busy, retry: Resource temporarily unavailable (os error 11)'
  seq=[{'rc':1,'err':BUSY},{'rc':1,'err':BUSY},{'rc':0,'out':'{"messages":[]}'}]
  slept=[]
  class R:
   def __init__(self,e):self.returncode=e['rc'];self.stdout=e.get('out','');self.stderr=e.get('err','')
  service.subprocess.run=lambda a,**k:R(seq.pop(0))
  service.time=type('T',(),{'sleep':staticmethod(lambda s:slept.append(s))})()
  try:self.assertEqual(service.command(['aplexer','message','inbox','--json']),'{"messages":[]}')
  finally:service.subprocess.run,service.time=real_run,real_time
  self.assertEqual(slept,[0.2,0.4])
 def test_busy_ack_and_unknown_verb_single_invocation(self):
  real_run=service.subprocess.run;calls=[]
  class R:
   returncode=1;stdout='';stderr='a: mailbox /home/alexey/git/cloudflare-agent-git is busy, retry: Resource temporarily unavailable (os error 11)'
  def fake(a,**k):calls.append(a);return R()
  service.subprocess.run=fake
  try:
   with self.assertRaises(service.AckUncertain):service.command([service.BINARY,'message','ack','id-1','--json'])
   with self.assertRaises(service.MutationUncertain) as ctx:service.command([service.BINARY,'state-report','--json','x'])
   self.assertNotIsInstance(ctx.exception,(service.DeliveryUncertain,service.AckUncertain))
  finally:service.subprocess.run=real_run
  self.assertEqual(len(calls),2)
 def test_generic_error_degrades_cycle(self):
  report={'timestamp':'t','identity':'x','principals':{},'errors':[],'actions':[],'degraded':False}
  service.record_cycle_failure(report,RuntimeError('quota query failed'))
  self.assertTrue(report['degraded'])
  self.assertEqual(report['observation'],'incomplete-cycle: RuntimeError')
  self.assertNotIn('uncertain_outcome',report)
  service.record_cycle_failure(report,service.MailboxBusy('command failed: mailbox busy after 5 retries'))
  self.assertTrue(report['degraded'])
  self.assertEqual(report['observation'],'incomplete-cycle: MailboxBusy')
 def test_active_principals_default(self):
  self.assertEqual(service.active_principals(), ['codex-principal', 'claude-principal'])
 def test_active_principals_env_exclusion(self):
  old = service.os.environ.get('SUPERVISION_EXCLUDE_PRINCIPALS')
  try:
   service.os.environ['SUPERVISION_EXCLUDE_PRINCIPALS'] = 'claude-principal'
   self.assertEqual(service.active_principals(), ['codex-principal'])
  finally:
   if old is not None: service.os.environ['SUPERVISION_EXCLUDE_PRINCIPALS'] = old
   else: service.os.environ.pop('SUPERVISION_EXCLUDE_PRINCIPALS', None)
 def test_active_principals_registry_exclusion(self):
  reg = {'excluded_principals': ['claude-principal']}
  self.assertEqual(service.active_principals(registry_raw=reg), ['codex-principal'])
  reg2 = {'agents': [{'tag': 'claude-principal', 'status': 'quiet'}]}
  self.assertEqual(service.active_principals(registry_raw=reg2), ['codex-principal'])
  reg3 = {'teams': [{'agents': [{'tag': 'claude-principal', 'status': 'morning-only'}]}]}
  self.assertEqual(service.active_principals(registry_raw=reg3), ['codex-principal'])
  reg4 = {'agents': [{'tag': 'claude-principal', 'supervision_excluded': True}]}
  self.assertEqual(service.active_principals(registry_raw=reg4), ['codex-principal'])
 def test_service_run_fail_closed_delivery_and_negatives(self):
  with tempfile.TemporaryDirectory() as td:
   tmp = pathlib.Path(td)
   root = tmp / 'root'
   (root / 'coordination').mkdir(parents=True)
   (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams': [{'id': 'T1', 'principal_tags': ['codex-principal']}]}))
   (root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': [{'id': 'task-1', 'team_id': 'T1', 'status': 'ready', 'owner_tag': 'codex-principal'}]}))
   private = tmp / 'private'
   private.mkdir()
   bin_dir = tmp / 'bin'
   bin_dir.mkdir()
   pinned = bin_dir / 'aplexer'
   pinned.write_bytes(b'PINNED')

   cycles = [0]
   calls = []
   captures_in_cycle = [0]
   screen_holder = ["› Ask Codex to do anything\n  GPT-6.1-Sol medium · Context 43% left\n  ? for shortcuts"]
   fresh_screen_holder = [None]
   deliver_ret = [{'status': 'not-ready', 'detail': 'recipient composer has an unsubmitted draft in progress (GPT-6.1-Sol medium · Context 43% left...); delivery fail-closed'}]

   def fake_cmd(args, timeout=20):
    words = [a for a in args[1:] if not a.startswith('-')]
    if words[:1] == ['whoami']:
     return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
    if 'idempotency-key' in args and 'help' in args:
     return '  --idempotency-key'
    if words[:1] == ['list']:
     captures_in_cycle[0] = 0
     cycles[0] += 1
     if cycles[0] >= 3:
      (private / 'stop').write_text('stop')
     return json.dumps([{'workspace': str(root), 'tag': 'codex-principal', 'id': 'sess-codex', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}])
    if 'inbox' in args:
     return json.dumps({'messages': []})
    if 'capture' in args:
     captures_in_cycle[0] += 1
     if captures_in_cycle[0] >= 2 and fresh_screen_holder[0] is not None:
      return fresh_screen_holder[0]
     return screen_holder[0]
    if args[0] == 'quse':
     return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 90}}}})
    if words[:2] == ['message', 'send']:
     return json.dumps({'id': 'm1', 'delivery': 'inbox'})
    return '{}'

   class R:
    def __init__(self, rc, out, err=''):
     self.returncode, self.stdout, self.stderr = rc, out, err

   def fake_run(args, **kw):
    calls.append(list(args))
    if 'send' in args:
     return R(0, json.dumps({'id': 'm1', 'delivery': 'inbox'}))
    if 'deliver' in args:
     return R(0, json.dumps(deliver_ret[0]))
    return R(0, '{}')

   real_cmd, real_run, real_time = service.command, service.subprocess.run, service.time
   real_root, real_priv, real_bin = service.ROOT, service.PRIVATE, service.BINARY
   real_defaults = service.recorded_send.__defaults__

   try:
    service.command = fake_cmd
    service.subprocess.run = fake_run
    service.recorded_send.__defaults__ = (fake_cmd,)
    service.time = type('T', (), {'time': staticmethod(lambda: 1000.0), 'sleep': staticmethod(lambda s: None)})()
    service.ROOT, service.PRIVATE = root, private
    service.BINARY = str(pinned)

    # 1. Fail-closed: not-ready outcome is preserved verbatim in delivery record and pending
    service.run()
    delivers = [c for c in calls if 'deliver' in c]
    self.assertTrue(delivers)
    self.assertTrue(all(c[0] == str(pinned) for c in delivers))
    self.assertEqual(delivers[0][0], str(pinned))
    self.assertEqual(delivers[0][3], 'm1')
    ev = json.loads((private / 'delivery-m1.json').read_text())
    self.assertEqual(ev.get('status'), 'not-ready')
    self.assertIn('recipient composer has an unsubmitted draft', ev.get('detail', ''))
    st = json.loads((private / 'state.json').read_text())
    self.assertEqual(st['codex-principal']['pending']['delivery'], 'not-ready')

    # 2. Negative: fresh_screen draft prevents delivery even when initial snapshot was empty
    calls.clear()
    cycles[0] = 0
    captures_in_cycle[0] = 0
    (private / 'stop').unlink(missing_ok=True)
    (private / 'state.json').unlink(missing_ok=True)
    screen_holder[0] = "› Ask Codex to do anything\n  GPT-6.1-Sol medium · Context 43% left"
    fresh_screen_holder[0] = "› Fix rate limiter\n  GPT-6.1-Sol medium · Context 43% left"
    service.run()
    delivers = [c for c in calls if 'deliver' in c]
    self.assertEqual(delivers, [])

    # 3. Negative: fresh_screen busy prevents delivery
    calls.clear()
    cycles[0] = 0
    captures_in_cycle[0] = 0
    (private / 'stop').unlink(missing_ok=True)
    (private / 'state.json').unlink(missing_ok=True)
    screen_holder[0] = "› Ask Codex to do anything\n  GPT-6.1-Sol medium · Context 43% left"
    fresh_screen_holder[0] = "• Working (2m • esc to interrupt)\n› Ask Codex to do anything"
    service.run()
    delivers = [c for c in calls if 'deliver' in c]
    self.assertEqual(delivers, [])

    # 4. Happy path: clean empty prompt and BINARY returning submitted records submitted
    calls.clear()
    cycles[0] = 0
    captures_in_cycle[0] = 0
    fresh_screen_holder[0] = None
    (private / 'stop').unlink(missing_ok=True)
    (private / 'state.json').unlink(missing_ok=True)
    screen_holder[0] = '› Ask Codex to do anything'
    deliver_ret[0] = {'status': 'submitted', 'id': 'm1'}
    service.run()
    delivers = [c for c in calls if 'deliver' in c]
    self.assertTrue(delivers)
    self.assertTrue(all(c[0] == str(pinned) for c in delivers))
    ev = json.loads((private / 'delivery-m1.json').read_text())
    self.assertEqual(ev.get('status'), 'submitted')
    st = json.loads((private / 'state.json').read_text())
    self.assertEqual(st['codex-principal']['pending']['delivery'], 'submitted')
   finally:
    service.command, service.subprocess.run, service.time = real_cmd, real_run, real_time
    service.recorded_send.__defaults__ = real_defaults
    service.ROOT, service.PRIVATE, service.BINARY = real_root, real_priv, real_bin

if __name__=='__main__':unittest.main()

