# Run inside a git repo prepared by a01_make_branches.py. Computes pairwise and sequential trial merges
# of agent0..agent9 with `git merge-tree --write-tree` (git >= 2.38): no checkout, no worktree.
import subprocess,time,itertools,json
def mt(a,b):
    r=subprocess.run(['git','merge-tree','--write-tree','--name-only',a,b],capture_output=True,text=True)
    return r.returncode, r.stdout
heads=[f'agent{i}' for i in range(10)]
t=time.time(); res={}
for a,b in itertools.combinations(heads,2):
    rc,out=mt(a,b); res[f'{a}+{b}']=rc
pair=time.time()-t
conf=[k for k,v in res.items() if v==1]
t=time.time(); cur='main'; landed=[]; rejected=[]
for h in heads:
    rc,out=mt(cur,h)
    if rc==0:
        tree=out.split('\n')[0]
        cur=subprocess.run(['git','-c','user.email=s@x','-c','user.name=s','commit-tree',tree,'-p',cur,'-p',h,'-m','trial'],capture_output=True,text=True).stdout.strip()
        landed.append(h)
    else: rejected.append(h)
seq=time.time()-t
print(json.dumps({'pairs':len(res),'pairwise_seconds':round(pair,2),'conflicting_pairs':conf,'sequential_seconds':round(seq,2),'landed':landed,'rejected':rejected},indent=1))
