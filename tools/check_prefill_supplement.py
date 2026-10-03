"""Verify/extract the complete supplement, replay 66 RTL calls and rebuild PC vectors."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(args):
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(args.package) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('ZIP CRC failed')
        manifest = json.loads(archive.read('B03_package_manifest.json'))
        if manifest['candidate'] != 'double':
            raise RuntimeError('Wrong candidate')
        for name, entry in manifest['files'].items():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise RuntimeError('Unsafe ZIP path: ' + name)
            content = archive.read(name)
            if len(content) != entry['bytes'] or sha(content) != entry['sha256']:
                raise RuntimeError('Payload mismatch: ' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for name in ('B03_package_manifest.json', 'B03_supplement_manifest.json'):
            (destination / name).write_bytes(archive.read(name))
        if sum(name.endswith('.xo') for name in archive.namelist()) != 1:
            raise RuntimeError('Expected one frozen candidate XO')
    cxx = shutil.which(args.cxx) or args.cxx
    env = os.environ.copy()
    env['PATH'] = str(Path(cxx).resolve().parent) + os.pathsep + env.get('PATH', '')
    compiler_helper = subprocess.check_output([cxx, '-print-prog-name=cc1plus'], text=True, env=env).strip()
    extra = []
    if Path(compiler_helper).is_file():
        folder = str(Path(compiler_helper).resolve().parent)
        env['COMPILER_PATH'] = folder + os.pathsep + str(Path(cxx).resolve().parent)
        extra = ['-B' + folder + os.sep]
    work = destination / 'work/supplement_check'
    work.mkdir(parents=True)
    steps = {}

    def run(name, command):
        log = work / (name + '.log')
        with log.open('wb') as output:
            completed = subprocess.run(command, cwd=destination, env=env, stdout=output, stderr=subprocess.STDOUT)
        steps[name] = {'exit_code': completed.returncode, 'log_sha256': sha(log.read_bytes()), 'arguments': command}
        if completed.returncode:
            raise RuntimeError(f'{name} failed; original log preserved: {log}')
        print('PASS ' + name, flush=True)
        return log.read_text(encoding='utf-8', errors='replace')

    run('rtl_replay', [sys.executable, 'tools/replay_prefill_delivery.py', '--cxx', cxx,
                       '--work', str(work / 'rtl'), '--receipt', str(work / 'rtl.receipt.json'),
                       '--expected-dir', 'evidence/b03/supplement/rtl_expected', '--check-expected'])
    common = [cxx, *extra, '-std=c++17', '-O2', '-ffp-contract=off', '-Wno-unknown-pragmas',
              '-DB02_CACHE_X', '-DB02_AXI_X128', '-DB03_TEST', '-DB03_REUSE', '-DB03_DOUBLE_BUFFER']
    suffix = '.exe' if os.name == 'nt' else ''
    pc = 'work/supplement_check/numerical' + suffix
    real = 'work/supplement_check/real' + suffix
    run('pc_compile', [*common, 'src/w4a8_prefill_v1.cpp', 'tb/tb_prefill_v1.cpp', '-o', pc])
    (destination / 'vectors/pc_regenerated').mkdir()
    text = run('pc_full50', [str(destination / pc), '--suite', 'full', '--dump', 'vectors/pc_regenerated'])
    if 'B03 PASS suite=full source=synthetic transactions=50' not in text:
        raise RuntimeError('Full50 PASS marker absent')
    run('real_compile', [*common, 'src/w4a8_prefill_v1.cpp', 'tests/numerical/prefill_tensor_replay.cpp', '-o', real])
    (destination / 'vectors/real_regenerated').mkdir()
    text = run('real_weight4', [str(destination / real), 'vectors/real_regenerated'])
    if 'B03 real-tensor PASS cases=4' not in text:
        raise RuntimeError('Real-weight4 PASS marker absent')
    counts = {}
    for original, regenerated in (('vectors/b03_double', 'vectors/pc_regenerated'), ('vectors/b03_double_real', 'vectors/real_regenerated')):
        recorded = {n.removeprefix(original + '/'): v for n, v in manifest['files'].items() if n.startswith(original + '/')}
        actual_names = {p.relative_to(destination / regenerated).as_posix() for p in (destination / regenerated).rglob('*') if p.is_file()}
        if set(recorded) != actual_names:
            raise RuntimeError('Regenerated vector set differs: ' + original)
        for name, entry in recorded.items():
            data = (destination / regenerated / name).read_bytes()
            if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
                raise RuntimeError('Regenerated vector SHA differs: ' + name)
        counts[original] = len(recorded)
    # Re-hash all immutable delivered bytes after the counterexample probes and compilation.
    for name, entry in manifest['files'].items():
        if sha((destination / name).read_bytes()) != entry['sha256']:
            raise RuntimeError('Delivered original changed during verification: ' + name)
    report = {'status': 'PASS', 'finished_at_local': datetime.now().astimezone().isoformat(),
              'package_sha256': sha(args.package.read_bytes()), 'all_payload_hashes_and_crc': 'PASS',
              'candidate_xo_sha256': manifest['files']['artifact/b03_candidate/w4a8_linear_v1.xo']['sha256'],
              'archived_rtl_replay_transactions': 66, 'pc_full50': 'PASS', 'real_weight4': 'PASS',
              'regenerated_vectors_exact_sha_match': counts, 'steps': steps,
              'scope': 'Clean extraction, fresh C++ compilation and replay of original RTL outputs. Not a new RTL run, implementation/BOARD test or A acceptance.'}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PASS clean supplement: archived RTL66 + PC50 + real4 + exact vector regeneration', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--receipt', type=Path, required=True)
    main(parser.parse_args())
