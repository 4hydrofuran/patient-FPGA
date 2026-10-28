"""Prepare a fresh B frontend + A realtime runtime candidate, without board execution."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from fast_response_prepare_support import refresh_bundle_manifest,verify_package

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare(a):
    parent=ROOT/'release/a12_realtime_tail_20261027_1446_BJT_v2/dual-neutral34-43-t4-out32'
    verify_package(parent)
    integrated=HERE/'integrated/B_601e69ca_A_fast_response_20261027_v2'
    merge=read(integrated/'MERGE.json');assert all(not r['status'].startswith('CONFLICT') for r in merge['files'])
    out=a.output.resolve();shutil.copytree(parent,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(HERE/'frontend_start_board.py',out/'start_board.py')
    for kind in ('ordinary','continuous'):
        window=out/kind
        shutil.copytree(integrated/'web_gateway',window/'web_gateway',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copyfile(HERE/'frontend_modes.py',window/'frontend_modes.py')
        managed=window/'web_managed.py';source=managed.read_text(encoding='utf-8')
        before='    return managed.create_managed_app(model, **options)';assert source.count(before)==1
        source=source.replace(before,'''    app = managed.create_managed_app(model, **options)
    from pathlib import Path
    import json
    window = Path(__file__).resolve().parent
    configuration = window / 'web-config.json'
    if domain == 'BOARD' and configuration.is_file() and json.loads(configuration.read_text()).get('backend_modes', {}).get('cpu'):
        from frontend_modes import install_cpu_mode
        install_cpu_mode(app, window/'bundle', available=model.available,
                         prompt_builder=prompt_builder, generation_timeout_s=generation_timeout_s)
    return app''')
        managed.write_text(source,encoding='utf-8')
        cpu=window/'web_gateway/src/patient_web/stdio_cpu.py'
        source=cpu.read_text(encoding='utf-8');assert source.count('max_tokens=24')==1
        source=source.replace('max_tokens=24','max_tokens=32');cpu.write_text(source,encoding='utf-8')
        config=read(window/'web-config.json')
        if kind=='continuous':
            config.pop('answer_cache',None) # First board window proves actual PL consumption.
            config.update(backend_modes=dict(cpu=True,initial='managed-pl',automatic_fallback=False),verify_first=True)
            config['browser_profile']='/home/ubuntu/snap/firefox/common/a12-b-latest-realtime-20261027'
        save(window/'web-config.json',config)
        refresh_bundle_manifest(window/'bundle')
        assert sha(window/'bundle/bin/qwen35-a12')=='bb66432dafdcda9d990f08b0c2e766e0c9d3de82070177199183268b069047fc'
    save(out/'B_FRONTEND_INTEGRATION.json',dict(upstream_commit=merge['upstream_commit'],provider='B',maintainer='A',
        parent_manifest_sha256=sha(parent/'MANIFEST.json'),prepared_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        first_board_window_answer_cache=False,actual_PL_answer_required=True,CPU='explicit serial CPU baseline / same compact facts / output32',
        model_native_checker_scoring_unchanged=True,BOARD='NOT_TESTED'))
    (out/'START_HERE.md').write_text('''# B最新前端 + A实时模型优化：上板准备候选

来源：B前端601e69ca；A运行时20261027_1446_BJT_v2。34/43前缀、连续4线程、32输出、22320逐问预算及原Owner恢复链保持。

本候选首次上板关闭答案目录，以证明真实模型消费PL结果；完整原目录仍随包保存。CPU为显式选择的串行对照，不把开发机1秒数据承诺给板端。CPU输出32并使用同一短事实输入和原checker/评分；每条回答保留实际来源，生成时不能切换。

先做PC离线与实际模型/浏览器检查。板卡必须是新鲜6.8.12-a10irq2启动、旧Owner已完成交接，才从continuous/fast_response_verify.py建立新独立web窗口。不得重放已经消费的目录；每次试验复制新目录。另见本次HANDOFF文档中的具体命令与前置。

首次配置verify_first=true，原PS入口先做一条真实FPGA网页回答，再创建空白用户会话；B原启动器和桌面安装器不在本次执行。结束问诊只冻结评分；停止整个服务由可信宿主创建continuous/stop-request.json，等待原Owner完成恢复与释放。

本包尚未部署/运行，BOARD=NOT_TESTED。旧已封包版本及B原件保留。
''',encoding='utf-8')
    meta=read(out/'MANIFEST.json');meta['profile_id']='b601e69ca-a-realtime-board-prep'
    meta['files']=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*'))
        if p.is_file() and p!=out/'MANIFEST.json' and '__pycache__' not in p.parts]
    save(out/'MANIFEST.json',meta);verify_package(out)
    print(json.dumps(dict(status='PREPARED_NOT_DEPLOYED',output=str(out),files=len(meta['files']),BOARD='NOT_TESTED'),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);prepare(p.parse_args())
