import subprocess, random, os
random.seed(7)
run=lambda *a: subprocess.run(a,check=True,capture_output=True,text=True).stdout
files=[f for f in run('git','ls-files').split('\n') if f.endswith('.ts') and os.path.getsize(f)>3000][:400]
hot='packages/wrangler/src/index.ts' if os.path.exists('packages/wrangler/src/index.ts') else files[0]
plan=[]
for i in range(10):
    run('git','checkout','-q','-B',f'agent{i}','main')
    touched=random.sample(files,5)
    if i%3==0: touched.append(hot)   # agents 0,3,6,9 all touch the hot file
    for f in touched:
        lines=open(f).read().split('\n')
        pos= 10 if f==hot else random.randrange(len(lines))
        lines.insert(pos,f'// agent{i} change')
        open(f,'w').write('\n'.join(lines))
    run('git','add','-A'); run('git','-c','user.email=s@x','-c','user.name=s','commit','-qm',f'agent{i}')
    plan.append(touched)
run('git','checkout','-q','main')
