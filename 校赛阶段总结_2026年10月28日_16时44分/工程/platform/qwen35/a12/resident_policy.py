"""Pinned application policy and literal original planner/checker, no model I/O."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import struct
import sys
import types
import hashlib
import argparse
from resident_evidence import ROOT,OUT,read,save,sha
from request_journal_verified import FrozenProbe,digest
from plm_journal import need

IDS=('warm_prefix',)+tuple('model_'+str(i) for i in range(1,9))
MAX_INPUTS=24
MAX_REJECTIONS=8

def prepare(revision=1):
    old=ROOT/'evidence/model_pl_A/20261026-short-prompt-v1/facts-only-02'
    app=OUT/'resident-app'
    if revision==1:shutil.copytree(old/'application/system_qwen35',app,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    template=OUT/'chat_template.jinja'
    if revision==1:shutil.copyfile(old/'chat_template.jinja',template)
    prefix=read(old/'PREFIX_CHOICES.json');tokens=next(q for q in prefix['candidates'] if len(q)==34)
    files=[dict(path=p.relative_to(app).as_posix(),sha256=sha(p)) for p in sorted(app.rglob('*')) if p.is_file()]
    policy=dict(schema='A12_BOUNDED_RESIDENT_POLICY_V1',max_model_requests=8,max_inputs=MAX_INPUTS,max_rejections=MAX_REJECTIONS,
        native_request_ids=list(IDS),total_calls=5000,max_loads=72,output_tokens=24,prefix_tokens=tokens,
        neutral_text=read(old/'WORKLOADS.json')['neutral_text'],chat_template_sha256=sha(template),files=files,
        case_ids=['SYN_CP_01','SYN_CP_02','SYN_CP_03'],case_sha256={name:sha(app/'cases'/(name+'.json')) for name in ('SYN_CP_01','SYN_CP_02','SYN_CP_03')},
        max_window_seconds=1800,CPU_window_seconds=180,medical_review='PENDING_TEACHER_REVIEW',production_enabled=False,
        input_scope='DYNAMIC_ORIGINAL_PLANNER_OVER_PINNED_SYNTHETIC_CASES_NOT_A_FROZEN_QUESTION_LIST')
    if revision>=2:
        entry=read(old/'native-PC/boundary-warm-34.json')['prefix_cache']['entries'][0]
        policy['PC_neutral_reference']={k:entry[k] for k in ('tokens','position','state_bytes','state_sha256','sequence_sha256','logits_bytes','logits_sha256')}
    if revision>=3:policy['private_control_requests']=9
    suffix='' if revision==1 else '-v'+str(revision);policy_path=OUT/('resident-policy'+suffix+'.json');prefix_path=OUT/('prefix-template'+suffix+'.json')
    save(policy_path,policy)
    cfg=read(old/'prefix-config-PC.json');cfg['allowed_prefixes']=[tokens]
    cfg['identity']['input_workload_sha256']=digest(dict(policy_sha256=sha(policy_path),input_scope=policy['input_scope']))
    cfg['identity']['resident_policy_sha256']=sha(policy_path)
    save(prefix_path,cfg)
    b=read(OUT/('BUILD-v2.json' if revision>=3 else 'BUILD-v1.json'));b.update(resident_policy=str(policy_path),resident_policy_sha256=sha(policy_path),
        resident_app=str(app),prefix_template=str(prefix_path),prefix_template_sha256=sha(prefix_path),
        chat_template=str(template),chat_template_sha256=sha(template))
    save(OUT/('SERVICE_BUILD-v'+str(revision)+'.json'),b)
    print('PREPARED_BOUNDED_RESIDENT_DYNAMIC_INPUT_POLICY')

def application(build,policy):
    base=Path(build['resident_app']);prefix='_a12_resident_'+build['resident_policy_sha256'][:20]
    for row in policy['files']:need(sha(base/row['path'])==row['sha256'],'resident application changed')
    for name,path in ((prefix,base),(prefix+'.app',base/'app')):
        if name not in sys.modules:
            m=types.ModuleType(name);m.__path__=[str(path)];sys.modules[name]=m
    for short in ('domain','planning','checking','scoring','session'):
        name=prefix+'.app.'+short;path=base/'app'/(short+'.py')
        if name not in sys.modules:
            m=types.ModuleType(name);m.__file__=str(path);m.__package__=prefix+'.app';sys.modules[name]=m
            exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__)
        need(Path(sys.modules[name].__file__)==path,'resident module namespace/path mismatch')
    return types.SimpleNamespace(**{short:sys.modules[prefix+'.app.'+short] for short in ('domain','planning','checking','session')})

class Probe(FrozenProbe):
    def __init__(self,build):
        super().__init__();self.build=build;need(sha(build['resident_policy'])==build['resident_policy_sha256'],'resident policy changed')
        self.policy=read(build['resident_policy']);p=self.policy
        need(p['schema']=='A12_BOUNDED_RESIDENT_POLICY_V1' and p['total_calls']==5000 and p['max_loads']==72 and p['max_model_requests']==8 and
            p['native_request_ids']==list(IDS) and p['output_tokens']==24 and p['max_inputs']==24 and p['private_control_requests']==9,'resident caps changed')
        need(sha(build['prefix_template'])==build['prefix_template_sha256'] and sha(build['chat_template'])==build['chat_template_sha256']==p['chat_template_sha256'],'resident template changed')
        self.prefix=read(build['prefix_template']);self.prefix_tokens=p['prefix_tokens'];need(len(self.prefix_tokens)==34 and self.prefix['allowed_prefixes']==[self.prefix_tokens],'resident neutral prefix differs')
        self.app=application(build,p)
        for name in p['case_ids']:need(self.app.domain.load_case(name).sha256==p['case_sha256'][name],'resident case changed')
        self.requests=[dict(id='warm_prefix',op='cache_create',tokens=self.prefix_tokens,max_tokens=1,cache_id='resident-neutral',cache_policy='R0',
            confirmed_prefix=True,prefill_chunk=256,logits_mode='final',profile=False,diagnostic_report=False)]
    def check_answer(self,request,result):
        item=request['application'];case=self.app.domain.load_case(item['case_id']);need(case.sha256==self.policy['case_sha256'][item['case_id']]==item['case_sha256'],'resident case identity changed')
        transcript=self.app.domain.Transcript.parse(item['transcript'])
        plan=self.app.planning.plan(case,transcript,item['trusted_played'])
        need(plan.route=='answer' and digest(plan.to_dict())==digest(item['plan']),'resident trusted plan/history differs')
        check=self.app.checking.check(plan,result['text']);need(check['status']=='pass','original resident content checker rejected model output')
        return check
    def check_warm(self,result):
        e=result['prefix_cache']['entries'];need(len(e)==1,'resident prefix inventory differs');e=e[0]
        # Native sequence SHA covers llama_state_seq_get_data, not token IDs;
        # position is zero based. Keep full checkpoint self-verification native.
        need(e['tokens']==34 and e['position']==33 and 0<e['state_bytes']<64*1024*1024 and
            e['logits_bytes']==248320*4 and len(e['state_sha256'])==len(e['logits_sha256'])==64,'resident neutral state shape/sequence differs')
        if self.build['domain']=='PC_REAL_MODEL_PLM_V1':
            ref=self.policy['PC_neutral_reference'];need({k:e[k] for k in ref}==ref,'resident CPU neutral checkpoint differs from accepted reference')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,default=1);a=p.parse_args();prepare(a.revision)
