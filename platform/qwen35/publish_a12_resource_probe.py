"""Publish the explicitly authorized A12 preboard deliverable with an isolated index.

No working checkout/index changes, force push, main/B/C update or board operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
REMOTE = 'https://github.com/4hydrofuran/patient-FPGA.git'
BASE = '4827305aacfa041421e0ba35c7115d820a851c8a'
BRANCH = 'codex/a12-resource-probe-preboard-20261025'
EV = ROOT/'evidence/a12_resource_probe_publication/20261025-v1'
PROBE = ROOT/'evidence/model_pl_A/20261025-resource-probe-v1'
RELEASE = ROOT/'release/a12_resource_probe_preboard_20261025'
SELF = 'platform/qwen35/publish_a12_resource_probe.py'
SOURCE_NAMES = ['resource_probe_policy.py', 'resource_probe_observer.py', 'resource_probe_case.py',
                'resource_probe_entry.py', 'resource_probe_prepare.py', 'resource_probe_native_pc.py',
                'test_resource_probe.py']
SECRET = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
          re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
          re.compile(rb'github_pat_[A-Za-z0-9_]{50,}'),
          re.compile(rb'AKIA[A-Z0-9]{16}'),
          re.compile(rb'(?i)https?://[^\s/:]+:[^\s/@]+@'),
          re.compile(rb'(?i)["\x27](?:password|passwd|api_key|access_token|refresh_token|client_secret|lease_token)["\x27]\s*:\s*["\x27][^"\x27]{4,}["\x27]')]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2)+'\n').encode('utf-8')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def git(*args, data=None, env=None):
    result = subprocess.run(['git', *args], cwd=ROOT, input=data, env=env,
                            capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError('git '+args[0]+' failed: '+result.stderr.decode(errors='replace'))
    return result.stdout


def workspace():
    return dict(head=git('rev-parse', 'HEAD').decode().strip(),
                branch=git('symbolic-ref', '--short', 'HEAD').decode().strip(),
                staged_raw_sha256=digest(git('diff', '--cached', '--raw', '-z')))


def scan(name, data):
    if any(pattern.search(data) for pattern in SECRET):
        raise RuntimeError('Credential pattern found; content withheld: '+name)


def prepare():
    if git('remote', 'get-url', 'origin').decode().strip() != REMOTE:
        raise RuntimeError('Unexpected remote')
    EV.mkdir(parents=True, exist_ok=False)
    write(EV/'WORKSPACE_BEFORE.json', encoded(workspace()))
    refs = git('ls-remote', '--heads', 'origin').decode()
    write(EV/'REMOTE_BEFORE.txt', refs.encode())
    if BASE+'\trefs/heads/a/a10-to-current-b-review-20261025' not in refs:
        raise RuntimeError('Published parent moved; inspect before choosing a new base')
    if 'refs/heads/'+BRANCH in refs:
        raise RuntimeError('Destination branch already exists; no overwrite')
    checks = []
    for command in ([os.sys.executable, '-B', 'scripts/release/check_contracts.py'],
                    [os.sys.executable, '-B', 'scripts/release/qwen35_config.py']):
        p = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
        checks.append(dict(argv=command, exit_code=p.returncode,
                           stdout=p.stdout.decode('utf-8', errors='replace'),
                           stderr=p.stderr.decode('utf-8', errors='replace')))
        if p.returncode:
            write(EV/'CHECKS.json', encoded(checks))
            raise RuntimeError('Publication guard failed')
    write(EV/'CHECKS.json', encoded(checks))
    final = json.loads((PROBE/'FINAL_REVIEW.json').read_text(encoding='utf-8'))
    for row in final['code']:
        if digest(Path(row['path']).read_bytes()) != row['sha256']:
            raise RuntimeError('Verified code changed: '+row['path'])
    static = json.loads((PROBE/'STATIC_REVIEW.json').read_text())
    package = PROBE/'bundle-v2.zip'
    if digest(package.read_bytes()) != static['zip_sha256']:
        raise RuntimeError('Verified final package changed')
    with zipfile.ZipFile(package) as z:
        if z.testzip() is not None:
            raise RuntimeError('Probe ZIP CRC mismatch')
        for info in z.infolist():
            scan('bundle-v2.zip:'+info.filename, z.read(info))
    reference = Path('C:/Users/Fang/Downloads/A12_PERMISSION_CHECK_RECOMMENDATIONS_20261025.md')
    ref_dest = ROOT/'docs/references'/reference.name
    if ref_dest.exists():
        if ref_dest.read_bytes() != reference.read_bytes():
            raise RuntimeError('Reference destination differs')
    else:
        write(ref_dest, reference.read_bytes())
    live = json.loads((ROOT/'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    scoped = live['a12_resource_probe_preboard_20261025']
    status_path = ROOT/'docs/status/A12_RESOURCE_PROBE_20261025.json'
    write(status_path, encoded(scoped))
    RELEASE.mkdir(parents=True, exist_ok=False)
    readme = '''# A12 普通 R0/warm/hit 资源探测：无板交付

本分支上传本次代码、优化计划、验证记录和最终探测包；基于此前已发布的A10至今工程汇总。

- [完整交接](../../docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md)
- [最终探测包 bundle-v2.zip](../../evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip)
- [验证报告](../../evidence/model_pl_A/20261025-resource-probe-v1/REPORT.md)
- [最终复核](../../evidence/model_pl_A/20261025-resource-probe-v1/FINAL_REVIEW.json)
- [安全检查优化计划](../../docs/A12_SAFETY_CHECK_OPTIMIZATION_PLAN_20261025.md)
- [CMA验收调整](../../docs/A12_CMA_AWARE_ACCEPTANCE_ADJUSTMENT_20261025.md)
- [用户提供的许可检查建议](../../docs/references/A12_PERMISSION_CHECK_RECOMMENDATIONS_20261025.md)
- [本任务状态](../../docs/status/A12_RESOURCE_PROBE_20261025.json)
- [既有工程基线源码与证据](../a10-to-current-b-review-20261025/README.md)

21项Linux PC控制测试和实际x86 CPU模型R0/warm/hit流程通过；无原始诊断文件，worker正常退出。
CMA门槛98304 KiB、MemAvailable门槛1114112 KiB及前缀规划余量保持。使用旧冻结107/70/37-token输入。
原生ARM程序、库、B来源硬件和公共契约未改；首包保持原逐调用许可、健康及fsync。

最终ZIP SHA256：acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa。
ZIP含manifest、固定工具链产物和UNBOUND管理器；不含权重、凭据或原始音频/数值转储。

包默认PLAN_ONLY、无计算授权。当前故障恢复、安全释放、新鲜审查和单独授权/绑定后才可另行板测。
BOARD/CMA改善/板端时延均未测；完整数值和最终性能验收尚未完成，不宣称TTFT达标。

直接代码和证据保持原始字节，部分历史文档仍保留本地绝对路径；本页提供仓库内可访问入口。
重复的解包目录、初版ZIP、其他任务的shared-before快照和全局状态文档未重复上传；原件均留本地。
完整复现还需要既有工程依赖及本地固定模型资产，不能将源码片段当作独立完整构建仓库。
'''
    write(RELEASE/'README.md', readme.encode())
    names = [SELF, 'docs/A12_SAFETY_CHECK_OPTIMIZATION_PLAN_20261025.md',
             'docs/A12_CMA_AWARE_ACCEPTANCE_ADJUSTMENT_20261025.md',
             'docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md',
             ref_dest.relative_to(ROOT).as_posix(), status_path.relative_to(ROOT).as_posix(),
             'release/a12_resource_probe_preboard_20261025/README.md']
    names += ['platform/qwen35/a12/'+n for n in SOURCE_NAMES]
    tops = ['BASELINE.json', 'FINAL_REVIEW.json', 'MANAGER.patch', 'MANAGER-bundle-v2.patch',
            'PACKAGE.json', 'PACKAGE-bundle-v2.json', 'REPORT.md', 'SHARED_STATUS_RECEIPT.json',
            'SOURCE_MANIFEST.json', 'STATIC_REVIEW.json', 'bundle-v2.zip']
    names += [(PROBE/n).relative_to(ROOT).as_posix() for n in tops]
    for directory in ['source', 'pc-tests-01', 'pc-tests-02', 'pc-tests-03', 'native-PC-01', 'native-PC-02']:
        names += [p.relative_to(ROOT).as_posix() for p in sorted((PROBE/directory).rglob('*'))
                  if p.is_file() and '__pycache__' not in p.parts]
    plans = ROOT/'evidence/a12_check_optimization_plan'
    names += [p.relative_to(ROOT).as_posix() for p in sorted(plans.rglob('*')) if p.is_file()]
    entries = []
    for name in sorted(set(names)):
        p = ROOT/name
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError('Outside/symlink source: '+name)
        data = p.read_bytes()
        if len(data) >= 95*1024**2:
            raise RuntimeError('Oversize Git blob: '+name)
        scan(name, data)
        entries.append(dict(path=name, bytes=len(data), sha256=digest(data)))
    manifest = dict(schema='A12_RESOURCE_PROBE_PUBLICATION_V1', base_commit=BASE, branch=BRANCH,
                    files=entries, board_contact=False, authorization_included=False,
                    scope='Only this chat deliverable; original working HEAD/index and other tasks untouched',
                    unchanged_final_probe_zip_sha256=static['zip_sha256'],
                    exclusions=['duplicate extracted bundles', 'initial ZIP', 'shared-before other-task snapshots',
                                'unrelated project changes', 'weights', 'credentials', 'raw diagnostics/audio'])
    write(RELEASE/'MANIFEST.json', encoded(manifest))
    sums = [r['sha256']+'  '+r['path'] for r in entries]
    sums.append(digest((RELEASE/'MANIFEST.json').read_bytes())+'  '+(RELEASE/'MANIFEST.json').relative_to(ROOT).as_posix())
    write(RELEASE/'SHA256SUMS.txt', ('\n'.join(sums)+'\n').encode())
    write(EV/'PREPARED.json', encoded(dict(status='REVIEWED_READY_TO_COMMIT', branch=BRANCH, base_commit=BASE,
        file_count=len(entries)+2, total_bytes=sum(r['bytes'] for r in entries),
        manifest_sha256=digest((RELEASE/'MANIFEST.json').read_bytes()), board_contact=False,
        credential_scan='High-confidence secret and credential-key patterns; ZIP members scanned individually')))
    print(json.dumps(dict(status='REVIEWED_READY_TO_COMMIT', files=len(entries)+2,
                         total_bytes=sum(r['bytes'] for r in entries), branch=BRANCH)))


def publish():
    before = json.loads((EV/'WORKSPACE_BEFORE.json').read_text())
    if workspace() != before:
        raise RuntimeError('Working HEAD/branch/index changed; refusing publication')
    if git('remote', 'get-url', 'origin').decode().strip() != REMOTE:
        raise RuntimeError('Remote changed')
    if git('ls-remote', '--heads', 'origin', 'refs/heads/'+BRANCH).strip():
        raise RuntimeError('Destination exists; no overwrite')
    prepared = json.loads((EV/'PREPARED.json').read_text())
    if digest((RELEASE/'MANIFEST.json').read_bytes()) != prepared['manifest_sha256']:
        raise RuntimeError('Prepared manifest changed')
    manifest = json.loads((RELEASE/'MANIFEST.json').read_text())
    files = {r['path']:r for r in manifest['files']}
    for name in ['MANIFEST.json', 'SHA256SUMS.txt']:
        p = RELEASE/name
        files[p.relative_to(ROOT).as_posix()] = dict(bytes=p.stat().st_size, sha256=digest(p.read_bytes()))
    with tempfile.TemporaryDirectory(prefix='a12-probe-isolated-index-') as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory)/'index'))
        git('read-tree', BASE, env=env)
        rows = []
        for name, row in sorted(files.items()):
            data = (ROOT/name).read_bytes()
            if len(data) != row['bytes'] or digest(data) != row['sha256']:
                raise RuntimeError('Source changed: '+name)
            oid = git('hash-object', '-w', '--stdin', data=data).strip()
            rows.append(b'100644 '+oid+b'\t'+name.encode()+b'\0')
        git('update-index', '-z', '--index-info', data=b''.join(rows), env=env)
        tree = git('write-tree', env=env).decode().strip()
        commit = git('-c', 'user.name=Member A (Codex)', '-c', 'user.email=codex@localhost',
                     'commit-tree', tree, '-p', BASE, '-m',
                     'Prepare A12 ordinary R0 warm hit resource probe with preboard evidence').decode().strip()
    changed = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', BASE, commit).decode().strip('\0').split('\0'))
    if changed != set(files):
        raise RuntimeError('Unexpected commit paths')
    for name, row in files.items():
        if digest(git('show', commit+':'+name)) != row['sha256']:
            raise RuntimeError('Commit payload differs: '+name)
    write(EV/'COMMIT.json', encoded(dict(commit=commit, tree=tree, branch=BRANCH, base_commit=BASE,
                                       files=len(files), all_commit_bytes_verified=True)))
    if workspace() != before:
        raise RuntimeError('Working state changed; no push')
    git('update-ref', 'refs/heads/'+BRANCH, commit, '0'*40)
    stdout = git('push', 'origin', 'refs/heads/'+BRANCH+':refs/heads/'+BRANCH)
    remote = git('ls-remote', '--heads', 'origin', 'refs/heads/'+BRANCH).decode().strip()
    if not remote or remote.split()[0] != commit:
        raise RuntimeError('Remote SHA not verified')
    unchanged = workspace() == before
    write(EV/'PUBLISHED.json', encoded(dict(status='PUSHED_REMOTE_SHA_VERIFIED', commit=commit, branch=BRANCH,
        remote=REMOTE, files=len(files), root_HEAD_branch_and_index_unchanged=unchanged,
        push_ref_only='refs/heads/'+BRANCH, board_contact=False, authorization_included=False,
        push_stdout=stdout.decode(errors='replace'))))
    if not unchanged:
        raise RuntimeError('Published, but working-state verification changed; inspect receipt')
    print(json.dumps(dict(status='PUSHED_REMOTE_SHA_VERIFIED', branch=BRANCH, commit=commit,
                         files=len(files), working_state_unchanged=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'publish'])
    action = parser.parse_args().action
    {'prepare': prepare, 'publish': publish}[action]()
