"""Prepare an independent two-neutral-prefix deployment; native/model/ABI remain pinned."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
from fast_response_prepare_support import verify_package,refresh_bundle_manifest
from fast_response_profile import validate_profile,digest
from neutral_prefixes import prefix_choices
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def prepare(a):
    parent=a.parent.resolve();out=a.output.resolve();verify_package(parent)
    definition=read(a.prefix_source/'EXTRA_PREFIX.json')
    assert read(a.prefix_source/'RESULT.json')['status']=='PASS_REAL_MODEL_TWO_NEUTRAL_PREFIXES'
    pc_config=read(a.prefix_source/'prefix-config-PC.json')
    threads=pc_config['identity']['threads'];extra_tokens=definition['prefix_tokens']
    out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    arm_sha=sha(parent/'continuous/bundle/bin/qwen35-a12')
    for kind in ('ordinary','continuous'):
        window=out/kind;bundle=window/'bundle'
        for p in HERE.glob('*.py'):
            if p.name not in ('fast_response_prepare.py','answer_cache_prepare.py','realtime_draft_prepare.py','tail_prefix_prepare.py'):
                shutil.copyfile(p,window/p.name)
        for name in ('native_pl.py','web_managed.py'):shutil.copyfile(ROOT/'system_qwen35/app'/name,window/name)
        shutil.copytree(HERE/'vendor/web_gateway',window/'web_gateway',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        profile=read(window/'profile.json')
        if kind=='continuous':
            previous_threads=profile['threads']
            profile['threads']=profile['kernel_threads']=threads
            profile['cache_id']='short34-t'+str(threads)
            profile['profile_id']=f'dual-neutral34-{extra_tokens}-t{threads}-out32'
            profile['prefix_identity'].update(threads=threads,kernel_threads=threads)
            if definition['label']=='severity_scale_label':
                from severity_scale_prompt import POLICY,policy_sha256
                profile['live_miss_prompt_policy']=POLICY
                profile['prefix_identity']['live_miss_prompt_policy_sha256']=policy_sha256()
            profile['additional_neutral_prefixes']=[definition]
            profile['prefix_identity']['neutral_prefix_choices_sha256']=digest([profile['prefix_token_ids'],definition['prefix_token_ids']])
            profile['prefix_identity']['neutral_prefix_routing_sha256']=digest([definition])
        validate_profile(profile);save(window/'profile.json',profile)
        cfg=read(bundle/'control/prefix-config.json')
        cfg['identity']=copy.deepcopy(profile['prefix_identity'])
        cfg['allowed_prefixes']=[p['prefix_token_ids'] for p in prefix_choices(profile)]
        save(bundle/'control/prefix-config.json',cfg)
        config=read(window/'web-config.json')
        if kind=='continuous':
            config['neutral_prefix_policy']='LONGEST_REVIEWED_PUBLIC_PREFIX_V2'
            config['browser_profile']=f'/home/ubuntu/snap/firefox/common/a12-tail-v2-t{threads}'
            requests=read(bundle/'control/requests.json')
            for request in requests:
                if request.get('cache_id'):request['cache_id']=profile['cache_id']
            save(bundle/'control/requests.json',requests)
            spec=read(bundle/'control/window-spec.json');spec['window_id']=f'UNBOUND-tail-v2-t{threads}-continuous'
            save(bundle/'control/window-spec.json',spec)
            policy=bundle/'platform/qwen35/a12/resource_probe_policy.py'
            policy.write_text(policy.read_text(encoding='utf-8').replace(repr('short34-t'+str(previous_threads)),repr(profile['cache_id'])),encoding='utf-8')
            if threads!=previous_threads:
                owner=bundle/'platform/qwen35/a12/cpu01b_window.py'
                source=owner.read_text(encoding='utf-8')
                before=f"str(model), '{previous_threads}', '1024', 'all', 'TILED', '{previous_threads}', '8'"
                assert source.count(before)==1
                owner.write_text(source.replace(before,f"str(model), '{threads}', '1024', 'all', 'TILED', '{threads}', '8'"),encoding='utf-8')
                manager=bundle/'control/resource_probe_manager.py'
                source=manager.read_text(encoding='utf-8');before=f"OMP_NUM_THREADS='{previous_threads}'"
                assert before in source
                manager.write_text(source.replace(before,f"OMP_NUM_THREADS='{threads}'"),encoding='utf-8')
        save(window/'web-config.json',config)
        refresh_bundle_manifest(bundle)
        assert sha(bundle/'bin/qwen35-a12')==arm_sha
    save(out/'PC_PREFIX_CONFIG.json',pc_config)
    save(out/'EXTRA_PREFIX.json',definition)
    budgets=read(out/'BUDGETS.json')
    extra_warm_runs=72*((extra_tokens+7)//8)
    budgets.update(startup_warm_worst_runs=360+extra_warm_runs,additional_warm_worst_runs=extra_warm_runs,primary_prefix_tokens=34,
        severity_prefix_tokens=extra_tokens,continuous_threads=threads,prefix_slot_limit=2,prefix_retained_limit_bytes=128*1024*1024,
        admission_prefix_reserve_bytes=192*1024*1024,question_reserve=22320,
        question_formula='unchanged conservative two-pass bound using shortest34 prefix',BOARD='NOT_TESTED')
    save(out/'BUDGETS.json',budgets)
    shutil.copyfile(out/'DERIVATION.json',out/'PARENT_REALTIME_V1_DERIVATION.json')
    save(out/'DERIVATION.json',dict(schema='A12_REALTIME_TAIL_PREFIX_V2',parent_manifest_sha256=sha(parent/'MANIFEST.json'),
        native_binary_changed=False,native_arm_sha256=arm_sha,native_pc_sha256=read(out/'SOURCE_PINS.json')['current_native_pc_sha256'],
        model_weights_changed=False,HLS_changed=False,public_ABI_changed=False,checker_scoring_changed=False,
        public_neutral_prefix_tokens=[34,extra_tokens],continuous_threads=threads,ordinary_threads=3,additional_prefix_contains_case_values=False,
        current_model_required_on_miss=True,case_answer_cache_used_for_performance=False,
        additional_startup_warm_runs=extra_warm_runs,conservative_question_reserve=22320,BOARD='NOT_TESTED'))
    cache=read(out/'CACHE_SOURCE.json');cache['neutral_prefixes']=[34,extra_tokens];cache['prefix_policy']='LONGEST_REVIEWED_PUBLIC_PREFIX_V2'
    save(out/'CACHE_SOURCE.json',cache)
    (out/'START_HERE.md').write_text('''# A12 实时模型长尾优化 v2：独立UNBOUND候选

模型/量化/native/HLS/公共ABI、原checker与评分不变。连续网页加载34-token中性前缀及EXTRA_PREFIX.json所列通用前缀，按完整prompt最长匹配；前缀只含通用词和固定量表满分，不含病例ID或患者评分值。每题评分值与完整答案每个token/EOS仍由本题真实模型计算。普通ordinary窗口仍原3线程/单前缀/24输出；连续线程及前缀长度见profile.json，保持32输出/22320保守逐问额度。

仍只有原允许的两个KV槽（每槽64MiB、合计128MiB），原192MiB前缀预留不变。额外启动预热及总预算见BUDGETS.json；实际保留内存及启动成本见报告。PC验收用--mode realtime，明确不加载答案缓存；正常hybrid模式保留原来源标记，未命中才运行实时模型。

在此目录先做离线检查，不接触设备：

```sh
python3 continuous/fast_response_verify.py --domain PC --bundle . --suite package
```

现有开发机环境的纯实时服务：

```sh
python3 continuous/answer_cache_serve_pc.py --mode realtime --output /tmp/a12-tail-pc-new-001 --port 18771
```

结束时在该PC输出目录创建stop-request.json，并等待正常RESULT.json回执。PC依赖/模型/二进制路径见PC_DEPENDENCIES.json，需现有环境。

BOARD尚未测试，另获实板授权、具备原irq2/登录/空闲条件后，才创建新Owner窗口：

```sh
sudo python3 continuous/fast_response_verify.py --domain BOARD --bundle . --suite web --execute-board --window-id a12-tail-v2-new-001
```

停止整个BOARD服务（结束问诊只冻结评分）：

```sh
sudo touch continuous/stop-request.json
```

等待在途及原Owner恢复/独立释放，再用旧v1独立包开新窗口回退；不要复用已消费授权。无模型权重、SDK/镜像或可重放执行授权。新板端时延/功耗/CMA/计数/恢复仍NOT_TESTED/null。
''',encoding='utf-8')
    metadata=read(out/'MANIFEST.json');metadata['profile_id']=f'dual-neutral34-{extra_tokens}-t{threads}-out32'
    metadata['files']=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'MANIFEST.json' and '__pycache__' not in p.parts]
    save(out/'MANIFEST.json',metadata);verify_package(out)
    return dict(status='UNBOUND_DUAL_NEUTRAL_PREFIX_DEPLOYMENT',output=str(out),files=len(metadata['files']),native_arm_sha256=arm_sha,BOARD='NOT_TESTED')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=ROOT/'release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32')
    p.add_argument('--prefix-source',type=Path,default=ROOT/'evidence/model_pl_A/20261027-realtime-tail-opt-v2/prefix-repeat')
    print(json.dumps(prepare(p.parse_args()),indent=2))
