"""Publish this chat's case20/frontend delta with a separate Git index; no board IO."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'platform/qwen35'))
import publish_a12_resource_probe as common

BASE = 'dac2141954b99bbed1b1d08377a3730df7e484a9'
BRANCH = 'codex/case20-frontend-updates-20261028'
EV = ROOT / 'evidence/case20_frontend_publication/20261028-v1'
MANIFEST = ROOT / 'release/case20_frontend_updates_20261028/MANIFEST.json'
TEXT = {'.py', '.ps1', '.sh', '.md', '.json', '.jsonl', '.txt', '.png', '.css',
        '.html', '.js', '.toml', '.yaml', '.yml', '.cfg', '.jinja', '.csv'}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def selected():
    files = set()

    def add_tree(relative):
        for p in (ROOT / relative).rglob('*'):
            if (p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts
                    and not p.name.startswith('permission_') and 'test_permission_' not in p.name
                    and (p.suffix in TEXT or p.name in ('.gitignore', '.gitattributes', 'LICENSE'))):
                files.add(p)

    for d in ('platform/qwen35/web', 'bench/qwen35/web', 'system_qwen35/cases',
              'data/patient_cases/chest_pain_20_20261027_v1',
              'evidence/model_pl_A/20261027-case20-natural-v1'):
        add_tree(d)
    for name in ('domain', 'checking', 'planning', 'session', 'cli', 'natural_prompt'):
        files.add(ROOT / f'system_qwen35/app/{name}.py')
    for suffix in ('case20-random-v1', 'cache-debug-v1', 'case-diversity-audit',
                   'frontend-simple-adjust', 'frontend-case-hints', 'frontend-all-case-hints'):
        add_tree('evidence/frontend_board_A/20261027-' + suffix)
    payload = ROOT / 'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1'
    for pattern in ('case20_*.py', 'cache_debug_*.py', 'frontend_simple_adjust.py',
                    'frontend_case_hints.py', 'frontend_all_case_hints.py'):
        files.update(payload.glob(pattern))
    for name in ('A12_CASE20_NATURAL_NOBOARD_20261027.md', 'A12_CASE20_RANDOM_BOARD_20261027.md',
                 'A12_CACHE_DEBUG_BOARD_20261027.md', 'A12_CASE20_DIVERSITY_AUDIT_20261027.md',
                 'A12_CASE20_FRONTEND_DELIVERY_20261028.md'):
        files.add(ROOT / 'docs' / name)
    for name in ('A_A12_CASE20_NATURAL_NOBOARD_20261027.md',
                 'A12_CASE20_RANDOM_BOARD_LIVE_20261027.md', 'A12_CACHE_DEBUG_BOARD_LIVE_20261027.md'):
        files.add(ROOT / 'docs/handoffs' / name)
    files.add(Path(__file__).resolve())
    return files


def prepare():
    EV.mkdir(parents=True, exist_ok=True)
    if common.git('remote', 'get-url', 'origin').decode().strip() != common.REMOTE:
        raise RuntimeError('Unexpected destination')
    if common.git('ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).strip():
        raise RuntimeError('Destination exists; inspect before updating')
    before = common.workspace()
    save(EV / 'WORKSPACE_BEFORE.json', before)
    files = selected()
    findings = []
    for p in sorted(files):
        try:
            common.scan(p.relative_to(ROOT).as_posix(), p.read_bytes())
        except RuntimeError:
            findings.append(p.relative_to(ROOT).as_posix())
    if findings:
        save(EV / 'SCAN_FINDINGS.json', dict(paths=findings, content_withheld=True))
        raise RuntimeError('Credential-pattern review needed; see SCAN_FINDINGS.json')
    save(MANIFEST, dict(base=BASE, branch=BRANCH, board_contact=False,
                       files=[dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size,
                                   sha256=common.digest(p.read_bytes())) for p in sorted(files)],
                       excluded=['Other task changes, A13 and permission scheduler',
                                 'Weights, licenses, credentials, images, old package archives'],
                       entry='docs/A12_CASE20_FRONTEND_DELIVERY_20261028.md'))
    files.add(MANIFEST)
    index = EV / 'publication.index'
    if index.exists():
        raise RuntimeError('Publication index already exists; inspect prepared state')
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    common.git('read-tree', BASE, env=env)
    paths = EV / 'PATHS.nul'
    paths.write_bytes(b''.join(p.relative_to(ROOT).as_posix().encode('utf-8') + b'\0' for p in sorted(files)))
    # Case/cache identities bind original bytes. Bypass text/eol attributes.
    names = [p.relative_to(ROOT).as_posix() for p in sorted(files)]
    ids = common.git('hash-object', '-w', '--no-filters', '--stdin-paths',
                     data=('\n'.join(names) + '\n').encode('utf-8')).splitlines()
    if len(ids) != len(names):
        raise RuntimeError('Blob inventory differs')
    records = b''.join(b'100644 ' + oid + b'\t' + name.encode('utf-8') + b'\0'
                       for name, oid in zip(names, ids))
    common.git('update-index', '-z', '--index-info', data=records, env=env)
    changed = common.git('diff', '--cached', '--name-only', '-z', BASE, env=env).split(b'\0')
    changed = [p.decode('utf-8') for p in changed if p]
    tree = common.git('write-tree', env=env).decode().strip()
    if common.workspace() != before:
        raise RuntimeError('Workspace branch or user index changed')
    save(EV / 'PREPARED.json', dict(base=BASE, branch=BRANCH, tree=tree,
                                  selected_files=len(files), changed_files=len(changed),
                                  bytes=sum(p.stat().st_size for p in files), changed=changed,
                                  workspace_unchanged=True, board_contact=False))
    print(json.dumps(dict(status='PREPARED', selected=len(files), changed=len(changed), tree=tree)))


def publish():
    prepared = json.loads((EV / 'PREPARED.json').read_text(encoding='utf-8'))
    before = common.workspace()
    env = dict(os.environ, GIT_AUTHOR_NAME='Member A (Codex)', GIT_AUTHOR_EMAIL='codex@localhost',
               GIT_COMMITTER_NAME='Member A (Codex)', GIT_COMMITTER_EMAIL='codex@localhost')
    message = ('Integrate 20 chest-pain cases, natural short answers and cache-aware random frontend\n\n'
               'Publish this chat scope and CPU/board evidence. Simplify review actions, hide cache '
               'controls during consultation and remove random-case hints. Preserve cache provenance '
               'and the distinction between 20 records and one chief-complaint category.\n')
    commit = common.git('commit-tree', prepared['tree'], '-p', BASE, data=message.encode(), env=env).decode().strip()
    common.git('update-ref', 'refs/heads/' + BRANCH, commit, '0' * 40)
    common.git('push', 'origin', 'refs/heads/' + BRANCH + ':refs/heads/' + BRANCH)
    remote = common.git('ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).decode().strip()
    if remote.split()[0] != commit:
        raise RuntimeError('Remote commit differs')
    if common.workspace() != before:
        raise RuntimeError('Workspace changed')
    save(EV / 'PUBLISHED.json', dict(status='PUSHED_REMOTE_VERIFIED', commit=commit, branch=BRANCH,
                                    remote=common.REMOTE, workspace_unchanged=True, board_contact=False))
    print(json.dumps(dict(status='PUSHED_REMOTE_VERIFIED', commit=commit, branch=BRANCH)))


if __name__ == '__main__':
    {'prepare': prepare, 'publish': publish}[sys.argv[1]]()
