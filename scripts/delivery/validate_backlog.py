#!/usr/bin/env python3
"""Validate durable delivery attribution without treating legacy status as evidence."""
import argparse,json
from pathlib import Path

def audit(tasks,backlog,registry):
 rows=tasks['tasks'];ids=[t['id'] for t in rows];errors=[];warnings=[]
 if len(ids)!=len(set(ids)):errors.append('Duplicate task IDs')
 if {p['id'] for p in registry.get('projects',[])}!={'agent-branches','agent-dashboard','quota-launcher'}:errors.append('Three project registrations required')
 for source in backlog['human_sources']:
  missing=set(source.get('task_ids',[]))-set(ids)
  if missing:errors.append(source['id']+': missing linked tasks '+','.join(sorted(missing)))
  if not source.get('requirement_summary') or not source.get('disposition'):errors.append(source['id']+': semantic disposition missing')
 for task in rows:
  if not task.get('project_id'):warnings.append({'task':task['id'],'gap':'Legacy project attribution requires owner audit'})
  if task.get('status')=='running' and not task.get('first_action'):warnings.append({'task':task['id'],'gap':'Running label has no explicit first-action receipt'})
  if task.get('status')=='done' and task.get('project_id') and not all(task.get(k) for k in ['accepted_at','tests','reviewer']):errors.append(task['id']+': project completion lacks accepted_at/tests/reviewer')
  if task.get('status') in ['queued','ready','blocked'] and not task.get('next_action'):errors.append(task['id']+': actionable next step missing')
 return {'schema_version':1,'errors':errors,'warnings':warnings,'task_count':len(rows),'source_count':len(backlog['human_sources']),'project_count':len(registry.get('projects',[])),'completion_policy':'Only independently accepted feature evidence can count as delivered; warnings are unknown, not failure or zero.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);args=p.parse_args()
 data=[json.loads((args.root/'coordination'/name).read_text()) for name in ['TASKS.json','DELIVERY-BACKLOG.json','TEAM-REGISTRY.json']]
 result=audit(*data);print(json.dumps(result,indent=2));return bool(result['errors'])
if __name__=='__main__':raise SystemExit(main())
