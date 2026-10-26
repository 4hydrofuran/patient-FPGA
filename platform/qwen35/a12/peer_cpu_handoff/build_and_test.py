"""Build/run synthetic PC components in a NEW external directory; no model/board."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
sys.dont_write_bytecode = True
from verify_package import verify

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', required=True, type=Path)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--full-shapes', action='store_true')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    verify(root)
    work = args.work.resolve()
    if work == root or work.is_relative_to(root) or root.is_relative_to(work):
        raise ValueError('Use a separate work directory outside package and its ancestors')
    if not 1 <= args.jobs <= 4:
        raise ValueError('jobs must be 1..4')
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SP_A12', 'LD_PRELOAD'))}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    commands = []
    def run(label, argv):
        with (work / (label + '.stdout.txt')).open('wb') as out, (work / (label + '.stderr.txt')).open('wb') as err:
            r = subprocess.run(argv, cwd=work, env=env, stdout=out, stderr=err)
        commands.append({'label': label, 'argv': argv, 'exit_code': r.returncode})
        (work / 'COMMANDS.json').write_text(json.dumps(commands, indent=2) + '\n', encoding='utf-8')
        if r.returncode:
            raise RuntimeError(label + ' failed; logs retained in ' + str(work))
    try:
        build = work / 'build'
        run('configure', ['cmake', '-S', str(root / 'tools'), '-B', str(build),
                         '-DPACKAGE_ROOT=' + str(root), '-DCMAKE_BUILD_TYPE=Release'])
        run('build', ['cmake', '--build', str(build), '--target', 'peer_projection_test', 'peer_profile_test',
                      '--parallel', str(args.jobs)])
        run('projection', [str(build / 'peer_projection_test')] + (['--full-shapes'] if args.full_shapes else []))
        run('profile', [str(build / 'peer_profile_test')])
        result = {'status': 'PASS_PC_SYNTHETIC_COMPONENTS', 'host_machine': platform.machine(),
                  'host_system': platform.system(), 'full_shapes': args.full_shapes,
                  'full_model': 'NOT_TESTED', 'BOARD': 'NOT_TESTED', 'ARM64_cross_build': 'NOT_TESTED',
                  'candidate_optimization': 'NOT_IMPLEMENTED', 'speedup': None,
                  'commands': commands}
        print(json.dumps(result, indent=2))
    except Exception as exc:
        result = {'status': 'FAIL', 'reason': str(exc), 'commands': commands, 'BOARD': 'NOT_TESTED'}
        raise
    finally:
        if 'result' in locals():
            result['log_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in work.glob('*.txt')}
            (work / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
