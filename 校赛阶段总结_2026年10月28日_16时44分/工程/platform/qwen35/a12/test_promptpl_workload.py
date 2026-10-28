"""Finite prompt identities/budgets and before-launch refusal, no native run."""
import copy
import json
from pathlib import Path
import tempfile
from promptpl_evidence import OUT,read,save,sha
from promptpl_workload import PromptProbe
from promptpl_manager import Manager

def refuses(call):
    try:call()
    except (RuntimeError,KeyError,ValueError,FileNotFoundError):return
    raise AssertionError('changed private prompt workload accepted')

def main():
    cohorts=read(OUT/'COHORTS.json')['cohorts'];tests=[]
    for row in cohorts:
        p=PromptProbe(read(row['build_path']));assert len(p.requests)==3 and row['worst_authorized_calls']<=5000
    tests.append('ALL_25_FIXED_COHORTS_UNDER_ORIGINAL_5000_WINDOW_CAP')
    b=read(cohorts[0]['build_path'])
    changed=copy.deepcopy(b);changed['prefix_tokens']=70;refuses(lambda:PromptProbe(changed));tests.append('OLD_PREFIX_LENGTH_REJECTED')
    with tempfile.TemporaryDirectory(prefix='a12-promptpl-policy-') as d:
        root=Path(d)
        for name,modify in [
            ('OUTPUT_LIMIT_8',lambda r:r[0].__setitem__('max_tokens',8)),
            ('OUTPUT_LIMIT_25',lambda r:r[0].__setitem__('max_tokens',25)),
            ('REQUEST_ID_REPLAY_ALIAS',lambda r:r[2].__setitem__('id','app_R0')),
            ('CHANGED_PROMPT',lambda r:r[0].__setitem__('prompt',r[0]['prompt']+'额外事实')),
            ('CHANGED_TOKENS',lambda r:r[0]['tokens'].__setitem__(0,r[0]['tokens'][0]+1)),
            ('WARM_PREFIX_TOKEN_CHANGED',lambda r:r[1]['tokens'].__setitem__(0,r[1]['tokens'][0]+1)),
            ('HIT_OLD_CACHE_SLOT',lambda r:r[2].__setitem__('cache_id','neutral')),
        ]:
            requests=read(b['requests_path']);modify(requests);path=root/(name+'.json');path.write_text(json.dumps(requests,ensure_ascii=False))
            changed=copy.deepcopy(b);changed.update(requests_path=str(path),requests_sha256=sha(path))
            refuses(lambda:PromptProbe(changed));tests.append(name+'_EVEN_WITH_REHASHED_JSON')
        cfg=read(b['prompt_prefix_template']);cfg['identity']['input_workload_sha256']='0'*64;path=root/'prefix.json';path.write_text(json.dumps(cfg))
        changed=copy.deepcopy(b);changed.update(prompt_prefix_template=str(path),prompt_prefix_sha256=sha(path))
        refuses(lambda:PromptProbe(changed));tests.append('PREFIX_WORKLOAD_BINDING_MISMATCH')
        changed=copy.deepcopy(b);changed['prompt_reference_artifacts'][0]['sha256']='0'*64
        refuses(lambda:PromptProbe(changed));tests.append('CHANGED_ACCEPTED_NUMERICAL_REFERENCE')
        changed=copy.deepcopy(b);changed['domain']='A12_PREPARED_BOARD_MODEL_PLM_V1';path=root/'board.json';path.write_text(json.dumps(changed))
        m=Manager.__new__(Manager);m.p=m.page=None
        refuses(lambda:m.__init__(path,root/'must-not-launch'));assert m.p is None and m.page is None and not (root/'must-not-launch').exists()
        tests.append('BOARD_DOMAIN_REFUSED_BEFORE_PAGE_DIRECTORY_OR_POPEN')
    m=Manager.__new__(Manager);m.prefix_tokens=34
    for request in (dict(id='app_hit',tokens=[]),dict(id='app_hit',tokens=[0]*34),dict(id='app_R0',tokens=[0]*129)):
        refuses(lambda:m.new_tokens(request))
    tests.append('NEW_TOKEN_ACCOUNTING_REJECTS_ZERO_NEGATIVE_AND_OVERSIZE')
    save(OUT/'WORKLOAD_POLICY_TEST.json',dict(status='PASS_FIXED_PROMPT_IDENTITIES_AND_DYNAMIC_ACCOUNTING_REFUSALS',tests=tests,count=len(tests),native_processes=0,BOARD='NOT_TESTED'))
    print('PASS_FIXED_PROMPT_IDENTITIES_AND_DYNAMIC_ACCOUNTING_REFUSALS',len(tests))
if __name__=='__main__':main()
