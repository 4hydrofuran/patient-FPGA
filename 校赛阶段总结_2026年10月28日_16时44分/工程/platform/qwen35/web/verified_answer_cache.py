"""Exact typed-fact reuse of prior, EOS-complete real model answers."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

SCHEMA='A12_VERIFIED_ANSWER_CACHE_V1'
POLICY='facts-only-02-verified-answers-v1'
IDENTITY_KEYS=('model_sha256','model_revision','runtime_base_commit','sidecar_sha256',
               'tensor_map_sha256','template_sha256','contract_sha256','sampler','quantization')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def model_identity(prefix_identity,reference,*,generation_policy=None):
    reference=Path(reference)
    result=dict(assets={k:prefix_identity[k] for k in IDENTITY_KEYS},policy=POLICY,
        checker_sha256=file_sha(reference/'checking.py'),planner_sha256=file_sha(reference/'planning.py'),
        generation=dict(sampling='greedy',enable_thinking=False,teacher_forced=False,max_tokens=64))
    if generation_policy is not None:
        from natural_patient_prompt import policy_sha256
        result.update(policy=generation_policy,prompt_policy_sha256=policy_sha256(),key_version=2)
        result['generation']['max_tokens']=32
    return result


def key_data(case,plan,identity):
    binding={'identity_sha256':digest(identity)} if identity.get('key_version')==2 else {'identity':identity}
    return dict(**binding,case_id=case.case_id,case_version=case.version,case_sha256=case.sha256,
        route=plan.route,required_fact_ids=list(plan.required_fact_ids),facts=[asdict(f) for f in plan.facts],
        max_sentences=plan.max_sentences)


class VerifiedAnswerCache:
    def __init__(self,path,*,identity,expected_sha256,max_entries=1320,max_bytes=8*1024*1024):
        path=Path(path)
        if path.stat().st_size>max_bytes:raise ValueError('answer catalog exceeds configured byte bound')
        if file_sha(path)!=expected_sha256:raise ValueError('answer catalog SHA differs')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema')!=SCHEMA or data.get('identity')!=identity or data.get('authorization_included') is not False:
            raise ValueError('answer catalog identity/schema differs')
        self.identity=copy.deepcopy(identity);self.catalog_sha256=expected_sha256
        self.records={};self.hits=0;self.misses=0;self.path=str(path)
        identity_sha=digest(identity)
        for row in data['entries']:
            origin=row['origin'];key=row['key'];text=row['text']
            bound=(row['key_data'].get('identity_sha256')==identity_sha if identity.get('key_version')==2
                   else row['key_data'].get('identity')==identity)
            if key in self.records or digest(row['key_data'])!=key or not bound:
                raise ValueError('duplicate or changed answer key')
            if (not isinstance(text,str) or not text or len(text)>220 or row['text_sha256']!=hashlib.sha256(text.encode()).hexdigest()
                or origin.get('status')!='OK' or origin.get('eos') is not True or origin.get('teacher_forced') is not False
                or origin.get('execution_kind') not in ('CPU_REFERENCE','FPGA_REAL') or not origin.get('result_sha256')
                or not origin.get('native_request_id') or origin.get('text_sha256')!=row['text_sha256']):
                raise ValueError('answer lacks real model/EOS provenance')
            self.records[key]=copy.deepcopy(row)
        if len(self.records)>max_entries:raise ValueError('catalog exceeds configured entry bound')
        self.bytes=path.stat().st_size
        self.origin_kinds=sorted({r['origin']['execution_kind'] for r in self.records.values()})

    def lookup(self,case,plan):
        if plan.route!='answer':return None
        from patient_web.reference.checking import check
        key=digest(key_data(case,plan,self.identity));row=self.records.get(key)
        if row is None or check(plan,row['text'])['status']!='pass':
            self.misses+=1;return None
        self.hits+=1
        return dict(text=row['text'],provenance=dict(catalog_sha256=self.catalog_sha256,key=key,
            text_sha256=row['text_sha256'],origin=copy.deepcopy(row['origin']),
            current_model_called=False,current_PL_submissions=0,validated_against_current_plan=True))

    def report(self):
        return dict(entries=len(self.records),bytes=self.bytes,hits=self.hits,misses=self.misses,
            catalog_sha256=self.catalog_sha256,origin_kinds=list(self.origin_kinds))
