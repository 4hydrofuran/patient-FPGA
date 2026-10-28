"""Negative controls for strict byte comparison and independent evidence runs."""
import copy
import json
import tempfile
from pathlib import Path
import tt10_01_diagnostic_pc as runner
from tt10_01_common import OUT,save
from tt10_01_numeric import concatenated,same_result


def main():
    checks=[]
    def check(name,condition):
        assert condition,name
        checks.append(name)
    with tempfile.TemporaryDirectory(prefix='tt10-01-source04-') as temp:
        root=Path(temp)
        def fixture(name,positions,inp,out):
            folder=root/name/'diag';folder.mkdir(parents=True)
            (folder/'input.f32').write_bytes(inp);(folder/'output.f32').write_bytes(out)
            (folder/'hybrid-state.bin').write_bytes(b'final-state')
            manifest=dict(projections=[dict(id='linear',input='input.f32',output='output.f32',T=len(positions),K=1,N=1)],logits=[])
            for p in positions:
                file='logits-%d.f32'%p;(folder/file).write_bytes(bytes([p])*4)
                manifest['logits'].append(dict(position=p,file=file))
            (folder/'manifest.json').write_text(json.dumps(manifest))
            return folder.parent
        ref=fixture('reference',[0,1],b'abcdefgh',b'ABCDEFGH')
        warm=fixture('warm',[0],b'abcd',b'ABCD')
        hit=fixture('hit',[1],b'efgh',b'EFGH')
        compare=lambda:concatenated(ref,warm,hit)
        gate=compare();check('JSON_roundtrip_preserves_all_position_keys_and_values',gate['equal'] and json.loads(json.dumps(gate))==gate)
        for name,field in [('input.f32','projection_difference'),('logits-1.f32','logits_difference'),('hybrid-state.bin','prefill_state_equal')]:
            p=hit/'diag'/name;before=p.read_bytes();p.write_bytes(bytes([before[0]^1])+before[1:])
            bad=compare();check(name+'_one_byte_change_rejected',not bad['equal'] and (bad[field] if field!='prefill_state_equal' else not bad[field]))
            p.write_bytes(before)
        manifest=hit/'diag/manifest.json';original=manifest.read_text();data=json.loads(original)
        data['logits']=[];manifest.write_text(json.dumps(data));check('missing_position_rejected',not compare()['equal'])
        data=json.loads(original);data['logits'][0]['position']=0;manifest.write_text(json.dumps(data))
        try:compare()
        except AssertionError:checks.append('duplicate_position_rejected')
        else:raise AssertionError('duplicate position accepted')
        data=json.loads(original);data['logits'][0]['position']='1';manifest.write_text(json.dumps(data))
        try:compare()
        except AssertionError:checks.append('non_integer_position_rejected')
        else:raise AssertionError('string input position accepted')
        manifest.write_text(original)
        p=hit/'diag/input.f32';before=p.read_bytes();p.write_bytes(before[:-1])
        try:compare()
        except AssertionError:checks.append('truncated_projection_rejected')
        else:raise AssertionError('truncated projection accepted')
        p.write_bytes(before)
        result=dict(status='OK',output_tokens=[1],text='x',eos=True,decode_calls=1,last_prompt_logits_fnv64='a',state_position_before_clear=1,state_position_after_clear=-1,state_cleared_before_response=True,last_prompt_logits_sha256='b',state_fingerprint=dict(kv='c',recurrent='d'))
        for field in ('last_prompt_logits_sha256','state_fingerprint'):
            other=copy.deepcopy(result);other.pop(field)
            check('missing_'+field+'_rejected',not same_result(result,other)['equal'])
        other=copy.deepcopy(result);other['state_fingerprint'].pop('recurrent')
        check('missing_state_component_rejected',not same_result(result,other)['equal'])
        old_out=runner.OUT;runner.OUT=root
        try:
            run=runner.claim_run('pc-diagnostic-04-first');sentinel=run/'sentinel';sentinel.write_bytes(b'retain')
            try:runner.claim_run('pc-diagnostic-04-first')
            except FileExistsError:checks.append('duplicate_run_refused_before_worker_launch')
            else:raise AssertionError('existing run accepted')
            check('previous_run_bytes_retained',sentinel.read_bytes()==b'retain')
            check('new_run_is_separate',runner.claim_run('pc-diagnostic-04-next')!=run)
        finally:runner.OUT=old_out
    save(OUT/'source04-continuation-20261025-v1/HARNESS_REGRESSION.json',dict(status='PASS',checks=checks,count=len(checks),BOARD='NOT_TESTED'))
    print(json.dumps(dict(status='PASS_SOURCE04_HARNESS_REGRESSION',checks=len(checks))))


if __name__=='__main__':main()
