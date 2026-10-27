"""Create named delivery archives and copy only accepted increments to a clean worktree."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[3]
EV = Path(__file__).resolve().parent
WORKTREE = Path('C:/Patientqwen_publish/a12_fast_response_cache_20261027')
RELEASE_REL = Path('release/a12_fast_response_verified_cache_20261027_v1')
OUT = ROOT / RELEASE_REL
BASE = ROOT / 'release/a12_fast_response_20261027_v2'
CACHE = ROOT / 'release/a12_verified_answer_cache_20261027'
STEM = 'KV260_Qwen35_A12'
SUFFIX = 'NoBoard_20261027_v1.zip'
TOTAL_NAME = f'{STEM}_FastResponse_VerifiedCache_{SUFFIX}'
SUMMARY_REL = 'docs/A12_FAST_RESPONSE_VERIFIED_CACHE_NOBOARD_SUMMARY_20261027.md'
UPLOADED = set()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def checked_archive(path, expected):
    assert sha(path.read_bytes()) == expected, path
    with zipfile.ZipFile(path) as handle:
        assert handle.testzip() is None, path


def publish(relative, data):
    relative = PurePosixPath(relative)
    assert not relative.is_absolute() and '..' not in relative.parts
    target = WORKTREE.joinpath(*relative.parts)
    assert target.resolve().is_relative_to(WORKTREE.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    assert sha(target.read_bytes()) == sha(data)
    UPLOADED.add(relative.as_posix())


assert (WORKTREE / '.git').is_file(), 'A new isolated git worktree is required'
assert read(EV / 'FINAL_REVIEW.json')['status'] == 'PASS_ALL_REQUIRED_NO_BOARD_CACHE_WORK'
OUT.mkdir(exist_ok=False)
baseline = read(BASE / 'ENGINEERING_ARCHIVE.json')
cache_source = read(CACHE / 'ENGINEERING_ARCHIVE.json')
cache_product = read(CACHE / 'ARCHIVE.json')
inputs = [
    (ROOT / baseline['path'], baseline['sha256'], f'{STEM}_EngineeringIncrement_Stage01_ShortPrompt_{SUFFIX}'),
    (ROOT / cache_source['path'], cache_source['sha256'], f'{STEM}_EngineeringIncrement_Stage02_VerifiedCache_{SUFFIX}'),
    (ROOT / cache_product['path'], cache_product['sha256'], f'{STEM}_Deployment_VerifiedCache_Hybrid34T2_{SUFFIX}'),
]
for path, expected, _ in inputs:
    checked_archive(path, expected)

# Preserve accepted source/evidence bytes, in the documented Stage01 -> Stage02 order.
# No untracked workspace enumeration or original staging/index modification is used.
for path, _, _ in inputs[:2]:
    with zipfile.ZipFile(path) as handle:
        for info in handle.infolist():
            if info.is_dir() or info.filename == 'ENGINEERING_MANIFEST.json':
                continue
            publish(info.filename, handle.read(info))
publish(SUMMARY_REL, (ROOT / SUMMARY_REL).read_bytes())
publish('evidence/model_pl_A/20261027-verified-answer-cache-v1/package_repository_delivery.py', Path(__file__).read_bytes())

inner_readme = '''# KV260 Qwen3.5 A12 快速响应与核验答案缓存：无板交付 v1

日期：2026-10-27（北京时间）。先读 SUMMARY_zh-CN.md，完整文件摘要见 MANIFEST.json。

## 按用途选文件

- packages/*Deployment_VerifiedCache_Hybrid34T2*：当前推荐部署候选。解压后从 hybrid34-threads2/START_HERE.md 开始；continuous 网页命中缓存，ordinary 仍运行实时模型。
- packages/*EngineeringIncrement_Stage01_ShortPrompt*：N0～N6短提示词工程源码、测试和原始PC证据。
- packages/*EngineeringIncrement_Stage02_VerifiedCache*：C0～C5缓存工程最终源码、测试、报告、198条真实模型证明、真实浏览器逐题数据及失败修复证据。

工程增量接续现有C:/Patientqwen工程，在新的复核目录按Stage01→Stage02顺序展开，重叠源码以Stage02为准。历史证据原样保留；旧封存入口里的工作区相对路径和旧包名是历史路径，当前包的选择以本页为准。它不是全仓库、模型权重或操作系统备份。

部署包内先运行PC package检查；模型权重、匹配依赖和合法的新执行窗口仍需现有环境提供。包内BOARD命令只有另获实板授权后才能执行，当前候选UNBOUND且没有可重放授权。停止服务需等待原Owner完成/释放回执；结束问诊只冻结评分。

已实测同机真实浏览器25题，完整核验答案显示中位875.0→42.3毫秒，缓存25/25低于1秒；每条保留“已核验模型答案·缓存”标记。原生成为CPU_REFERENCE，本轮缓存不执行模型；未命中继续原模型/PL路径。该数据不是模型计算加速比或实板成绩。

独立纯实时Short34T2和Legacy70T2回退ZIP在仓库同一发布目录，与本总交付包并列。需要回退时先正常停止并释放当前窗口，再开独立新窗口。

BOARD仍NOT_TESTED；板端可见时延、真实PL未命中和硬件恢复/释放待后续实测。无模型权重、凭据、许可证正文或板端计算授权。
'''
top = TOTAL_NAME.removesuffix('.zip')
payloads = {
    'README_zh-CN.md': inner_readme.encode('utf-8'),
    'SUMMARY_zh-CN.md': (ROOT / SUMMARY_REL).read_bytes(),
    'provenance/STAGE01_ENGINEERING_ARCHIVE.original.json': (BASE / 'ENGINEERING_ARCHIVE.json').read_bytes(),
    'provenance/STAGE02_ENGINEERING_ARCHIVE.original.json': (CACHE / 'ENGINEERING_ARCHIVE.json').read_bytes(),
    'provenance/DEPLOYMENT_ARCHIVE.original.json': (CACHE / 'ARCHIVE.json').read_bytes(),
}
for path, _, name in inputs:
    payloads['packages/' + name] = path.read_bytes()
internal_manifest = dict(
    schema='a12-named-delivery.v1', date='2026-10-27', timezone='Asia/Shanghai',
    files=[dict(path=name, bytes=len(data), sha256=sha(data)) for name, data in sorted(payloads.items())],
    source_overlay_order=['Stage01_ShortPrompt', 'Stage02_VerifiedCache'],
    BOARD='NOT_TESTED', model_weights_included=False, authorization_included=False,
)
payloads['MANIFEST.json'] = (json.dumps(internal_manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
main_archive = OUT / TOTAL_NAME
# Inner ZIPs are already compressed; STORE avoids expensive duplicate compression.
with zipfile.ZipFile(main_archive, 'x', compression=zipfile.ZIP_STORED) as handle:
    for name, data in sorted(payloads.items()):
        handle.writestr(top + '/' + name, data)
with zipfile.ZipFile(main_archive) as handle:
    assert handle.testzip() is None
    for name, data in payloads.items():
        assert sha(handle.read(top + '/' + name)) == sha(data)

rows = [dict(name=TOTAL_NAME, role='recommended_delivery', bytes=main_archive.stat().st_size,
             sha256=sha(main_archive.read_bytes()), payloads=len(payloads), CRC_SHA_readback='PASS')]
old_archives = {row['profile_id']: row for row in read(BASE / 'ARCHIVES.json')}
for profile, label in [('short34-threads2', 'Short34T2'), ('legacy70-threads2', 'Legacy70T2')]:
    original = old_archives[profile]
    source = ROOT / original['path']
    checked_archive(source, original['sha256'])
    name = f'{STEM}_LiveModel_{label}_{SUFFIX}'
    shutil.copyfile(source, OUT / name)
    assert sha((OUT / name).read_bytes()) == original['sha256']
    rows.append(dict(name=name, role='independent_live_model_rollback', bytes=source.stat().st_size,
                     sha256=original['sha256'], source=original['path'], CRC_SHA_readback='PASS'))
assert all(row['bytes'] < 100 * 1024 * 1024 for row in rows)
save(OUT / 'DELIVERY.json', dict(
    status='PASS_NAMED_ARCHIVES_CRC_SHA_READBACK', date='2026-10-27', version='v1',
    repository='https://github.com/4hydrofuran/patient-FPGA',
    branch='codex/a12-fast-response-cache-delivery-20261027',
    base_commit='ec5542e7a86f670410550661a4c46f2b206317f4',
    artifacts=rows, actual_browser_pairs=25, live_median_ms=875.0, cache_median_ms=42.3,
    cached_answers_under_1s=25, catalog_real_model_answers=198, BOARD='NOT_TESTED',
    source_stage01_sha256=baseline['sha256'], source_stage02_sha256=cache_source['sha256'],
    deployment_sha256=cache_product['sha256'], model_weights_included=False,
    authorization_included=False,
))
(OUT / 'SHA256SUMS.txt').write_text(''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows), encoding='utf-8')
repo_readme = f'''# A12 快速响应与核验答案缓存：2026-10-27 无板交付 v1

[中文总结](../../{SUMMARY_REL})说明用途、实际改善、验证范围、资源成本、包的区别和后续实板工作。

| 文件 | 选择方式 |
| --- | --- |
| [{TOTAL_NAME}]({TOTAL_NAME}) | **推荐下载**；含总结、缓存部署候选、两个阶段工程源码/测试/证据及逐文件清单 |
| [{rows[1]['name']}]({rows[1]['name']}) | 纯实时模型34-token/2线程候选，逐问运行模型 |
| [{rows[2]['name']}]({rows[2]['name']}) | 原70-token/2线程独立回退候选 |

校验见 [SHA256SUMS.txt](SHA256SUMS.txt)，机器可读信息见 [DELIVERY.json](DELIVERY.json)。三个ZIP均已CRC/SHA回读；改名没有修改原部署或工程ZIP内部字节。总交付包解压后先读README_zh-CN.md，再按用途选择Deployment或EngineeringIncrement，工程按Stage01→Stage02接续。

实际同机真实浏览器25题，完整核验答案显示中位875.0→42.3毫秒，缓存25/25低于1秒。198条均由实际CPU模型生成并核验；每问重新路由、核验和评分，页面标明缓存来源。未命中走原模型路径。该结果属于开发机缓存命中，不能作为实板或模型本身计算加速的结论。

源码可直接浏览仓库platform/qwen35/web、system_qwen35/app及bench/qwen35/web；详细原始证据在evidence/model_pl_A/20261027-verified-answer-cache-v1。当前部署候选UNBOUND，无模型权重或执行授权。板端可见时延、真实PL未命中、Owner恢复/释放仍NOT_TESTED。
'''
(OUT / 'README.md').write_text(repo_readme, encoding='utf-8')
for path in OUT.iterdir():
    publish((RELEASE_REL / path.name).as_posix(), path.read_bytes())
save(EV / 'REPOSITORY_DELIVERY_FILES.json', [dict(path=name, sha256=sha((WORKTREE / name).read_bytes())) for name in sorted(UPLOADED)])
(EV / 'publish-paths.nul').write_bytes(b''.join(name.encode('utf-8') + b'\0' for name in sorted(UPLOADED)))
print(json.dumps(dict(status='PREPARED_AND_HASH_VERIFIED', branch='codex/a12-fast-response-cache-delivery-20261027',
                     copied_paths=len(UPLOADED), archives=rows), ensure_ascii=False, indent=2))
