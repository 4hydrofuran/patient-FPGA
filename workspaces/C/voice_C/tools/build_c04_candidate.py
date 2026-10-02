"""Create one local engineering package; pending-license model assets omitted."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT.parent
EVIDENCE=ROOT/'evidence/c04'
RELEASE=ROLE/'releases/c04'


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def archive(candidate, output):
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(candidate.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(candidate).as_posix())


def manifest(candidate,commit,reproduction=None):
    files=[dict(path=p.relative_to(candidate).as_posix(),bytes=p.stat().st_size,
           sha256=hashlib.sha256(p.read_bytes()).hexdigest())
           for p in sorted(candidate.rglob('*')) if p.is_file() and p!=candidate/'manifest.json']
    contract=json.loads((candidate/'contracts/contract_lock.json').read_text('utf-8'))
    tests=dict(pc=dict(status='PASS',evidence=['evidence/workspace_unittest.log','evidence/measurements/report.json']),
        package_reproduction=dict(status='PASS' if reproduction else 'NOT_TESTED',
            evidence=['evidence/independent_reproduction.json'] if reproduction else []),
        quality=dict(status='NOT_TESTED',evidence=['docs/quality_report.json']),
        aarch64_build=dict(status='NOT_TESTED',evidence=['evidence/arm_inspection.json']),
        board=dict(status='NOT_TESTED',evidence=[]),
        physical_offline_reboot=dict(status='NOT_TESTED',evidence=[]),
        csim=dict(status='NOT_APPLICABLE',evidence=[]),cosim=dict(status='NOT_APPLICABLE',evidence=[]),
        implementation=dict(status='NOT_APPLICABLE',evidence=[]))
    dump(candidate/'manifest.json',dict(schema_version=1,module_type='voice',module_id='C_pc_candidate_v1',
        contract_sha256=contract['contract_sha256'],source_commit=commit,source_commit_scope='REAL_LOCAL_CANDIDATE_SOURCE_SNAPSHOT_NOT_ORIGINAL_ROLE_REPOSITORY',
        platform=dict(arch='x86_64',os='Windows',python='CPython 3.12',board='KV260_PLANNED_NOT_TESTED'),
        entrypoints=dict(worker='bin/worker.py',selftest='bin/selftest.py',installer='tools/install_candidate.py'),
        tests=tests,board_identity=None,files=files,
        release_status='ENGINEERING_DRAFT_FINAL_HUMAN_QUALITY_AND_WEIGHT_LICENSE_PENDING',
        assets=dict(weights_included=False,private_audio_included=False,windows_wheels=True,arm_wheels=True,
                    public_audio='ONE_CC_BY_4_0_RESTORED_DEVELOPMENT_SMOKE_WITH_ATTRIBUTION'),
        adoption='UNDECIDED_DEFAULT_NOT_REPLACED',distribution='LOCAL_ONLY_NOT_SENT_OR_PUBLISHED'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=int,default=1,choices=range(1,10))
    args=parser.parse_args()
    release_base=RELEASE if args.attempt==1 else RELEASE/f'attempt_{args.attempt:02}'
    candidate=release_base/'C_pc_candidate_v1'; candidate.mkdir(parents=True,exist_ok=False)
    for folder in ('voicec','configs','bin','deploy'):
        shutil.copytree(ROOT/folder,candidate/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('test_c00.py','test_microphone.py','test_c04.py'):
        (candidate/'tests').mkdir(exist_ok=True); shutil.copyfile(ROOT/'tests'/name,candidate/'tests'/name)
    tool_names=['install_candidate.py','materialize_local_assets.py','stream_c03_microphone.py','run_microphone.ps1']
    (candidate/'tools').mkdir()
    for name in tool_names:shutil.copyfile(ROOT/'tools'/name,candidate/'tools'/name)
    shutil.copytree(ROOT/'tools/c04_network_guard',candidate/'tools/c04_network_guard')
    shutil.copyfile(ROLE/'docs/plan_qwen35/tools/verify_bundle.py',candidate/'tools/verify_bundle.py')
    shutil.copytree(ROLE/'docs/plan_qwen35/contracts',candidate/'contracts')
    for kind in ('asr','tts'):
        dest=candidate/f'assets/{kind}';dest.mkdir(parents=True)
        shutil.copyfile(ROOT/f'assets/{kind}/model.lock.json',dest/'model.lock.json')
    shutil.copytree(ROOT/'assets/wheels',candidate/'assets/wheels')
    shutil.copyfile(ROOT/'requirements-c01.lock.txt',candidate/'requirements-c01.lock.txt')
    arm=json.loads((EVIDENCE/'arm/wheels.lock.json').read_text('utf-8')); arm_records=[]
    (candidate/'assets/arm/wheels').mkdir(parents=True)
    for row in arm:
        name='assets/arm/wheels/'+row['filename']
        shutil.copyfile(EVIDENCE/'arm'/row['filename'],candidate/name)
        arm_records.append(dict(path=name,bytes=row['bytes'],sha256=row['sha256']))
    dump(candidate/'assets/arm/wheels/wheels.lock.json',arm_records)
    shutil.copyfile(EVIDENCE/'arm/requirements-aarch64.lock.txt',candidate/'assets/arm/requirements-aarch64.lock.txt')
    (candidate/'data').mkdir()
    for name in ('recording_plan.jsonl','tts_listening.template.jsonl','authorization.template.json','metrics_definition.json'):
        shutil.copyfile(ROOT/'data'/name,candidate/'data'/name)
    source=json.loads((ROOT/'data/c01_public/manifest.jsonl').read_text('utf-8').splitlines()[0])
    shutil.copyfile(ROOT/'data/c01_public'/source['audio_path'],candidate/'data/c04_public_smoke.wav')
    shutil.copyfile(ROOT/'data/c01_public/ATTRIBUTION.md',candidate/'data/PUBLIC_AUDIO_ATTRIBUTION.md')
    dump(candidate/'data/public_smoke.json',dict(audio_path='data/c04_public_smoke.wav',source_record=source,
        license='CC-BY-4.0',source_revision='c621c0b7b569dcebcd50273a187a35d1a1fc895f',
        modification='MODEL_RESTORED_24K_TO_WINDOWED_SINC_16K_NO_CROP',human_reference_verified=False,split='DEVELOPMENT_NOT_FINAL'))
    (candidate/'docs').mkdir();shutil.copyfile(ROOT/'C04_README.md',candidate/'docs/C04_SCOPE.md')
    shutil.copyfile(ROOT/'MICROPHONE_README.md',candidate/'docs/MICROPHONE_HISTORY.md')
    dump(candidate/'docs/quality_report.json',dict(status='FINAL_QUALITY_NOT_TESTED',public_development_cer=148/606,
        human_final_cer=None,target_authorized_mandarin_cer=.15,human_tts_listened=0,human_tts_pending=14,
        user_device_feedback='用户确认此前麦克风识别问题是设备原因',quality_after_device_fix='NOT_TESTED',
        audible_ms=None,main_app_e2e_rounds=0,board='NOT_TESTED'))
    notices='''# 模型与依赖来源/许可\n\nASR Zipformer-small-CTC INT8、Matcha Baker、Vocos 的导出权重分发许可仍待确认，模型目录资源均不在 zip 中。Baker 训练数据标明非商业限制。包内 model.lock.json 记录来源、固定版本与 hash，不代表外发获准。\n\nWindows 与 Linux ARM64 wheel 来自固定 PyPI 版本：NumPy 2.5.3（BSD-3-Clause 主许可）、sherpa-onnx / sherpa-onnx-core 1.13.8（Apache-2.0 主许可）；wheel 自带许可证与第三方声明，保留原 wheel。主许可不能替代 wheel 内各第三方条款的核对。详见 assets/arm 的固定记录及 evidence/arm_inspection.json 内嵌许可证路径。\n\n公开烟测音频 google/fleurs-r，CC BY 4.0，固定 revision 与变换在 data/PUBLIC_AUDIO_ATTRIBUTION.md、public_smoke.json；这是修复后的开发语音，不是学生/最终测试录音。私人麦克风记录、C02 合成盲听音频与虚拟环境未包含。\n\n当前整体外发状态：LOCAL_ONLY / NOT_PUBLISHED / NOT_SENT。源码工程草稿并非全部质量或法律验收通过。\n'''
    (candidate/'docs/SOURCES_AND_LICENSES.md').write_text(notices,encoding='utf-8')
    measurement=json.loads((EVIDENCE/'measurements/report.json').read_text('utf-8'))
    if measurement['status']!='PASS':raise RuntimeError('Measurements failed; preserve draft and failure evidence')
    shutil.copytree(EVIDENCE/'measurements',candidate/'evidence/measurements')
    shutil.copyfile(EVIDENCE/'unittest.log',candidate/'evidence/workspace_unittest.log')
    shutil.copyfile(EVIDENCE/'arm/inspection.json',candidate/'evidence/arm_inspection.json')
    shutil.copyfile(EVIDENCE/'freeze.json',candidate/'evidence/freeze.json')
    summary=dict(module_id='C_pc_candidate_v1',date='2026-10-02',recommendation='ONE_PROVISIONAL_ENGINEERING_CANDIDATE_NOT_ADOPTED',
        selection=dict(asr_threads=2,tts_threads=2,tts_batch=1,speed=1.0,silence_scale=1.0,chunk_ms=200,endpoint_seconds=1.2),
        measured=measurement,weights_included=False,private_audio_included=False,
        quality='FINAL_HUMAN_ASR_AND_TTS_PENDING',physical_offline_reboot='NOT_TESTED',board='NOT_TESTED',
        default_replaced=False,A_delivery='NOT_SENT',rollback='Default remains selected; candidate runtime is isolated')
    dump(candidate/'ONE_PAGE_SUMMARY.json',summary)
    (candidate/'ONE_PAGE_SUMMARY.md').write_text('''# C_pc_candidate_v1 一页摘要\n\n状态：电脑工程草稿，真人最终质量/权重分发许可待验收，BOARD_NOT_TESTED；尚未发布给 A，默认系统保持原选择。\n\n固定 Zipformer-small-CTC INT8 + Matcha Baker/Vocos，2 线程，TTS 速度/暂停 1.0、批次 1，200 ms PCM，端点 1.2 秒仅提示、finish 唯一提交。\n\n工程证据：工作区完整回归、30 次新进程 ASR/流式/TTS 冷启动循环、200 次模块循环。详细计时/失败口径见 ONE_PAGE_SUMMARY.json；200 次不是完整应用端到端轮数。物理断网/OS 重启、真人 CER/发音、实际扬声器出声、2 小时稳定性、ARM64 原生 import 和板端未验收。\n\nzip 提供源码、离线 Windows/ARM64 wheel、安装、自测、公开烟测与署名、来源/许可、完整 manifest 和真实源码 Git 快照 bundle。未含模型资源及私人录音；权重需独立获准和 hash 核对。\n\n使用顺序：静态核验 → 安装到新 runtime → 契约 selftest → 获准本地模型 → --real selftest → 独立真人质量/实际断网重启 → 决定交付。默认不自动替换，出现失败停止测试并保留报告。\n''',encoding='utf-8')
    (candidate/'README.md').write_text('''# C_pc_candidate_v1（本地工程草稿）\n\n先阅读 ONE_PAGE_SUMMARY.md。模型权重因许可待确认而未包含，不包含私人音频。Python 3.12 x64 Windows 是本次验证平台；ARM64 仅安装准备。\n\n```powershell\npython tools/verify_bundle.py . --contract contracts/contract_lock.json\npython tools/install_candidate.py --target-runtime C:/approved/new/voice_runtime\n& C:/approved/new/voice_runtime/.venv/Scripts/python.exe C:/approved/new/voice_runtime/bin/selftest.py --output C:/approved/new/contract_results\n```\n\n安装和结果目录必须在原包外，且尚不存在。依赖安装仅使用包内固定 wheel，不联网、不升级全局环境。自测默认做契约/工程检查，--real 才执行真实 ASR/流式/TTS，模型缺失时明确失败。要复现 --real，先将获准的固定资源放进 runtime/assets 并核对 lock；同电脑可用 tools/materialize_local_assets.py 的本地复制工具，不能因此认为获准外发。\n\n```powershell\npython tools/materialize_local_assets.py --source-voice-root C:/approved/existing/voice_C --target-runtime C:/approved/new/voice_runtime\n& C:/approved/new/voice_runtime/.venv/Scripts/python.exe C:/approved/new/voice_runtime/bin/selftest.py --real --output C:/approved/new/real_results\n```\n\nworker 入口：在 runtime 下使用 .venv/Scripts/python.exe bin/worker.py --spool NEW_SPOOL --asr-config configs/asr.selected.json --tts-config configs/tts.selected.json --stream-config configs/stream.selected.json --diagnostic-log NEW_AUDIT_DIRECTORY。stdout 仅 UTF-8 JSONL，--diagnostic-log 只记有界元数据。音频输入和播放由主应用负责，Windows 独立麦克风工具位于 tools/run_microphone.ps1。默认不录音，只有明确执行麦克风工具才开始短时采集；原音频用后删除。\n\n源码提交是独立候选快照；provenance/source_snapshot.bundle 包含该真实提交，source_files.json 可核对源码逐字节匹配。原角色工作区未伪造 Git 提交。\n\n质量、断网边界、许可与 A53 限制详见 docs/C04_SCOPE.md、docs/SOURCES_AND_LICENSES.md、deploy/aarch64/README.md。不得据 PC 工程 PASS 认定真人质量、外发许可或板端 PASS。\n''',encoding='utf-8')
    snapshot=release_base/'source_snapshot';snapshot.mkdir(exist_ok=False)
    source_files=[]
    for p in sorted(candidate.rglob('*')):
        rel=p.relative_to(candidate)
        if p.is_file() and rel.parts[0] in ('voicec','tests','bin','tools','configs','deploy','contracts','docs'):
            dest=snapshot/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
            source_files.append(rel.as_posix())
    commands=[['git','init','-b','candidate-source'],
        ['git','-c','core.autocrlf=false','add','--',*source_files],
        ['git','-c','user.name=Codex local source snapshot','-c','user.email=local-snapshot@invalid',
         '-c','commit.gpgsign=false','commit','-m','Freeze C04 engineering candidate source snapshot']]
    records=[]
    for cmd in commands:
        proc=subprocess.run(cmd,cwd=snapshot,capture_output=True,text=True,encoding='utf-8')
        records.append(dict(argv=cmd,exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
        if proc.returncode:raise RuntimeError('Source snapshot Git operation failed: '+proc.stderr)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=snapshot,text=True).strip()
    (candidate/'provenance').mkdir()
    subprocess.run(['git','bundle','create',str(candidate/'provenance/source_snapshot.bundle'),'HEAD'],cwd=snapshot,check=True)
    dump(candidate/'provenance/source_files.json',dict(source_commit=commit,scope='REAL_LOCAL_SOURCE_SNAPSHOT',
        files=[dict(path=n,sha256=hashlib.sha256((candidate/n).read_bytes()).hexdigest()) for n in source_files]))
    command_name='source_snapshot_commands.json' if args.attempt==1 else f'source_snapshot_commands_{args.attempt:02}.json'
    dump(EVIDENCE/command_name,dict(source_commit=commit,repository=str(snapshot),commands=records))
    manifest(candidate,commit)
    zip_path=EVIDENCE/('preflight_package.zip' if args.attempt==1 else f'preflight_package_{args.attempt:02}.zip')
    archive(candidate,zip_path)
    print(json.dumps(dict(candidate=str(candidate),source_commit=commit,preflight_zip=str(zip_path)),ensure_ascii=False))


if __name__=='__main__':main()
