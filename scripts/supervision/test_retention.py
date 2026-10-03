import gzip,hashlib,json,pathlib,tempfile,unittest
from unittest.mock import patch
from retention import archive_verified,archive_operational,read_archived,storage_guard,StorageFull
from service import recorded_send

class PreserveEvidence(unittest.TestCase):
 def test_archive_roundtrip_manifest(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'events.jsonl';data=b'{"kind":"event"}\n'*100
   source.write_bytes(data);record=archive_verified(source,spool)
   self.assertFalse(source.exists())
   packed=(spool/record['archive']).read_bytes()
   self.assertEqual(gzip.decompress(packed),data)
   self.assertEqual(record['sha256'],hashlib.sha256(data).hexdigest())
   manifest=json.loads((spool/'archives/manifest.jsonl').read_text())
   self.assertEqual(manifest['archive'],record['archive'])
 def test_never_overwrite_archive(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'events.jsonl'
   source.write_bytes(b'old');one=archive_verified(source,spool)
   source.write_bytes(b'new');two=archive_verified(source,spool)
   self.assertNotEqual(one['archive'],two['archive'])
   self.assertEqual(gzip.decompress((spool/one['archive']).read_bytes()),b'old')
 def test_protected_pending_evidence(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'receipt-pending.json';source.write_text('{}')
   self.assertEqual(archive_operational(spool,{'pending'},keep=0),0)
   self.assertTrue(source.exists())
 def test_hard_guard_preserves_source(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'events.jsonl';source.write_bytes(b'proof')
   with self.assertRaises(StorageFull):archive_verified(source,spool,hard=1)
   self.assertEqual(source.read_bytes(),b'proof')
   self.assertEqual(storage_guard(spool,soft=1,hard=2)['state'],'paused-hard-limit')
 def test_archived_receipt_reusable(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'receipt-key.json';source.write_text('{"id":"existing-envelope"}')
   archive_verified(source,spool)
   self.assertEqual(read_archived(spool,source.name)['id'],'existing-envelope')
 def test_tampered_archive_refused(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'receipt-key.json';source.write_text('{"id":"existing"}')
   record=archive_verified(source,spool);(spool/record['archive']).write_bytes(gzip.compress(b'{"id":"forged"}'))
   with self.assertRaises(RuntimeError):read_archived(spool,source.name)
 def test_changed_original_not_removed(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'events.jsonl';source.write_bytes(b'old evidence')
   compress=gzip.compress
   def concurrent_append(data,mtime):
    source.write_bytes(b'old evidence plus concurrent event')
    return compress(data,mtime=mtime)
   with patch('retention.gzip.compress',side_effect=concurrent_append):record=archive_verified(source,spool)
   self.assertEqual(source.read_bytes(),b'old evidence plus concurrent event')
   self.assertEqual(gzip.decompress((spool/record['archive']).read_bytes()),b'old evidence')
 def test_archived_send_receipt_never_resends(self):
  with tempfile.TemporaryDirectory() as folder:
   spool=pathlib.Path(folder);source=spool/'receipt-key.json';source.write_text('{"id":"already-recorded"}')
   archive_verified(source,spool)
   def forbidden_send(args):raise AssertionError('native send must not run')
   result=recorded_send('binary','peer','key','body',spool,'sender',False,forbidden_send)
   self.assertEqual(result['id'],'already-recorded')
if __name__=='__main__':unittest.main()
