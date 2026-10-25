"""Local-only compute handoff; explicit scopes, isolated Git index, no board I/O."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'release/a10-to-current-b-review-20261025'
EV = ROOT / 'evidence/A10_to_current_publication/20261025-v1'
BASE = 'c5173996a676dbbf5a57f70dce6181d1f4793ed5'
BRANCH = 'a/a10-to-current-b-review-20261025'
REMOTE = 'https://github.com/4hydrofuran/patient-FPGA.git'
SUMMARY = 'docs/A10_TO_CURRENT_ENGINEERING_SUMMARY_FOR_B_20261025.md'
SELF = 'platform/qwen35/package_a10_to_current_b_review.py'
TEXT = {'.py', '.ps1', '.sh', '.c', '.cpp', '.h', '.hpp', '.inc', '.s',
        '.json', '.jsonl', '.md', '.txt', '.csv', '.yaml', '.yml', '.lock',
        '.patch', '.diff', '.cfg', '.tcl', '.cmake', '.dts', '.dtsi', '.rst',
        '.v', '.sv', '.xdc', '.rpt', '.log', '.ini', '.toml', '.xml', '.sources'}
SPECIAL = {'Makefile', 'CMakeLists.txt', 'LICENSE', 'LICENSE.txt', 'NOTICE', 'contracts.lock'}
CODE = {'.py', '.ps1', '.sh', '.c', '.cpp', '.h', '.hpp', '.inc', '.s',
        '.patch', '.diff', '.tcl', '.cmake', '.v', '.sv', '.xdc'}
SCOPES = [
    'platform/qwen35/a11', 'platform/qwen35/a12',
    'runtime/qwen35_cpu', 'runtime/qwen35_w4a8', 'modules/linear_A',
    'system_qwen35/app', 'system_qwen35/cases', 'system_qwen35/__init__.py',
    'config/qwen35', 'contracts/qwen35',
    'quant/export_w4a8', 'quant/reference', 'quant/tests',
    'hw/linear_A', 'platform/local/a11-mlp-20261023-v1',
    'hw/linear_B_received/B03-supplement-e227297-20261003/payload/src',
    'hw/linear_B_received/B03-supplement-e227297-20261003/payload/contracts',
    'hw/linear_B_received/B03-supplement-e227297-20261003/payload/B03_supplement_manifest.json',
    'release/a12_cpu_peer_01_03_20261024_v1',
    'evidence/mlp_board_A', 'evidence/model_pl_A',
    'platform/toolchain.lock.json',
    'scripts/release/check_contracts.py', 'scripts/release/qwen35_config.py',
    SUMMARY, SELF,
]
PRIVATE = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
           re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
           re.compile(rb'github_pat_[A-Za-z0-9_]{50,}'),
           re.compile(rb'AKIA[A-Z0-9]{16}'),
           re.compile(rb'(?i)https?://[^\s/:]+:[^\s/@]+@')]
SECRET_KEYS = {'password', 'passwd', 'private_key', 'api_key', 'access_token',
               'refresh_token', 'authorization', 'client_secret', 'lease_token'}
# Deliberately excludes generic token/token_id: those are numerical model evidence.


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def git(*args, data=None, env=None):
    p = subprocess.run(['git', *args], cwd=ROOT, input=data, env=env,
                       capture_output=True, timeout=180)
    if p.returncode:
        raise RuntimeError('git ' + args[0] + ': ' + p.stderr.decode(errors='replace'))
    return p.stdout


def checks():
    rows = []
    for cmd in ([sys.executable, '-B', 'scripts/release/check_contracts.py'],
                [sys.executable, '-B', 'scripts/release/qwen35_config.py']):
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=60)
        rows.append(dict(argv=cmd, exit_code=p.returncode,
                         stdout=p.stdout.decode('utf-8', errors='replace'),
                         stderr=p.stderr.decode('utf-8', errors='replace')))
        if p.returncode:
            break
    result = dict(domain='PC_PUBLICATION_ONLY', board_contact=False,
                  cma_candidate_tests_restarted=False,
                  passed=len(rows) == 2 and all(x['exit_code'] == 0 for x in rows),
                  commands=rows)
    dump(EV/'CHECKS.json', result)
    if not result['passed']:
        raise RuntimeError('Checks failed; original outputs retained')


def exclusion(p, name):
    low = name.lower()
    parts = p.relative_to(ROOT).parts
    if p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve()):
        return 'symlink_or_outside_workspace'
    if any(x.lower() in {'.git', '__pycache__', '.venv', 'venv', 'node_modules',
                         'cmakefiles', '.xil'} for x in parts):
        return 'cache_or_generated_build_directory'
    if any(any(w in x.lower() for w in ('audio', 'voice', 'tts', 'asr')) or
           re.search(r'(?:^|[_-])a13(?:$|[_-])', x.lower()) for x in parts):
        return 'audio_out_of_scope_by_user'
    if p.name == 'test_capture.py':
        return 'audio_capture_test_out_of_scope_by_user'
    if any(word in p.name.lower() for word in ['known_hosts', 'credential', 'ssh_auth',
                                               'auth_broker', 'password', 'securestring']):
        return 'operator_authentication_material'
    if any(x.lower().startswith(('capture-', 'capture_', 'uart-', 'uart_', 'ssh-'))
           for x in parts):
        return 'transport_capture_not_selected'
    if p.suffix.lower() not in TEXT and p.name not in SPECIAL:
        return 'binary_weight_dump_image_archive_or_unselected_type'
    if p.name.lower().startswith('.env') or p.suffix.lower() in {'.key', '.pem', '.lic'}:
        return 'private_or_license_material'
    if p.stat().st_size > 8 * 1024**2:
        return 'large_text_local_only'
    if p.suffix.lower() in {'.jsonl', '.log', '.txt', '.csv'} and p.stat().st_size > 512 * 1024:
        return 'large_raw_stream_local_only_summary_and_manifests_selected'
    if '/vendor/' in low and any(x in low for x in ['/tests/', '/examples/']):
        return 'vendor_optional_tests_examples'
    return None


def redact(v, path='$', changes=None):
    if isinstance(v, dict):
        result = {}
        for k, x in v.items():
            keypath = path + '.' + k
            if k.lower() in SECRET_KEYS and x not in (None, False, '', '[REDACTED_FOR_PUBLICATION]'):
                result[k] = '[REDACTED_FOR_PUBLICATION]'
                changes.append(keypath)
            else:
                result[k] = redact(x, keypath, changes)
        return result
    if isinstance(v, list):
        return [redact(x, path + '[' + str(i) + ']', changes) for i, x in enumerate(v)]
    return v


def public_bytes(name, raw):
    text = raw.decode('utf-8-sig')
    if '\0' in text:
        raise ValueError('embedded_NUL_not_public_text')
    changes = []
    if name.endswith('.json'):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            value = redact(obj, changes=changes)
            if changes:
                return encoded(value), changes
    # Redact credential literals inside diagnostic strings, never numeric token IDs.
    if name.startswith('evidence/'):
        pattern = r'''(?i)(["'](?:password|passwd|api_key|access_token|refresh_token|lease_token)["']\s*:\s*["'])([^"'\r\n]+)(["'])'''
        text, count = re.subn(pattern, lambda m: m[1] + '[REDACTED_FOR_PUBLICATION]' + m[3], text)
        if count:
            changes.append('embedded_credential_fields:' + str(count))
            return text.encode('utf-8'), changes
    return raw, changes


def prepare():
    if OUT.exists():
        raise FileExistsError('Output already exists; do not overwrite: ' + str(OUT))
    if git('remote', 'get-url', 'origin').decode().strip() != REMOTE:
        raise RuntimeError('Unexpected remote')
    if not json.loads((EV/'CHECKS.json').read_text(encoding='utf-8'))['passed']:
        raise RuntimeError('Publication checks missing')
    paths = {}
    scopes = [ROOT/x for x in SCOPES]
    scopes += sorted((ROOT/'hw/linear_B_received/B03-supplement-e227297-20261003/payload').glob('hls_prefill_*.cfg'))
    scopes += sorted((ROOT/'docs').glob('A11*.md'))
    scopes += sorted((ROOT/'docs').glob('A12*.md'))
    for pattern in ['A11*.md', 'A12*.md', 'A_A11*.md', 'A_A12*.md', 'A_A12*.json']:
        scopes += sorted((ROOT/'docs/handoffs').glob(pattern))
    scopes += [EV/'CHECKS.json']
    missing = []
    for scope in scopes:
        if not scope.exists():
            missing.append(scope.relative_to(ROOT).as_posix())
            continue
        for p in ([scope] if scope.is_file() else sorted(scope.rglob('*'))):
            if p.is_file():
                paths[p.relative_to(ROOT).as_posix()] = p
    groups = {'SOURCE': {}, 'MODEL_EVIDENCE': {}}
    entries, excluded = {}, []
    for name, p in sorted(paths.items()):
        reason = exclusion(p, name)
        if reason:
            excluded.append(dict(path=name, bytes=p.stat().st_size, reason=reason))
            continue
        raw = p.read_bytes()
        try:
            payload, redactions = public_bytes(name, raw)
        except (UnicodeDecodeError, ValueError):
            excluded.append(dict(path=name, bytes=len(raw), reason='not_valid_public_UTF8_text'))
            continue
        hits = [i for i, pattern in enumerate(PRIVATE) if pattern.search(payload)]
        if hits:
            excluded.append(dict(path=name, bytes=len(raw), reason='high_confidence_secret_pattern', patterns=hits))
            continue
        group = 'SOURCE' if (not name.startswith('evidence/') or p.suffix.lower() in CODE) else 'MODEL_EVIDENCE'
        groups[group][name] = payload
        entries[name] = dict(group=group, bytes=len(payload), sha256=sha(payload),
                             source_bytes=len(raw), source_sha256=sha(raw), redactions=redactions)
    # Required engineering endpoints prevent an accidentally empty handoff.
    required = [SUMMARY, SELF, 'system_qwen35/app/checking.py',
                'platform/qwen35/a12/tt10_01_diag_reader.py',
                'runtime/qwen35_w4a8/cpu_backend.cpp', 'hw/linear_A/KERNEL_SOURCE.json',
                'evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v3/execution-01/REPORT.md']
    absent = [x for x in required if x not in entries]
    if absent:
        raise RuntimeError('Required paths absent: ' + repr(absent))
    OUT.mkdir(parents=True)
    manifest = dict(format='A10_TO_CURRENT_COMPUTE_REVIEW_V1', base_commit=BASE,
                    branch=BRANCH, board_contact=False, audio_included=False,
                    source_tip_cma_status='PAUSED_LATEST_EDITS_NOT_REVALIDATED_NOT_DEPLOYED',
                    TT10_01='INCOMPLETE', TTFT_le_10s=False,
                    missing_optional_scopes=missing, files=entries)
    dump(OUT/'MANIFEST.json', manifest)
    dump(OUT/'EXCLUDED.json', dict(scope='Explicit compute scopes only; all audio omitted',
         original_files_deleted=False, exclusions=excluded))
    archives = {}
    for group, files in groups.items():
        dest = OUT/(group + '.zip')
        with zipfile.ZipFile(dest, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2026, 10, 25, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
            z.writestr('PACKAGE_MANIFEST.json', encoded(dict(group=group,
                       files={n: entries[n] for n in files})))
        if dest.stat().st_size >= 95 * 1024**2:
            raise RuntimeError('Archive too large; split before publishing')
        with zipfile.ZipFile(dest) as z:
            if z.testzip() is not None:
                raise RuntimeError('ZIP CRC mismatch')
            for name in files:
                b = z.read(name)
                if sha(b) != entries[name]['sha256'] or len(b) != entries[name]['bytes']:
                    raise RuntimeError('ZIP payload mismatch: ' + name)
        archives[dest.name] = dict(bytes=dest.stat().st_size, sha256=sha(dest.read_bytes()), files=len(files))
    (OUT/'SUMMARY.md').write_bytes((ROOT/SUMMARY).read_bytes())
    (OUT/'README.md').write_text(
        '# A10结束后的计算工程：B优化评估包\n\n'
        '先读 [SUMMARY.md](SUMMARY.md)。SOURCE.zip 为源码和冻结版本；MODEL_EVIDENCE.zip 为筛选后的文本证据。'
        '解压两个包到同一新目录，保持相对路径，按 MANIFEST.json 核对SHA256。\n\n'
        '不含音频工程、权重、工具SDK、硬件/启动镜像或原始二进制诊断。原件保留，排除范围见 EXCLUDED.json。'
        '当前CMA候选最新修改尚未复验，TT10-01未完成；不得用本包作为板端执行授权或TTFT≤10秒证明。\n\n'
        '历史证据可能引用未收录大文件，完整构建需另行准备固定依赖。此次仅做本地契约/配置及发布完整性检查，未读板。\n',
        encoding='utf-8', newline='\n')
    # Fresh re-read catches files changed by an ongoing local task while packaging.
    changed = [n for n, e in entries.items() if sha((ROOT/n).read_bytes()) != e['source_sha256']]
    if changed:
        dump(OUT/'SOURCE_CHANGED_DURING_PACKAGING.json', changed)
        raise RuntimeError('Source changed during packaging; retained attempt must not publish')
    dump(OUT/'PACKAGE_CHECK.json', dict(domain='PC_PUBLICATION_ONLY', board_contact=False,
         audio_included=False, original_files_deleted=False, zip_crc_pass=True,
         all_published_file_hashes_pass=True, source_snapshot_unchanged=True,
         credential_scan='High-confidence patterns; narrowed credential-key redaction; operator captures excluded',
         numerical_token_fields_preserved=True, archives=archives,
         included_files=len(entries), excluded_files=len(excluded),
         redacted_files=sum(bool(e['redactions']) for e in entries.values())))
    lines = [sha(p.read_bytes()) + '  ' + p.name for p in sorted(OUT.iterdir()) if p.is_file()]
    (OUT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(archives=archives, included=len(entries), excluded=len(excluded)), indent=2))


def publish():
    if git('remote', 'get-url', 'origin').decode().strip() != REMOTE:
        raise RuntimeError('Unexpected remote')
    head = git('rev-parse', 'HEAD')
    staged = git('diff', '--cached', '--raw', '-z')
    paths = [p.relative_to(ROOT).as_posix() for p in sorted(OUT.iterdir()) if p.is_file()]
    paths += [SUMMARY, SELF]
    # Require each release artifact still matches its preparation-time hash.
    for line in (OUT/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, leaf = line.split('  ', 1)
        if sha((OUT/leaf).read_bytes()) != digest:
            raise RuntimeError('Release file changed: ' + leaf)
    with tempfile.TemporaryDirectory(prefix='a10-b-review-index-') as td:
        env = os.environ.copy()
        env['GIT_INDEX_FILE'] = str(Path(td)/'index')
        git('read-tree', BASE, env=env)
        records = []
        for name in paths:
            oid = git('hash-object', '-w', '--no-filters', '--stdin', data=(ROOT/name).read_bytes()).strip()
            records.append(b'100644 '+oid+b'\t'+name.encode('utf-8')+b'\0')
        git('update-index', '-z', '--index-info', data=b''.join(records), env=env)
        tree = git('write-tree', env=env).strip().decode()
        commit = git('-c', 'user.name=Member A (Codex)', '-c', 'user.email=codex@localhost',
                     'commit-tree', tree, '-p', BASE, '-m',
                     'Publish A11 A12 CPU TT10 compute engineering and B review summary').strip().decode()
    changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', BASE, commit)
    if set(changed.decode('utf-8').strip('\0').split('\0')) != set(paths):
        raise RuntimeError('Commit contains unexpected changes')
    for name in paths:
        if git('show', commit+':'+name) != (ROOT/name).read_bytes():
            raise RuntimeError('Commit bytes mismatch: ' + name)
    if head != git('rev-parse', 'HEAD') or staged != git('diff', '--cached', '--raw', '-z'):
        raise RuntimeError('Working branch/index changed; refusing push')
    git('update-ref', 'refs/heads/'+BRANCH, commit, '0'*40)
    push = git('push', 'origin', 'refs/heads/'+BRANCH+':refs/heads/'+BRANCH)
    remote = git('ls-remote', '--heads', 'origin', 'refs/heads/'+BRANCH).decode().strip()
    if remote.split()[0] != commit:
        raise RuntimeError('Remote SHA mismatch')
    unchanged = head == git('rev-parse', 'HEAD') and staged == git('diff', '--cached', '--raw', '-z')
    dump(EV/'PUBLISHED.json', dict(commit=commit, branch=BRANCH, remote=REMOTE,
         base_commit=BASE, remote_verified=True, root_HEAD_and_index_unchanged=unchanged,
         board_contact=False, audio_included=False, files=paths,
         push_stdout=push.decode(errors='replace')))
    if not unchanged:
        raise RuntimeError('Post-push root state changed; inspect receipt')
    print(json.dumps(dict(commit=commit, branch=BRANCH, root_HEAD_and_index_unchanged=unchanged)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['checks', 'prepare', 'publish'])
    action = parser.parse_args().action
    {'checks': checks, 'prepare': prepare, 'publish': publish}[action]()
