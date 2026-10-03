import copy, fcntl, hashlib, json, pathlib, tempfile, unittest, uuid
from ack_reconciliation import exact_ack

class NativeAck(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.ws=str(self.root/'workspace')
  self.mid=str(uuid.uuid4());self.sender=str(uuid.uuid4());self.recipient=str(uuid.uuid4());self.tag='codex-principal'
  self.pending={'id':self.mid,'sender_id':self.sender,'delivery':'inbox'}
  self.box=self.root/'messages'/hashlib.sha256(self.ws.encode()).hexdigest()[:32]
  (self.box/'msgs').mkdir(parents=True);(self.box/'cursors').mkdir();(self.box/'.mailbox.lock').touch()
  self.env={'schema_version':1,'id':self.mid,'workspace':self.ws,'from':{'session_id':self.sender,'tag':'experiment-supervision','workspace':self.ws},'to':{'session_id':self.recipient,'tag':self.tag}}
  self.cursor={'exceptions':[self.mid]};self.write()
 def tearDown(self): self.tmp.cleanup()
 def write(self):
  (self.box/'workspace.json').write_text(json.dumps({'workspace':self.ws}))
  (self.box/'msgs'/(self.mid+'.json')).write_text(json.dumps(self.env))
  (self.box/'cursors'/(self.recipient+'.json')).write_text(json.dumps(self.cursor))
 def check(self):return exact_ack(self.pending,self.recipient,self.tag,self.ws,self.root)
 def test_changed_service_sender_exact_ack(self):
  before={str(p):p.read_bytes() for p in self.box.rglob('*') if p.is_file()}
  self.assertEqual(self.check()['original_sender_id'],self.sender)
  self.assertEqual(before,{str(p):p.read_bytes() for p in self.box.rglob('*') if p.is_file()})
 def test_absence_from_inbox_not_ack(self):self.cursor={};self.write();self.assertIsNone(self.check())
 def test_wrong_sender(self):self.env['from']['session_id']=str(uuid.uuid4());self.write();self.assertIsNone(self.check())
 def test_reused_recipient_tag_not_ack(self):self.env['to']['session_id']=str(uuid.uuid4());self.write();self.assertIsNone(self.check())
 def test_wrong_workspace(self):self.env['workspace']='/different';self.write();self.assertIsNone(self.check())
 def test_legacy_highwater_alone_not_ack(self):self.cursor={'acked_through':self.mid};self.write();self.assertIsNone(self.check())
 def test_ack_other_message_not_ack(self):self.cursor={'exceptions':[str(uuid.uuid4())]};self.write();self.assertIsNone(self.check())
 def test_pruned_envelope_not_ack(self):(self.box/'msgs'/(self.mid+'.json')).unlink();self.assertIsNone(self.check())
 def test_symlink_rejected(self):
  p=self.box/'cursors'/(self.recipient+'.json');p.unlink();target=self.root/'outside';target.write_text(json.dumps(self.cursor));p.symlink_to(target);self.assertIsNone(self.check())
 def test_oversized_cursor_rejected(self):(self.box/'cursors'/(self.recipient+'.json')).write_bytes(b' '*1048577);self.assertIsNone(self.check())
 def test_locked_mailbox_nonblocking(self):
  with (self.box/'.mailbox.lock').open('rb') as h:
   fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);self.assertIsNone(self.check())
 def test_malformed_cursor_rejected(self):(self.box/'cursors'/(self.recipient+'.json')).write_text('bad');self.assertIsNone(self.check())
 def test_wrong_metadata(self):(self.box/'workspace.json').write_text('{"workspace":"other"}');self.assertIsNone(self.check())

if __name__=='__main__':unittest.main()
