"""Isolated facts-only prompt experiment; actual CPU model, original checker.

Question interpretation stays in the original planner/Session. The new prompt
does not repeat that untrusted question after the trusted facts were selected.
Never changes the default application, original probe, model or backend.
"""
import argparse
import ast
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import textwrap
from plmode_evidence import ROOT,read,save,sha,pin
import short_prompt_offline as prior
from resource_probe_policy import require

OUT=ROOT/'evidence/model_pl_A/20261026-short-prompt-v1'
PARENT=ROOT/'evidence/model_pl_A/20261026-pl-mode-v1'
SYSTEM='你是模拟病人。请逐字复制用户提供的事实句，必须保留每个字及句号，不要解释。'
USER_PREFIX='事实句：\n'

def streamed_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def prompt_source(original):
    tree=ast.parse(original);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prompt_messages')
    replacement='''def prompt_messages(p, question):
    if p.route != 'answer' or not p.facts:
        raise ValueError('facts-only generation requires an original answer plan')
    system = SYSTEM_LITERAL
    payload = PREFIX_LITERAL + '\\n'.join(forms(f)[0] + '。' for f in p.facts)
    return [{'role':'system','content':system},{'role':'user','content':payload}]
'''.replace('SYSTEM_LITERAL',repr(SYSTEM)).replace('PREFIX_LITERAL',repr(USER_PREFIX))
    lines=original.splitlines(True);candidate=''.join(lines[:node.lineno-1])+replacement+''.join(lines[node.end_lineno:])
    def protected(text):return [ast.dump(n,include_attributes=False) for n in ast.parse(text).body
        if not(isinstance(n,ast.FunctionDef) and n.name=='prompt_messages')]
    require(protected(candidate)==protected(original),'non-prompt application code changed')
    return candidate

