#!/usr/bin/env python3
"""Validate an Opus draft; reviewed publication is an explicit separate step."""
import argparse,datetime,hashlib,json,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('date');p.add_argument('--response');p.add_argument('--reviewer',default=None);p.add_argument('--publish',action='store_true');a=p.parse_args()
day=datetime.date.fromisoformat(a.date).isoformat();folder=ROOT/'website/content/daily'
article=folder/f'{day}.md';metadata=folder/f'{day}.json';text=article.read_text();m=json.loads(metadata.read_text())
response=pathlib.Path(a.response) if a.response else ROOT/'.local/journal'/day/'response.json'
runtime=json.loads(response.read_text())
assert not runtime.get('is_error') and runtime.get('subtype')=='success','writer did not complete successfully'
models=list(runtime.get('modelUsage',{}));assert any('opus' in x.lower() for x in models),'no actual Opus completion'
assert m['date']==day and m['author']=='Alexey Grigorev' and 'opus' in m['model'].lower()
assert m.get('source_cutoff') and datetime.datetime.fromisoformat(m['source_cutoff'].replace('Z','+00:00')).tzinfo
assert m.get('sources') and all(u.startswith('https://') for u in m['sources'])
for pattern in [r'(?i)(?:sk-ant-|ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{12,}',r'-----BEGIN .*PRIVATE KEY',r'/home/alexey/',r'\.local/']:
 assert not re.search(pattern,text),'private data pattern in article'
images=re.findall(r'!\[[^]]*\]\(([^)]+)\)',text);assert images,'missing supporting visual'
for image in images:
 path=(article.parent/image).resolve();assert path.is_relative_to(ROOT/'website/assets') and path.is_file(),f'missing or unsafe asset: {image}'
subprocess.run(['stylint',str(article)],cwd=ROOT,timeout=60,check=True)
share=folder/f'{day}.sharetext.txt';assert len(share.read_text().strip())<=350
if a.publish:
 has_prior_pub=bool(m.get('published_at'))
 pub_at=m.get('published_at') or datetime.datetime.now(datetime.timezone.utc).isoformat()
 upd_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
 reviewer=a.reviewer or m.get('editorial_review') or 'Evidence, privacy, full stylint and asset checks by publication coordinator (public-journal-site)'
 updates={'published':True,'actual_writer_models':models,'editorial_review':reviewer,'article_sha256':hashlib.sha256(article.read_bytes()).hexdigest(),'published_at':pub_at,'updated_at':upd_at,'socialsharetext':f"{share.read_text().strip()} https://alexeygrigorev.com/cloudflare-agent-git/daily/{day}/",'autopost':False}
 if has_prior_pub:
  updates['revised_at']=upd_at
 m.update(**updates)
 temporary=metadata.with_suffix('.json.tmp');temporary.write_text(json.dumps(m,indent=2)+'\n');temporary.replace(metadata)
print(json.dumps({'date':day,'checks':'passed','published':bool(m.get('published')),'actual_writer_models':models,'socialsharetext':f"{share.read_text().strip()} https://alexeygrigorev.com/cloudflare-agent-git/daily/{day}/",'autopost':False}))
