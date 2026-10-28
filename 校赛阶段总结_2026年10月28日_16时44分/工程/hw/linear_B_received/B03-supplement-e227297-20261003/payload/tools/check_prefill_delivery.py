"""Verify a delivered payload, then compile/run its candidate in a fresh directory."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main(package, variant, destination, receipt):
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Delivery CRC failed')
        manifest = json.loads(archive.read('B03_package_manifest.json'))
        if manifest['candidate'] != variant:
            raise RuntimeError('Wrong candidate')
        for name, entry in manifest['files'].items():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError('Unsafe archive member')
            content = archive.read(name)
            if sha(content) != entry['sha256'] or len(content) != entry['bytes']:
                raise RuntimeError(f'Payload hash mismatch: {name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    env = os.environ.copy()
    env['PATH'] = 'D:/mingw64/bin;' + env.get('PATH', '')
    helper = 'D:/mingw64/libexec/gcc/x86_64-w64-mingw32/16.2.0'
    env['COMPILER_PATH'] = helper + ';D:/mingw64/bin'
    defines = ['-DB02_CACHE_X', '-DB02_AXI_X128', '-DB03_TEST', '-DB03_REUSE']
    if variant == 'double':
        defines.append('-DB03_DOUBLE_BUFFER')
    common = ['D:/mingw64/bin/g++.exe', '-B' + helper + '/', '-std=c++17', '-O2', '-ffp-contract=off', '-Wno-unknown-pragmas', *defines]
    steps = {}
    def run(name, arguments):
        log = destination / (name + '.log')
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run(arguments, cwd=destination, env=env, stdout=output, stderr=subprocess.STDOUT)
        steps[name] = {'exit_code': result.returncode, 'arguments': arguments, 'log_sha256': sha(log.read_bytes())}
        if result.returncode:
            raise RuntimeError(f'{name} failed: {log}')
        return log.read_text(encoding='utf-8', errors='replace')
    run('native_compile', [*common, 'src/w4a8_prefill_v1.cpp', 'tb/tb_prefill_v1.cpp', '-o', 'clean_numerical.exe'])
    numerical = run('native_test', [str(destination / 'clean_numerical.exe'), '--suite', 'full'])
    if 'B03 PASS suite=full source=synthetic transactions=50' not in numerical:
        raise RuntimeError('Full 50-case PASS absent')
    run('real_compile', [*common, 'src/w4a8_prefill_v1.cpp', 'tests/numerical/prefill_tensor_replay.cpp', '-o', 'clean_real.exe'])
    (destination / 'vectors/clean_real').mkdir(parents=True, exist_ok=True)
    real = run('real_test', [str(destination / 'clean_real.exe'), 'vectors/clean_real'])
    if 'B03 real-tensor PASS cases=4' not in real:
        raise RuntimeError('Four real-weight PC cases absent')
    critical = {name: entry['sha256'] for name, entry in manifest['files'].items()
                if name.startswith(('src/', 'tb/', 'host/', 'reference/', 'tests/', 'contracts/', 'vectors/model_source/'))}
    report = {'status': 'PASS', 'variant': variant, 'finished_at_local': datetime.now().astimezone().isoformat(),
              'scope': 'Clean extracted candidate PC full50 and real-weight4. Final package must retain these exact tested payload hashes.',
              'source_payload_sha256': critical, 'steps': steps}
    receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS clean delivered source: full50 + real-weight4; payload CRC and all file hashes verified')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('variant', choices=['reuse', 'double'])
    parser.add_argument('destination', type=Path)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    main(args.package.resolve(), args.variant, args.destination.resolve(), args.receipt.resolve())
