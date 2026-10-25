"""Prepare a new unbound package from frozen v3 bytes; never run board helpers."""
import argparse
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from resource_probe_entry import sha, validate_bundle
from resource_probe_policy import HARD_RUNS, OFF, validate_plan, require

ROOT = Path(__file__).resolve().parents[3]
PARENT = ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v3/bundle-v4'
OUT = ROOT/'evidence/model_pl_A/20261025-resource-probe-v1'
NAMES = ('resource_probe_policy.py', 'resource_probe_observer.py', 'resource_probe_case.py',
         'resource_probe_entry.py')


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def replace_once(text, before, after):
    require(text.count(before) == 1, 'frozen manager anchor differs')
    return text.replace(before, after, 1)


def derive_manager(before):
    tree = ast.parse(before)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_case')
    lines = before.splitlines(True)
    text = ''.join(lines[:node.lineno-1]) + '''def run_case(worker, owner, path, *, real):
    return execute_case(worker, owner, path, real=real, api=globals())
''' + ''.join(lines[node.end_lineno:])
    marker = '\nSPEC ='
    text = replace_once(text, marker, "\nfrom resource_probe_case import execute_case\nos.environ['SP_TT10_CONFIG']=str(BUNDLE/'control/prefix-config.json')\n"+marker)
    start = text.index("        before = p.snapshot('archive_cache_before')")
    end = text.index("        p.service('stop')", start)
    text = text[:start] + text[end:]
    start = text.index("        s1 = run / 's1'")
    end = text.index('        p.no_users(module_loaded=False)', start)
    text = text[:start] + text[end:]
    start = text.index("        if not capacity['allowed']:")
    end = text.index('        p.wait_prepl_quiet()', start)
    text = text[:start] + "        if not capacity['allowed']:\n            raise RuntimeError('unchanged full BO capacity admission failed; owner retained')\n" + text[end:]
    text = replace_once(text, "    assert os.geteuid() == 0", "    raise PermissionError('UNBOUND probe: future recovery, safe release, fresh binding and separate authorized driver required')\n    assert os.geteuid() == 0")
    # No direct runnable board entry is distributed. The future binding must remove
    # this explicit stop under a new reviewed manifest and authorization.
    old = "if __name__ == '__main__':\n    main()"
    text = replace_once(text, old, "if __name__ == '__main__':\n    raise SystemExit('UNBOUND_RESOURCE_PROBE_NO_COMPUTE_AUTHORIZATION')")
    def stable(source):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name not in ('main', 'run_case')}
    require(stable(before) == stable(text), 'safety class/helper AST changed')
    compile(text, 'resource_probe_manager', 'exec')
    return text


