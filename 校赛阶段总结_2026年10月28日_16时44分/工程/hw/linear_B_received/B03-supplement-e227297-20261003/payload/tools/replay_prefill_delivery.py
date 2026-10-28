"""Replay original double RTL Y/meta with an independently compiled dense golden.

Python 3.9+, a C++17 compiler and a little-endian host are sufficient.
No Vitis license, FPGA, prior build directory or executable is required.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ('smoke', 'gate_t1', 'gate_t8', 'down_t1', 'down_t8',
          'stall_basic', 'stall_lifecycle', 'stall_tail', 'stall_max_k', 'stall_max_n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def binary_tv(path, width):
    data = path.read_bytes()
    records, offset = {}, 0
    while data[offset:offset + 8] != bytes.fromhex('5a5aa5a50f0ff0f0'):
        if offset + 8 > len(data):
            raise RuntimeError('Missing binary TV terminator: ' + str(path))
        reserved, depth = struct.unpack_from('>II', data, offset)
        transaction = len(records)
        offset += 8
        end = offset + depth * width
        if end > len(data) or reserved != 0:
            raise RuntimeError('Invalid binary TV record: ' + str(path))
        # HLS binary TV serializes each physical bus word in big-endian order.
        records[transaction] = b''.join(data[i:i + width][::-1] for i in range(offset, end, width))
        offset = end
    if offset + 8 != len(data):
        raise RuntimeError('Extra data after TV terminator: ' + str(path))
    return records


def text_tv(path):
    data = path.read_text(encoding='ascii')
    records = {}
    for transaction, values in re.findall(r'\[\[transaction\]\]\s+(\d+)\s+(.*?)\[\[/transaction\]\]', data, re.S):
        words = re.findall(r'0x([0-9a-fA-F]+)', values)
        if len(words) != 1 or int(transaction) in records:
            raise RuntimeError('Unsupported text TV record: ' + str(path))
        records[int(transaction)] = int(words[0], 16)
    if not records or '[[[runtime]]]' not in data or '[[[/runtime]]]' not in data:
        raise RuntimeError('Invalid scalar/meta TV: ' + str(path))
    return records


def run(args):
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    cxx = shutil.which(args.cxx) or args.cxx
    env = os.environ.copy()
    env['PATH'] = str(Path(cxx).resolve().parent) + os.pathsep + env.get('PATH', '')
    helper = subprocess.check_output([cxx, '-print-prog-name=cc1plus'], env=env, text=True).strip()
    extra = []
    if Path(helper).is_file():
        compiler_dir = str(Path(helper).resolve().parent)
        env['COMPILER_PATH'] = compiler_dir + os.pathsep + str(Path(cxx).resolve().parent)
        extra = ['-B' + compiler_dir + os.sep]
    executable = work / ('replay.exe' if os.name == 'nt' else 'replay')
    compile_args = [cxx, *extra, '-std=c++17', '-O2', '-ffp-contract=off',
                    str(ROOT / 'tests/numerical/replay_archived_rtl.cpp'), '-o', str(executable)]
    with (work / 'compile.log').open('wb') as output:
        subprocess.run(compile_args, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
    result = {'status': 'RUNNING', 'candidate': 'double', 'scope': 'Independent dense golden replay of archived actual RTL, not a new RTL simulation.',
              'compile_arguments': compile_args, 'compile_log_sha256': sha((work / 'compile.log').read_bytes()), 'groups': {}}
    negative_directory = None
    for group in args.groups:
        folder = ROOT / f'evidence/b03/batches/double/{group}'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8-sig'))
        # Check the original manifests before any parsing or numerical acceptance.
        for name, entry in manifest['files'].items():
            if name.startswith('tv/'):
                data = (folder / name).read_bytes()
                if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
                    raise RuntimeError('Original RTL TV hash mismatch: ' + name)
        cdata, rtl = folder / 'tv/cdatafile', folder / 'tv/rtldatafile'
        memory = {bus: binary_tv(cdata / f'c.w4a8_linear_v1.autotvin_{bus}.dat', width)
                  for bus, width in (('gmem_w', 16), ('gmem_sw', 4), ('gmem_x', 16), ('gmem_y', 4))}
        actual_y = binary_tv(rtl / 'rtl.w4a8_linear_v1.autotvout_gmem_y.dat', 4)
        initial_meta = text_tv(cdata / 'c.w4a8_linear_v1.autotvin_gmem_meta.dat')
        actual_meta = text_tv(rtl / 'rtl.w4a8_linear_v1.autotvout_gmem_meta.dat')
        scalars = {name: text_tv(cdata / f'c.w4a8_linear_v1.autotvin_{name}.dat')
                   for name in ('t', 'n', 'k', 'abi_version', 'w_bytes', 'sw_bytes', 'x_bytes', 'sx_bytes', 'y_bytes', 'meta_bytes', 'job_id', 'w_packed', 'sw', 'xq', 'sx', 'y', 'meta')}
        ids = set(map(int, manifest['cases']))
        if any(set(values) != ids for values in (*memory.values(), actual_y, initial_meta, actual_meta, *scalars.values())):
            raise RuntimeError('TV transaction set does not match original manifest')
        outputs = {}
        for transaction in sorted(ids):
            case = manifest['cases'][str(transaction)]
            directory = work / group / str(transaction)
            directory.mkdir(parents=True)
            scalar = {name: values[transaction] for name, values in scalars.items()}
            # Slice merged masters using their recorded byte offsets, not assumed pointer-zero layouts.
            files = {'w.bin': memory['gmem_w'][transaction][scalar['w_packed']:],
                     'sw.bin': memory['gmem_sw'][transaction][scalar['sw']:],
                     'x.bin': memory['gmem_x'][transaction][scalar['xq']:],
                     'sx.bin': memory['gmem_x'][transaction][scalar['sx']:],
                     'y_before.bin': memory['gmem_y'][transaction][scalar['y']:],
                     'y_actual.bin': actual_y[transaction][scalar['y']:],
                     'meta_before.bin': initial_meta[transaction].to_bytes(64, 'little')[scalar['meta']:scalar['meta'] + 40],
                     'meta_actual.bin': actual_meta[transaction].to_bytes(64, 'little')[scalar['meta']:scalar['meta'] + 40]}
            for name, data in files.items():
                (directory / name).write_bytes(data)
            (directory / 'request.txt').write_text(' '.join(str(scalar[name]) for name in ('t','n','k','abi_version','w_bytes','sw_bytes','x_bytes','sx_bytes','y_bytes','meta_bytes','job_id')), encoding='ascii')
            public = case['case'].startswith(('qwen35_', 'prefill_tail_', 'maximum_k_', 'maximum_n_'))
            (directory / 'tolerance.txt').write_text('0.0001 0.00001' if public else '0.000001 0', encoding='ascii')
            # ASCII relative job paths avoid Windows CRT argv code-page conversion of the extraction root.
            completed = subprocess.run([str(executable), str(directory.relative_to(work))], cwd=work, env=env, capture_output=True, text=True)
            (directory / 'replay.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
            if completed.returncode:
                raise RuntimeError(f'{group}/{transaction}: {completed.stderr.strip()}')
            outputs[str(transaction)] = {'case': case['case'], 'status': 'PASS', 'expected': {}}
            for name in ('expected_y.bin', 'expected_meta.bin', 'expected_partials.bin'):
                data = (directory / name).read_bytes()
                outputs[str(transaction)]['expected'][name] = {'bytes': len(data), 'sha256': sha(data)}
                if args.expected_dir:
                    target = args.expected_dir.resolve() / group / str(transaction) / name
                    if args.check_expected:
                        if target.read_bytes() != data:
                            raise RuntimeError('Independent expected differs from delivered file: ' + str(target))
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
            if group == 'gate_t1':
                negative_directory = directory
        result['groups'][group] = {'transactions': len(ids), 'status': 'PASS', 'results': outputs}
        print(f'PASS archived double {group}: {len(ids)} transactions', flush=True)
    # Counterexample tests prove this entry actually checks both output and metadata.
    probes = {}
    if negative_directory:
        for name, byte_offset, expected_error in (('y_actual.bin', 0, 'RTL Y mismatch'), ('meta_actual.bin', 8, 'RTL meta mismatch')):
            target = negative_directory / name
            original = target.read_bytes()
            damaged = bytearray(original)
            if name == 'y_actual.bin':
                damaged[:4] = struct.pack('<f', 0.0)
            else:
                damaged[byte_offset] ^= 1
            target.write_bytes(damaged)
            tested = subprocess.run([str(executable), str(negative_directory.relative_to(work))], cwd=work, env=env, capture_output=True, text=True)
            target.write_bytes(original)
            if tested.returncode == 0 or expected_error not in tested.stderr:
                raise RuntimeError('Negative probe did not reject ' + name)
            probes[name] = {'expected': 'FAIL', 'exit_code': tested.returncode, 'message': tested.stderr.strip(), 'original_restored': True}
    result.update(status='PASS', finished_at_local=datetime.now().astimezone().isoformat(),
                  transactions=sum(v['transactions'] for v in result['groups'].values()), negative_probes=probes,
                  cpp_sha256=sha((ROOT / 'tests/numerical/replay_archived_rtl.cpp').read_bytes()),
                  golden_sha256=sha((ROOT / 'tb/golden_w4a8.hpp').read_bytes()))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'PASS total {result["transactions"]} archived RTL transactions; Y/meta counterexamples rejected', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='g++', help='GCC-compatible C++17 compiler path')
    parser.add_argument('--work', type=Path, required=True, help='New empty replay directory; preserved on failure')
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--groups', nargs='+', choices=GROUPS, default=list(GROUPS))
    parser.add_argument('--expected-dir', type=Path)
    parser.add_argument('--check-expected', action='store_true', help='Compare regenerated independent expected to delivered files')
    arguments = parser.parse_args()
    if arguments.check_expected and not arguments.expected_dir:
        parser.error('--check-expected requires --expected-dir')
    run(arguments)
