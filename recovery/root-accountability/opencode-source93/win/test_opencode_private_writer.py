import unittest,pathlib,uuid,json,unittest.mock as mock,os
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import opencode_private_writer as writer
HERE=pathlib.Path(__file__).resolve().parent
class CompactWriterTests(unittest.TestCase):
 def test_exact_writer_delta(self):
  old=(HERE.parents[1]/'api-adoption5/private_writer.py').read_text()
  self.assertEqual((HERE/'opencode_private_writer.py').read_text(),old.replace("+'.pending-'+uuid.uuid4().hex","+'.p-'+uuid.uuid4().hex"))
 def test_birth_path_budgets(self):
  base='C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap';here=base+'/operational-runtime1/opencode-operating-candidate12';k='a'*64
  paths=[here+'/guardian-private/'+p+k+'.private.json' for p in ('preserving-','factory-','completed-')]+[here+'/'+p+k+'.private.json' for p in ('opencode-holding-','opencode-predecessor-')]+[base+'/runtime/api-root/preserving-'+k+'/'+p for p in ('native-startup-'+str(uuid.uuid4())+'.private.json','opencode-controller.private.json','opencode-guardian-checkpoint.private.json','root-runtime.json','opencode-keeper.private.json','ra-'+('a'*43)+'.json')]
  for p in paths:self.assertLessEqual(len(p+'.p-'+'a'*32),259,p)
  self.assertGreater(len(paths[0]+'.pending-'+'a'*32),259)
 def test_actual_long_atomic_write(self):
  directory=HERE/'guardian-private';writer.ensure_private_directory(directory);p=directory/('preserving-'+'f'*64+'.private.json')
  value={'v':1,'fixture':'own-source-only-no-authority'};writer.save(p,value);self.assertEqual(json.loads(p.read_bytes()),value)
  self.assertFalse(list(directory.glob(p.name+'.p-*')));self.assertEqual(len(str(p)+'.p-'+'a'*32),259)
 def test_full_uuid_exclusive_collision_preserves_target(self):
  directory=HERE/'guardian-private';writer.ensure_private_directory(directory);p=directory/'collision.private.json';writer.save(p,{'original':True});fixed=uuid.UUID('12345678-1234-5678-1234-567812345678');temp=p.with_name(p.name+'.p-'+fixed.hex);temp.write_text('occupied')
  try:
   with mock.patch.object(writer.uuid,'uuid4',return_value=fixed):
    with self.assertRaises(FileExistsError):writer.save(p,{'changed':True})
   self.assertEqual(json.loads(p.read_bytes()),{'original':True});self.assertEqual(temp.read_text(),'occupied')
  finally:temp.unlink()
 def test_fsync_failure_preserves_old_target(self):
  directory=HERE/'guardian-private';writer.ensure_private_directory(directory);p=directory/'fsync.private.json';writer.save(p,{'old':True})
  with mock.patch.object(writer.os,'fsync',side_effect=OSError('fixture-fsync')):
   with self.assertRaises(OSError):writer.save(p,{'new':True})
  self.assertEqual(json.loads(p.read_bytes()),{'old':True})

 def test_reversible_full_digest_archive_name_and_rejection(self):
  import base64
  from opencode_shell_runtime import reply_archive_name
  pin='0123456789abcdef'*4;name=reply_archive_name(pin)
  self.assertEqual(base64.urlsafe_b64decode(name[3:-5]+'=').hex(),pin)
  self.assertEqual(len(name),51)
  for bad in ('a'*63,'A'*64,'../'+pin,True):
   with self.assertRaises(RuntimeError):reply_archive_name(bad)
 def test_actual_archive_write_read_preserves_full_digest(self):
  from opencode_shell_runtime import reply_archive_name
  directory=HERE/('fixture-'+('a'*32));writer.ensure_private_directory(directory)
  pin='0123456789abcdef'*4;p=directory/reply_archive_name(pin);value={'full_digest':pin,'authority_effect':False}
  writer.save(p,value);self.assertEqual(json.loads(p.read_bytes()),value)
  self.assertLessEqual(len(str(p)+'.p-'+('a'*32)),259)

if __name__=='__main__':unittest.main()
