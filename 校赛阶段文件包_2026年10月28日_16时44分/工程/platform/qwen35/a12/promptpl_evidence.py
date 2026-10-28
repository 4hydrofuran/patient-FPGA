"""Facts-only prompt/private-protocol integration evidence; PC only."""
import copy
from pathlib import Path
import shutil
from modelpl_evidence import ROOT,read,save,sha,pin
from request_journal_verified import digest

PARENT=ROOT/'evidence/model_pl_A/20261026-short-prompt-v1'
MODE=ROOT/'evidence/model_pl_A/20261026-pl-mode-v1'
COHORT=PARENT/'facts-only-02'
OUT=ROOT/'evidence/model_pl_A/20261026-prompt-private-v1'
WORK=Path('/home/member-a/kv260-build/a12-prompt-private-20261026-v1')
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')

def prepare():
    OUT.mkdir();WORK.mkdir();parent=read(PARENT/'FINAL_REVIEW.json');baseline=parent['source']+parent['evidence']
    for row in baseline:assert sha(ROOT/row['path'])==row['sha256']
    save(OUT/'BASELINE.json',dict(files=baseline+[pin(PARENT/'FINAL_REVIEW.json'),pin(PARENT/'TERMINAL_VERIFICATION.json')],
        previous_turn_classification='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
    cohort=read(COHORT/'TOKENIZED_WORKLOADS.json');quality=read(COHORT/'RESULT.json');assert quality['quality_rejections']==[] and quality['prefix_tokens']==34
    choices=read(COHORT/'PREFIX_CHOICES.json')['candidates'];prefix=next(a for a in choices if len(a)==34)
    old=read(MODE/'BUILD-v2.json');groups=OUT/'cohorts';groups.mkdir();builds=[]
    for row in cohort['real_inputs']:
        folder=groups/row['id'];folder.mkdir();r0=copy.deepcopy(row);r0.update(id='app_R0',cache_policy='R0')
        warm=dict(id='warm_prefix',op='cache_create',tokens=prefix,max_tokens=1,cache_id='short-neutral',cache_policy='R0',confirmed_prefix=True,
            prefill_chunk=256,logits_mode='final',profile=False,diagnostic_report=False)
        hit=copy.deepcopy(row);hit.update(id='app_hit',cache_policy='TT10_REQUIRE_HIT',cache_id='short-neutral')
        requests=[r0,warm,hit];save(folder/'requests.json',requests)
        cfg=read(COHORT/'prefix-config-PC.json');cfg['identity']['input_workload_sha256']=digest(requests)
        save(folder/'prefix-template.json',cfg)
        refs=[COHORT/'native-PC'/(row['id']+'-'+mode)/'result.json' for mode in ('R0','hit')]
        refs.append(COHORT/'native-PC/boundary-warm-34.json')
        build=copy.deepcopy(old);build.update(workspace=str(WORK),prompt_cohort_id=row['id'],prefix_tokens=len(prefix),
            requests_path=str(folder/'requests.json'),requests_sha256=sha(folder/'requests.json'),
            prompt_prefix_template=str(folder/'prefix-template.json'),prompt_prefix_sha256=sha(folder/'prefix-template.json'),
            accepted_prompt_workloads=str(COHORT/'TOKENIZED_WORKLOADS.json'),accepted_prompt_workloads_sha256=sha(COHORT/'TOKENIZED_WORKLOADS.json'),
            prompt_reference_artifacts=[dict(path=str(p),sha256=sha(p)) for p in refs],
            Board_deployed=False,production_enabled=False,BOARD='NOT_TESTED')
        save(folder/'BUILD.json',build)
        worst=72*sum((len(q['tokens'])-(len(prefix) if q['id']=='app_hit' else 0)+7)//8+(q['max_tokens']-1 if q['op']!='cache_create' else 0) for q in requests)
        assert worst<=5000
        builds.append(dict(id=row['id'],build_path=str(folder/'BUILD.json'),sha256=sha(folder/'BUILD.json'),worst_authorized_calls=worst))
    assert len(builds)==25;save(OUT/'COHORTS.json',dict(status='PREPARED_25_NEW_IDENTITIES_PRIVATE_PC_ONLY',cohorts=builds,
        actual_native_recompiled=False,public_ABI_changed=False,BOARD='NOT_TESTED',production_enabled=False))
    print('PREPARED_25_NEW_IDENTITIES_PRIVATE_PC_ONLY')
if __name__=='__main__':prepare()
