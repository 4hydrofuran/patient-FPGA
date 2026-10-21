"""Receive the pinned A07 release without changing A's original files."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request

from b04_common import ROOT, digest, now, safe_path, write_json
from b04_stage import member_name

REVISION = '6dd1a93c2fa44b045276c24f4cc79d94e54b88b3'
REPOSITORY = '4hydrofuran/patient-FPGA'
PREFIX = 'release/a07_b04_v3/'


def request_bytes(url):
    """Retry transient transport failures, recording each failure for provenance."""
    failures = []
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'B04-pinned-receiver'})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read(), failures
        except Exception as error:
            failures.append({'attempt': attempt + 1, 'error': str(error)})
            if attempt == 3:
                raise RuntimeError(json.dumps({'url': url, 'failures': failures})) from error
            time.sleep(min(attempt + 1, 3))


def receive(target, receipt):
    target = Path(target).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError('The received snapshot must stay inside B workspace')
    tree_data, tree_failures = request_bytes(
        'https://api.github.com/repos/' + REPOSITORY + '/git/trees/' + REVISION + '?recursive=1')
    tree = json.loads(tree_data)
    if tree.get('truncated') or tree.get('sha') != REVISION:
        raise ValueError('Incomplete or mismatched Git tree')
    files = [item for item in tree['tree'] if item['type'] == 'blob' and item['path'].startswith(PREFIX)]
    if not files or any(item['mode'] != '100644' for item in files):
        raise ValueError('Unexpected release tree or nonregular file')
    names = [member_name(item['path'][len(PREFIX):]) for item in files]
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError('Case-colliding received paths')
    target.mkdir(parents=True, exist_ok=True)

    def fetch(item):
        name = member_name(item['path'][len(PREFIX):])
        path = safe_path(target, name)
        failures = []
        if path.exists():
            data = path.read_bytes()
        else:
            data, failures = request_bytes('https://raw.githubusercontent.com/' + REPOSITORY + '/' + REVISION + '/' + item['path'])
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
        if len(data) != item['size'] or blob != item['sha']:
            raise ValueError('Received file does not match pinned Git object: ' + name)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return name, {'bytes': len(data), 'git_blob_sha1': blob,
                      'sha256': hashlib.sha256(data).hexdigest(), 'transport_retries': failures}

    checked = {}
    errors = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch, item): item['path'] for item in files}
        for future in as_completed(futures):
            try:
                name, entry = future.result()
                checked[name] = entry
                if len(checked) % 100 == 0:
                    print('Received and Git-verified', len(checked), '/', len(files), flush=True)
            except Exception as error:
                errors.append({'path': futures[future], 'error': str(error)})
    report = {'status': 'FAIL' if errors else 'PASS', 'finished_at': now(),
              'repository': REPOSITORY, 'revision': REVISION, 'subtree': PREFIX,
              'target': str(target), 'expected_files': len(files), 'received_files': len(checked),
              'tree_sha256': hashlib.sha256(tree_data).hexdigest(), 'tree_transport_retries': tree_failures,
              'files': dict(sorted(checked.items())), 'errors': errors,
              'scope': 'Pinned Git reception only; not joint runtime or BOARD acceptance.'}
    write_json(receipt, report)
    if errors:
        raise RuntimeError('Reception incomplete; preserve files and rerun to resume')
    print('PASS A07 pinned reception:', len(checked), 'files', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', default='evidence/b04/a07_received_20261021')
    parser.add_argument('--receipt', default='reports/b04/joint_20261021/receive.json')
    args = parser.parse_args()
    receive(ROOT / args.target, ROOT / args.receipt)