def prepare():
    require(os.name=='posix' and os.uname().machine=='x86_64','PC-only prompt preparation')
    OUT.mkdir();baseline=read(PARENT/'FINAL_REVIEW.json');files=baseline['source']+baseline['evidence']
    for row in files:require(sha(ROOT/row['path'])==row['sha256'],'immediate parent evidence changed')
    save(OUT/'BASELINE.json',dict(files=files+[pin(PARENT/'FINAL_REVIEW.json'),pin(PARENT/'TERMINAL_VERIFICATION.json')],
        previous_turn_classification='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in ('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md'):
        shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
    folder=OUT/'facts-only-01';folder.mkdir();app=folder/'application';package=app/'system_qwen35/app';package.mkdir(parents=True)
    shutil.copyfile(ROOT/'system_qwen35/__init__.py',app/'system_qwen35/__init__.py')
    for name in ('__init__.py','domain.py','planning.py','checking.py','session.py','scoring.py'):
        shutil.copyfile(ROOT/'system_qwen35/app'/name,package/name)
    original=(package/'checking.py').read_text(encoding='utf-8');(package/'checking.py').write_text(prompt_source(original),encoding='utf-8')
    cases=app/'system_qwen35/cases';cases.mkdir()
    for name in ('schema.json','SYN_CP_01.json','SYN_CP_02.json','SYN_CP_03.json'):
        source=ROOT/'system_qwen35/cases'/name
        require(name=='schema.json' or read(source).get('synthetic') is True,'only explicit synthetic cases allowed')
        shutil.copyfile(source,cases/name)
    template=ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja';shutil.copyfile(template,folder/'chat_template.jinja')
    sys.path.insert(0,str(app))
    from system_qwen35.app.domain import load_case,Transcript
    from system_qwen35.app.planning import plan
    from system_qwen35.app.checking import prompt_messages,check
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    env=ImmutableSandboxedEnvironment();render=env.from_string(template.read_text(encoding='utf-8'));rows=[];neutral=None
    data=read(prior.FROZEN/'WORKLOADS.json')
    for source in data['real_inputs']:
        item=source['application'];case=load_case(item['case_id'])
        p=plan(case,Transcript.parse(dict(request_id=source['id'],text=item['question'],source='typed',final=True)),())
        require(p.route=='answer' and case.sha256==item['case_sha256'] and prior.canonical_sha(p.to_dict())==prior.canonical_sha(item['plan']),'frozen question/case/plan changed')
        messages=prompt_messages(p,item['question']);payload=messages[1]['content'];require(messages[0]['content']==SYSTEM and payload.startswith(USER_PREFIX),'new prompt policy differs')
        # Check the supplied material with the original checker before generation;
        # this is a fixture gate, never a replacement for checking model output.
        require(check(p,payload[len(USER_PREFIX):])['status']=='pass','input relation surfaces fail original checker')
        prompt=render.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
        offset=prompt.index(USER_PREFIX)+len(USER_PREFIX);prefix=prompt[:offset]
        require(neutral is None or prefix==neutral,'facts-only neutral prefix varies');neutral=prefix
        row=copy.deepcopy(source);row.pop('tokens',None);row.pop('prefix_audit',None)
        row.update(prompt=prompt,max_tokens=24,state_fingerprint=True,diagnostic_report=False,profile=False,logits_mode='final')
        row['application'].update(plan=p.to_dict(),messages=messages);rows.append(row)
    require(len(rows)==25 and len(data['policy_inputs'])==7,'all fixed inputs required')
    save(folder/'WORKLOADS.json',dict(schema='SHORT_PROMPT_PC_INPUTS_V1',real_inputs=rows,policy_inputs=data['policy_inputs'],neutral_text=neutral,
        variant='facts_only_trusted_plan',numerical_state_fingerprint='PC_ONLY_NO_RAW_STATE_FILE',output_limit=24,BOARD='NOT_TESTED',board_package=False))
    expected=read(prior.PROBE/'bundle-v2/control/prefix-config.json')['identity']['model_sha256'];require(streamed_sha(prior.MODEL)==expected,'model GGUF changed')
    pins=[dict(path=p.relative_to(folder).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(app.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    save(folder/'PREPARED.json',dict(status='ISOLATED_FACTS_ONLY_PROMPT_CPU_CANDIDATE',files=pins,
        workload_sha256=sha(folder/'WORKLOADS.json'),template_sha256=sha(folder/'chat_template.jinja'),parent_workload_sha256=sha(prior.FROZEN/'WORKLOADS.json'),
        protected_probe_zip_sha256=sha(prior.PROBE/'bundle-v2.zip'),default_checking_sha256=sha(ROOT/'system_qwen35/app/checking.py'),
        old_runner_sha256=sha(ROOT/'platform/qwen35/a12/short_prompt_offline.py'),model_sha256=expected,
        question_omitted_from_generation=True,question_retained_in_original_routing_and_request_identity=True,
        checker_and_fact_values_unchanged=True,model_quality='NOT_TESTED',BOARD='NOT_TESTED'))
    save(OUT/'PLAN.json',dict(status='ISOLATED_PC_EXPERIMENT_NOT_DEFAULT',rationale='Existing failures include question echo, relation paraphrase, omitted numerical scale and combined clauses. Keep original planner and deliver only its trusted approved fact surfaces to the model.',
        original_failures=['DEV-002','DEV-005','DEV-011','DEV-012','DEV-014','V02','V07','V08'],fixed_model_inputs=25,fixed_policy_inputs=7,
        output_limit=24,checker_changed=False,model_decoding='UNCHANGED_GREEDY_UNCONSTRAINED',template_fallback_counts_as_model_success=False,
        prefix_policy='NEW_ACTUAL_TOKEN_BOUNDARY_AND_IDENTITY_REQUIRED_NO_OLD_SNAPSHOT_REUSE',heavy_diagnostic_files=0,
        protected_default_sources=[pin(ROOT/'system_qwen35/app'/name) for name in ('checking.py','planning.py','session.py','domain.py')],
        production_enabled=False,BOARD='NOT_TESTED'))
    print('PREPARED_FACTS_ONLY_CPU_PROMPT 25 7')

def identity_config(parent,binary_sha,libraries,workloads,prefix_choices,template_sha):
    config=prior.identity_config(parent,binary_sha,libraries,workloads,prefix_choices,template_sha)
    config['identity']['prompt_policy_sha256']=prior.canonical_sha(dict(system=SYSTEM,user_prefix=USER_PREFIX,question_interpretation='ORIGINAL_PLANNER_ONLY'))
    return config

def run():
    require(os.name=='posix' and os.uname().machine=='x86_64','PC-only prompt experiment; never a Board fallback')
    folder=OUT/'facts-only-01';require(sha(ROOT/'platform/qwen35/a12/short_prompt_offline.py')==read(folder/'PREPARED.json')['old_runner_sha256'],'frozen runner changed')
    # The actual original run body remains byte-identical. Only its private
    # prompt-policy identity builder differs; no monkeypatch of the old module.
    source=textwrap.dedent(inspect.getsource(prior.run));scope=dict(prior.__dict__,identity_config=identity_config)
    exec(compile(source,str(ROOT/'platform/qwen35/a12/short_prompt_offline.py')+'#facts-only-identity','exec'),scope)
    save(OUT/'RUNNER_REUSE.json',dict(old_runner_sha256=read(folder/'PREPARED.json')['old_runner_sha256'],
        run_body_sha256=hashlib.sha256(source.encode()).hexdigest(),body_changed=False,private_identity_override=True,BOARD='NOT_TESTED'))
    scope['run'](folder)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);a=p.parse_args()
    prepare() if a.action=='prepare' else run()
