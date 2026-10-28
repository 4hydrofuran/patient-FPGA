"""Prepare independent UNBOUND ordinary/web candidates without contacting devices."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from fast_response_profile import digest, pair_budget, validate_profile
from short_prompt_adapter import policy_sha256

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2.zip'
FACTS=ROOT/'evidence/model_pl_A/20261026-short-prompt-v1/facts-only-02'
BASE_SHA='55cb8fd6892c71c4c2989bf375950ae971179195fbc0809f6207fdf0131980e2'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def replace_once(source, before, after):
    if source.count(before)!=1:raise ValueError('pinned source anchor differs: '+before[:100])
    return source.replace(before,after,1)


def manifest(directory):
    return [dict(path=p.relative_to(directory).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
            for p in sorted(directory.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p!=directory/'MANIFEST.json']


def prepare(profile_id, output):
    settings=read(ROOT/'config/qwen35/web.fast-response.json')
    selected=settings['profiles'][profile_id]
    if sha(BASE)!=BASE_SHA:raise ValueError('accepted ordinary source archive differs')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    short=selected['prompt_policy']=='facts-only-02'
    cohort=read(FACTS/'TOKENIZED_WORKLOADS.json')
    prefix=read(FACTS/'prefix-config-PC.json')['allowed_prefixes'][0] if short else None
    with zipfile.ZipFile(BASE) as z:
        original_prefix=json.loads(z.read('control/prefix-config.json'))
        if not short:prefix=original_prefix['allowed_prefixes'][0]
        # Duration carries units/time; the exact selected workload is frozen below.
        row=copy.deepcopy(next(r for r in cohort['real_inputs'] if r['id']=='DEV-004')) if short else json.loads(z.read('control/requests.json'))[0]
        identity=copy.deepcopy(original_prefix['identity'])
        identity.update(threads=selected['threads'],kernel_threads=selected['threads'])
        if short:identity.update(prompt_policy_sha256=policy_sha256(),
            input_workload_sha256=digest(cohort),neutral_prefix_choices_sha256=digest([prefix]))
        profile=dict(schema='A12_FAST_RESPONSE_PROFILE_V1',profile_id=profile_id,
            prompt_policy=selected['prompt_policy'],prefix_tokens=len(prefix),prefix_token_ids=prefix,
            prefix_sha256=digest(prefix),cache_id='short34-t'+str(selected['threads']) if short else 'neutral',
            context_tokens=1024,output_tokens=24,threads=selected['threads'],kernel_threads=selected['threads'],
            warm_request_id='warm_prefix',prefix_identity=identity,authorization_included=False,
            neutral_text=cohort['neutral_text'] if short else row['prompt'].split('"')[0],
            template_sha256=identity['template_sha256'],model_sha256=identity['model_sha256'],
            prefix_snapshot_observed_PC_bytes=21614659,BOARD='NOT_TESTED')
        validate_profile(profile)
        allowed={'id','op','prompt','tokens','application','max_tokens','logits_mode','prefill_chunk','cache_policy'}
        row={k:v for k,v in row.items() if k in allowed}
        row.update(id='app_R0',op='generate',max_tokens=24 if short else 8,logits_mode='final',prefill_chunk=256,cache_policy='R0')
        requests=[row,dict(id='warm_prefix',op='cache_create',tokens=prefix,max_tokens=1,
            confirmed_prefix=True,cache_id=profile['cache_id'],cache_policy='R0',prefill_chunk=256,logits_mode='final'),
            dict(copy.deepcopy(row),id='app_hit',cache_policy='TT10_REQUIRE_HIT',cache_id=profile['cache_id'])]
        worst=pair_budget(requests,len(prefix))
        if worst>5000:raise ValueError('selected pair exceeds separate 5000-call window')
        for kind in ('ordinary','continuous'):
            window=output/kind;bundle=window/'bundle';bundle.mkdir(parents=True)
            z.extractall(bundle)
            for p in HERE.glob('*.py'):
                if p.name!='fast_response_prepare.py':shutil.copyfile(p,window/p.name)
            for name in ('web_managed.py','native_pl.py'):shutil.copyfile(ROOT/'system_qwen35/app'/name,window/name)
            shutil.copytree(HERE/'vendor/web_gateway',window/'web_gateway',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            shutil.copyfile(FACTS/'chat_template.jinja',bundle/'control/chat_template.jinja')
            save(window/'profile.json',profile)
            save(window/'web-config.json',dict(continuous=True,profile='profile.json',
                browser_profile='/home/ubuntu/snap/firefox/common/a12-'+profile_id,
                dependency_paths=['/home/ubuntu/patient-web-demo-20261026/.venv/lib/python3.12/site-packages']))
            save(bundle/'control/requests.json',requests)
            save(bundle/'control/prefix-config.json',dict(schema='TT10_01_CONFIG_V1',max_slots=2,
                max_slot_bytes=67108864,allowed_prefixes=[prefix],identity=identity))
            spec=read(bundle/'control/window-spec.json')
            spec.update(window_id='UNBOUND-'+profile_id+'-'+kind,variant='fast_response_'+kind,
                prefix_tokens=len(prefix),output_token_limit=24,prompt_token_limit=1024,
                calculated_worst_case=worst,**settings[kind],request_limit=3 if kind=='ordinary' else 2000)
            spec.pop('weight_load_limit',None)
            save(bundle/'control/window-spec.json',spec)
            budget=read(bundle/'evidence/RESOURCE_CALL_BUDGET.json')
            budget['profiles'][0].update(max_successful_runs=spec['max_runs'],output_token_limit=24,
                prompt_token_limit=1024,max_session_seconds=spec['max_session_seconds'],request_limit=spec['request_limit'])
            save(bundle/'evidence/RESOURCE_CALL_BUDGET.json',budget)
            policy=bundle/'platform/qwen35/a12/resource_probe_policy.py'
            source=policy.read_text(encoding='utf-8')
            source=replace_once(source,"1, 8), 'output limit changed'","1, 24), 'output limit changed'")
            source=replace_once(source,"len(request['tokens']) <= 128","len(request['tokens']) <= 1024")
            source=source.replace("== 'neutral'",'== '+repr(profile['cache_id']))
            source=replace_once(source,"spec.get('output_token_limit') == 8 and spec.get('prompt_token_limit') == 128",
                                "spec.get('output_token_limit') == 24 and spec.get('prompt_token_limit') == 1024")
            policy.write_text(source,encoding='utf-8')
            helper=bundle/'platform/qwen35/a12/tt10_00_app.py'
            source=helper.read_text(encoding='utf-8')
            source=replace_once(source,'from system_qwen35.app.session import Session','from patient_web.reference.session import Session')
            source=replace_once(source,"Session(item['case_id'], software_test=True)",
                "Session(item['case_id'], software_test=True"+(", prompt_builder=__import__('short_prompt_adapter').prompt_messages" if short else '')+")")
            helper.write_text(source,encoding='utf-8')
            if selected['threads']!=2:
                owner=bundle/'platform/qwen35/a12/cpu01b_window.py'
                source=replace_once(owner.read_text(encoding='utf-8'),
                    "str(model), '2', '1024', 'all', 'TILED', '2', '8'",
                    "str(model), '3', '1024', 'all', 'TILED', '3', '8'")
                owner.write_text(source,encoding='utf-8')
                manager=bundle/'control/resource_probe_manager.py'
                manager.write_text(replace_once(manager.read_text(encoding='utf-8'),"OMP_NUM_THREADS='2'","OMP_NUM_THREADS='3'"),encoding='utf-8')
            for p in (bundle/'platform/qwen35/a12/resource_probe_policy.py',helper):ast.parse(p.read_text(encoding='utf-8'))
            bm=read(bundle/'manifest.json')
            bm['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
            save(bundle/'manifest.json',bm)
    save(output/'COHORT.json',cohort)
    original={r['id']:r for r in read(ROOT/'eval/qwen35/a02/dev/questions-v2.json')}
    save(output/'POLICY_CASES.json',{r['id']:original[r['id']]['case_id'] for r in cohort['policy_inputs']})
    save(output/'LEGACY_PC.json',dict(prefix_tokens=original_prefix['allowed_prefixes'][0],
        binding_sha256=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/ready-PC.json')['prefix_cache']['binding_sha256']))
    save(output/'PC_DEPENDENCIES.json',dict(project_root=str(ROOT),
        model=str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),
        binary='/home/member-a/kv260-build/a12-tt10-01-20261024-v1/pc04/qwen35-a12',
        library_dir=str(Path(read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')['workspace'])/'pc')))
    # A small predetermined board sequence; each entry retains original question/facts.
    order=['DEV-004','DEV-001','DEV-009','DEV-011','DEV-012','V07','V08','DEV-003']
    sequence=[];active_case=None
    for index in order:
        r=next(r for r in cohort['real_inputs'] if r['id']==index);case_id=r['application']['case_id']
        if case_id!=active_case:
            if active_case is not None:sequence.append(dict(action='finish'))
            sequence.append(dict(action='start',case_id=case_id));active_case=case_id
        sequence.append(dict(action='question',id=index,case_id=case_id,question=r['application']['question'],kind='MODEL'))
    for r in cohort['policy_inputs'][:2]:
        case_id=original[r['id']]['case_id']
        if case_id!=active_case:
            sequence.extend([dict(action='finish'),dict(action='start',case_id=case_id)]);active_case=case_id
        sequence.append(dict(action='question',id=r['id'],case_id=case_id,question=r['question'],kind='POLICY_ZERO_MODEL'))
    sequence.extend([dict(action='finish'),dict(action='host_stop')])
    save(output/'BOARD_SEQUENCE.json',dict(steps=sequence,model_questions=8,policy_questions=2,BOARD='NOT_TESTED'))
    from continuous_sessions import question_reserve
    save(output/'BUDGETS.json',dict(ordinary_worst_calls=worst,ordinary_limit=5000,
        question_reserve=question_reserve(1024,len(prefix),24),
        formula='72 * (ceil((context-prefix)/8) + output-1)',context_tokens=1024,
        prefix_tokens=len(prefix),output_tokens=24,continuous_limit=60000,
        selected_request_id='app_R0',selected_question=row['application'].get('question'),authorization_included=False))
    save(output/'SOURCE_PINS.json',dict(baseline_archive_sha256=BASE_SHA,
        frontend_commit='40498c2388b6293d68f38907c71ffd8933a5803e',
        candidate='facts-only-02' if short else 'legacy',model_copied=False,
        native_binary_sha256=identity['executable_sha256'],BOARD='NOT_TESTED'))
    (output/'START_HERE.md').write_text(start_here(profile_id,worst),encoding='utf-8')
    save(output/'MANIFEST.json',dict(schema='A12_FAST_RESPONSE_PACKAGE_V1',status='UNBOUND',
        profile_id=profile_id,authorization_included=False,files=manifest(output)))
    return dict(output=str(output),profile_id=profile_id,status='UNBOUND',ordinary_worst_calls=worst,
                board_contacted=False,files=len(read(output/'MANIFEST.json')['files']))


def start_here(profile_id,worst):
    return f'''# {profile_id}: UNBOUND deployment candidate

Prepared offline. BOARD is NOT_TESTED; no replayable compute authority is included.
Model weights, sidecar, tensor map, default platform and machine libraries remain external.
The native binary is the accepted 115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab.
The frozen gateway is derived from 40498c2388b6293d68f38907c71ffd8933a5803e.

From this directory, offline package/dependency check (never contacts devices):

```sh
python3 ordinary/fast_response_verify.py --domain PC --bundle . --suite package
```

Use a fresh extracted directory and fresh independent Owner ID for each BOARD window.
Only after separate BOARD execution authorization and accepted irq2 startup/handover:

```sh
sudo python3 ordinary/fast_response_verify.py --domain BOARD --bundle . --suite ordinary --execute-board --window-id a12-{profile_id}-pair-001
sudo python3 continuous/fast_response_verify.py --domain BOARD --bundle . --suite web --execute-board --window-id a12-{profile_id}-web-001
```

Run the second command after the first Owner has restored and independently released.
The ordinary pair has exactly 3 frozen R0/warm/hit requests; worst {worst}/5000 calls, 1800 seconds.
Continuous mode has 60000 calls/14400 seconds, context 1024/output 24 and one worker.
The prefix must warm successfully before accepting input. The model must hit the bound cache.
Stop the whole continuous service from another trusted local shell:

```sh
sudo touch continuous/stop-request.json
```

Wait for in-flight completion, worker exit, original Owner restore/release receipts.
The original result-only HTTP service can remain for 30 minutes after hardware release.
Finish consultation freezes its score; it does not stop the model.

Rollback: stop and release the candidate, then use a fresh legacy70-threads2 package/directory and new Owner ID.
Never swap profiles inside a running window or reset a consumed run-v1 directory.
The package consumes its own web_gateway, adapters, prefix config and profile. Existing BOARD Python
dependencies may be reused from /home/ubuntu/patient-web-demo-20261026/.venv/lib/python3.12/site-packages.
No dependency installation, kernel change, login, reboot or flash action is performed by --help or offline checks.

Actual CPU generation (explicit external PC assets; no download):

```sh
python3 continuous/fast_response_verify.py --domain PC --bundle . --suite model --output /tmp/a12-pc-new-attempt
```

PC_DEPENDENCIES.json records local defaults; --model, --pc-binary and --pc-library-dir override them.
The 25-case model suite applies to the short profile. Legacy mode is covered by compatibility tests.
Browser timing uses performance.now and checked-answer DOM observations after two animation frames.
Backend timing uses Python monotonic_ns with nested stages. Join by session/request ID;
never subtract timestamps from these different clocks or count fixture/unchecked text as model latency.
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',choices=('short34-threads2','short34-threads3','legacy70-threads2'),default='short34-threads2')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.profile,a.output),indent=2))


if __name__=='__main__':main()
