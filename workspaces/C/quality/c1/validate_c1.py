"""Verify frozen bytes, schema/case links, source partition and near duplicates."""
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
import re
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'app/.deps'))
from jsonschema import Draft202012Validator

CATEGORIES = {'normal','synonym','multi_slot','negation','repeated','unknown','contradiction','injection','crosstalk','score_cheating'}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).lower() if c.isalnum())


def record_schema():
    text={'type':'string','minLength':1}
    ids={'type':'array','items':text,'uniqueItems':True}
    def obj(properties):
        return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)
    return {'$schema':'https://json-schema.org/draft/2020-12/schema', **obj({
        'schema_version':{'const':'c1.1.0'}, 'test_id':text, 'split':{'enum':['test','dev']},
        'dataset_version':{'const':'engineering-v1'}, 'case_id':text, 'case_version':{'const':'0.1.0-draft'},
        'case_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}, 'rubric_version':{'const':'0.1.0-draft'},
        'category':{'enum':sorted(CATEGORIES|{'dev_workflow'})},
        'input':obj({'text':text,'mode':{'const':'assessment'},'context_setup':obj({
            'active_turns':{'type':'array','items':{'type':'object'}},
            'foreign_sessions':{'type':'array','items':{'type':'object'}}, 'repeated_question':{'type':'boolean'}})}),
        'allowed_fact_ids':ids,'forbidden_fact_ids':ids,'allowed_unknown_ids':ids,'must_cover_slots':ids,
        'expected_behavior':{'enum':['answer_known','state_unknown','refuse_control']}, 'reference_answer':text,
        'scoring_labels':obj({'intents':ids,'criterion_ids':ids,'repetition_must_not_add_points':{'type':'boolean'},'llm_may_set_score':{'const':False}}),
        'constraints':obj({k:{'const':False} for k in ['case_mutation_allowed','cross_session_read_allowed','hidden_hint_allowed','fabricated_evidence_allowed','backend_mutation_allowed']}),
        'provenance':obj({'source_pool':text,'source_file':text,'source_row':{'type':'integer','minimum':1},'family_id':text,
                          'author_kind':{'const':'AI_AUTHORED_ENGINEERING'},'clinical_independence_claim':{'const':False}}),
        'review':obj({'status':{'const':'ENGINEERING_DRAFT'},'reviewer':{'type':'null'},'reviewed_at':{'type':'null'},'approval_reference':{'type':'null'}}),
    })}


