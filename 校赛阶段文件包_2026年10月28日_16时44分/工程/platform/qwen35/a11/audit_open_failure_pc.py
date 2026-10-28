"""Extend cold-open fault coverage without connecting to or modifying the board.

Compile both pinned original and diagnostic backend against locally derived,
explicit control doubles. This is NOT a claim about physical driver cleanup or
the cause of the real error. Existing evidence/staged bundle remain immutable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT / 'evidence/mlp_board_A/20261023-integration-v1'
PINNED = {
    PRIOR/'backend-v1/derived/backend.cpp': 'd580ccff42b980933e5dd871048e050435c2d7413243f5c08d1a01154fceb880',
    PRIOR/'backend-diagnostic-v2/derived/backend.cpp': '6465cb04e08b6f8014df65f864ef0e6e321a878cd4e374f84158c75118d238fe',
    ROOT/'platform/qwen35/a07/control/stubs/control_xrt.hpp': '6072542cf9c0e0610c785af007624c9724b2e8e07e264d14168289a129bab4b9',
    ROOT/'platform/local/a11-mlp-20261023-v1/manifest.json': '3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c',
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def main(out):
    for path, expected in PINNED.items():
        need(sha(path) == expected, 'changed pinned source: '+str(path))
    out.mkdir(parents=True, exist_ok=False)
    stubs = out/'stubs'
    shutil.copytree(ROOT/'platform/qwen35/a07/control/stubs', stubs)
    text = (stubs/'control_xrt.hpp').read_text()

    def replace(old, new):
        nonlocal text
        need(text.count(old) == 1, 'ambiguous stub patch: '+old)
        text = text.replace(old, new)

    replace('inline unsigned allocations=0,live=0,device_opens=0,starts=0;',
            'inline unsigned allocations=0,live=0,device_opens=0,starts=0,attempts=0;')
    replace('size_t bytes;int group;uint64_t address;',
            'unsigned ordinal;size_t bytes;int group;uint64_t address;')
    replace('allocation(size_t n,int g):bytes(n)',
            'allocation(size_t n,int g):ordinal(++attempts),bytes(n)')
    replace('fail("allocate");next_address+=n+4096;',
            'fail("allocate_"+std::to_string(ordinal));fail("allocate");next_address+=n+4096;')
    replace('control::fail("group_id");return control::argument_groups.at(arg);',
            'control::fail("group_"+std::to_string(arg));control::fail("group_id");return control::argument_groups.at(arg);')
    replace('size_t size()const{return p->bytes;}',
            'size_t size()const{return control::fault=="size_"+std::to_string(p->ordinal)?p->bytes+1:p->bytes;}')
    replace('control::fault=="bad_address"?UINT64_MAX:p->address;',
            '(control::fault=="bad_address"||control::fault=="address_"+std::to_string(p->ordinal))?UINT64_MAX:p->address;')
    (stubs/'control_xrt.hpp').write_text(text)
    shutil.copyfile(Path(__file__), out/Path(__file__).name)
    harness = ROOT/'platform/qwen35/a11/open_failure_harness.cpp'
    shutil.copyfile(harness, out/harness.name)
    cases = [('normal', 0, None)]
    cases += [(name, 8, phase) for name, phase in (
        ('device_open', 'device_open_and_name'), ('load_xclbin', 'load_xclbin_and_uuid'),
        ('kernel_open', 'kernel_open'), ('run_create', 'run_object_no_submission'))]
    cases += [(f'group_{i}', 8, 'argument_groups') for i in range(6)]
    cases += [(f'allocate_{i+1}', 8, 'allocate_'+name) for i, name in enumerate(('x','sx','y','meta'))]
    cases += [(f'{kind}_{i}', 8, 'verify_bo_ranges') for kind in ('size','address') for i in range(1,5)]
    cases += [('policy_name', 2, 'device_open_and_name'), ('policy_uuid', 2, 'load_xclbin_and_uuid')]
    cases += [(f'policy_group_{i}', 2, 'argument_groups') for i in range(6)]
    need(len(cases) == 31, 'case count drift')
    commands = []

    def call(argv, cwd):
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60)
        entry = dict(argv=argv, cwd=str(cwd), exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
        commands.append(entry)
        (out/'commands.json').write_text(json.dumps(commands, indent=2))
        need(p.returncode == 0, 'PC command failed; see commands.json')
        return entry

    results = {}
    for variant in ('backend-v1', 'backend-diagnostic-v2'):
        target = out/variant
        target.mkdir()
        shutil.copyfile(PRIOR/variant/'derived/backend.cpp', target/'backend.cpp')
        original = read(PRIOR/variant/'commands.json')[0]['argv']
        remap = {
            '-I'+str(ROOT/'platform/qwen35/a07/control/stubs'): '-I'+str(stubs),
            str(PRIOR/variant/'test_api.cpp'): str(out/harness.name),
            str(PRIOR/variant/'derived/backend.cpp'): str(target/'backend.cpp'),
            str(PRIOR/variant/'control-test'): str(target/'open-fault-test'),
        }
        need(all(key in original for key in remap), 'compile command changed')
        call([remap.get(a, a) for a in original], target)
        results[variant] = {}
        for mode, expected, phase in cases:
            folder = target/mode
            folder.mkdir()
            # Explicitly synthetic policies/bitstream; cannot pass production gates.
            fixture = PRIOR/'backend-v1/control-results/open_device_open'
            for filename in ('source.json','profile.json','config.json','not-a-bitstream.txt'):
                shutil.copyfile(fixture/filename, folder/filename)
            profile = read(folder/'profile.json')
            if mode == 'policy_name':
                profile['device_name'] = 'CONTROL_ONLY_WRONG_DEVICE'
            elif mode == 'policy_uuid':
                profile['xclbin_uuid'] = 'CONTROL_ONLY_WRONG_UUID'
            elif mode.startswith('policy_group_'):
                profile['argument_groups'][int(mode.rsplit('_',1)[1])] += 1
            (folder/'profile.json').write_text(json.dumps(profile, indent=2))
            command = call([str(target/'open-fault-test'), mode, 'config.json', str(expected)], folder)
            actual = json.loads(command['stdout'])
            need(actual['status_code'] == expected and actual['mock_submissions'] == 0 and
                 actual['live_stub_allocations'] == 0, 'unexpected PC open result')
            if variant == 'backend-diagnostic-v2':
                rows = [json.loads(line) for line in command['stderr'].splitlines() if line.startswith('{')]
                if expected:
                    need(len(rows) == 1 and rows[0]['phase'] == phase and
                         rows[0]['status_code'] == expected and rows[0]['does_not_prove_resource_release'] is True,
                         'diagnostic mismatch: '+mode)
                else:
                    need(not rows and not command['stderr'], 'unexpected success diagnostic')
            results[variant][mode] = actual
    need(results['backend-v1'] == results['backend-diagnostic-v2'], 'diagnostics changed API behavior')
    for path, expected in PINNED.items():
        need(sha(path) == expected, 'source mutated: '+str(path))
    # Validate the immutable stopped-window seal, including raw board observations.
    seal = read(PRIOR/'stopped_audit_01/SEAL.json')
    for name, record in seal['files'].items():
        path = ROOT/name
        need(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'old seal differs: '+name)
    summary = dict(status='PC_OPEN_FAILURE_COVERAGE_PASS', cases_per_variant=31,
        failed_open_cases_per_variant=30, variants=2, mock_submissions=0,
        tested_failure_phases_match=True, observed_status_codes_unchanged=True,
        prior_sealed_files_unchanged=len(seal['files']), original_board_failure_cause='UNKNOWN',
        board_operations=0, BOARD='NOT_TESTED', physical_cleanup_proven=False,
        recovery_authorized=False, next='Await scoped recovery decision; no new board retry.',
        sources={str(p.relative_to(ROOT)):h for p,h in PINNED.items()})
    (out/'AUDIT.json').write_text(json.dumps(summary, indent=2))
    files = {str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p))
             for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'SEAL.json').write_text(json.dumps(dict(status='PC_ONLY_NOT_BOARD',files=files),indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.resolve())
