"""只收集本任务的真实工具记录，独占新目标；不连接板卡或复用失败结果。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def copy(source, target):
    assert source.is_file() and not source.is_symlink(), source
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    assert sha(source) == sha(target)


def save(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def modules():
    receipt = json.loads((E / 'modules-queue-run-v5.json').read_text(encoding='utf-8'))
    result = json.loads(receipt['stdout'])
    assert receipt['exit_code'] == result['exit_code'] == 0
    work = Path(result['cwd'])
    assert work.parent == Path('/home/member-a/kv260-build/ra02-coordinator/work')
    assert '-A-a13-codecm-modules-v5-' in work.name
    out = E / 'module-candidates-v5'
    out.mkdir(exist_ok=False)
    for path in sorted(work.rglob('*')):
        if path.is_file() and (path.suffix in {'.c', '.h', '.ko', '.json', '.patch', '.log', '.txt'} or
                               path.name in {'Makefile', 'Module.symvers', 'modules.order'}):
            copy(path, out / path.relative_to(work))
    count = 0
    for path in (out / 'modules').glob('*.ko'):
        header = path.read_bytes()[:20]
        assert header[:5] == b'\x7fELF\x02' and int.from_bytes(header[18:20], 'little') == 183
        count += 1
    assert count == 3
    for name in ['a13_serial_dai.c', 'a13_codec_card.c']:
        assert sha(out / 'modules' / name) == sha(Path(__file__).resolve().parent / 'drivers' / name)
    stdout = (out / 'stdout.txt').read_text(encoding='utf-8')
    assert stdout.count('vermagic:') == 3 and stdout.count('6.8.12-a10irq2 SMP') == 3
    save(out / 'RESULT.json', {'status': 'PASS_THREE_AARCH64_MATCHING_KERNEL_MODULES',
          'count': 3, 'kernel': '6.8.12-a10irq2', 'source_job': result,
          'BOARD': 'NOT_TESTED', 'installed': False,
          'files': {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}})


def native():
    out = E / 'native-tools'
    out.mkdir(exist_ok=False)
    results = {}
    for attempt in ['s01', 's02', 's03', 's04', 's05', 'b01', 'b02', 'b03', 'b04', 'b05', 'p01', 'p02', 'p03', 'p04']:
        work = ROOT / 'local' / ('a13c_' + attempt)
        complete = json.loads((work / 'NATIVE_COMPLETION.json').read_text(encoding='utf-8'))
        inputs = json.loads((work / 'INPUTS.json').read_text(encoding='utf-8'))
        for name, digest in inputs['files'].items():
            assert sha(work / name) == digest, (attempt, name)
        target = out / attempt
        target.mkdir()
        for path in sorted(work.iterdir()):
            if path.is_file() and (path.suffix in {'.json', '.log', '.rpt', '.txt', '.tcl', '.xdc'}):
                copy(path, target / path.name)
        for folder in ['inputs', 'reports']:
            for path in sorted((work / folder).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    copy(path, target / path.relative_to(work))
        for path in sorted((work / 'project/codec_master.runs').rglob('runme.log')):
            copy(path, target / 'run-logs' / path.relative_to(work / 'project/codec_master.runs'))
        results[attempt] = {'completion': complete, 'inputs_sha256': sha(work / 'INPUTS.json'),
                            'local_attempt': str(work), 'acceptance_not_inferred_from_exit_code': True}
    final = ROOT / 'local/a13c_b05'
    artifacts = out / 'b05/artifacts'
    for name, source in [('codec_master.xsa', final / 'codec_master.xsa'),
                          ('codec_master_routed.dcp', final / 'codec_master_routed.dcp'),
                          ('codec_master.bit', final / 'project/codec_master.runs/impl_1/MPSoC_ext_platform_wrapper.bit')]:
        copy(source, artifacts / name)
    save(out / 'RESULT.json', {'status': 'COLLECTED_NOT_AN_ACCEPTANCE_REPORT',
          'attempts': results, 'BOARD': 'NOT_TESTED', 'deployment_allowed': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['modules', 'native'])
    args = parser.parse_args()
    modules() if args.kind == 'modules' else native()
    print(json.dumps({'collected': args.kind, 'BOARD': 'NOT_TESTED'}))