def prepare(destination):
    baseline = json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'))
    require(sha(PARENT/'manifest.json') == baseline['parent_manifest_sha256'], 'parent manifest changed')
    for row in baseline['parent_files']:
        p = PARENT/row['path']
        require(p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'parent bytes changed')
    destination.mkdir(exist_ok=False)
    for row in baseline['parent_files']:
        name = row['path']
        # Old top-level controller entrypoints are not alternative executable routes.
        if name.startswith('control/') and name.endswith('.py') and '/support/' not in name:
            continue
        if name == 'control/preflight.json':
            continue
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT/name, target)
    for name in NAMES:
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name, destination/'platform/qwen35/a12'/name)
    parent_requests = json.loads((PARENT/'control/requests.json').read_text(encoding='utf-8'))
    r0 = copy.deepcopy(next(r for r in parent_requests if r['id'] == 'app_R0'))
    warm = copy.deepcopy(next(r for r in parent_requests if r['id'] == 'warm_prefix'))
    hit = copy.deepcopy(next(r for r in parent_requests if r['id'] == 'app_hit'))
    requests = [r0, warm, hit]
    for r in requests:
        r.pop('prefix_audit', None)
        for key in OFF:
            r.pop(key, None)
        r.update(logits_mode='final', profile=False, diagnostic_report=False,
                 state_fingerprint=False, dump_state=False, a12_consumer_trace=False)
    spec = json.loads((PARENT/'control/window-spec.json').read_text(encoding='utf-8'))
    spec.pop('legacy_reference', None)
    spec.update(window_id='a12-resource-probe-20261025-v1', variant='ordinary_resource_probe',
                request_limit=3, resource_probe=True, authorization_included=False,
                calculated_worst_case=3024)
    validate_plan(requests, spec)
    for name, obj in [('requests.json', requests), ('window-spec.json', spec)]:
        (destination/'control'/name).unlink()
        write(destination/'control'/name, obj)
    write(destination/'control/activation.json', dict(status='UNBOUND_WAITING_RECOVERY_AND_NEW_AUTHORIZATION',
                                                   execution_enabled=False, authorization_included=False))
    write(destination/'control/preflight.json', dict(status='FRESH_PREFLIGHT_REQUIRED', boot_id=None, kernel_raw=None))
    before = (PARENT/'control/cpu01_manager.py').read_text(encoding='utf-8')
    after = derive_manager(before)
    (destination/'control/resource_probe_manager.py').write_text(after, encoding='utf-8', newline='\n')
    # Writeable only in this new directory; old provenance remains frozen in BASELINE.
    evidence = destination/'evidence/RESOURCE_CALL_BUDGET.json'
    budget = json.loads(evidence.read_text(encoding='utf-8'))
    for profile in budget['profiles']:
        if profile['scope'] == 'all':
            profile.update(request_limit=3, prompt_token_limit=128, output_token_limit=8)
    evidence.write_text(json.dumps(budget, indent=2)+'\n', encoding='utf-8')
    readme = '''# A12 ordinary resource probe (unbound, no BOARD authorization)

Run only the local audit: python -B platform/qwen35/a12/resource_probe_entry.py --bundle . --plan-only

Exactly app_R0 -> warm_prefix -> app_hit, old frozen 107/70/37-token workload.
No heavy diagnostic exports, legacy comparison or diagnostic readback.
Original per-submit permissions/fsync, health thresholds, BO/meta validation remain.
Native ARM executable, libraries, XCLBIN and B-origin hardware bytes are unchanged.

The manager intentionally refuses direct execution. There is NO executable board
driver or compute authorization in this deliverable. A separate future reviewed
binding must verify fault recovery, safe release, current identity/boot/kernel,
fresh full preflight, unique lease/locks and explicit compute authorization.
It must pin a new manifest, review the exact manager changes and add the existing
independent/delayed release postchecks. Never activate using old v3 authorization.

Resource-probe results are exploratory. Full numerical/performance acceptance,
teacher review, CMA recovery and actual latency are NOT_TESTED/null here.
The frozen application's old prompt is intentional; no claim about the new short prompt.
'''
    (destination/'README_RESOURCE_PROBE.md').write_text(readme, encoding='utf-8')
    for path in destination.rglob('*.py'):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    manifest = dict(schema_version=1, module_id='A12_ORDINARY_RESOURCE_PROBE_V1', provider='B', maintainer='A',
                    contract_sha256=baseline['contract_files'][0]['sha256'], authorization_included=False,
                    parent_manifest_sha256=baseline['parent_manifest_sha256'], budget=spec,
                    files=[dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
                           for p in sorted(destination.rglob('*')) if p.is_file()])
    # Contract canonical digest is distinct from the contracts.lock file digest.
    manifest['contract_sha256'] = json.loads((PARENT/'manifest.json').read_text())['contract_sha256']
    write(destination/'manifest.json', manifest)
    audit = validate_bundle(destination)
    patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                       fromfile='frozen/cpu01_manager.py', tofile='probe/resource_probe_manager.py'))
    with (destination.parent/('MANAGER-'+destination.name+'.patch')).open('x', encoding='utf-8') as stream:
        stream.write(patch)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=OUT/'bundle-v1')
    args = parser.parse_args()
    audit = prepare(args.destination)
    archive = args.destination.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(args.destination.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(args.destination).as_posix())
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, 'ZIP CRC failed')
    record = dict(status='PREPARED_UNBOUND_NO_BOARD_EXECUTION', local_audit=audit,
                  manifest_sha256=sha(args.destination/'manifest.json'), zip_sha256=sha(archive),
                  zip_bytes=archive.stat().st_size, BOARD='NOT_TESTED', new_PL_calls=0,
                  cma_improvement=None, TTFT_app_s=None, runtime_binary_changed=False)
    write(args.destination.parent/('PACKAGE-'+args.destination.name+'.json'), record)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
