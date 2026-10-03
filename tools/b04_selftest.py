"""Compile B's independent probes and inspect original selected-kernel RTL completion bytes."""
import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess

from b04_common import ROOT, META_GROUPS, compiler, digest, now, read_json, run, text_tv, write_json


def main(args):
    work = ROOT / args.work
    work.mkdir(parents=True, exist_ok=False)
    cxx, extra, env = compiler(args.cxx)
    suffix = '.exe' if os.name == 'nt' else ''
    steps = {}
    executables = {}
    for name, source in [('unit', 'private_probe_test.cpp'), ('meta', 'meta_probe_cli.cpp')]:
        executable = work / (name + suffix)
        _, steps[name + '_compile'] = run([cxx, *extra, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                    'tests/b04/' + source, '-o', executable.relative_to(ROOT).as_posix()], ROOT, work / (name + '_compile.log'), env)
        executables[name] = executable.resolve()
    text, steps['unit_run'] = run([str(executables['unit'])], ROOT, work / 'unit.log', env)
    matched = re.search(r'B04 PRIVATE PROBE PASS checks=(\d+)', text)
    if not matched:
        raise RuntimeError('Independent unit checks did not report success')
    groups = {}
    negative_probes = 0
    selected = META_GROUPS if not args.no_archived_rtl else ()
    for group in selected:
        folder = ROOT / 'evidence/b03/batches/double' / group
        manifest = read_json(folder / 'manifest.json')
        names = ['tv/cdatafile/c.w4a8_linear_v1.autotvin_' + name + '.dat'
                 for name in ('gmem_meta', 'meta', 'meta_bytes', 'job_id', 't', 'n', 'k')]
        names.append('tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_meta.dat')
        for name in names:
            entry = manifest['files'][name]
            if (folder / name).stat().st_size != entry['bytes'] or digest(folder / name) != entry['sha256']:
                raise RuntimeError('Original RTL input hash differs: ' + group + '/' + name)
        initial = text_tv(folder / names[0])
        scalars = {name: text_tv(folder / ('tv/cdatafile/c.w4a8_linear_v1.autotvin_' + name + '.dat'))
                   for name in ('meta', 'meta_bytes', 'job_id', 't', 'n', 'k')}
        actual = text_tv(folder / names[-1])
        ids = set(map(int, manifest['cases']))
        if any(set(values) != ids for values in (initial, actual, *scalars.values())):
            raise RuntimeError('Original meta/scalar transaction set differs from manifest')
        cases = []
        for transaction in sorted(actual):
            offset = scalars['meta'][transaction]
            if offset > 24:
                raise RuntimeError('Private 40-byte meta window exceeds original 64-byte bus record')
            before = initial[transaction].to_bytes(64, 'little')[offset:offset + 40]
            wire = actual[transaction].to_bytes(64, 'little')[offset:offset + 40]
            expected_file = ROOT / 'evidence/b03/supplement/rtl_expected' / group / str(transaction) / 'expected_meta.bin'
            expected = expected_file.read_bytes()
            if wire != expected:
                raise RuntimeError('Archived actual meta differs from independent B03 expected')
            meta = struct.unpack('<IIQIIQQ', expected)
            previous = struct.unpack_from('<Q', before, 24)[0] if len(before) >= 32 else 0
            t, n, k, job = (scalars[name][transaction] for name in ('t', 'n', 'k', 'job_id'))
            weight = ((n + 31) // 32 * 32) * ((k + 127) // 128 * 128) // 2 if 1 <= n <= 4864 and 1 <= k <= 4864 else 0
            provided = min(len(wire), scalars['meta_bytes'][transaction])
            target = work / 'rtl_meta' / group / (str(transaction) + '.bin')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(wire[:provided])
            command = [str(executables['meta']), target.relative_to(work).as_posix(), str(job), str(previous), str(weight)]
            result = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=15, check=True)
            probe = json.loads(result.stdout)
            expected_consume = (provided >= 40 and job != 0 and meta[0] == 0x57344138 and meta[1] == 0xB3030002
                                and meta[2] == job and meta[3] == 0 and meta[4] == 1
                                and meta[5] == (previous + 1) % (1 << 64) and meta[6] == weight and weight > 0)
            if probe['consume_y'] != expected_consume:
                raise RuntimeError('Archived meta acceptance differs: ' + group + '/' + str(transaction))
            if expected_consume and probe['public_status'] != 0:
                raise RuntimeError('Valid archived completion did not map to SP_OK')
            cases.append({'transaction': transaction, 'case': manifest['cases'][str(transaction)]['case'],
                          'actual_meta_sha256': digest(target), 'expected_meta_sha256': digest(expected_file), **probe})
            if expected_consume:
                for byte_index in (8, 24):
                    changed = bytearray(wire)
                    changed[byte_index] ^= 1
                    bad = target.with_name(str(transaction) + '_bad_' + str(byte_index) + '.bin')
                    bad.write_bytes(changed)
                    response = subprocess.run([str(executables['meta']), bad.relative_to(work).as_posix(), str(job), str(previous), str(weight)],
                                              cwd=work, env=env, capture_output=True, text=True, timeout=15, check=True)
                    rejection = json.loads(response.stdout)
                    if rejection['consume_y'] or rejection['public_status'] == 0:
                        raise RuntimeError('Changed job/counter was accepted')
                    negative_probes += 1
        groups[group] = {'transactions': len(cases), 'status': 'PASS', 'cases': cases}
        print('PASS B04 actual archived completion ' + group + ': ' + str(len(cases)), flush=True)
    report = {'status': 'PASS', 'finished_at': now(), 'unit_checks': int(matched.group(1)),
              'archived_rtl_meta_transactions': sum(data['transactions'] for data in groups.values()),
              'job_counter_mutation_rejections': negative_probes, 'groups': groups, 'steps': steps,
              'input_sha256': {name: digest(ROOT / name) for name in ('host/b04_private_probe.hpp', 'tests/b04/private_probe_test.cpp', 'tests/b04/meta_probe_cli.cpp', 'tools/b04_selftest.py', 'tools/b04_common.py')},
              'scope': 'CPU conformance probes plus original RTL metadata replay, not new RTL or public XRT lifecycle/BOARD acceptance.'}
    write_json(ROOT / args.receipt, report)
    print('PASS B04 independent private probe checks=' + matched.group(1), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--work', default='build/b04/selftest')
    parser.add_argument('--receipt', default='reports/b04/selftest.receipt.json')
    parser.add_argument('--no-archived-rtl', action='store_true', help='Run only independent small CPU probes; receipt clearly records zero archived calls')
    main(parser.parse_args())
