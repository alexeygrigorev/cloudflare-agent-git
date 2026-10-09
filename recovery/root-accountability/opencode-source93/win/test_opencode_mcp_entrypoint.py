import unittest
from unittest.mock import patch
import opencode_mcp_entrypoint as module

class EntryTests(unittest.TestCase):
    def test_native_prewarm_lists_fixed_tools_without_profile_or_authority(self):
        tools=module.LazyTools('preserving-'+'a'*64,'b'*64)
        with patch.object(module,'selected_binding',side_effect=AssertionError('binding read forbidden')):
            protocol=module.FixedMCPProtocol(tools)
            protocol.handle({'jsonrpc':'2.0','id':1,'method':'initialize'})
            listed=protocol.handle({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
            self.assertEqual(len(listed['result']['tools']),5)
            self.assertIsNone(tools.runtime)
    def test_missing_factory_binding_never_uses_predecessor(self):
        with patch.object(module,'load_private',side_effect=RuntimeError('absent')):
            with self.assertRaises(RuntimeError):module.selected_binding('preserving-'+'a'*64,'b'*64)
    def test_selected_profile_pin_is_from_fixed_private_factory_record(self):
        name='preserving-'+'a'*64;directory=module.LEAVES/name
        value={'v':1,'state_dir':str(directory),'source_manifest_sha256':'b'*64,'profile_sha256':'c'*64}
        with patch.object(module,'load_private',return_value=value):
            self.assertEqual(module.selected_binding(name,'b'*64),(directory,'c'*64))
            value['source_manifest_sha256']='d'*64
            with self.assertRaises(RuntimeError):module.selected_binding(name,'b'*64)
    def test_model_path_or_extra_credential_cannot_select_constructor(self):
        with patch.object(module,'load_private',side_effect=AssertionError('read forbidden')):
            with self.assertRaises(RuntimeError):module.selected_binding('../old-root','b'*64)

if __name__=='__main__':unittest.main()
