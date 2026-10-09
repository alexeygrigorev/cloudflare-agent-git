"""Finite stdio controller assembly; no model/session/factory launch.

The cold factory must supply the source-pinned private dependencies. This
assembly has no fallback to a predecessor, caretaker token or generic loader.
"""
import pathlib,time
from opencode_runtime_profile import validate_profile,ControllerInput
from opencode_controller_store import ControllerStore,JournalLock
from opencode_controller_journal import ControllerJournal
from opencode_fixed_binder import FixedBinder
from opencode_full_startup import FullStartup

class ControllerRuntime:
    def __init__(self,profile,directory,source_sha256,*,private_load,private_save,
                 verify_private,kernel_reader,history_reader,dispatch_read,
                 authority_post,denial_reader,startup_root,snapshot_path,
                 snapshot_sha256,source_guard,native_identity_guard,clock=time.time):
        self.guard=source_guard;self.identity=native_identity_guard
        self.profile=validate_profile(profile,directory,source_sha256)
        self.guard();verify_private(pathlib.Path(directory));self.identity(self.profile)
        self.startup=FullStartup(startup_root)
        self.startup.documents() # fail before any authority RPC if inputs drift
        self.kernel=kernel_reader
        def binding(context):
            self.guard();self.identity(self.profile)
            current=self.kernel()
            return (context.get('owner')==self.profile['owner']
                and context.get('session_id')==self.profile['session_id']
                and context.get('kernel_ref')==current.get('kernel_ref')
                and current.get('owner')==self.profile['owner']
                and current.get('native_actor')==self.profile['native'])
        self.store=ControllerStore(directory,private_load,private_save,verify_private)
        self.journal=ControllerJournal(self.store.read,self.store.save,binding)
        self.journal.lock=JournalLock(self.store)
        # history_reader(selected) is the authenticated base-context reader.
        # It must never call this ControllerInput.current recursively.
        self.input=ControllerInput(self.profile,dispatch_read,self.journal,self.kernel,history_reader,clock)
        self.binder=FixedBinder(self.profile['owner'],self.profile['controller_credential'],
            authority_post,self.input.current,self.journal,pathlib.Path(startup_root),
            pathlib.Path(snapshot_path),snapshot_sha256,denial_reader,clock,startup_bundle=self.startup)
    def run_stdio(self,input_stream,output_stream):
        self.guard();self.identity(self.profile)
        self.binder.run_stdio(input_stream,output_stream)

def main():
    # No arbitrary command-line import/profile path can bypass the factory.
    # Until the separately reviewed native factory constructor is bound, a
    # standalone invocation holds before credentials/model/authority effects.
    raise RuntimeError('fixed reviewed factory runtime constructor not installed')

if __name__=='__main__':main()
