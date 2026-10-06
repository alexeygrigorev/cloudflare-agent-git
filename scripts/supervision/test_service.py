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

 def test_check_pending_slo_direct(self):
    """Test check_pending_slo calculation and precise blocking reasons."""
    t_now = 1000.0
    pending_fresh = {'id': 'm1', 'created_at': '1970-01-01T00:15:00+00:00'} # age = 100s
    pending_old = {'id': 'm2', 'created_at': '1970-01-01T00:05:00+00:00'} # age = 700s
    item = {'alive': True, 'composer': 'empty', 'reported_state': 'idle', 'reason': 'idle-empty'}

    is_beyond, dur, slo, reason = service.check_pending_slo(pending_fresh, 'codex-principal', item, now_ts=t_now)
    self.assertFalse(is_beyond)
    self.assertEqual(dur, 100.0)
    self.assertEqual(slo, 300)
    self.assertIsNone(reason)

    is_beyond, dur, slo, reason = service.check_pending_slo(pending_old, 'codex-principal', item, now_ts=t_now)
    self.assertTrue(is_beyond)
    self.assertEqual(dur, 700.0)
    self.assertEqual(slo, 300)

 def test_parse_and_validate_turn_hook_event(self):
    """Test parsing and validation of authoritative turn-boundary hook events."""
    valid_event = {
        'type': 'turn_complete',
        'state': 'idle-empty',
        'prompt_seq': 42,
        'session_id': '93cf28f2-2872-411c-a5da-179e1b83b59f',
        'engine': 'zcodex',
        'timestamp_ms': 1791118000000,
        'workload_pid': 12345,
        'active_children': 0,
        'composer_state': 'empty'
    }
    parsed = service.parse_and_validate_turn_hook_event(valid_event)
    self.assertTrue(parsed['syntax_valid'])
    self.assertTrue(parsed['authenticated_channel_required'])
    self.assertEqual(parsed['engine'], 'zcodex')
    self.assertEqual(parsed['prompt_seq'], 42)

    with self.assertRaises(ValueError):
        service.parse_and_validate_turn_hook_event({**valid_event, 'engine': 'unauthorized_engine'})

    with self.assertRaises(ValueError):
        service.parse_and_validate_turn_hook_event({**valid_event, 'active_children': 2})

 def test_known_footer_classifier_mismatch_annotates_diagnostic_hold(self):
    """Test that delivery refusal with footer signature annotates diagnostic_hold and includes it in blocked_beyond_slo escalation."""
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

      # Pre-stage a pending message that is already beyond SLO (created 400s ago)
      # created_at at t=600, current time t=1000 => age=400s >= 300s SLO
      initial_memory = {
          'codex-principal': {
              'event_key': 'ev-1',
              'session_id': 'sess-codex',
              'ready_snapshot_count': 2,
              'pending': {
                  'id': 'm-hold-1',
                  'sender_id': 'sup-1',
                  'sender_tag': 'experiment-supervision',
                  'recipient_session_id': 'sess-codex',
                  'recipient_tag': 'codex-principal',
                  'delivery': 'inbox',
                  'created_at': '1970-01-01T00:10:00+00:00'  # timestamp 600.0
              }
          }
      }
      (private / 'state.json').write_text(json.dumps(initial_memory))

      deliver_ret = [{'status': 'not-ready', 'detail': 'recipient composer has an unsubmitted draft in progress (GPT-6.1-Sol medium · Context 43% left...); delivery fail-closed'}]
      calls = []
      cycles = [0]

      def fake_cmd(args, timeout=20):
        words = [a for a in args[1:] if not a.startswith('-')]
        if words[:1] == ['whoami']:
          return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
        if words[:1] == ['list']:
          cycles[0] += 1
          if cycles[0] >= 2:
            (private / 'stop').write_text('stop')
          return json.dumps([{'workspace': str(root), 'tag': 'codex-principal', 'id': 'sess-codex', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}])
        if 'capture' in args:
          return '› Ask Codex to do anything'
        if args[0] == 'quse':
          return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 90}}}})
        return '{}'

      class R:
        def __init__(self, rc, out, err=''):
          self.returncode, self.stdout, self.stderr = rc, out, err

      def fake_run(args, **kw):
        calls.append(list(args))
        if 'deliver' in args:
          return R(0, json.dumps(deliver_ret[0]))
        return R(0, '{}')

      real_cmd, real_run, real_time = service.command, service.subprocess.run, service.time
      real_root, real_priv, real_bin = service.ROOT, service.PRIVATE, service.BINARY

      try:
        service.command = fake_cmd
        service.subprocess.run = fake_run
        service.time = type('T', (), {'time': staticmethod(lambda: 1000.0), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = root, private, str(pinned)

        service.run()

        st = json.loads((private / 'state.json').read_text())
        item = st['codex-principal']
        self.assertEqual(item.get('diagnostic_hold'), 'known-footer-classifier-mismatch')
        self.assertEqual(item.get('pending', {}).get('diagnostic_hold'), 'known-footer-classifier-mismatch')
        self.assertEqual(item.get('status'), 'blocked_beyond_slo')
        self.assertIn('[diagnostic_hold: known-footer-classifier-mismatch]', item.get('blocking_reason', ''))
        self.assertEqual(item.get('cooldown_until'), 1300.0)

        status_rep = json.loads((private / 'status.json').read_text())
        self.assertTrue(status_rep.get('degraded'))
        escalations = [a for a in status_rep.get('actions', []) if a.get('kind') == 'pending-blocked-beyond-slo-escalation']
        self.assertTrue(escalations)
        esc = escalations[0]
        self.assertEqual(esc['recipient'], 'codex-principal')
        self.assertEqual(esc['message_id'], 'm-hold-1')
        self.assertEqual(esc['diagnostic_hold'], 'known-footer-classifier-mismatch')
        self.assertEqual(esc['recovery_owner'], 'ant-head-never-timer-custody-20261006')
        self.assertIn('[diagnostic_hold: known-footer-classifier-mismatch]', esc['blocking_reason'])
      finally:
        service.command, service.subprocess.run, service.time = real_cmd, real_run, real_time
        service.ROOT, service.PRIVATE, service.BINARY = real_root, real_priv, real_bin

 def test_blocked_beyond_slo_applies_backoff_cooldown(self):
    """Test that blocked_beyond_slo sets 300s cooldown and suppresses subsequent delivery attempts until expired."""
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

      # Pre-stage a pending message created 400s ago (age=400 >= 300s SLO)
      initial_memory = {
          'codex-principal': {
              'event_key': 'ev-1',
              'session_id': 'sess-codex',
              'ready_snapshot_count': 2,
              'pending': {
                  'id': 'm-cool-1',
                  'sender_id': 'sup-1',
                  'sender_tag': 'experiment-supervision',
                  'recipient_session_id': 'sess-codex',
                  'recipient_tag': 'codex-principal',
                  'delivery': 'not-ready',
                  'created_at': '1970-01-01T00:10:00+00:00'  # timestamp 600.0
              }
          }
      }
      (private / 'state.json').write_text(json.dumps(initial_memory))

      curr_time = [1000.0]
      calls = []
      cycles = [0]

      def fake_cmd(args, timeout=20):
        words = [a for a in args[1:] if not a.startswith('-')]
        if words[:1] == ['whoami']:
          return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
        if words[:1] == ['list']:
          cycles[0] += 1
          if cycles[0] >= 2:
            (private / 'stop').write_text('stop')
          return json.dumps([{'workspace': str(root), 'tag': 'codex-principal', 'id': 'sess-codex', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}])
        if 'capture' in args:
          return '› Ask Codex to do anything'
        if args[0] == 'quse':
          return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 90}}}})
        return '{}'

      class R:
        def __init__(self, rc, out, err=''):
          self.returncode, self.stdout, self.stderr = rc, out, err

      def fake_run(args, **kw):
        calls.append(list(args))
        if 'deliver' in args:
          return R(0, json.dumps({'status': 'not-ready', 'detail': 'composer busy'}))
        return R(0, '{}')

      real_cmd, real_run, real_time = service.command, service.subprocess.run, service.time
      real_root, real_priv, real_bin = service.ROOT, service.PRIVATE, service.BINARY

      try:
        service.command = fake_cmd
        service.subprocess.run = fake_run
        service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = root, private, str(pinned)

        # Cycle 1: at t=1000.0, pending message is blocked beyond SLO. Cooldown should be set to 1300.0
        service.run()

        st = json.loads((private / 'state.json').read_text())
        item = st['codex-principal']
        self.assertEqual(item['status'], 'blocked_beyond_slo')
        self.assertEqual(item['cooldown_until'], 1300.0)

        # Cycle 2: advance time to 1100.0 (still within cooldown: 1100 < 1300). Delivery should NOT be attempted
        calls.clear()
        cycles[0] = 0
        (private / 'stop').unlink(missing_ok=True)
        curr_time[0] = 1100.0

        service.run()

        delivers_during_cooldown = [c for c in calls if 'deliver' in c]
        self.assertEqual(delivers_during_cooldown, [])

        # Cycle 3: advance time to 1301.0 (cooldown expired: 1301 >= 1300). Delivery SHOULD be attempted
        calls.clear()
        cycles[0] = 0
        (private / 'stop').unlink(missing_ok=True)
        curr_time[0] = 1301.0

        service.run()

        delivers_after_cooldown = [c for c in calls if 'deliver' in c]
        self.assertTrue(delivers_after_cooldown)
        self.assertEqual(delivers_after_cooldown[0][3], 'm-cool-1')
      finally:
        service.command, service.subprocess.run, service.time = real_cmd, real_run, real_time
        service.ROOT, service.PRIVATE, service.BINARY = real_root, real_priv, real_bin

 def test_head_ready_delta_tracking_and_deduplication(self):
  root = pathlib.Path(tempfile.mkdtemp())
  private = root / 'private'
  private.mkdir(parents=True, exist_ok=True)
  pinned = root / 'aplexer'
  pinned.write_text('#!/bin/sh\nexit 0\n')
  pinned.chmod(0o755)

  # Write initial team registry and tasks
  registry = {
    'teams': [
      {'id': 'e-branches', 'head_tag': 'agent-branches-head', 'principal_tags': ['codex-principal']}
    ]
  }
  (root / 'coordination').mkdir(parents=True, exist_ok=True)
  (root / 'coordination' / 'TEAM-REGISTRY.json').write_text(json.dumps(registry))

  tasks = [
    {'id': 't-task-1', 'owner_tag': 'agent-branches-head', 'status': 'ready', 'type': 'code'}
  ]
  (root / 'coordination' / 'TASKS.json').write_text(json.dumps(tasks))

  curr_time = [1000.0]
  sent_messages = []
  cycles = [0]
  current_sess_id = ['sess-head-1']

  def fake_cmd(args, timeout=20):
    words = [a for a in args[1:] if not a.startswith('-')]
    if words[:1] == ['whoami']:
      return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
    if words[:1] == ['list']:
      cycles[0] += 1
      if cycles[0] >= 1:
        (private / 'stop').write_text('stop')
      return json.dumps([
        {'workspace': str(root), 'tag': 'agent-branches-head', 'id': current_sess_id[0], 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
      ])
    if 'capture' in args:
      return '› \n'
    if words[:2] == ['message', 'send']:
      if '--help' in args:
        return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
      body = args[-1]
      to_tag = args[args.index('--to')+1] if '--to' in args else 'unknown'
      sent_messages.append({'to': to_tag, 'body': body, 'time': curr_time[0]})
      mid = f"m-head-{len(sent_messages)}"
      return json.dumps({'id': mid, 'delivery': 'inbox', 'created_at': '2026-10-06T18:00:00Z', 'body': body})
    if words[:2] == ['message', 'inbox']:
      return json.dumps([])
    return '{}'

  real_cmd, real_run, real_time = service.command, service.subprocess.run, service.time
  real_root, real_priv, real_bin = service.ROOT, service.PRIVATE, service.BINARY
  real_defaults = service.recorded_send.__defaults__

  try:
    service.command = fake_cmd
    service.recorded_send.__defaults__ = (fake_cmd,)
    service.subprocess.run = lambda *a, **k: type('R', (), {'returncode': 0, 'stdout': '{}', 'stderr': ''})()
    service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
    service.ROOT, service.PRIVATE, service.BINARY = root, private, str(pinned)

    # Stage 1: First appearance of ready task. Overdue episode at t=1200 (1200 - 1000 >= 180s).
    # Notification should be sent with ready_delta=True.
    curr_time[0] = 1200.0
    service.run()

    st = json.loads((private / 'state.json').read_text())
    head_item = st.get('agent-branches-head', {})
    self.assertTrue(head_item.get('ready_delta'))
    self.assertEqual(head_item.get('last_notified_ready_ids'), ['t-task-1'])
    self.assertIsNotNone(head_item.get('ready_fingerprint'))
    self.assertEqual(head_item.get('last_notified_ready_fingerprint'), head_item.get('ready_fingerprint'))
    self.assertEqual(len(sent_messages), 1)
    self.assertIn('t-task-1', sent_messages[0]['body'])

    # Stage 2: Head ACKs the message (pending cleared). Time advances by 200s (episode changes).
    # Task set has NOT changed (still identical t-task-1). Repetitive dump should be strictly suppressed.
    sent_messages.clear()
    cycles[0] = 0
    (private / 'stop').unlink(missing_ok=True)
    # Clear pending in state to simulate ACK reconciliation
    st['agent-branches-head']['pending'] = None
    (private / 'state.json').write_text(json.dumps(st))
    curr_time[0] = 1400.0

    service.run()

    st = json.loads((private / 'state.json').read_text())
    head_item = st.get('agent-branches-head', {})
    self.assertFalse(head_item.get('ready_delta'))
    self.assertTrue(head_item.get('ready_deduped'))
    self.assertEqual(head_item.get('last_notified_ready_ids'), ['t-task-1'])
    self.assertEqual(head_item.get('last_notified_ready_fingerprint'), head_item.get('ready_fingerprint'))
    # Crucial invariant: ZERO repetitive messages sent!
    self.assertEqual(len(sent_messages), 0)

    # Stage 3: Same t-task-1 ID, but updated failure/status/evidence/next_action (e.g. status='ready', error='executor crash')
    # Fingerprint changes -> ready_delta is True, escalation message sent even within same 180s episode (1410 // 180 == 1400 // 180 == 7)!
    tasks[0]['error'] = 'executor crash'
    tasks[0]['failure_count'] = 1
    tasks[0]['next_action'] = 'diagnose crash and relaunch'
    (root / 'coordination' / 'TASKS.json').write_text(json.dumps(tasks))
    sent_messages.clear()
    cycles[0] = 0
    (private / 'stop').unlink(missing_ok=True)
    curr_time[0] = 1410.0

    service.run()

    st = json.loads((private / 'state.json').read_text())
    head_item = st.get('agent-branches-head', {})
    self.assertTrue(head_item.get('ready_delta'))
    self.assertEqual(head_item.get('last_notified_ready_ids'), ['t-task-1'])
    self.assertEqual(head_item.get('last_notified_ready_fingerprint'), head_item.get('ready_fingerprint'))
    self.assertEqual(len(sent_messages), 1)
    self.assertIn('t-task-1', sent_messages[0]['body'])

    # Stage 4: Session restart (session_id changes to sess-head-2).
    # ACK previous message, keep identical task -> ready_delta is True due to session change, message sent to new session.
    current_sess_id[0] = 'sess-head-2'
    sent_messages.clear()
    cycles[0] = 0
    (private / 'stop').unlink(missing_ok=True)
    st['agent-branches-head']['pending'] = None
    (private / 'state.json').write_text(json.dumps(st))
    curr_time[0] = 1800.0

    service.run()

    st = json.loads((private / 'state.json').read_text())
    head_item = st.get('agent-branches-head', {})
    self.assertEqual(head_item.get('session_id'), 'sess-head-2')
    self.assertTrue(head_item.get('ready_delta'))
    self.assertEqual(len(sent_messages), 1)
    self.assertIn('t-task-1', sent_messages[0]['body'])

    # Stage 5: A new task 't-task-2' is added to ready tasks.
    st['agent-branches-head']['pending'] = None
    (private / 'state.json').write_text(json.dumps(st))
    tasks.append({'id': 't-task-2', 'owner_tag': 'agent-branches-head', 'status': 'ready', 'type': 'code'})
    (root / 'coordination' / 'TASKS.json').write_text(json.dumps(tasks))
    sent_messages.clear()
    cycles[0] = 0
    (private / 'stop').unlink(missing_ok=True)
    curr_time[0] = 2000.0

    service.run()

    st = json.loads((private / 'state.json').read_text())
    head_item = st.get('agent-branches-head', {})
    self.assertTrue(head_item.get('ready_delta'))
    self.assertEqual(head_item.get('last_notified_ready_ids'), ['t-task-1', 't-task-2'])
    # New notification with updated task set SHOULD be sent
    self.assertEqual(len(sent_messages), 1)
    self.assertIn('t-task-1', sent_messages[0]['body'])
    self.assertIn('t-task-2', sent_messages[0]['body'])

  finally:
    service.command, service.subprocess.run, service.time = real_cmd, real_run, real_time
    service.ROOT, service.PRIVATE, service.BINARY = real_root, real_priv, real_bin
    service.recorded_send.__defaults__ = real_defaults

 def test_task_ready_fingerprint_sensitivity(self):
  """Ensure task_ready_fingerprint responds to all meaningful task attributes and ignores non-fingerprinted fields."""
  base_task = {
    'id': 'task-100',
    'status': 'ready',
    'owner_tag': 'head-1',
    'updated_at': '2026-10-06T12:00:00Z',
    'blocked_on': ['dep-1', 'dep-2'],
    'next_action': 'investigate crash',
    'evidence_paths': ['evidence/log1.txt'],
    'failure_count': 0,
    'error': None,
    'blocking_reason': None,
    'acceptance_status': 'in_progress',
    'description': 'do work'
  }
  base_fp = service.task_ready_fingerprint(base_task)

  # 1. Non-monitored field changes (description) -> fingerprint identical
  modified = dict(base_task, description='completely different text')
  self.assertEqual(service.task_ready_fingerprint(modified), base_fp)

  # 2. Blocked_on reordering -> fingerprint identical
  reordered_deps = dict(base_task, blocked_on=['dep-2', 'dep-1'])
  self.assertEqual(service.task_ready_fingerprint(reordered_deps), base_fp)

  # 3. Evidence_paths reordering -> fingerprint identical
  reordered_ev = dict(base_task, evidence_paths=['evidence/log2.txt', 'evidence/log1.txt'])
  base_with_ev = dict(base_task, evidence_paths=['evidence/log1.txt', 'evidence/log2.txt'])
  self.assertEqual(service.task_ready_fingerprint(reordered_ev), service.task_ready_fingerprint(base_with_ev))

  # 4. Each sensitive attribute change causes fingerprint change
  sensitive_changes = [
    ('status', 'blocked'),
    ('owner_tag', 'head-2'),
    ('owner', 'head-alt'),
    ('updated_at', '2026-10-06T12:05:00Z'),
    ('blocked_on', ['dep-3']),
    ('next_action', 'restart worker'),
    ('evidence_paths', ['evidence/err.log']),
    ('failure_count', 1),
    ('error', 'OOM killed'),
    ('blocking_reason', 'missing credentials'),
    ('acceptance_status', 'failed')
  ]
  for key, val in sensitive_changes:
    changed_task = dict(base_task, **{key: val})
    if key == 'owner':
      changed_task.pop('owner_tag', None)
    self.assertNotEqual(
      service.task_ready_fingerprint(changed_task),
      base_fp,
      f"Field '{key}' change failed to alter task ready fingerprint"
    )

 def test_format_supervision_body_delta_and_bounded(self):
    """Ensure format_supervision_body correctly handles delta mode and full mode with source pointer."""
    tasks = [
      {'id': 'task-a', 'status': 'ready', 'owner_tag': 'head-1', 'project_id': 'proj-1'},
      {'id': 'task-b', 'status': 'running', 'owner_tag': 'head-2', 'project_id': 'proj-2'},
    ]
    # Full mode
    body_full = service.format_supervision_body('key-1', tasks, is_delta=False)
    self.assertIn('Tasks: [proj-1] task-a (ready, head-1); [proj-2] task-b (running, head-2)', body_full)

    # Delta mode
    body_delta = service.format_supervision_body('key-2', tasks[:1], is_delta=True, source_pointer='coordination/TASKS.json')
    self.assertIn('Changed actionable tasks (source: coordination/TASKS.json): [proj-1] task-a (ready, head-1)', body_delta)
    self.assertNotIn('task-b', body_delta)

 def test_principal_supervision_delta_payload_bounding(self):
    """
    Ensure principal supervision envelopes bound payloads:
    1. Initial notification sends bounded actionable tasks + pointer.
    2. Repeated identical tasks tick suppresses resending.
    3. Changed task sends ONLY the changed actionable task, not the full roster.
    4. Session restart resets and sends bounded initial task set.
    """
    import shutil
    Path = pathlib.Path
    tmp = Path(tempfile.mkdtemp())
    self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

    priv = tmp / 'private'
    priv.mkdir(parents=True, exist_ok=True)
    coord = tmp / 'coordination'
    coord.mkdir(parents=True, exist_ok=True)
    pinned = tmp / 'aplexer'
    pinned.write_text('#!/bin/sh\nexit 0\n')
    pinned.chmod(0o755)

    # Generate 25 tasks across projects to simulate a large project roster
    tasks_data = []
    for i in range(25):
      tasks_data.append({
        'id': f'task-{i:02d}',
        'status': 'ready' if i < 5 else 'blocked',
        'owner_tag': 'codex-principal',
        'project_id': 'agent-branches' if i % 2 == 0 else 'agent-bus',
        'updated_at': '2026-10-06T12:00:00Z',
        'blocked_on': [],
        'next_action': 'execute'
      })

    with open(coord / 'TASKS.json', 'w') as f:
      json.dump(tasks_data, f)

    entities_data = [
      {'id': 'agent-branches', 'principal_tags': ['codex-principal']},
      {'id': 'agent-bus', 'principal_tags': ['codex-principal']},
    ]
    with open(coord / 'TEAM-REGISTRY.json', 'w') as f:
      json.dump({'projects': entities_data}, f)

    current_sess_id = ['sess-codex-1']
    sent_bodies = []

    def fake_cmd(args, timeout=20):
      words = [a for a in args[1:] if not a.startswith('-')]
      if words[:1] == ['whoami']:
        return json.dumps({'workspace': str(tmp), 'tag': 'experiment-supervision', 'id': 'sup-1'})
      if '--help' in args or 'help' in args:
        return '  --idempotency-key'
      if words[:1] == ['list']:
        (priv / 'stop').write_text('stop')
        return json.dumps([
          {'workspace': str(tmp), 'tag': 'codex-principal', 'id': current_sess_id[0], 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
        ])
      if 'inbox' in args:
        return json.dumps({'messages': []})
      if 'capture' in args:
        return "› Ask Codex to do anything\n  GPT-6.1 Context 50% left"
      if args[0] == 'quse':
        return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 85}}}})
      return '{}'

    def fake_recorded_send(binary, tag, key, body, spool, sender_id, supports_key):
      sent_bodies.append(body)
      return {
        'id': f'msg-{len(sent_bodies)}',
        'delivery': 'inbox',
        'body': body
      }

    real_cmd, real_run, real_time = service.command, service.subprocess.run, service.time
    real_root, real_priv, real_bin = service.ROOT, service.PRIVATE, service.BINARY
    real_defaults = service.recorded_send.__defaults__
    real_recorded_send = service.recorded_send
    real_composer = service.composer

    t0 = [1000000.0]

    try:
      service.ROOT = tmp
      service.PRIVATE = priv
      service.BINARY = str(pinned)
      service.command = fake_cmd
      service.subprocess.run = lambda *a, **k: type('R', (), {'returncode': 0, 'stdout': '{}', 'stderr': ''})()
      service.recorded_send = fake_recorded_send
      service.recorded_send.__defaults__ = (fake_cmd,)
      service.composer = lambda screen, tag: 'empty'
      service.time = type('T', (), {
        'time': staticmethod(lambda: t0[0]),
        'sleep': staticmethod(lambda s: None)
      })()

      # Step 1: Initial run
      (priv / 'stop').unlink(missing_ok=True)
      service.run()
      self.assertEqual(len(sent_bodies), 1, "Initial cycle should send an envelope")
      init_body = sent_bodies[0]
      self.assertIn('Tasks: ', init_body)
      # Bounded: should contain at most 10 tasks, not all 25
      task_count_in_body = sum(1 for i in range(25) if f'task-{i:02d} ' in init_body)
      self.assertLessEqual(task_count_in_body, 10, "Initial envelope must bound tasks to at most 10")

      # Step 2: Simulate ACK of initial message and next cycle with unchanged tasks
      state_file = priv / 'state.json'
      with open(state_file) as f:
        st = json.load(f)
      # Reconcile pending message as acked
      st['codex-principal']['pending'] = None
      with open(state_file, 'w') as f:
        json.dump(st, f)

      t0[0] += 30.0
      (priv / 'stop').unlink(missing_ok=True)
      service.run()
      self.assertEqual(len(sent_bodies), 1, "Unchanged tasks should NOT send a new envelope")

      # Step 3: Change exactly ONE task (task-03 status changes from ready to running)
      tasks_data[3]['status'] = 'running'
      tasks_data[3]['updated_at'] = '2026-10-06T12:05:00Z'
      with open(coord / 'TASKS.json', 'w') as f:
        json.dump(tasks_data, f)

      t0[0] += 30.0
      (priv / 'stop').unlink(missing_ok=True)
      service.run()
      self.assertEqual(len(sent_bodies), 2, "Task change should send a delta envelope")
      delta_body = sent_bodies[1]
      self.assertIn('Changed actionable tasks (source: coordination/TASKS.json): ', delta_body)
      self.assertIn('task-03 (running, codex-principal)', delta_body)
      # Must NOT contain unchanged tasks in the delta list
      self.assertNotIn('task-00', delta_body)
      self.assertNotIn('task-01', delta_body)
      self.assertNotIn('task-02', delta_body)

      # Step 4: Next cycle without changes -> suppressed
      with open(state_file) as f:
        st = json.load(f)
      st['codex-principal']['pending'] = None
      with open(state_file, 'w') as f:
        json.dump(st, f)

      t0[0] += 30.0
      (priv / 'stop').unlink(missing_ok=True)
      service.run()
      self.assertEqual(len(sent_bodies), 2, "Unchanged tick after delta should be suppressed")

      # Step 5: Session restart -> new session receives bounded initial set
      current_sess_id[0] = 'sess-codex-2'
      t0[0] += 30.0
      (priv / 'stop').unlink(missing_ok=True)
      service.run()
      self.assertEqual(len(sent_bodies), 3, "Session change should trigger fresh bounded envelope")
      session_body = sent_bodies[2]
      self.assertIn('Tasks: ', session_body)

    finally:
      service.ROOT = real_root
      service.PRIVATE = real_priv
      service.BINARY = real_bin
      service.command = real_cmd
      service.subprocess.run = real_run
      service.recorded_send = real_recorded_send
      service.recorded_send.__defaults__ = real_defaults
      service.composer = real_composer
      service.time = real_time


 def test_is_task_eligible_for_supervision_stale_owner_rejection(self):
  """
  Negative tests verifying that obsolete owners (Grok, stopped Claude, legacy Ant)
  and ancient running labels are rejected, while active custody tasks are accepted (C3025).
  """
  from scripts.supervision.service import is_task_eligible_for_supervision

  # Negative 1: Obsolete Grok owners and dormant team a06-a10
  t_grok_head = {'id': 't-grok-1', 'status': 'running', 'owner': 'grok-head', 'team_id': 'a06-a10'}
  t_grok_worker = {'id': 't-grok-2', 'status': 'ready', 'owner': 'grok-worker', 'team_id': 'a06-a10'}
  self.assertFalse(is_task_eligible_for_supervision(t_grok_head), "Grok head must be rejected as obsolete")
  self.assertFalse(is_task_eligible_for_supervision(t_grok_worker), "Grok worker must be rejected as obsolete")

  # Negative 2: Stopped Claude implementation owner (Claude is monitoring principal only per user26)
  t_claude_impl = {'id': 't-claude-1', 'status': 'running', 'owner': 'claude-principal', 'project_id': 'agent-branches'}
  t_claude_ready = {'id': 't-claude-2', 'status': 'ready', 'owner': 'claude-worker', 'project_id': 'agent-branches'}
  self.assertFalse(is_task_eligible_for_supervision(t_claude_impl), "Claude implementation owner must be rejected")
  self.assertFalse(is_task_eligible_for_supervision(t_claude_ready), "Claude worker owner must be rejected")

  # Negative 3: Legacy Ant owners (exited / non-active custody sessions)
  t_ant_legacy = {'id': 't-ant-1', 'status': 'running', 'owner': 'antigravity-head', 'project_id': 'agent-branches'}
  t_ant_old = {'id': 't-ant-2', 'status': 'in_progress', 'owner': 'ant-head-operational-resume-20261005', 'project_id': 'agent-branches'}
  self.assertFalse(is_task_eligible_for_supervision(t_ant_legacy), "Legacy antigravity-head must be rejected")
  self.assertFalse(is_task_eligible_for_supervision(t_ant_old), "Old operational-resume ant session must be rejected")

  # Negative 4: Dormant older research teams (unmaintained / non-reacquired)
  t_a01 = {'id': 't-a01', 'status': 'ready', 'owner': 'zcode-independent', 'team_id': 'a01-harness'}
  t_a05 = {'id': 't-a05', 'status': 'ready', 'owner': 'space-bunny-head', 'team_id': 'a05'}
  self.assertFalse(is_task_eligible_for_supervision(t_a01), "Dormant a01-harness team must be rejected")
  self.assertFalse(is_task_eligible_for_supervision(t_a05), "Dormant a05 team must be rejected")

  # Positive 2: Reopened lane with genuine active custody owner (C3034)
  t_reopened_a01 = {'id': 't-reopened-1', 'status': 'running', 'owner': 'ant-head-never-timer-custody-20261006', 'team_id': 'a01-harness'}
  self.assertTrue(is_task_eligible_for_supervision(t_reopened_a01), "Reopened lane task with genuine active custody owner must be eligible")

  # Negative 5: Ancient running label with unknown / unmaintained owner and fresh unknown alias (fails honest)
  t_ancient_running = {'id': 't-ancient', 'status': 'running', 'owner': 'nonexistent-session', 'project_id': 'agent-dashboard'}
  t_unknown_alias = {'id': 't-unknown-alias', 'status': 'running', 'owner': 'fresh-unknown-alias-123', 'project_id': 'agent-branches'}
  self.assertFalse(is_task_eligible_for_supervision(t_ancient_running), "Ancient running label without active custody owner must be rejected")
  self.assertFalse(is_task_eligible_for_supervision(t_unknown_alias), "Fresh unknown owner alias must fail honest")

  # Positive 1: Genuine active custody tasks
  t_branches_active = {'id': 't-branches', 'status': 'in_progress', 'owner': 'ant-head-never-timer-custody-20261006', 'project_id': 'agent-branches'}
  t_ql_ready = {'id': 't-ql', 'status': 'ready', 'owner': 'ql-head-feedback-custody-20261006', 'project_id': 'quota-launcher'}
  t_coord_active = {'id': 't-coord', 'status': 'in_progress', 'owner': 'coord-917-custody-resume-20261006', 'project_id': 'agent-coordination'}
  t_unassigned_ready = {'id': 't-unassigned', 'status': 'queued', 'owner': None, 'project_id': 'agent-dashboard'}
  self.assertTrue(is_task_eligible_for_supervision(t_branches_active), "Active branches custody task must be eligible")
  self.assertTrue(is_task_eligible_for_supervision(t_ql_ready), "Active QL custody ready task must be eligible")
  self.assertTrue(is_task_eligible_for_supervision(t_coord_active), "Active coord custody task must be eligible")
  self.assertTrue(is_task_eligible_for_supervision(t_unassigned_ready), "Unassigned queued task must be eligible")

 def test_supervision_payload_filters_obsolete_owners_and_ancient_running_labels(self):
  """
  Test that the principal supervision payload strictly filters out obsolete Grok,
  stopped Claude, legacy Ant, and ancient running labels, bounding to genuine active tasks
  while preserving task history on disk (read-only collector) (C3025).
  """
  import shutil
  td = tempfile.mkdtemp()
  try:
   root = pathlib.Path(td) / 'workspace'
   priv = root / '.local' / 'supervision'
   coord = root / 'coordination'
   coord.mkdir(parents=True)
   priv.mkdir(parents=True)

   pinned = root / 'aplexer'
   pinned.write_text('#!/bin/sh\nexit 0\n')
   pinned.chmod(0o755)

   real_root = service.ROOT
   real_priv = service.PRIVATE
   real_bin = service.BINARY
   real_cmd = service.command
   real_run = service.subprocess.run
   real_recorded_send = service.recorded_send
   real_defaults = service.recorded_send.__defaults__
   real_composer = service.composer
   real_time = service.time

   sent_envelopes = []

   def fake_send(bin_path, to, key, body, spool=None, sender_id=None, supports_key=True):
    sent_envelopes.append({'to': to, 'key': key, 'body': body})
    return {'status': 'inbox', 'id': f'm-filter-{len(sent_envelopes)}', 'delivery': 'inbox'}

   t0 = [1000000.0]

   reg_data = {
     'teams': [
       {'id': 'a06-a10', 'name': 'Grok Team', 'head_tag': 'grok-head', 'principal_tags': ['codex-principal']},
       {'id': 'oversight', 'name': 'Oversight', 'head_tag': 'codex-principal', 'principal_tags': ['codex-principal']},
     ],
     'projects': [
       {'id': 'agent-branches', 'name': 'Agent Branches', 'head_tag': 'ant-head-never-timer-custody-20261006', 'principal_tags': ['codex-principal']},
       {'id': 'quota-launcher', 'name': 'Quota Launcher', 'head_tag': 'ql-head-feedback-custody-20261006', 'principal_tags': ['codex-principal']},
       {'id': 'agent-dashboard', 'name': 'Agent Dashboard', 'head_tag': 'agent-dashboard-head', 'principal_tags': ['codex-principal']},
     ]
   }
   with open(coord / 'TEAM-REGISTRY.json', 'w') as f:
    json.dump(reg_data, f)

   # Populate TASKS.json with a mix of obsolete and genuine tasks
   tasks_data = [
     # Obsolete Grok tasks (with ancient running label)
     {'id': 'task-grok-1', 'status': 'running', 'owner': 'grok-head', 'team_id': 'a06-a10'},
     {'id': 'task-grok-2', 'status': 'running', 'owner': 'grok-head', 'team_id': 'a06-a10'},
     # Stopped Claude implementation task
     {'id': 'task-claude-1', 'status': 'running', 'owner': 'claude-principal', 'project_id': 'agent-branches'},
     # Legacy Ant tasks
     {'id': 'task-ant-1', 'status': 'running', 'owner': 'antigravity-head', 'project_id': 'agent-branches'},
     {'id': 'task-ant-2', 'status': 'running', 'owner': 'antigravity-head', 'project_id': 'agent-branches'},
     # Ancient running task with dead session
     {'id': 'task-ancient-1', 'status': 'running', 'owner': 'dead-session-tag', 'project_id': 'agent-dashboard'},
     # Genuine active custody tasks
     {'id': 'task-genuine-ready-1', 'status': 'ready', 'owner': 'ql-head-feedback-custody-20261006', 'project_id': 'quota-launcher'},
     {'id': 'task-genuine-ready-2', 'status': 'queued', 'owner': None, 'project_id': 'agent-dashboard'},
     {'id': 'task-genuine-active-1', 'status': 'in_progress', 'owner': 'ant-head-never-timer-custody-20261006', 'project_id': 'agent-branches'},
   ]
   initial_tasks_json = json.dumps(tasks_data, indent=2)
   with open(coord / 'TASKS.json', 'w') as f:
    f.write(initial_tasks_json)

   fake_sessions = [
     {'id': 'sess-codex', 'tag': 'codex-principal', 'reported_state': 'idle', 'workspace': str(root), 'workload_pid': os.getpid()},
     {'id': 'sess-ant', 'tag': 'ant-head-never-timer-custody-20261006', 'reported_state': 'running', 'workspace': str(root), 'workload_pid': os.getpid()},
     {'id': 'sess-ql', 'tag': 'ql-head-feedback-custody-20261006', 'reported_state': 'running', 'workspace': str(root), 'workload_pid': os.getpid()},
   ]

   def fake_cmd(args, timeout=20):
    words = [a for a in args[1:] if not a.startswith('-')]
    if words[:1] == ['whoami']:
      return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
    if '--help' in args or 'help' in args:
      return '  --idempotency-key'
    if words[:1] == ['list']:
      (priv / 'stop').write_text('stop')
      return json.dumps(fake_sessions)
    if 'inbox' in args:
      return json.dumps({'messages': []})
    if 'capture' in args:
      return "› Ask Codex to do anything\\n  GPT-6.1 Context 50% left"
    if args[0] == 'quse':
      return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 85}}}})
    return '{}'

   service.ROOT = root
   service.PRIVATE = priv
   service.BINARY = str(pinned)
   service.command = fake_cmd
   service.subprocess.run = lambda *a, **k: type('R', (), {'returncode': 0, 'stdout': '{}', 'stderr': ''})()
   service.recorded_send = fake_send
   service.recorded_send.__defaults__ = (fake_cmd,)
   service.composer = lambda screen, tag: 'empty'
   service.time = type('T', (), {
     'time': staticmethod(lambda: t0[0]),
     'sleep': staticmethod(lambda s: None)
   })()

   (priv / 'stop').unlink(missing_ok=True)
   service.run()

   codex_envelopes = [e for e in sent_envelopes if e['to'] == 'codex-principal']
   self.assertEqual(len(codex_envelopes), 1, "Exactly 1 supervision envelope should be sent to codex-principal")
   body = codex_envelopes[0]['body']

   # 1. Verify genuine tasks ARE present in the principal payload
   self.assertIn('task-genuine-ready-1', body)
   self.assertIn('task-genuine-ready-2', body)
   self.assertIn('task-genuine-active-1', body)

   # 2. Verify obsolete / ancient tasks are strictly EXCLUDED from the principal payload
   self.assertNotIn('task-grok-1', body)
   self.assertNotIn('task-grok-2', body)
   self.assertNotIn('task-claude-1', body)
   self.assertNotIn('task-ant-1', body)
   self.assertNotIn('task-ant-2', body)
   self.assertNotIn('task-ancient-1', body)

   # 3. Verify task history is preserved and collector is read-only
   with open(coord / 'TASKS.json') as f:
    current_tasks_json = f.read()
   self.assertEqual(current_tasks_json, initial_tasks_json, "TASKS.json must not be modified by read-only collector")

  finally:
   service.ROOT = real_root
   service.PRIVATE = real_priv
   service.BINARY = real_bin
   service.command = real_cmd
   service.subprocess.run = real_run
   service.recorded_send = real_recorded_send
   service.recorded_send.__defaults__ = real_defaults
   service.composer = real_composer
   service.time = real_time
   shutil.rmtree(td, ignore_errors=True)

if __name__=='__main__':unittest.main()
