"""Prepare one explicitly owned inert consumer; never publish or activate."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path
from kg_microbe_fleet import load_fleet_manifest
from plugins.repository_settings import RepositorySettings
from plugins.lock_manager import LockManager
from kg_microbe_governance.freshness_candidates import prepare_batch

SOURCE = Path('/Users/marcin/agent-work/claw/stream-c-freshness-20261110/canonical-source')
SOURCE_SHA = '02554818325cd77ddfb72a45a26b4d1d76d6b136'
LOCKS = Path('/Users/marcin/agent-work/claw/stream-c-onboarding-20261108/workspace/locks')
OWNER = 'stream-c-freshness-20261110'
BRANCH = 'prepare/repository-freshness-v1-stream-c-20261110'
PREFIX = 'workflow/candidates/repository-freshness-v1/'
def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=180, **kwargs).stdout.strip()
def git(root, *args):
    return run(['git','-C',str(root),*args])
def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True);stream.write('\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('key');parser.add_argument('root',type=Path);parser.add_argument('scaffold_sha');parser.add_argument('main_sha');parser.add_argument('seed_sha');a=parser.parse_args()
    fleet=load_fleet_manifest();m=fleet.get(a.key)
    settings=RepositorySettings.from_environment({'repositories':{a.key:{'path':str(a.root)}}},environ={},manifest=fleet)
    target=settings.get_target(a.key);target.open()
    assert git(a.root,'rev-parse','--show-toplevel') == str(a.root)
    assert git(SOURCE,'rev-parse','HEAD') == SOURCE_SHA
    assert not git(SOURCE,'status','--porcelain=v1','--untracked-files=all')
    assert not git(a.root,'status','--porcelain=v1','--untracked-files=all')
    base_api=json.loads(run(['gh','pr','view','1','--repo',m.github,'--json','headRefOid,headRefName,state,isDraft,statusCheckRollup']))
    assert base_api['headRefOid']==a.scaffold_sha and base_api['headRefName']=='stream-c/scaffold' and base_api['state']=='OPEN'
    assert base_api['statusCheckRollup'] and all(c.get('conclusion')=='SUCCESS' for c in base_api['statusCheckRollup'])
    assert json.loads(run(['gh','api','repos/'+m.github+'/commits/main']))['sha']==a.main_sha
    for branch,expected in [('main',a.main_sha),('stream-c/scaffold',a.scaffold_sha),('stream-c/seed',a.seed_sha)]:
        assert git(a.root,'rev-parse','refs/heads/'+branch)==expected
        assert git(a.root,'ls-remote','origin','refs/heads/'+branch).split()[0]==expected
    area=a.root.parent/'freshness-20261110';area.mkdir(exist_ok=False);evidence=area/'evidence';evidence.mkdir();wt=area/'worktree'
    env=dict(os.environ);env[m.environment_variable]=str(a.root)
    config=run(['uv','run','--no-sync','openclaw-cli','config','validate'],cwd=SOURCE,env=env)
    (evidence/'config-validation.txt').write_text(config+'\n')
    before={'at':datetime.now(timezone.utc).isoformat(),'key':a.key,'github':m.github,'main':a.main_sha,'scaffold':a.scaffold_sha,'seed':a.seed_sha,'scaffold_pr':base_api,'scaffold_tree':git(a.root,'rev-parse',a.scaffold_sha+'^{tree}'),'seed_tree':git(a.root,'rev-parse',a.seed_sha+'^{tree}'),'worktrees':git(a.root,'worktree','list','--porcelain'),'refs':git(a.root,'for-each-ref','--format=%(refname) %(objectname)','refs/heads/'),'origin_urls':git(a.root,'remote','-v')}
    save(evidence/'before.json',before)
    with LockManager({'locks_dir':str(LOCKS),'my_id':OWNER}).lock(a.key,'freshness_candidate_worktree',timeout=600):
        git(a.root,'fetch','origin','refs/heads/main:refs/remotes/origin/main','refs/heads/stream-c/scaffold:refs/remotes/origin/stream-c/scaffold')
        assert git(a.root,'rev-parse','origin/main')==a.main_sha
        assert git(a.root,'rev-parse','origin/stream-c/scaffold')==a.scaffold_sha
        git(a.root,'worktree','add','-b',BRANCH,str(wt),a.scaffold_sha)
    root_map={a.key:{'root':str(wt),'expected_head':a.scaffold_sha,'expected_branch':BRANCH,'default_branch':'main','ownership':{'owner_id':OWNER,'repository_key':a.key,'root':str(wt),'head':a.scaffold_sha,'branch':BRANCH}}}
    save(evidence/'root-map.json',root_map)
    args=dict(source_root=SOURCE,source_commit=SOURCE_SHA,root_map=root_map,locks_dir=LOCKS,owner_id=OWNER,keys=[a.key])
    dry=prepare_batch(**args);save(evidence/'dry-run.json',dry)
    assert not (wt/PREFIX).exists()
    applied=prepare_batch(**args,apply=True);save(evidence/'applied.json',applied)
    assert dry['results'][0]['files']==applied['results'][0]['files']
    assert git(wt,'rev-parse','HEAD')==a.scaffold_sha
    assert not git(wt,'diff','--name-only',a.scaffold_sha)
    files=git(wt,'ls-files','--others','--exclude-standard').splitlines()
    expected=sorted(PREFIX+p for p in ['SKILL.md','contract.yaml','proposal.json','schema.yaml'])
    assert sorted(files)==expected
    hashes={p:sha(wt/p) for p in expected}
    assert {p.removeprefix(PREFIX):h for p,h in hashes.items()}==applied['results'][0]['files']
    for branch,expected_sha in [('main',a.main_sha),('stream-c/scaffold',a.scaffold_sha),('stream-c/seed',a.seed_sha)]:
        assert git(a.root,'rev-parse','refs/heads/'+branch)==expected_sha
    save(evidence/'readback.json',{'at':datetime.now(timezone.utc).isoformat(),'source_commit':SOURCE_SHA,'worktree':str(wt),'branch':BRANCH,'base':a.scaffold_sha,'main':a.main_sha,'files':hashes,'prior_tracked_tree_unchanged':True,'scaffold_seed_and_main_refs_unchanged':True,'installed':False,'adopted':False,'source_released':False,'bootstrap_dependency':m.github+'#1 at '+a.scaffold_sha,'unresolved':['Canonical verified release and payload/provenance refresh','Scaffold dependency merge and candidate refresh','Separately authorized consumer merge, boundary adoption and runtime integration']})
    print(json.dumps({'worktree':str(wt),'evidence':str(evidence),'files':hashes},indent=2))
if __name__=='__main__': main()
