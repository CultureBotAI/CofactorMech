"""Independent persisted-byte checks for a generated inert proposal."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from datetime import datetime, timezone
import yaml
from kg_microbe_workflows import _validator, WorkflowError
from kg_microbe_workflows.freshness_contract import load_adoption

def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args])
def h(raw):return hashlib.sha256(raw).hexdigest()
p=argparse.ArgumentParser();p.add_argument('area',type=Path);a=p.parse_args()
wt=a.area/'worktree';ev=a.area/'evidence';source=Path('/Users/marcin/agent-work/claw/stream-c-freshness-20261110/canonical-source')
before=json.loads((ev/'before.json').read_text());dry=json.loads((ev/'dry-run.json').read_text());rootmap=json.loads((ev/'root-map.json').read_text())
base=before['scaffold'];key=before['key'];candidate=wt/'workflow/candidates/repository-freshness-v1'
proposal=json.loads((candidate/'proposal.json').read_text());ref=proposal['canonical_source']['reviewed_source_commit']
assert ref=='02554818325cd77ddfb72a45a26b4d1d76d6b136'
assert proposal['canonical_source']['released'] is False and proposal['installed'] is False and proposal['adopted'] is False
assert proposal['authority']=='proposal_only' and proposal['state']=='blocked_on_canonical_release'
assert proposal['repository_key']==key and proposal['github_repository']==before['github']
assert proposal['observed_base']['head']==base and proposal['observed_base']['branch']==rootmap[key]['expected_branch']
expected_paths={'contract.yaml':'src/kg_microbe_workflows/templates/repository-freshness-v1.yaml','schema.yaml':'src/kg_microbe_workflows/schema/repository-freshness-v1.yaml','SKILL.md':'src/kg_microbe_skills/canonical/repository-freshness.md'}
for dest,src in expected_paths.items():
 raw=git(source,'show',ref+':'+src)
 assert h(raw)==proposal['canonical_source']['files'][src]
 rendered=raw
 if dest=='SKILL.md':
  rendered=raw.replace(b'{{ display_name }}',before['github'].split('/')[1].encode()).replace(b'{{ github }}',before['github'].encode())
 assert (candidate/dest).read_bytes()==rendered
 assert h(rendered)==dry['results'][0]['files'][dest]
for kind in ['manifest','loader']:
 f=proposal['fleet_provenance'];assert h(git(source,'show',ref+':'+f[kind+'_path']))==f[kind+'_sha256']
contract=yaml.safe_load((candidate/'contract.yaml').read_text())
errors=list(_validator((candidate/'schema.yaml').read_text(),'RepositoryFreshnessContract').iter_errors(contract));assert not errors,errors
rejected=False
try:
 load_adoption(candidate/'proposal.json',expected_sha256=h((candidate/'proposal.json').read_bytes()),repository_key=key,repository_root=wt,workflow_sha256='0'*64,run_id='rejection-probe-only',cycle=1,predecessor_receipt_sha256=None)
except WorkflowError as exc:
 rejected=True;rejection=str(exc)
assert rejected
changed=git(wt,'diff','--name-only',base).decode().splitlines();assert all(p.startswith('workflow/candidates/repository-freshness-v1/') for p in changed)
# This supplements the generator's four preserved fields with every tracked base blob/mode.
entries=git(wt,'ls-tree','-r','-z',base).split(b'\0');checked=0
for entry in filter(None,entries):
 meta,rawpath=entry.split(b'\t',1);mode,kind,oid=meta.decode().split();path=rawpath.decode();target=wt/path
 assert kind=='blob'
 raw=target.readlink().as_posix().encode() if mode=='120000' else target.read_bytes()
 assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid,path
 if mode!='120000':assert bool(target.stat().st_mode&0o111)==(mode=='100755'),path
 checked+=1
assert git(source,'rev-parse','HEAD').decode().strip()==ref
assert not git(source,'status','--porcelain=v1','--untracked-files=all').strip()
result={'at':datetime.now(timezone.utc).isoformat(),'source':ref,'key':key,'base':base,'head':git(wt,'rev-parse','HEAD').decode().strip(),'validated_candidate_files':{p.name:h(p.read_bytes()) for p in sorted(candidate.iterdir())},'all_base_blobs_and_modes_preserved':checked,'contract_schema_valid':True,'proposal_refused_as_adoption':rejection,'released':False,'installed':False,'adopted':False}
name='verified-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'
with (ev/name).open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(result,indent=2))
