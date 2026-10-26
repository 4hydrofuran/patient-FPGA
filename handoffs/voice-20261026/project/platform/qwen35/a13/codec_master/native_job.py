"""复用既有协作队列协议，隔离新候选；等待真实原生退出才释放预约。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parent
PWSH = 'C:/Users/Fang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
QUEUE = '/mnt/c/Patientqwen/platform/ra02/build_queue.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def hold(attempt):
    central = Path('/home/member-a/kv260-build/ra02-coordinator')
    active = json.loads((central / 'active.json').read_text())
    assert active['job'] == Path.cwd().name
    assert active['owner'] == 'A' and not active['board_authorized']
    work = ROOT / ('local/a13c_' + attempt)
    work.mkdir(exist_ok=False)
    for path in SRC.rglob('*'):
        if path.is_file() and path.suffix in {'.v', '.tcl', '.ps1', '.xdc', '.py'}:
            target = work / 'inputs' / path.relative_to(SRC)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    subprocess.run([sys.executable, '-B', str(work / 'inputs/generate_vectors.py')], cwd=work, check=True)
    if attempt.startswith('b'):
        xsa = Path('/home/member-a/AMDDesignTools/2026.1/Vitis/base_platforms/kv260_base/hw/hw.xsa')
        assert sha(xsa) == '97daf86957a2839965cac39a0a6dc36a4619c96c127ad8fb98b9ca5e960c0630'
        (work / 'official').mkdir()
        with zipfile.ZipFile(xsa) as archive:
            data = archive.read('prj/my_project.srcs/sources_1/bd/MPSoC_ext_platform/MPSoC_ext_platform.bd')
        with (work / 'official/MPSoC_ext_platform.bd').open('xb') as stream:
            stream.write(data)
        if attempt == 'b04':
            # 只复制本任务已退出构建的2026.1标准IP缓存，之后以read权限使用。
            # 缓存逐文件hash纳入本次输入；RTL/顶层仍重新综合实现，不继承旧STA。
            previous = ROOT / 'local/a13c_b03'
            assert (previous / 'NATIVE_COMPLETION.json').is_file()
            shutil.copytree(previous / 'project/codec_master.cache/ip', work / 'ipcache')
    if attempt.startswith('p'):
        previous = ROOT / 'local/a13c_b05'
        complete = json.loads((previous / 'NATIVE_COMPLETION.json').read_text())
        assert complete['exit_code'] == 1
        (work / 'reference').mkdir()
        shutil.copyfile(previous / 'codec_master_routed.dcp', work / 'reference/codec_master_routed.dcp')
    manifest = {p.relative_to(work).as_posix(): sha(p) for p in work.rglob('*') if p.is_file()}
    save(work / 'INPUTS.json', {'files': manifest, 'BOARD': 'NOT_TESTED', 'programming_allowed': False})
    request = {'attempt': attempt, 'job': active['job'], 'request_id': uuid.uuid4().hex,
               'inputs_sha256': sha(work / 'INPUTS.json'), 'BOARD': 'NOT_TESTED'}
    save(work / 'NATIVE_REQUEST.json', request)
    print(json.dumps(request), flush=True)
    while not (work / 'NATIVE_COMPLETION.json').exists():
        time.sleep(1)
    complete = json.loads((work / 'NATIVE_COMPLETION.json').read_text())
    assert all(complete[key] == value for key, value in request.items())
    assert complete['receipt_sha256'] == sha(work / 'native-execution.json')
    receipt = json.loads((work / 'native-execution.json').read_text())
    assert receipt['exit_code'] == complete['exit_code']
    print(json.dumps(complete))
    return complete['exit_code']


def run(attempt):
    assert sys.platform == 'win32'
    work = ROOT / ('local/a13c_' + attempt)
    assert re.fullmatch(r'C:/Patientqwen/local/a13c_[sbp][0-9][0-9]', work.as_posix())
    request = json.loads((work / 'NATIVE_REQUEST.json').read_text())
    assert request['attempt'] == attempt
    assert sha(work / 'INPUTS.json') == request['inputs_sha256']
    for name, digest in json.loads((work / 'INPUTS.json').read_text())['files'].items():
        assert (work / name).resolve().is_relative_to(work.resolve())
        assert sha(work / name) == digest
    queue = json.loads(subprocess.check_output(['wsl', '-d', 'KV260-A-2204', '--', 'python3', QUEUE, 'status']))
    assert queue['active']['job'] == request['job'] and not queue['active']['board_authorized']
    assert not (work / 'NATIVE_COMPLETION.json').exists()
    save(work / 'QUEUE_AT_LAUNCH.json', queue)
    spec = importlib.util.spec_from_file_location('record', ROOT / 'platform/a1/record.py')
    record = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(record)
    code = record.run([PWSH, '-NoProfile', '-File', str(work / 'inputs/run_native.ps1'),
                       '-WorkDir', str(work), '-Mode', {'s': 'sim', 'b': 'build', 'p': 'postcheck'}[attempt[0]]],
                      work / 'native-execution.json', cwd=str(work))
    save(work / 'NATIVE_COMPLETION.json', dict(request, exit_code=code,
         receipt_sha256=sha(work / 'native-execution.json')))
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['hold', 'run'])
    parser.add_argument('attempt')
    args = parser.parse_args()
    assert re.fullmatch(r'[sbp][0-9][0-9]', args.attempt)
    raise SystemExit(hold(args.attempt) if args.mode == 'hold' else run(args.attempt))
