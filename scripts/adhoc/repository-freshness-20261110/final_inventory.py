"""Final read-only remote/local inventory; never queues, merges or adopts."""
import json,subprocess,hashlib
from datetime import datetime,timezone
from pathlib import Path
from kg_microbe_fleet import load_fleet_manifest
from plugins.repository_settings import RepositorySettings
ROOT=Path('/Users/marcin/agent-work/claw/stream-c-freshness-20261110')
SOURCE=ROOT/'canonical-source';fleet=load_fleet_manifest()
def run(args):return subprocess.check_output(args,text=True).strip()
def git(root,*args):return run(['git','-C',str(root),*args])
def gh(*args):return json.loads(run(['gh',*args]))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
source=json.loads((ROOT/'evidence/reviewed-source-validation.json').read_text())
result={'at':datetime.now(timezone.utc).isoformat(),'scope':'Cofactor then Assay inert candidate preparation only','canonical_source':source,'consumers':{},'claw_queue_hold_preserved':True,'merges_releases_activation_native_input_or_runtime_changes':False}
for key,num in [('cofactormech',11),('assaymech',5)]:
 m=fleet.get(key);area=Path('/Users/marcin/agent-work')/m.display_name/'freshness-20261110';w=area/'worktree';e=area/'evidence';before=json.loads((e/'before.json').read_text());commit=json.loads((e/'committed-candidate.json').read_text())
 settings=RepositorySettings.from_environment({'repositories':{key:{'path':str(w)}}},environ={},manifest=fleet);settings.get_target(key).open()
 pr=gh('pr','view',str(num),'--repo',m.github,'--json','number,url,headRefOid,headRefName,baseRefName,baseRefOid,state,isDraft,autoMergeRequest,statusCheckRollup,files,body')
 assert pr['headRefOid']==commit['head']==git(w,'rev-parse','HEAD')
 assert pr['baseRefOid']==before['scaffold'] and pr['baseRefName']=='stream-c/scaffold'
 assert pr['state']=='OPEN' and pr['isDraft'] and pr['autoMergeRequest'] is None
 assert len(pr['files'])==4 and all(x['changeType']=='ADDED' and x['path'].startswith('workflow/candidates/repository-freshness-v1/') for x in pr['files'])
 assert len(pr['statusCheckRollup'])==2 and all(c['conclusion']=='SUCCESS' for c in pr['statusCheckRollup'])
 assert not git(w,'status','--porcelain=v1','--untracked-files=all')
 originals={}
 root=w.parents[1]/'repo';seed=w.parents[1]/'seed'
 remote={r.split()[1]:r.split()[0] for r in git(root,'ls-remote','--heads','origin').splitlines()}
 for branch,sha in [('main',before['main']),('stream-c/scaffold',before['scaffold']),('stream-c/seed',before['seed'])]:
  assert git(root,'rev-parse','refs/heads/'+branch)==sha and remote['refs/heads/'+branch]==sha
 for name,path,sha in [('scaffold',root,before['scaffold']),('seed',seed,before['seed'])]:
  assert git(path,'rev-parse','HEAD')==sha and not git(path,'status','--porcelain=v1','--untracked-files=all')
  originals[name]={'head':sha,'clean':True}
 repo=gh('api','repos/'+m.github,'--jq','{full_name,default_branch,visibility}');main=gh('api','repos/'+m.github+'/commits/main','--jq','{sha,tree:.commit.tree.sha}')
 assert main['sha']==before['main'] and main['tree']=='4b825dc642cb6eb9a060e54bf8d69288fbee4904'
 pause=gh('api','repos/'+m.github+'/actions/variables/MERGE_QUEUE_AUTOMATION_PAUSED');assert pause['value']=='true'
 proposal=json.loads((w/'workflow/candidates/repository-freshness-v1/proposal.json').read_text())
 assert all(proposal[x] is False for x in ['installed','adopted']) and proposal['canonical_source']['released'] is False
 assert proposal['canonical_source']['reviewed_source_commit']==source['source_commit']
 review=next((area/'review').glob('independent-pr-review-*.json'));rv=json.loads(review.read_text());assert rv['reviewed_head']==pr['headRefOid'] and rv['confirmed_findings']==[]
 pr['body_sha256']=hashlib.sha256(pr.pop('body').encode()).hexdigest()
 result['consumers'][key]={'pr':pr,'repository':repo,'main':main,'original_worktrees':originals,'queue_paused':True,'source_and_candidate_hashes':proposal['canonical_source'],'fleet_provenance':proposal['fleet_provenance'],'candidate_sha256':{f.name:digest(f) for f in sorted((w/'workflow/candidates/repository-freshness-v1').iterdir())},'review':{'path':str(review),'sha256':digest(review),'verdict':rv['verdict']},'checks':commit['checks'],'base_tree_preserved':before['scaffold_tree'],'installed':False,'adopted':False}
result['canonical_pr_current']=gh('pr','view','1128','--repo','CultureBotAI/culturebotai-claw','--json','state,isDraft,headRefOid,mergedAt,mergeCommit')
result['release_observations']=[]
for endpoint in ['git/ref/tags/repository-freshness-v1.0.0','releases/tags/repository-freshness-v1.0.0']:
 p=subprocess.run(['gh','api','repos/CultureBotAI/culturebotai-claw/'+endpoint],text=True,capture_output=True)
 data=json.loads(p.stdout)
 assert p.returncode==0 or (p.returncode==1 and data.get('status')=='404')
 result['release_observations'].append({'endpoint':endpoint,'exit_code':p.returncode,'response':data,'checked_at':datetime.now(timezone.utc).isoformat()})
assert git(SOURCE,'rev-parse','HEAD')==source['source_commit'] and not git(SOURCE,'status','--porcelain=v1','--untracked-files=all')
result['helpers_sha256']={p.name:digest(p) for p in sorted((ROOT/'helpers').glob('*.py'))}
result['unresolved_steps']=['User scaffold merge decisions and subsequent candidate base refresh/rechecks','Verify actual protected canonical release/publication and refresh candidate payload/provenance against that source','Consumer merge decisions remain outstanding','Active workflow/profile and native/controller integration, assessed boundary adoption and runtime deployment require separate authorization']
result['completed_at']=datetime.now(timezone.utc).isoformat()
path=ROOT/'evidence/final-handoff.json'
with path.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print(str(path))
print(json.dumps({k:{'pr':v['pr']['url'],'head':v['pr']['headRefOid'],'base':v['pr']['baseRefOid'],'checks':[c['conclusion'] for c in v['pr']['statusCheckRollup']],'review':v['review']['verdict']} for k,v in result['consumers'].items()},indent=2))