def validate_records(test, dev, cases, rubric):
    validator=Draft202012Validator(record_schema())
    if len(test)!=324 or len(dev)!=54:
        raise ValueError('Expected 324 test and 54 development records')
    ids=[]
    case_map={c['case_id']:c for c in cases}
    criterion_ids={c['criterion_id'] for c in rubric['criteria']}
    for split,rows in [('test',test),('dev',dev)]:
        for r in rows:
            validator.validate(r)
            ids.append(r['test_id'])
            if r['split']!=split or r['case_id'] not in case_map:
                raise ValueError('Wrong split/case')
            c=case_map[r['case_id']]
            canonical=(json.dumps(c,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
            if r['case_sha256']!=hashlib.sha256(canonical).hexdigest():
                raise ValueError('Case hash mismatch')
            known={f['fact_id'] for f in c['facts']}
            unknown={f['fact_id'] for f in c['unknowns']}
            if set(r['allowed_fact_ids']) & set(r['forbidden_fact_ids']) or set(r['allowed_fact_ids']) | set(r['forbidden_fact_ids']) != known:
                raise ValueError('Disclosure partition not exhaustive/disjoint')
            if not set(r['allowed_unknown_ids']) <= unknown:
                raise ValueError('Unknown fact id')
            expected_slots={f['slot'] for f in c['facts']+c['unknowns'] if f['fact_id'] in r['allowed_fact_ids']+r['allowed_unknown_ids']}
            if expected_slots!=set(r['must_cover_slots']):
                raise ValueError('Slot/fact mapping mismatch')
            if not set(r['scoring_labels']['criterion_ids']) <= criterion_ids:
                raise ValueError('Unknown rubric criterion')
            all_intents={i for rule in c['disclosure_rules'] for i in rule['trigger_intents']}
            if not set(r['scoring_labels']['intents']) <= all_intents:
                raise ValueError('Unknown intent')
            if r['expected_behavior']=='state_unknown' and (r['allowed_fact_ids'] or not r['allowed_unknown_ids']):
                raise ValueError('Unknown question has unexpected known truth')
            if r['expected_behavior']=='refuse_control' and r['must_cover_slots']:
                raise ValueError('Control refusal must not request patient slots')
            if r['category']=='repeated' and not r['input']['context_setup']['active_turns']:
                raise ValueError('Repeated question lacks context')
            if r['category']=='crosstalk' and any(x['case_id']==r['case_id'] for x in r['input']['context_setup']['foreign_sessions']):
                raise ValueError('Foreign session is active case')
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate record id')
    norm=[normalize(r['input']['text']) for r in test]
    if len(norm)!=len(set(norm)):
        raise ValueError('Duplicate normalized test question')
    for cid in case_map:
        rows=[r for r in test if r['case_id']==cid]
        if len(rows)!=108 or {r['category'] for r in rows}!=CATEGORIES:
            raise ValueError('Incomplete per-case coverage')


def leakage_audit(test, dev):
    t_families={r['provenance']['family_id'] for r in test}
    d_families={r['provenance']['family_id'] for r in dev}
    t_sources={r['provenance']['source_file'] for r in test}
    d_sources={r['provenance']['source_file'] for r in dev}
    if t_families & d_families or t_sources & d_sources:
        raise ValueError('Source/template group shared across splits')
    # Different cases do not make copies independent; evaluate distinct utterances.
    d_unique={normalize(r['input']['text']):r['test_id'] for r in dev}
    near=[]
    largest=(0,None,None)
    for r in test:
        text=normalize(r['input']['text'])
        for other,did in d_unique.items():
            ratio=SequenceMatcher(None,text,other,autojunk=False).ratio()
            if ratio>largest[0]: largest=(ratio,r['test_id'],did)
            if ratio>=.80:
                near.append(dict(test_id=r['test_id'],dev_id=did,ratio=round(ratio,6)))
    return dict(test_count=len(test), development_records=len(dev), distinct_test_inputs=len({normalize(r['input']['text']) for r in test}),
        distinct_dev_inputs=len(d_unique), shared_source_files=sorted(t_sources&d_sources), shared_family_ids=sorted(t_families&d_families),
        near_duplicate_threshold=.80, normalization='NFKC, lowercase, alphanumeric only',
        max_cross_split_similarity=round(largest[0],6), max_similarity_pair=list(largest[1:]), near_duplicate_pairs=near,
        statistical_independence='NOT_ESTABLISHED: same author and three draft cases', semantic_leakage='Lexical audit cannot prove absence; manual review pending')


def load_frozen(directory=None):
    p=Path(directory) if directory else HERE/'frozen'
    manifest=json.loads((p/'freeze_manifest.json').read_text(encoding='utf-8'))
    for f in manifest['files']:
        target=p/f['path']
        if target.resolve().is_relative_to(p.resolve()) is False:
            raise ValueError('Manifest path escapes dataset')
        if hashlib.sha256(target.read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('Frozen bytes changed: '+f['path'])
    if manifest['testset_sha256'] != hashlib.sha256((p/'test_set.engineering_v1.jsonl').read_bytes()).hexdigest():
        raise ValueError('Top-level testset hash mismatch')
    test=read_jsonl(p/'test_set.engineering_v1.jsonl')
    dev=read_jsonl(p/'dev_set.engineering_v1.jsonl')
    cases=[json.loads(x.read_text(encoding='utf-8')) for x in sorted((p/'cases').glob('*.json'))]
    rubric=json.loads((p/'rubric_snapshot.json').read_text(encoding='utf-8'))
    validate_records(test,dev,cases,rubric)
    audit=leakage_audit(test,dev)
    if audit['near_duplicate_pairs']:
        raise ValueError('Cross-split near duplicate detected')
    return manifest,test,dev,cases,rubric,audit


if __name__=='__main__':
    manifest,test,dev,cases,rubric,audit=load_frozen()
    print(json.dumps(dict(status='PASS_ENGINEERING_DATASET',test_count=len(test),dev_count=len(dev),
        categories=dict(Counter(r['category'] for r in test)),audit=audit,medical_review='PENDING_NOT_SENT'),ensure_ascii=False,indent=2))
