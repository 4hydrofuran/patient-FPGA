"""Prepare an independent UNBOUND cache/live-miss deployment with actual catalog proofs."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
from verified_answer_cache import VerifiedAnswerCache,file_sha,model_identity
from fast_response_prepare_support import verify_package


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def prepare(parent,catalog_build,output):
    parent=Path(parent).resolve();catalog_build=Path(catalog_build).resolve();output=Path(output).resolve()
    verify_package(parent)
    result=read(catalog_build/'RESULT.json')
    if result.get('accepted')!=198 or result.get('failures') or result.get('worker_exit')!=0:
        raise ValueError('complete actual model catalog is required')
    identity=model_identity(read(parent/'continuous/profile.json')['prefix_identity'],HERE/'vendor/web_gateway/src/patient_web/reference')
    cache=VerifiedAnswerCache(catalog_build/'catalog.json',identity=identity,expected_sha256=result['catalog_sha256'])
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(parent,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    changes=[]
    for kind in ('ordinary','continuous'):
        window=output/kind
        for p in HERE.glob('*.py'):
            if p.name not in ('fast_response_prepare.py','answer_cache_prepare.py'):
                shutil.copyfile(p,window/p.name);changes.append((window/p.name).relative_to(output).as_posix())
        for name in ('web_managed.py','native_pl.py'):shutil.copyfile(ROOT/'system_qwen35/app'/name,window/name)
        shutil.copytree(HERE/'vendor/web_gateway',window/'web_gateway',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        config=read(window/'web-config.json')
        if kind=='continuous':
            target=window/'answer-cache'
            shutil.copytree(catalog_build,target,ignore=shutil.ignore_patterns('worker','ready.json','__pycache__'))
            config['answer_cache']=dict(enabled=True,path='answer-cache/catalog.json',sha256=result['catalog_sha256'],
                policy='VERIFIED_MODEL_REPLAY_WITH_EXPLICIT_ORIGIN',live_miss='ORIGINAL_FPGA_REQUIRED')
        else:config.pop('answer_cache',None)
        save(window/'web-config.json',config)
    save(output/'CACHE_SOURCE.json',dict(schema='A12_CACHE_DEPLOYMENT_V1',mode='VERIFIED_MODEL_REPLAY',
        parent_profile='short34-threads2',parent_manifest_sha256=file_sha(parent/'MANIFEST.json'),
        catalog_sha256=result['catalog_sha256'],cache=cache.report(),current_live_binary_sha256=file_sha(output/'continuous/bundle/bin/qwen35-a12'),
        current_cached_inference=False,cached_answer_source='MODEL_CACHE',cached_origin='CPU_REFERENCE',
        live_miss_backend_required='FPGA_REAL',authorization_included=False,BOARD='NOT_TESTED',changed_runtime_files=changes))
    shutil.copyfile(output/'DERIVATION.json',output/'PARENT_DERIVATION.json')
    save(output/'DERIVATION.json',dict(provider='A',parent_profile='short34-threads2',
        parent_manifest_sha256=file_sha(parent/'MANIFEST.json'),answer_policy='VERIFIED_MODEL_REPLAY_WITH_EXPLICIT_ORIGIN',
        cache_catalog_sha256=result['catalog_sha256'],changed_runtime_files=changes,
        gateway_changes=['reference/session.py','engine.py','managed.py','delivery.py','manager.py','static/console.js'],
        model_weights_changed=False,native_binary_changed=False,HLS_changed=False,public_ABI_changed=False,
        web_receipt_revision='text-delivery.v2 for MODEL_CACHE; v1 retained',BOARD='NOT_TESTED'))
    (output/'START_HERE.md').write_text('''# 核验模型答案复用：UNBOUND候选

本包基于旧34-token候选，含198条真实CPU Qwen生成/EOS/原checker通过的答案；每问重新路由、核验、发布与评分。
命中标记MODEL_CACHE，本轮llm_calls=0、actual_backend=null；原CPU生成来源独立保存。它不代表本轮真实PL计算。
连续网页启用复用；普通R0/warm/hit窗口继续真实模型运行。模型/权重/量化/HLS/xclbin/公共ABI不变。

离线依赖与目录检查，不接触设备：

```sh
python3 continuous/fast_response_verify.py --domain PC --bundle . --suite package
```

另行获实板执行授权并具备原irq2/登录/空闲条件后，在新目录、新Owner ID下启动：

```sh
sudo python3 continuous/fast_response_verify.py --domain BOARD --bundle . --suite web --execute-board --window-id a12-verified-cache-new-001
```

停止整个服务（结束问诊仅冻结评分）：

```sh
sudo touch continuous/stop-request.json
```

等待在途完成、原Owner恢复与独立释放回执；不重置run-v1或复用已消费窗口。
未命中继续原34-token NativePL，24输出/1024上下文、10584最坏逐问预留，缺预算不发送；不自动CPU回退。
旧70和纯实时34回退：正常停止并释放本包，再从已封存的a12_fast_response_20261027_v2独立包启动新窗口。

PC真实浏览器测试工具：answer_cache_serve_pc.py（live/cache）、answer_cache_browser.py（Windows Edge）和
answer_cache_verify.py（catalog/compare）。PC依赖见PC_DEPENDENCIES.json；帮助不会启动设备或模型。
真实BOARD可见时延、硬件计数与释放尚未测试。数据包无计算授权；不得把CPU缓存结果标为FPGA_REAL。
''',encoding='utf-8')
    metadata=read(output/'MANIFEST.json');metadata['profile_id']='verified-answer-cache34-threads2'
    metadata['files']=[dict(path=p.relative_to(output).as_posix(),bytes=p.stat().st_size,sha256=file_sha(p))
        for p in sorted(output.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p!=output/'MANIFEST.json']
    save(output/'MANIFEST.json',metadata)
    return dict(status='UNBOUND_CACHE_PACKAGE_PREPARED',output=str(output),entries=198,
        files=len(metadata['files']),authorization_included=False,BOARD='NOT_TESTED')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--catalog-build',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=ROOT/'release/a12_fast_response_20261027_v2/short34-threads2')
    a=p.parse_args();print(json.dumps(prepare(a.parent,a.catalog_build,a.output),indent=2))
