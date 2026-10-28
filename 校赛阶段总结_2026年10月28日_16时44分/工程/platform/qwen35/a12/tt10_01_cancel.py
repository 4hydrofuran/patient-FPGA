"""Real CPU cancellation: discard delivery, retain public checkpoint, clear private/work state."""
import json,subprocess,time
from tt10_01_common import ROOT,OUT,FROZEN,WORK,j,save,sha
from tt10_01_pc import environment,launch


def main():
    pc=j(OUT/'PC.json');assert pc['status'].startswith('PASS_PC')
    config_path=OUT/pc['run_directory']/'pc-config.json';env=environment();env['SP_TT10_CONFIG']=str(config_path)
    directory=OUT/'pc-cancel';worker,ready=launch(WORK/'pc/qwen35-a12',directory,env);binding=ready['prefix_cache']['binding_sha256']
    prefix=j(FROZEN/'WORKLOADS.json')['real_inputs'][0]['tokens'][:pc['prefix_tokens']]
    owner=dict(kind='case_session',case_id='SYN_CP_01',case_sha256='1'*64,session_id='cancel-session',epoch=0)
    try:
        for name,namespace in [('public',dict(kind='public_neutral')),('private',owner)]:
            worker.send(dict(id='warm-'+name,op='cache_create',tokens=prefix,max_tokens=1,cache_id=name,cache_owner=namespace,
                             cache_binding_sha256=binding,confirmed_prefix=True,cache_policy='R0'))
            result=worker.get(180);assert result['type']=='cache_created' and result['status']=='OK';save(directory/('warm-'+name+'.json'),result)
        request=dict(id='cancel-active',op='generate',tokens=prefix+[100]*(950-len(prefix)),max_tokens=64,cache_policy='TT10_REQUIRE_HIT',
                     cache_id='private',cache_owner=owner,cache_binding_sha256=binding,state_fingerprint=True,profile=False,teacher_tokens=[10]*64)
        save(directory/'cancel-request.json',request);worker.send(request)
        first=worker.get(300);assert first['type']=='token';worker.cancel('TT10_01_PC_CANCEL_AFTER_FIRST_TOKEN')
        assert worker.close(timeout=45) and worker.process.returncode==0
        wire=[json.loads(s) for s in (directory/'stdout.jsonl').read_text().splitlines()]
        result=next(r for r in wire if r.get('id')=='cancel-active' and r['type']=='result')
        assert result['status']=='CANCELLED' and not result['partial_output_usable'] and result['state_cleared_before_response'] and result['state_position_after_clear']==-1
        assert [e['id'] for e in result['prefix_cache']['entries']]==['public']
        save(OUT/'CANCEL.json',dict(status='PASS_PC_CANCELLATION_DELIVERY_DISCARD_AND_STATE_CLEAR',first_token_observed=True,
            normal_exit=0,private_snapshots_removed=True,public_neutral_snapshot_retained=True,no_generated_output_checkpoint_committed=True,
            late_result_not_delivered=True,native_result=result,BOARD='NOT_TESTED',cooperative_cancel_signal='SIGUSR1',forced_termination=False))
    finally:
        if not worker.closed:worker.close(45)
    cfg=j(config_path);cfg['identity']['executable_sha256']='0'*64;bad=OUT/'bad-executable-config.json';save(bad,cfg)
    bad_env=dict(env,SP_TT10_CONFIG=str(bad))
    argv=[str(WORK/'pc/qwen35-a12'),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
    r=subprocess.run(argv,input='{"op":"shutdown"}\n',capture_output=True,text=True,env=bad_env,timeout=120)
    save(OUT/'BAD_CONFIG.json',dict(argv=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    assert r.returncode==2 and not r.stdout and 'identity differs' in r.stderr
    save(OUT/'PC_AUDIT_FINAL.json',dict(status='PASS_FULL_PC_PREFIX_NUMERICAL_FAULT_AND_CANCEL_GATES',model_checks=pc['count'],
        component_checks=15,application_pairs=25,prefix_tokens=pc['prefix_tokens'],startup_wrong_executable_refused=True,
        cancellation='PASS_CPU_ONLY_NOT_BOARD',native_sha256=sha(WORK/'pc/qwen35-a12'),old_interrupted_run='USER_PAUSE_RETAINED_NOT_MODEL_FAILURE',BOARD='NOT_TESTED'))
    print('TT10_01_FULL_PC_FAULT_CANCEL_AND_IDENTITY_PASS')


if __name__=='__main__':main()
