"""Seal the tested deployment, engineering evidence and named combined delivery."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_realtime_model_draft_20261027_v1'
PACKAGE=RELEASE/'realtime34-threads3-out32'
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from fast_response_prepare_support import verify_package
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

assert read(EV/'FINAL_REVIEW.json')['status']=='PASS_PC_RUNTIME_PACKAGE_SOURCE_VERIFIED'
assert read(EV/'verify-report02-command/COMMAND.json')['exit_code']==0
assert read(EV/'config-final-command/COMMAND.json')['exit_code']==0
assert read(EV/'ARM_A53_REBOUND.json')['runtime_helpers_unchanged']

# The only post-browser addition to the deployed directory is the measured report.
manifest=read(PACKAGE/'MANIFEST.json')
manifest['files']=[dict(path=p.relative_to(PACKAGE).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                   for p in sorted(PACKAGE.rglob('*')) if p.is_file() and p!=PACKAGE/'MANIFEST.json' and '__pycache__' not in p.parts]
save(PACKAGE/'MANIFEST.json',manifest);verify_package(PACKAGE)
stem='KV260_Qwen35_A12_RealtimeModel_VerifiedDraft'
suffix='NoBoard_20261027_v1.zip'
product=RELEASE/(stem+'_Deployment_'+suffix)
with zipfile.ZipFile(product,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for row in manifest['files']:z.write(PACKAGE/row['path'],PACKAGE.name+'/'+row['path'])
    z.write(PACKAGE/'MANIFEST.json',PACKAGE.name+'/MANIFEST.json')
with zipfile.ZipFile(product) as z:
    assert z.testzip() is None
    for row in manifest['files']:
        data=z.read(PACKAGE.name+'/'+row['path'])
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
product_receipt=dict(name=product.name,role='Deployment',bytes=product.stat().st_size,sha256=sha(product),
                     verified_payload_files=len(manifest['files']),CRC_SHA_readback='PASS')
save(RELEASE/'PRODUCT_ARCHIVE.json',product_receipt)

summary=ROOT/'docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md'
paths=set()
for row in read(EV/'IMPLEMENTED_SOURCE_PINS.json'):
    path=ROOT/row['path'];assert sha(path)==row['sha256'];paths.add(path)
for name in ('docs/A12_REALTIME_MISS_OPTIMIZATION_4H_PLAN_20261027.md',
             'docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md',
             'docs/handoffs/A_A12_REALTIME_MODEL_MISS_NOBOARD_20261027.md',
             'docs/PROJECT_STATUS.json','docs/TEST_MATRIX.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md'):
    paths.add(ROOT/name)
suffixes={'.json','.jsonl','.csv','.txt','.log','.md','.py','.png','.sh','.diff','.cpp','.hpp','.h','.make'}
for path in EV.rglob('*'):
    if not path.is_file() or path.suffix not in suffixes or '__pycache__' in path.parts:continue
    relative=path.relative_to(EV)
    if relative.parts[0] in ('archive-command','publish-command'):continue
    # Only synthetic evidence, worker/proof data and fixed source/build files.
    if any(part.lower().startswith(('edge-profile','browser-profile')) for part in relative.parts):continue
    paths.add(path)
rows=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)]
engineering_manifest=dict(schema='A12_REALTIME_ENGINEERING_INCREMENT_V1',files=rows,
    applies_after_commit='d9ed467ea57700ad96edd86790ae1fb65cc112c9',
    scope='owned implementation, actual PC evidence, source/build metadata and current docs; no model weights',BOARD='NOT_TESTED')
save(RELEASE/'ENGINEERING_MANIFEST.json',engineering_manifest)
engineering=RELEASE/(stem+'_EngineeringIncrement_'+suffix)
with zipfile.ZipFile(engineering,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for row in rows:z.write(ROOT/row['path'],row['path'])
    z.write(RELEASE/'ENGINEERING_MANIFEST.json','ENGINEERING_MANIFEST.json')
with zipfile.ZipFile(engineering) as z:
    assert z.testzip() is None
    for row in rows:
        data=z.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
engineering_receipt=dict(name=engineering.name,role='EngineeringIncrement',bytes=engineering.stat().st_size,
    sha256=sha(engineering),verified_payload_files=len(rows),CRC_SHA_readback='PASS')

readme='''# A12 实时模型未命中优化：无板总交付 v1

日期2026-10-27（北京时间）。先读SUMMARY_zh-CN.md，再按用途选packages内的子包。

- Deployment：当前推荐部署候选。解压后从realtime34-threads3-out32/START_HERE.md开始；continuous缓存未命中时每问真实目标模型验证，ordinary仍原串行R0/warm/hit窗口。
- EngineeringIncrement：本轮源码、测试、198组真实模型配对、浏览器逐题数据、交叉构建及原失败证据。用于已有Patientqwen工程接续，前一交付commit为d9ed467；在新复核目录展开，不是模型权重、工具链或系统备份。

完整回答真实浏览器25题：879.0→618.3ms中位，23/25低于1秒。部署副本另测622.8ms中位。以上答案缓存命中0、各25次实际模型调用，中性KV前缀仍复用；不是冷启动速度或实板速度。

每个草稿token和EOS均由目标贪心选择核验，失败全清状态并重放完整prompt；只从原checker已有表达选择完整输入。新连续32输出/22320保守预算，修复旧24在3个双事实组合缺EOS；不截断答案换速度。旧缓存来源保留，未命中MODEL与命中MODEL_CACHE分开。

包内MANIFEST.json及checksums/SUBPACKAGES.sha256提供摘要。Deployment先运行PC package检查，模型与匹配依赖仍需现有环境；BOARD尚未运行，另获实板授权后才按其START_HERE创建新Owner窗口。停止需等待原完成/恢复/独立释放，再从旧独立包开新窗口回退。
'''
payloads={
    'README_zh-CN.md':readme.encode('utf-8'),
    'SUMMARY_zh-CN.md':summary.read_bytes(),
    'packages/'+product.name:product.read_bytes(),
    'packages/'+engineering.name:engineering.read_bytes(),
    'checksums/SUBPACKAGES.sha256':''.join(r['sha256']+'  packages/'+r['name']+'\n' for r in (product_receipt,engineering_receipt)).encode('utf-8'),
}
inner=dict(schema='A12_REALTIME_TOTAL_DELIVERY_V1',files=[dict(path=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest()) for n,d in sorted(payloads.items())],
           model_weights_included=False,authorization_included=False,BOARD='NOT_TESTED')
payloads['MANIFEST.json']=(json.dumps(inner,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
total=RELEASE/(stem+'_'+suffix);top=total.stem
with zipfile.ZipFile(total,'x',compression=zipfile.ZIP_STORED) as z:
    for name,data in payloads.items():z.writestr(top+'/'+name,data)
with zipfile.ZipFile(total) as z:
    assert z.testzip() is None
    for name,data in payloads.items():assert z.read(top+'/'+name)==data
total_receipt=dict(name=total.name,role='RecommendedCombinedDelivery',bytes=total.stat().st_size,sha256=sha(total),
                   verified_payload_files=len(payloads),CRC_SHA_readback='PASS')
assert total.stat().st_size<100*1024*1024
archives=dict(status='PASS_ALL_ARCHIVES_CRC_SHA_READBACK',artifacts=[total_receipt,product_receipt,engineering_receipt],
    model_weights_included=False,authorization_included=False,BOARD='NOT_TESTED')
save(RELEASE/'ARCHIVES.json',archives);save(EV/'ARCHIVES.json',archives)
(RELEASE/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in archives['artifacts']),encoding='utf-8')
(RELEASE/'START_HERE.md').write_text(f'''# KV260 Qwen3.5 A12：实时模型未命中优化（2026-10-27，v1）

推荐下载总包：[{total.name}]({total.name})，约{total.stat().st_size/1024/1024:.1f}MiB。内含Deployment、EngineeringIncrement、中文总结和校验清单；两个子包的区别见总包README。

[中文总结](../../docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md)说明实际改善、完整性、资源、失败尝试及使用方式。新鲜真实浏览器25题，完整核验答案中位879.0→618.3ms，23/25低于1秒；部署副本复测622.8ms。每题实际运行模型，答案缓存命中0；中性34-token KV前缀仍复用。198组最终输入逐token/EOS/原checker通过。

默认候选realtime34-threads3-out32：3线程、原checker短表达、严格目标贪心验证。连续32输出/22320保守额度覆盖验证与完整重放；ordinary仍原24。旧缓存目录保留原生成来源，不冒充新推理。

从Deployment解压目录的START_HERE开始，先做PC package检查；现有模型资产和依赖仍需本机提供。ARM已显式按2026.1 SDK/cortex-a53构建；新BOARD时延、真实PL未命中、硬件恢复/释放、CMA及功耗计数仍NOT_TESTED/null。另获实板授权后才能执行包内BOARD命令。

[SHA256SUMS.txt](SHA256SUMS.txt)与[ARCHIVES.json](ARCHIVES.json)提供总包及子包摘要。仓库主下载是总包，子包位于其packages内；本地同目录也保留两份子包，方便复核。工程源码及证据在仓库原路径直接浏览。旧交付均保留。
''',encoding='utf-8')
save(RELEASE/'DELIVERY.json',dict(status=archives['status'],recommended=total_receipt,
    subpackages_inside_combined=[product_receipt,engineering_receipt],
    summary='docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md',
    real_browser_pairs=25,before_median_ms=879.0,after_median_ms=618.3,package_repeat_median_ms=622.8,
    under_1s='23/25',answer_cache_hits=0,actual_model_requests_per_group=25,BOARD='NOT_TESTED'))
completion=dict(status='PASS_ALL_REQUIRED_NO_BOARD_REALTIME_OPTIMIZATION',runtime_review_sha256=sha(EV/'FINAL_REVIEW.json'),
    archives=archives,remaining_required_no_board_items=[],remaining_board_items=['visible latency','real PL miss','original Owner restore/independent release'],
    BOARD='NOT_TESTED',board_actions=0,board_latency_s=None,board_real_PL_miss=None,board_restore_release=None)
save(EV/'COMPLETION.json',completion)
print(json.dumps(dict(status=completion['status'],delivery=total_receipt,engineering_files=len(rows),BOARD='NOT_TESTED'),indent=2))
