"""A sole shared-queue job; clean work dirs, no edits to B originals."""
import json
from pathlib import Path
import shutil
import sys
R = Path('/mnt/c/Patientqwen')
E = R / 'evidence/A06_acceptance/a-owned-closeout-v1'
B = R / 'hw/linear_B_received/B03-supplement-e227297-20261003'
sys.path.insert(0, str(R / 'platform/a1'))
from record import run


def main():
    work = Path.cwd()
    result = {}
    result['serialization'] = run(['python3', str(R / 'platform/qwen35/a06/portable_supplement.py'),
                      str(B / 'B03_A06_supplement_20261003.zip'), str(work / 'portable'),
                      '--cxx', '/usr/bin/g++', '--receipt', str(E / 'portable-receipt.json')],
                      E / 'commands/portable.json')
    if result['serialization'] == 0:
        destination = E / 'portable-logs'; destination.mkdir()
        for p in (work / 'portable/work/supplement_check').iterdir():
            if p.is_file() and p.suffix in ['.log', '.json', '.patch']:
                shutil.copyfile(p, destination / p.name)
    # Same installed major version, official license only, no change to target.
    # This is an alternative *real* local Vitis Csim, not native g++ emulation.
    result['windows_csim'] = run([
        '/mnt/c/Patientqwen/platform/local/a1/venv/Scripts/python.exe',
        'C:/Patientqwen/platform/qwen35/a06/closeout_csim.py',
        '--work', 'C:/Patientqwen/platform/build/a06-closeout-native-csim-v1',
        '--label', 'windows-csim-v1'], E / 'commands/windows-csim-launch.json')
    (E / 'job-result.json').write_text(json.dumps(dict(result, work=str(work)), indent=2))
    # Failure is retained as a failed queue job, not suppressed for convenience.
    return int(any(result.values()))


if __name__ == '__main__':
    raise SystemExit(main())
