"""A-owned serialization-only repair of B03's clean supplement verifier.

Delivered source/XO/vectors are immutable. Two generated testbench copies write
JSON in binary mode with explicit CRLF, matching the frozen Windows-produced
manifest on both Linux and Windows. No post-hoc value normalization, hash skip,
or numerical/compiler change is permitted.
"""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

PACKAGE_SHA = '506f079daabf37f6dc539d35c49add0b4c0e7629a0a97c461c470b0f75c59513'
WITNESSES = {
    'tb/tb_prefill_v1.cpp': '69952372c1c5cc980c13ce68e931af2243866b48f725a650fd84ccf1f1a61178',
    'tests/numerical/prefill_tensor_replay.cpp': '4a32cf3895d6b9ec85d0073ac7688a47527a3241bb2005b5c3acb7bde4653b05',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(name):
    path = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or path.is_absolute()
            or '..' in path.parts or str(path) != name):
        raise ValueError('Unsafe archive member: ' + name)
    return path


def portable_bench(name, original):
    if name not in WITNESSES or sha(original) != WITNESSES[name]:
        raise ValueError('Unexpected original testbench identity: ' + name)
    # Source CRLF is retained. Only the output stream mode and output newline
    # literal change; no mathematical, error-checking or tolerance code changes.
    text = original.decode('utf-8')
    stream = ('std::ofstream description(prefix + ".json");' if name.startswith('tb/')
              else 'std::ofstream description(prefix+".json");')
    ending = '}\\n";'
    if text.count(stream) != 1 or text.count(ending) != 1:
        raise ValueError('Non-unique serialization patch sites')
    text = text.replace(stream, stream[:-2] + ', std::ios::binary);', 1)
    text = text.replace(ending, '}\\r\\n";', 1)
    return text.encode('utf-8')


def verify_vectors(destination, manifest):
    counts = {}
    for original, regenerated in [('vectors/b03_double', 'vectors/pc_regenerated'),
                                   ('vectors/b03_double_real', 'vectors/real_regenerated')]:
        recorded = {n.removeprefix(original + '/'): v for n, v in manifest['files'].items()
                    if n.startswith(original + '/')}
        folder = destination / regenerated
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        if actual != set(recorded):
            raise ValueError('Regenerated vector set differs: ' + original)
        for name, entry in recorded.items():
            data = (folder / name).read_bytes()
            if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
                raise ValueError('Regenerated vector SHA differs: ' + name)
        counts[original] = len(recorded)
    return counts


def main(args):
    destination = args.destination.resolve()
    if sha(args.package.read_bytes()) != PACKAGE_SHA:
        raise ValueError('Package SHA changed')
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(args.package) as archive:
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('Duplicate member or CRC failure')
        for name in names:
            safe_relative(name)
        manifest = json.loads(archive.read('B03_package_manifest.json'))
        if manifest['candidate'] != 'double':
            raise ValueError('Wrong candidate')
        if set(names) != set(manifest['files']) | {'B03_package_manifest.json', 'B03_supplement_manifest.json'}:
            raise ValueError('Manifest/member set mismatch')
        for name, entry in manifest['files'].items():
            content = archive.read(name)
            if len(content) != entry['bytes'] or sha(content) != entry['sha256']:
                raise ValueError('Payload mismatch: ' + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for name in ('B03_package_manifest.json', 'B03_supplement_manifest.json'):
            (destination / name).write_bytes(archive.read(name))
        if sum(name.endswith('.xo') for name in names) != 1:
            raise ValueError('Expected one frozen candidate XO')
    work = destination / 'work/supplement_check'
    work.mkdir(parents=True)
    overlays = {}
    for name in WITNESSES:
        original = (destination / name).read_bytes()
        data = portable_bench(name, original)
        path = Path(name).with_name('a06_portable_' + Path(name).name)
        (destination / path).write_bytes(data)
        patch = ''.join(difflib.unified_diff(original.decode().splitlines(keepends=True),
                      data.decode().splitlines(keepends=True), fromfile=name, tofile=path.as_posix()))
        (work / (Path(name).name + '.patch')).write_bytes(patch.encode())
        overlays[name] = {'derived_path': path.as_posix(), 'original_sha256': sha(original),
                          'derived_sha256': sha(data), 'owner': 'A',
                          'change': 'JSON output binary mode + explicit CRLF only'}
    cxx = shutil.which(args.cxx) or args.cxx
    env = os.environ.copy()
    env['PATH'] = str(Path(cxx).resolve().parent) + os.pathsep + env.get('PATH', '')
    compiler_helper = subprocess.check_output([cxx, '-print-prog-name=cc1plus'], text=True, env=env).strip()
    extra = []
    if Path(compiler_helper).is_file():
        folder = str(Path(compiler_helper).resolve().parent)
        env['COMPILER_PATH'] = folder + os.pathsep + str(Path(cxx).resolve().parent)
        extra = ['-B' + folder + os.sep]
    steps = {}

    def run(name, command):
        log = work / (name + '.log')
        with log.open('xb') as output:
            completed = subprocess.run(command, cwd=destination, env=env,
                                       stdout=output, stderr=subprocess.STDOUT)
        steps[name] = {'exit_code': completed.returncode, 'log_sha256': sha(log.read_bytes()),
                       'arguments': command, 'cwd': str(destination)}
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
    run('pc_compile', [*common, 'src/w4a8_prefill_v1.cpp', overlays['tb/tb_prefill_v1.cpp']['derived_path'], '-o', pc])
    (destination / 'vectors/pc_regenerated').mkdir()
    text = run('pc_full50', [str(destination / pc), '--suite', 'full', '--dump', 'vectors/pc_regenerated'])
    if 'B03 PASS suite=full source=synthetic transactions=50' not in text:
        raise RuntimeError('Full50 PASS marker absent')
    run('real_compile', [*common, 'src/w4a8_prefill_v1.cpp', overlays['tests/numerical/prefill_tensor_replay.cpp']['derived_path'], '-o', real])
    (destination / 'vectors/real_regenerated').mkdir()
    text = run('real_weight4', [str(destination / real), 'vectors/real_regenerated'])
    if 'B03 real-tensor PASS cases=4' not in text:
        raise RuntimeError('Real-weight4 PASS marker absent')
    counts = verify_vectors(destination, manifest)
    for name, entry in manifest['files'].items():
        if sha((destination / name).read_bytes()) != entry['sha256']:
            raise ValueError('Delivered original changed: ' + name)
    report = {'status': 'PASS_A_SERIALIZATION_OVERLAY', 'owner': 'A',
              'finished_utc': datetime.now(timezone.utc).isoformat(),
              'package_sha256': PACKAGE_SHA, 'all_payload_hashes_and_crc': 'PASS',
              'immutable_payload_files': len(manifest['files']), 'overlays': overlays,
              'candidate_xo_sha256': manifest['files']['artifact/b03_candidate/w4a8_linear_v1.xo']['sha256'],
              'archived_rtl_replay_transactions': 66, 'pc_full50': 'PASS', 'real_weight4': 'PASS',
              'regenerated_vectors_exact_sha_match': counts, 'steps': steps,
              'scope': 'A repair of B serialization. Archived RTL replay, not a new RTL run or BOARD test.',
              'original_strict_failure_preserved': True, 'kernel_source_modified': False}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('PASS A serialization repair: RTL66 + PC50 + real4 + all382 exact SHA; originals unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--receipt', type=Path, required=True)
    main(parser.parse_args())
