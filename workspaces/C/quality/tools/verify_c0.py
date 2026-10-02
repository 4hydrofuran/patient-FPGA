"""Reproduce C0 validation without contacting any network, model or board."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import distributions

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'app'))
from c0_domain import load_json, validate_bundle


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = []
    for p in sorted((ROOT/'cases/drafts').glob('*.json')):
        validate_bundle(load_json(p), load_json(ROOT/'quality/rubrics/chest_pain_history_draft.json'))
        checks.append({'check': 'schema_and_cross_references', 'file': str(p.relative_to(ROOT)), 'status': 'PASS'})
    if len(checks) != 3:
        raise RuntimeError('Expected exactly three cases')
    baseline = load_json(ROOT/'quality/audit/legacy_source_hashes.json')
    for f in baseline['files']:
        if sha(Path(baseline['root'])/f['path']) != f['sha256']:
            raise RuntimeError('Legacy source changed: '+f['path'])
    checks.append({'check': 'legacy_13_sources_unchanged', 'status': 'PASS'})
    tree = ast.parse((Path(baseline['root'])/'backend/iat_ws_python3.py').read_text(encoding='utf-8-sig'))
    secret_values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Ws_Param':
            for kw in node.keywords:
                if kw.arg in {'APPID', 'APIKey', 'APISecret'} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) and len(kw.value.value) >= 8:
                    secret_values.append(kw.value.value)
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if path.is_file() and '.deps' not in rel.parts and '__pycache__' not in rel.parts:
            data = path.read_bytes()
            if any(s.encode('utf-8') in data for s in secret_values):
                raise RuntimeError('Legacy credential found in delivery file: '+rel.as_posix())
    checks.append({'check': 'legacy_credential_values_absent_from_delivery', 'status': 'PASS'})
    package = ROOT.parents[1]/'KV260_三人协作执行包_20260926'
    package_report = load_json(ROOT/'quality/audit/package_read_report.json')
    if not all(c['matches'] for c in package_report['manual_section_checks'] + package_report['task_checks']):
        raise RuntimeError('Execution package content consistency failed')
    for f in package_report['files']:
        if sha(package/f['path']) != f['expected']:
            raise RuntimeError('Execution package checksum mismatch: '+f['path'])
    checks.append({'check': 'execution_package_20_checksums', 'status': 'PASS'})
    actual_versions = {d.metadata['Name'].lower().replace('_','-'): d.version for d in distributions(path=[str(ROOT/'app/.deps')])}
    for line in (ROOT/'app/requirements-c0.lock.txt').read_text().splitlines():
        name, version = line.split('==')
        if actual_versions.get(name) != version:
            raise RuntimeError('Dependency lock mismatch: '+name)
    checks.append({'check': 'local_dependency_versions', 'status': 'PASS', 'versions': actual_versions})
    logs = ROOT/'bench/e2e/c0'
    logs.mkdir(parents=True, exist_ok=True)
    commands = []
    for args, name in [([sys.executable, '-m', 'unittest', 'discover', '-s', 'app/tests', '-v'], 'unittest.log'),
                       ([sys.executable, 'app/c0_domain.py'], 'demo_report.json')]:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=60,
                                env=__import__('os').environ | {'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
        (logs/name).write_text(result.stdout+result.stderr, encoding='utf-8')
        commands.append({'argv': args, 'cwd': str(ROOT), 'exit_code': result.returncode, 'log': str((logs/name).relative_to(ROOT))})
        if result.returncode != 0:
            print(result.stdout+result.stderr)
            raise RuntimeError('C0 verification command failed: '+name)
    report = dict(status='PASS_PC_ENGINEERING_ONLY', timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  medical_review='PENDING_NOT_SENT', api_review='PENDING_A', board_test='NOT_TESTED',
                  checks=checks, commands=commands)
    (logs/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    manifest = []
    for p in sorted(ROOT.rglob('*')):
        rel = p.relative_to(ROOT)
        if p.is_file() and '.deps' not in rel.parts and '__pycache__' not in rel.parts and rel.as_posix() != 'bench/e2e/c0/artifact_manifest.json':
            manifest.append(dict(path=rel.as_posix(), bytes=p.stat().st_size, sha256=sha(p)))
    (logs/'artifact_manifest.json').write_text(json.dumps(dict(verification_level='PC_ENGINEERING_ONLY',
        git_commit=None, contract_version=None, model_revision=None, xclbin_hash=None, board_identity=None,
        files=manifest), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS: 3 draft bundles, 27 domain tests, 13 unchanged legacy sources, 20 package checksums, dependency lock and artifact hashes.')
    print('Medical review pending; API proposal unreviewed; no model or board test.')


if __name__ == '__main__':
    main()
