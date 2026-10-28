"""Extend the frozen raw-model auditor; separately verify live-source evidence."""
import argparse
import ast
import os
from pathlib import Path
import textwrap
import modelpl_audit as frozen
from livegen_evidence import ROOT,OUT,read,save,sha
from livegen_source import fd_identity
from request_journal_verified import digest

def auditor():
    source=ROOT/'platform/qwen35/a12/modelpl_audit.py'
    pins={r['path']:r['sha256'] for r in read(ROOT/'evidence/model_pl_A/20261026-model-route-v1/FINAL_REVIEW.json')['source']}
    assert sha(source)==pins['platform/qwen35/a12/modelpl_audit.py']
    raw=source.read_text(encoding='utf-8');node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='audit')
    text=textwrap.dedent('\n'.join(raw.splitlines()[node.lineno-1:node.end_lineno]));anchor="        else:raise AssertionError('unlisted model journal event '+event)";assert text.count(anchor)==1
    text=text.replace(anchor,"""        elif event=='LIVE_GENERATION_BIND':
            source_meta=read(folder/'LIVE_SOURCE.json')
            assert contexts==1 and current is None and not completed and row['Board_approval'] is False
            assert row['context_sha256']==ready['bridge']['a12_route']['pc_plm']['bound_context_sha256'] and row['domain']==source_meta['domain']
            assert row['source_identity_sha256']==source_meta['identity_sha256'] and row['generation_epoch']==source_meta['epoch'] and row['mutation_serial']==source_meta['mutation_serial']==0
        elif event=='LIVE_GENERATION_RESIDENT':
            assert contexts==1 and current is None and not completed and row['Board_approval'] is False and row['Board_BO_inventory'] is None
            assert row['CPU_residency']=={k:ready['bridge']['a12_route'][k] for k in row['CPU_residency']}
            assert row['resident_report_sha256']==digest(ready['bridge']['a12_route'])
"""+anchor)
    scope=dict(frozen.__dict__,OUT=OUT);exec(compile(text,str(source)+'#live-source-audit','exec'),scope);return scope['audit']

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);a=p.parse_args();suite=read(OUT/(a.suite+'-SUITE.json'));check=auditor();results=[]
    for tag in suite['windows']:
        folder=OUT/tag;result=check(tag);meta=read(folder/'LIVE_SOURCE.json');run=read(folder/'RESULT.json');launch=read(folder/'LAUNCH.json')
        assert meta['domain']=='PC_ACTUAL_CPU_MODEL_LIVE_SOURCE_FIXTURE_NO_DEVICE' and not meta['real_Board_health'] and not meta['Board_approval']
        assert digest(meta['nodes'])==meta['node_fingerprint']
        identity=dict(domain=meta['domain'],boot=meta['boot'],lease_sha256=meta['lease_sha256'],node_fingerprint=meta['node_fingerprint'],platform_epoch=meta['epoch'],mutation_serial=0)
        assert digest(identity)==meta['identity_sha256']
        assert sha(folder/'generation-fixture/lease.json')==meta['lease_sha256']
        lease=read(folder/'generation-fixture/lease.json');assert lease['boot_id'].strip()==meta['boot']
        for row in meta['nodes']:
            actual=Path(row['path'])
            if launch['fault']=='same_uuid_reload':
                assert list(fd_identity(actual.lstat()))!=row['identity']
                old=Path(str(actual).replace('/device-generation','/old-device-generation'))
                assert list(fd_identity(old.lstat()))==row['identity']
            else:assert list(fd_identity(actual.lstat()))==row['identity']
        rows=[frozen.strict_json(x) for x in (folder/'state/control.jsonl').read_bytes().splitlines()];events=[x['event'] for x in rows]
        assert events.count('LIVE_GENERATION_BIND')==events.count('LIVE_GENERATION_RESIDENT')==1
        assert events.index('CONTEXT_BIND')<events.index('LIVE_GENERATION_BIND')<events.index('READY')<events.index('LIVE_GENERATION_RESIDENT')<events.index('BEGIN')
        assert run['source_mutation_serial']==(1 if launch['fault']=='platform_mutation' else 0)
        assert run['source_normal_terminal'] is (launch['fault'] is None) and run['source_revoked'] is (launch['fault'] is not None)
        g=read(folder/'READY.json')['bridge']['a12_route']['pc_plm']['generation_consumer']
        assert g['attached'] is True and g['expected_domain']==g['required_domain']==1 and g['slot_state']==1 and not g['Board_approval']
        result.update(live_source_scope='PC_FIXTURE_REAL_OS_HANDLES_NOT_BOARD_SOURCE_VALIDATION',same_UUID_recreation_proof=launch['fault']=='same_uuid_reload');results.append(result)
    assert len(results)==5 and sum(r['status']=='ACCEPTED_PC_MODEL_ORDINARY_WINDOW' for r in results)==2
    save(OUT/(a.suite+'-AUDIT.json'),dict(status='PASS_FIVE_ACTUAL_MODEL_LIVE_SOURCE_WINDOWS',windows=results,
        BOARD='NOT_TESTED',actual_PL_results_consumed=False,Board_health=None,Board_CMA=None,full_intermediate_state='NOT_TESTED'))
    print('PASS_FIVE_ACTUAL_MODEL_LIVE_SOURCE_WINDOWS')
if __name__=='__main__':main()
