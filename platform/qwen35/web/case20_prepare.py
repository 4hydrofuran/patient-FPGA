"""Package the twenty-case web candidate locally; never stage or activate a board."""
import argparse
import copy
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
from fast_response_prepare_support import refresh_bundle_manifest
from fast_response_profile import pair_budget,validate_profile
from verified_answer_cache import file_sha

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def manifest(out):
    save(out/'MANIFEST.json',dict(schema='A12_FAST_RESPONSE_PACKAGE_V1',status='UNBOUND',
        profile_id='case20-natural-t4-out32',authorization_included=False,
        files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=file_sha(p))
            for p in sorted(out.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p.name!='.DS_Store' and p!=out/'MANIFEST.json']))

def prepare(a):
    parent=ROOT/'release/a12_b_frontend_boardprep_20261027_v2/b601e69ca-realtime34-43-t4'
    out=a.output.resolve();build=a.catalog_build.resolve()
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc','answer-cache'),dirs_exist_ok=a.refresh)
    integrated=HERE/'integrated/B_601e69ca_A_case20_20261027/web_gateway'
    runtime=('fast_response_profile.py','verified_answer_cache.py','answer_cache_profile.py',
        'natural_patient_prompt.py','answer_cache_serve_pc.py','answer_cache_checks_pc.py','answer_cache_verify.py',
        'answer_cache_build.py','case20_noboard.py')
    for kind in ('ordinary','continuous'):
        window=out/kind;bundle=window/'bundle'
        for name in runtime:shutil.copyfile(HERE/name,window/name)
        shutil.copytree(integrated,window/'web_gateway',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copytree(ROOT/'system_qwen35/cases',bundle/'application/system_qwen35/cases',dirs_exist_ok=True)
        for name in ('domain.py','checking.py','planning.py','session.py','cli.py','natural_prompt.py'):
            shutil.copyfile(ROOT/'system_qwen35/app'/name,bundle/'application/system_qwen35/app'/name)
        cpu=window/'web_gateway/src/patient_web/stdio_cpu.py'
        cpu.write_text(cpu.read_text(encoding='utf-8').replace('max_tokens=24','max_tokens=32'),encoding='utf-8')
        config=read(window/'web-config.json');config.pop('answer_cache',None)
        if kind=='continuous':
            profile=read(build/'profile.json');validate_profile(profile);save(window/'profile.json',profile)
            cfg=read(bundle/'control/prefix-config.json')
            cfg.update(identity=copy.deepcopy(profile['prefix_identity']),allowed_prefixes=[profile['prefix_token_ids']])
            save(bundle/'control/prefix-config.json',cfg)
            requests=read(bundle/'control/requests.json')
            for request in requests:
                if request.get('cache_id'):request['cache_id']=profile['cache_id']
                if request.get('op')=='cache_create':request['tokens']=profile['prefix_token_ids']
                elif request.get('op')=='generate':request['max_tokens']=32
            save(bundle/'control/requests.json',requests)
            spec=read(bundle/'control/window-spec.json')
            spec.update(window_id='UNBOUND-case20-natural-continuous',prefix_tokens=profile['prefix_tokens'],
                calculated_worst_case=pair_budget(requests,profile['prefix_tokens']),output_token_limit=32)
            save(bundle/'control/window-spec.json',spec)
            config.update(verify_first=False,verify_continuous=False,natural_patient_policy=profile['natural_patient_policy'],
                browser_profile='/home/ubuntu/snap/firefox/common/a12-case20-natural')
            policy=bundle/'platform/qwen35/a12/resource_probe_policy.py'
            policy.write_text(policy.read_text(encoding='utf-8').replace(repr('short34-t4'),repr(profile['cache_id'])),encoding='utf-8')
        save(window/'web-config.json',config)
        refresh_bundle_manifest(bundle)
    shutil.copyfile(build/'prefix-config-PC.json',out/'PC_PREFIX_CONFIG.json')
    budgets=read(out/'BUDGETS.json')
    budgets.update(startup_warm_worst_runs=360,additional_warm_worst_runs=0,
        severity_prefix_tokens=None,active_prefix_slots=1,primary_prefix_tokens=34)
    save(out/'BUDGETS.json',budgets)
    for name in ('SOURCE_PINS.json','CACHE_SOURCE.json','DERIVATION.json','B_FRONTEND_INTEGRATION.json'):
        shutil.copyfile(out/name,out/('PARENT_CASE20_'+name))
    pins=read(out/'SOURCE_PINS.json')
    pins.update(frontend_commit='601e69ca2896aa9939c1d7e28220b35a59150260',candidate='patient-natural-short-v1',
        live_miss_prompt_policy='patient-natural-short-v1')
    save(out/'SOURCE_PINS.json',pins)
    save(out/'CACHE_SOURCE.json',dict(status='PENDING_FULL1320',cached_answer_source='MODEL_CACHE',
        cached_origin='CPU_REFERENCE',live_miss_requires_current_model=True,live_miss_output_limit=32,
        neutral_prefixes=[34],authorization_included=False,BOARD='NOT_TESTED'))
    save(out/'DERIVATION.json',dict(schema='A12_CASE20_NATURAL_V1',parent_manifest_sha256=file_sha(parent/'MANIFEST.json'),
        cases_changed=True,checker_changed=True,planner_changed=True,scoring_changed=False,
        native_binary_changed=False,model_weights_changed=False,HLS_changed=False,public_ABI_changed=False,
        public_neutral_prefix_tokens=[34],continuous_threads=4,ordinary='legacy smoke reference',BOARD='NOT_TESTED'))
    b=read(out/'B_FRONTEND_INTEGRATION.json')
    b.update(case20_maintainer='A',model_native_checker_scoring_unchanged=False,model_native_scoring_unchanged=True,
        first_board_window_answer_cache=None,actual_PL_answer_required=None,BOARD='NOT_TESTED')
    save(out/'B_FRONTEND_INTEGRATION.json',b)
    save(out/'CASE20_SOURCE.json',dict(case_commit='12c29cee1a57e64d2cf5533b90d46959bf8e0733',
        frontend_commit='601e69ca2896aa9939c1d7e28220b35a59150260',provider='B frontend / case library author',
        maintainer='A',cases=20,answer_plans=1320,active_web='continuous',ordinary='legacy smoke reference',
        naturalness='patient short-form surfaces and authored opening variations; bounded target generation',
        public_prefix_slots=1,public_prefix_tokens=34,native_binary_changed=False,model_weights_changed=False,
        HLS_changed=False,public_ABI_changed=False,BOARD='NOT_TESTED',board_actions=0))
    (out/'START_HERE.md').write_text('''# 二十例患者短答：无板候选

continuous 为新版网页入口：20例、60句主诉、1320个单/双事实答案键；主诉不计入提问评分。
使用患者口语短句及少量表达变化，目标Qwen实际生成、完整EOS与当前事实核对后才入缓存。
开放改写在pilot01/02出现漏事实/额外判断，最终使用有限口语表达；不是无限制自由对话。
单份34-token公共前缀复用，4线程、32输出、1024上下文；模型/native/HLS/公共ABI不变。
缓存命中保留MODEL_CACHE及原CPU_REFERENCE来源，未命中仍实际调用所选后端。
ordinary 保留旧普通smoke配置，不作为新版自然回答性能入口。旧封存包原样保留。

PC运行（现有WSL虚拟环境，模型权重不随包提供）：

```sh
python continuous/answer_cache_serve_pc.py --mode cache --parent . --catalog continuous/answer-cache/catalog.json --realtime-draft --output /tmp/case20-pc-new --port 18781
```

访问 http://127.0.0.1:18781/ 。在该输出目录创建stop-request.json可正常停止PC服务。
纯实时对照使用 --mode realtime，并去掉 --catalog 参数。
本包本轮未上传或连接板卡；板端性能、资源和部署仍未测试。
''',encoding='utf-8')
    manifest(out)
    return dict(status='LOCAL_CANDIDATE_PREPARED_CACHE_PENDING',output=str(out),board_actions=0)

def finish(a):
    out=a.output.resolve();build=a.catalog_build.resolve();result=read(build/'RESULT.json')
    if result['accepted']!=1320 or result['failures'] or result['worker_exit']!=0:
        raise RuntimeError('complete generated catalog required')
    for kind in ('ordinary','continuous'):
        bundle=out/kind/'bundle'
        shutil.copyfile(HERE/'answer_cache_checks_pc.py',out/kind/'answer_cache_checks_pc.py')
        for name in ('domain.py','checking.py','planning.py','session.py','cli.py','natural_prompt.py'):
            shutil.copyfile(ROOT/'system_qwen35/app'/name,bundle/'application/system_qwen35/app'/name)
        refresh_bundle_manifest(bundle)
    target=out/'continuous/answer-cache';target.mkdir(exist_ok=False)
    for name in ('catalog.json','RESULT.json'):shutil.copyfile(build/name,target/name)
    # Proofs stay on disk; the live cache loads only catalog.json.
    shutil.copytree(build/'proof',target/'proof')
    config=read(out/'continuous/web-config.json')
    config['answer_cache']=dict(enabled=True,path='answer-cache/catalog.json',sha256=result['catalog_sha256'],
        policy='VERIFIED_MODEL_REPLAY_WITH_EXPLICIT_ORIGIN',live_miss='ORIGINAL_FPGA_REQUIRED')
    save(out/'continuous/web-config.json',config)
    source=read(out/'CASE20_SOURCE.json');source.update(cache_entries=result['accepted'],catalog_bytes=result['catalog_bytes'],
        catalog_sha256=result['catalog_sha256'],proof_directory='continuous/answer-cache/proof',BOARD='NOT_TESTED')
    save(out/'CASE20_SOURCE.json',source);manifest(out)
    save(out/'CACHE_SOURCE.json',dict(status='COMPLETE_CPU_GENERATED_1320',entries=1320,
        catalog_bytes=result['catalog_bytes'],catalog_sha256=result['catalog_sha256'],
        cached_answer_source='MODEL_CACHE',cached_origin='CPU_REFERENCE',live_miss_requires_current_model=True,
        neutral_prefixes=[34],live_miss_output_limit=32,authorization_included=False,BOARD='NOT_TESTED'))
    manifest(out)
    return dict(status='LOCAL_COMPLETE_CASE20_CANDIDATE',entries=1320,output=str(out),board_actions=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','finish'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--catalog-build',type=Path,required=True)
    p.add_argument('--refresh',action='store_true',help='refresh this local unactivated candidate')
    a=p.parse_args();print(json.dumps(prepare(a) if a.action=='prepare' else finish(a),indent=2))
