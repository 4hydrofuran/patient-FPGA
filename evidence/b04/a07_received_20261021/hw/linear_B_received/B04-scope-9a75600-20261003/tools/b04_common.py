"""Small standard-library helpers shared by B04 profile, selftest and packaging."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ['-DB02_CACHE_X', '-DB02_AXI_X128', '-DB03_TEST', '-DB03_REUSE', '-DB03_DOUBLE_BUFFER']
PUBLIC_SYMBOLS = ['sp_linear_open_v1', 'sp_linear_load_v1', 'sp_linear_run_v1',
                  'sp_linear_report_v1', 'sp_linear_unload_v1', 'sp_linear_close_v1']
META_GROUPS = ('smoke', 'gate_t1', 'gate_t8', 'down_t1', 'down_t8',
               'stall_basic', 'stall_lifecycle', 'stall_tail', 'stall_max_k', 'stall_max_n')


def text_tv(path):
    """Read one scalar/512-bit meta word per original HLS text transaction."""
    data = Path(path).read_text(encoding='ascii')
    records = {}
    for transaction, values in re.findall(r'\[\[transaction\]\]\s+(\d+)\s+(.*?)\[\[/transaction\]\]', data, re.S):
        words = re.findall(r'0x([0-9a-fA-F]+)', values)
        if len(words) != 1 or int(transaction) in records:
            raise ValueError('Unsupported or duplicate text TV record: ' + str(path))
        records[int(transaction)] = int(words[0], 16)
    if not records or '[[[runtime]]]' not in data or '[[[/runtime]]]' not in data:
        raise ValueError('Invalid scalar/meta TV: ' + str(path))
    return records


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def compiler(cxx):
    executable = shutil.which(cxx) or cxx
    env = os.environ.copy()
    env['PATH'] = str(Path(executable).resolve().parent) + os.pathsep + env.get('PATH', '')
    helper = subprocess.check_output([executable, '-print-prog-name=cc1plus'], text=True, env=env, timeout=20).strip()
    extra = []
    if Path(helper).is_file():
        folder = str(Path(helper).resolve().parent)
        env['COMPILER_PATH'] = folder + os.pathsep + str(Path(executable).resolve().parent)
        extra = ['-B' + folder + os.sep]
    return executable, extra, env


def run(command, cwd, log, env=None, timeout=120):
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('wb') as output:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=output,
                                stderr=subprocess.STDOUT, timeout=timeout)
    evidence = {'arguments': [str(arg) for arg in command], 'exit_code': result.returncode,
                'log_sha256': digest(log)}
    if result.returncode:
        raise RuntimeError('Command failed; original log preserved: ' + str(log))
    return log.read_text(encoding='utf-8', errors='replace'), evidence


def safe_path(base, name):
    path = (Path(base) / name).resolve()
    if not path.is_relative_to(Path(base).resolve()):
        raise ValueError('Path escapes delivery root: ' + name)
    return path
