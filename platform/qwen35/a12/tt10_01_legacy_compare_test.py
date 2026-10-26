"""Real preserved ARM artifacts plus corruption/absence regressions; no model run."""
import copy,json,tempfile
from pathlib import Path
from tt10_01_common import OUT,FROZEN,save
from tt10_01_legacy_compare import fields,compare_legacy_case,j
from tt10_01_numeric import same_result
def main():
    old=FROZEN/'cpu02/readback-v1/run-v1/s1/diag_exact'
    new=OUT/'window-20261025-v2/execution-01/readback-01/run-v1/s1/diag_exact'
    result=compare_legacy_case(old,new)
    assert result['historical_comparison_pass'] and result['raw_file_count']==444
    assert result['historical_final_state_sha256']=='NOT_AVAILABLE_NO_HISTORICAL_TERMINAL_BYTES'
    assert not result['terminal_sha_equality_claimed']
    a=j(old/'result.json');b=j(new/'result.json');pin=result['historical_prompt_sha256'];checks=1
    for field in ('output_tokens','text','eos','decode_calls','last_prompt_logits_fnv64'):
        corrupt=copy.deepcopy(b);corrupt[field]=None
        assert not fields(a,corrupt,pin)['historical_required_fields_equal'];checks+=1
    for field in ('bytes','fnv64'):
        corrupt=copy.deepcopy(b);corrupt['state_fingerprint'][field]+=1
        assert not fields(a,corrupt,pin)['historical_required_fields_equal'];checks+=1
    for field in ('last_prompt_logits_sha256','state_fingerprint'):
        corrupt=copy.deepcopy(b);del corrupt[field]
        assert not fields(a,corrupt,pin)['historical_required_fields_equal'];checks+=1
    enriched=copy.deepcopy(a);enriched['state_fingerprint']['sha256']='0'*64
    assert not fields(enriched,b,pin)['historical_required_fields_equal'];checks+=1
    corrupt=copy.deepcopy(b);del corrupt['state_fingerprint']['sha256']
    assert not same_result(b,corrupt)['equal'];checks+=1
    corrupt=copy.deepcopy(b);corrupt['last_prompt_logits_sha256']='0'*64
    assert not same_result(b,corrupt)['equal'];checks+=1
    # Existing historical SHA metadata is checked against its own bytes, never ignored.
    enriched=copy.deepcopy(a);enriched['last_prompt_logits_sha256']='0'*64
    assert not fields(enriched,b,pin)['historical_required_fields_equal'];checks+=1
    save(OUT/'window-20261025-v2/execution-01/LEGACY_SCHEMA_PC_REVIEW.json',dict(
        status='PASS_SCHEMA_BOUND_HISTORICAL_COMPARISON_NOT_A_NEW_BOARD_RUN',checks=checks,
        actual_preserved_ARM_case=result,original_generic_comparator_unchanged=True,
        historical_terminal_SHA_still_not_verifiable=True,source03_model_rerun=False,model_runs=0))
    print(json.dumps(dict(status='PASS_LEGACY_SCHEMA_PC_REGRESSIONS',checks=checks,raw_files=444,model_runs=0)))
if __name__=='__main__':main()
