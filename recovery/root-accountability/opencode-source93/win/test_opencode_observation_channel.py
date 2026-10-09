import copy,unittest
from opencode_observation_channel import ObservationChannel,OP,sha
class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.owner={'project':'owned','role':'root','actor':'native-owned','generation':'win32:123:456','epoch':12}
        self.native={'id':'native-owned','tag':'fixed-root'}
        self.context={'owner_ref':sha(list(self.owner.values())),'profile_sha256':'a'*64,'kernel_ref':'fixed-kernel','session_id':'ses_owned','revision':1}
        self.kernel={'native_actor':self.native,'owner':self.owner,'profile_sha256':'a'*64,'kernel_ref':'fixed-kernel','session_id':'ses_owned',
            'job':{'queried':True,'active_processes':4},'processes':[{'pid':p,'creation_filetime':1000+p,'session_id':2,'state':'alive'} for p in range(1,5)]}
        self.guards=[];self.channel=ObservationChannel(self.native,self.owner,'b'*64,lambda:copy.deepcopy(self.context),
            lambda c:[{'info':{'sessionID':'ses_owned'}}],lambda:copy.deepcopy(self.kernel),lambda c:self.guards.append(c),clock=lambda:100,
            batch_reader=lambda:{'revision':self.context['revision'],'context':copy.deepcopy(self.context),'helper_contexts':[copy.deepcopy(self.context)]})
        self.command={'owner':self.owner,'operation':OP,'payload':{},'key':'server-selected-key'}
    def test_one_current_source_projection(self):
        result=self.channel.execute(self.command);self.assertEqual(result['state'],'completed');self.assertEqual(len(self.guards),2)
        e=result['evidence'];self.assertEqual(e['kernel_before'],e['kernel_after']);self.assertFalse(e['authority_effect'])
    def test_caller_cannot_select_proof_or_owner(self):
        for command in (dict(self.command,payload={'context':self.context}),dict(self.command,owner=dict(self.owner,epoch=11)),dict(self.command,operation='root-kill')):
            with self.assertRaises(RuntimeError):self.channel.execute(command)
        self.assertEqual(self.guards,[])
    def test_reused_kernel_unknown_job_or_wrong_session(self):
        for change in ('job','process','session'):
            saved=copy.deepcopy(self.kernel)
            if change=='job':self.kernel['job']['queried']=False
            elif change=='process':self.kernel['processes'][0]['state']='unknown'
            else:self.kernel['processes'][0]['session_id']=1
            with self.assertRaises(RuntimeError):self.channel.execute(self.command)
            self.kernel=saved
    def test_revision_change_during_read_denied(self):
        def history(c):self.context['revision']+=1;return []
        self.channel.history_reader=history
        with self.assertRaises(RuntimeError):self.channel.execute(self.command)
if __name__=='__main__':unittest.main()
