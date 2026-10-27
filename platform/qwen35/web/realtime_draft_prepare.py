"""Prepare a separate UNBOUND hybrid deployment with real-time greedy draft misses."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
from fast_response_prepare_support import verify_package,refresh_bundle_manifest
from fast_response_profile import validate_profile
from continuous_sessions import question_reserve
from realtime_draft import STRATEGY


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def prepare(args):
    parent=args.parent.resolve();output=args.output.resolve()
    verify_package(parent)
    assert args.arm_binary.is_file() and args.pc_binary.is_file()
    prefix_pc=read(args.pc_config)
    assert prefix_pc['identity']['executable_sha256']==sha(args.pc_binary)
    assert prefix_pc['identity']['threads']==prefix_pc['identity']['kernel_threads']==args.threads
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(parent,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    native_sha=sha(args.arm_binary)
    for kind in ('ordinary','continuous'):
        window=output/kind;bundle=window/'bundle'
        for p in HERE.glob('*.py'):
            if p.name not in ('fast_response_prepare.py','answer_cache_prepare.py','realtime_draft_prepare.py'):
                shutil.copyfile(p,window/p.name)
        for name in ('web_managed.py','native_pl.py'):
            shutil.copyfile(ROOT/'system_qwen35/app'/name,window/name)
        shutil.copytree(HERE/'vendor/web_gateway',window/'web_gateway',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        profile=read(window/'profile.json')
        old_threads=profile['threads']
        profile['threads']=profile['kernel_threads']=args.threads
        profile['cache_id']='short34-t'+str(args.threads)
        identity=profile['prefix_identity']
        identity.update(executable_sha256=native_sha,threads=args.threads,kernel_threads=args.threads)
        if args.compact and kind=='continuous':
            from compact_fact_prompt import POLICY,policy_sha256
            profile['live_miss_prompt_policy']=POLICY
            identity['live_miss_prompt_policy_sha256']=policy_sha256()
        config=read(window/'web-config.json')
        if kind=='continuous':
            profile['realtime_draft_strategy']=STRATEGY
            profile['output_tokens']=32
            config['realtime_draft_strategy']=STRATEGY
            config['answer_cache']['live_miss']='FPGA_REQUIRED_GREEDY_DRAFT_VERIFY_OR_FULL_SERIAL_REPLAY'
            config['browser_profile']='/home/ubuntu/snap/firefox/common/a12-realtime-draft-t'+str(args.threads)
        else:
            profile.pop('realtime_draft_strategy',None)
            profile['output_tokens']=24
            config.pop('realtime_draft_strategy',None)
        validate_profile(profile)
        save(window/'profile.json',profile);save(window/'web-config.json',config)
        prefix=read(bundle/'control/prefix-config.json');prefix['identity']=copy.deepcopy(identity)
        save(bundle/'control/prefix-config.json',prefix)
        shutil.copyfile(args.arm_binary,bundle/'bin/qwen35-a12')
        requests=read(bundle/'control/requests.json')
        for req in requests:
            if req.get('cache_id'):req['cache_id']=profile['cache_id']
        save(bundle/'control/requests.json',requests)
        spec=read(bundle/'control/window-spec.json')
        spec['window_id']='UNBOUND-realtime-draft-t'+str(args.threads)+'-'+kind
        if kind=='continuous':
            spec['output_token_limit']=32
            policy=bundle/'platform/qwen35/a12/resource_probe_policy.py'
            source=policy.read_text(encoding='utf-8')
            assert "1, 24), 'output limit changed'" in source and "spec.get('output_token_limit') == 24" in source
            source=source.replace("1, 24), 'output limit changed'","1, 32), 'output limit changed'")
            source=source.replace("spec.get('output_token_limit') == 24","spec.get('output_token_limit') == 32")
            policy.write_text(source,encoding='utf-8')
            budget=read(bundle/'evidence/RESOURCE_CALL_BUDGET.json')
            budget['profiles'][0]['output_token_limit']=32
            save(bundle/'evidence/RESOURCE_CALL_BUDGET.json',budget)
        save(bundle/'control/window-spec.json',spec)
        policy=bundle/'platform/qwen35/a12/resource_probe_policy.py'
        source=policy.read_text(encoding='utf-8')
        source=source.replace(repr('short34-t'+str(old_threads)),repr(profile['cache_id']))
        policy.write_text(source,encoding='utf-8')
        if args.threads!=old_threads:
            owner=bundle/'platform/qwen35/a12/cpu01b_window.py'
            source=owner.read_text(encoding='utf-8')
            before="str(model), '2', '1024', 'all', 'TILED', '2', '8'"
            assert source.count(before)==1
            source=source.replace(before,"str(model), '3', '1024', 'all', 'TILED', '3', '8'")
            owner.write_text(source,encoding='utf-8')
            manager=bundle/'control/resource_probe_manager.py'
            manager.write_text(manager.read_text(encoding='utf-8').replace("OMP_NUM_THREADS='2'","OMP_NUM_THREADS='3'"),encoding='utf-8')
        refresh_bundle_manifest(bundle)
    deps=read(output/'PC_DEPENDENCIES.json');deps['binary']=str(args.pc_binary.resolve())
    save(output/'PC_DEPENDENCIES.json',deps);save(output/'PC_PREFIX_CONFIG.json',prefix_pc)
    budgets=read(output/'BUDGETS.json')
    budgets.update(question_reserve=question_reserve(1024,34,32,draft_strategy=STRATEGY),output_tokens=32,
        formula='2 * 72 * (ceil((context-prefix)/8) + output-1); verification + complete serial replay',
        ordinary_output_tokens=24,ordinary_strategy='SERIAL_GREEDY_UNCHANGED')
    save(output/'BUDGETS.json',budgets)
    source=read(output/'CACHE_SOURCE.json');source.update(current_live_binary_sha256=native_sha,
        live_miss_backend_required='FPGA_REAL_WITH_STRICT_GREEDY_DRAFT_VERIFICATION',
        live_miss_requires_current_model=True,live_miss_output_limit=32,live_miss_admission_runs=22320)
    source.pop('changed_runtime_files',None)
    source['runtime_files_index']='MANIFEST.json'
    source.update(cache_origin_prompt_policy='facts-only-02-verified-answers-v1',
                  live_miss_prompt_policy='allowed-compact-01' if args.compact else 'original-forms-0')
    save(output/'CACHE_SOURCE.json',source)
    shutil.copyfile(output/'DERIVATION.json',output/'PARENT_CACHE_DERIVATION.json')
    save(output/'DERIVATION.json',dict(schema='A12_REALTIME_DRAFT_DEPLOYMENT_V1',provider='A',
        parent_manifest_sha256=sha(parent/'MANIFEST.json'),native_binary_changed=True,
        native_arm_sha256=native_sha,native_pc_sha256=sha(args.pc_binary),threads=args.threads,
        generation_strategy=STRATEGY,public_ABI_changed=False,HLS_changed=False,model_weights_changed=False,
        quantization_changed=False,prefix_policy_changed=False,answer_cache_source_changed=False,
        live_miss_expression_policy_changed=args.compact,neutral_prefix_and_SYSTEM_changed=False,
        original_24_token_EOS_counterexample='pairs198-v2/proof/pair-039-serial.json',
        ordinary_output_limit=24,continuous_output_limit=32,conservative_question_budget=22320,
        authorization_included=False,BOARD='NOT_TESTED'))
    save(output/'REALTIME_SOURCE.json',dict(strategy=STRATEGY,proposal='CURRENT_INPUT_FACTS_WITH_NUMERIC_SPACING',
        acceptance='TARGET_GREEDY_ARGMAX_EVERY_TOKEN_PLUS_EOS',rejection='CLEAR_ALL_STATE_RESTORE_NEUTRAL_PREFIX_REPLAY_FULL_PROMPT',
        native_arm_sha256=native_sha,native_pc_sha256=sha(args.pc_binary),
        current_request_requires_target_model=True,answer_cache_for_miss=False,
        live_miss_prompt_policy='allowed-compact-01' if args.compact else 'original-forms-0',BOARD='NOT_TESTED'))
    (output/'START_HERE.md').write_text('''# A12 实时模型草稿验证：独立UNBOUND候选

本包保留已核验答案缓存，并优化必须实时运行模型的未命中路径。continuous命中仍标MODEL_CACHE；未命中由真实目标模型验证本次事实草稿的每个token与EOS，来源MODEL。草稿未通过则全清recurrent/conv/KV、恢复中性前缀并重放原prompt，正常实时生成。不是未核验文本回显。

连续窗口输出上限32（旧24在3个双事实组合缺EOS），1024上下文、physical_ubatch=8、34-token中性前缀不变。每问保守预留22320次运行，显式覆盖验证和完整重放；实际用量另记。ordinary仍是24上限的原串行R0/warm/hit窗口。模型/量化/HLS/公共ABI不变；native二进制是本次新派生版本。

从本目录离线检查（不接触设备）：

```sh
python3 continuous/fast_response_verify.py --domain PC --bundle . --suite package
```

现有开发机环境的纯实时PC服务（完全不加载答案缓存）：

```sh
python3 continuous/answer_cache_serve_pc.py --mode realtime --output /tmp/a12-realtime-new-pc-001 --port 8768
```

PC工具使用PC_DEPENDENCIES.json和PC_PREFIX_CONFIG.json中的现有开发机模型/二进制/依赖；ARM部署二进制在各bundle/bin内。新的PC进程用独立输出目录，结束时在该输出目录创建stop-request.json并等待RESULT.json的正常关闭回执。

BOARD尚未测试。只有另获实板授权、具备原irq2/登录/空闲条件后，才从新目录/新Owner窗口执行：

```sh
sudo python3 continuous/fast_response_verify.py --domain BOARD --bundle . --suite web --execute-board --window-id a12-realtime-draft-new-001
```

停止整个BOARD服务（结束问诊仅冻结评分）：

```sh
sudo touch continuous/stop-request.json
```

等待在途完成与原Owner恢复/独立释放回执，再从旧a12_verified_answer_cache_20261027或a12_fast_response_20261027_v2独立目录开新窗口回退。不要复用已消费窗口。此包无模型权重、工具链、系统镜像或可重放计算授权。

PC完整回答的实测前后对照、198组合、错误草稿重放、资源和失败记录见本轮REPORT；PC速度不替代实板时延/功耗/CMA/计数与恢复/释放。
''',encoding='utf-8')
    with (output/'START_HERE.md').open('a',encoding='utf-8') as f:
        f.write('\n本候选线程数：'+str(args.threads)+'。未命中输入表达策略：'+('allowed-compact-01（仅从原checker允许表达中选择较短的完整表达）' if args.compact else '原forms[0]')+'。\n')
        f.write('旧缓存目录的生成策略仍为facts-only-02-verified-answers-v1，来源/模型/病例/事实身份逐次复核；目录不被标为新输入策略生成。新策略只在未命中后构造实时模型输入，可能改变措辞，原必需事实及原checker不变。\n')
    manifest=read(output/'MANIFEST.json')
    manifest['profile_id']='realtime-greedy-draft-t'+str(args.threads)+'-o32'
    manifest['files']=[dict(path=p.relative_to(output).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                       for p in sorted(output.rglob('*')) if p.is_file() and p!=output/'MANIFEST.json' and '__pycache__' not in p.parts]
    save(output/'MANIFEST.json',manifest)
    verify_package(output)
    return dict(status='UNBOUND_REALTIME_DRAFT_PACKAGE_PREPARED',output=str(output),files=len(manifest['files']),
                native_arm_sha256=native_sha,threads=args.threads,question_reserve=22320,BOARD='NOT_TESTED')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent',type=Path,default=ROOT/'release/a12_verified_answer_cache_20261027/hybrid34-threads2')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--arm-binary',type=Path,required=True)
    p.add_argument('--pc-binary',type=Path,required=True);p.add_argument('--pc-config',type=Path,required=True)
    p.add_argument('--threads',type=int,choices=(2,3),default=2)
    p.add_argument('--compact',action='store_true')
    print(json.dumps(prepare(p.parse_args()),indent=2))
