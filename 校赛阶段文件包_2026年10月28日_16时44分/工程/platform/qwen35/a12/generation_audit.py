"""Extend the pinned raw-native auditor with strict generation event checks."""
import argparse
import ast
import textwrap
import modelpl_audit as frozen
from generation_evidence import ROOT,OUT,PARENT,read,save,sha
from request_journal_verified import digest

def auditor():
    source=ROOT/'platform/qwen35/a12/modelpl_audit.py'
    pins={r['path']:r['sha256'] for r in read(PARENT/'FINAL_REVIEW.json')['source']}
    assert sha(source)==pins['platform/qwen35/a12/modelpl_audit.py']
    raw=source.read_text(encoding='utf-8');node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='audit')
    text=textwrap.dedent('\n'.join(raw.splitlines()[node.lineno-1:node.end_lineno]));anchor="        else:raise AssertionError('unlisted model journal event '+event)"
    assert text.count(anchor)==1
    text=text.replace(anchor,"""        elif event=='GENERATION_BIND':
            assert contexts==1 and current is None and not completed and row['Board_approval'] is False
            assert row['domain']=='PC_GENERATION_FIXTURE_NO_DEVICE' and row['context_sha256']==ready['bridge']['a12_route']['pc_plm']['bound_context_sha256']
            identity=read(folder/'generation-fixture/identity.json');lease=read(folder/'generation-fixture/lease.json')
            if launch['fault']=='generation_mutate':identity['device_generation']='PC_NO_DEVICE'
            assert digest(identity)==row['source_identity_sha256'] and row['generation_epoch']==identity['epoch']==lease['epoch']
        elif event=='GENERATION_RESIDENT':
            assert contexts==1 and current is None and not completed and row['Board_approval'] is False and row['real_BO_inventory'] is None
            assert row['CPU_residency']=={k:ready['bridge']['a12_route'][k] for k in row['CPU_residency']}
"""+anchor)
    scope=dict(frozen.__dict__,OUT=OUT);exec(compile(text,str(source)+'#generation-audit','exec'),scope);return scope['audit']

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);a=p.parse_args();suite=read(OUT/(a.suite+'-SUITE.json'));check=auditor()
    results=[]
    for tag in suite['windows']:
        folder=OUT/tag;result=check(tag);launch=read(folder/'LAUNCH.json')
        packets=[read(folder/'READY.json')]
        if launch['fault'] is None:packets += [read(folder/(name+'-MODEL_RESULT.json'))['result'] for name in ('app_R0','warm_prefix','app_hit')]
        for q in packets:
            g=q['bridge']['a12_route']['pc_plm']['generation_consumer']
            assert g['schema']=='A12_GENERATION_CONSUMER_V1' and g['attached'] is True and g['required_domain']==g['expected_domain']==1 and not g['Board_approval']
            assert g['slot_state']==(1 if q['type']=='ready' else 2) and g['healthy_ns']>0 and g['hardware_completions'] is None
        rows=[frozen.strict_json(line) for line in (folder/'state/control.jsonl').read_bytes().splitlines()]
        events=[q['event'] for q in rows];assert events.count('GENERATION_BIND')==events.count('GENERATION_RESIDENT')==1
        assert events.index('CONTEXT_BIND')<events.index('GENERATION_BIND')<events.index('READY')<events.index('GENERATION_RESIDENT')<events.index('BEGIN')
        assert not any(p.name in ('dump_state','diagnostic_dir') for p in folder.rglob('*'))
        result.update(generation_consumer='PC_ONLY_NATIVE_CHECKS_PRESENT',live_Board_source='NOT_IMPLEMENTED');results.append(result)
    assert len(results)==6 and sum(r['status']=='ACCEPTED_PC_MODEL_ORDINARY_WINDOW' for r in results)==2
    save(OUT/(a.suite+'-AUDIT.json'),dict(status='PASS_SIX_ACTUAL_MODEL_PC_GENERATION_WINDOWS',windows=results,
        verification='RAW_NATIVE_CURRENT_PRIVATE_FILES_HASH_CHAIN_FROZEN_TOKEN_LOGITS_PREFIX_DIGESTS_AND_SPECIFIC_FAULT_TARGETS',
        full_intermediate_state='NOT_TESTED',BOARD='NOT_TESTED',real_PL_results_consumed=False))
    print('PASS_SIX_ACTUAL_MODEL_PC_GENERATION_WINDOWS')
if __name__=='__main__':main()
