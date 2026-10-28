"""Read-only GitHub intake of the explicitly requested B03 snapshot.

No checkout/merge of A, no execution of downloaded scripts, no B workspace scan.
Git blob SHA1 is checked against the commit tree; SHA256 seals local bytes.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
COMMIT = 'fdd1d656290b9cd94152a6525c8be4e083dbd928'
VERSION = 'B03-fdd1d656290b-20261003'
DEST = ROOT / 'hw/linear_B_received' / VERSION
EVIDENCE = ROOT / 'evidence/A06_acceptance/intake-v1'
API = 'https://api.github.com/repos/4hydrofuran/patient-FPGA'
RAW = f'https://raw.githubusercontent.com/4hydrofuran/patient-FPGA/{COMMIT}/'

def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'A06-readonly-intake'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise

def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)

def selected(p):
    return (p in ['README.md', 'PROJECT_STATUS.json', '.gitignore', '.gitattributes',
                  'run_prefill.ps1', 'run_selftest.ps1'] or
            p.startswith(('baseline/b02/', 'src/', 'host/', 'reference/', 'fixtures/',
                          'contracts/', 'tb/tb_prefill', 'tb/golden_',
                          'tests/numerical/prefill', 'tests/support/',
                          'docs/b03/', 'reports/b03/', 'evidence/b03/batches/baseline/',
                          'evidence/b03/verification/', 'evidence/b03/model_source/',
                          'evidence/b03/postcheck_consumer/')) or
            (p.startswith('hls_prefill_') and p.endswith('.cfg')) or
            p in ['tools/archive_prefill_batches.py', 'tools/audit_prefill_replay.py',
                  'tools/complete_prefill_postcheck.ps1', 'tools/summarize_prefill.py',
                  'tools/verify_prefill_artifact.py'])

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for p in ['AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md',
              'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md']:
        target = EVIDENCE / 'before' / p
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue  # preserve original preimage across interrupted downloads
        with target.open('xb') as out, (ROOT / p).open('rb') as inp:
            shutil.copyfileobj(inp, out)
    for label, cmd in [('git-status', ['git', 'status', '--porcelain=v1']),
                       ('git-head', ['git', 'rev-parse', 'HEAD'])]:
        if (EVIDENCE / (label + '.json')).exists():
            continue
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True)
        write_new(EVIDENCE / (label + '.json'), json.dumps({
            'argv':cmd, 'exit_code':result.returncode,
            'stdout':result.stdout.decode('utf-8'),
            'stderr':result.stderr.decode('utf-8')}, indent=2).encode())
    tree_path = EVIDENCE / 'remote-tree.json'
    raw_tree = tree_path.read_bytes() if tree_path.exists() else get(API + f'/git/trees/{COMMIT}?recursive=1')
    tree = json.loads(raw_tree)
    if tree.get('truncated'):
        raise RuntimeError('Truncated remote tree: cannot inventory delivery')
    if not tree_path.exists():
        write_new(tree_path, raw_tree)
    if not (EVIDENCE / 'releases.json').exists():
        write_new(EVIDENCE / 'releases.json', get(API + '/releases'))
    entries = [v for v in tree['tree'] if v['type']=='blob' and selected(v['path'])]
    def download(entry):
        p = PurePosixPath(entry['path'])
        if p.is_absolute() or '..' in p.parts or entry['mode'] not in ('100644','100755'):
            raise ValueError('Unsafe path/mode: ' + str(p))
        target = DEST / str(p)
        data = target.read_bytes() if target.exists() else get(RAW + urllib.parse.quote(str(p)))
        sha1 = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if sha1 != entry['sha'] or len(data) != entry['size']:
            raise ValueError('Remote blob mismatch: ' + str(p))
        if not target.exists():
            write_new(target, data)
        return dict(path=str(p), size=len(data), git_blob_sha1=sha1,
                    sha256=hashlib.sha256(data).hexdigest())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(download, entries))
    manifest = dict(provider='B', source_commit=COMMIT,
                    remote='https://github.com/4hydrofuran/patient-FPGA',
                    branch='b/qwen35-compute', status='RECEIVED_NOT_ACCEPTED',
                    files=sorted(files, key=lambda x:x['path']),
                    remote_xo_paths=[x['path'] for x in tree['tree'] if x['path'].endswith('.xo')],
                    no_whole_repository_merge=True, downloaded_scripts_executed=False)
    write_new(EVIDENCE / 'download-manifest.json', json.dumps(manifest, indent=2).encode())
    print(json.dumps({'files':len(files),'bytes':sum(f['size'] for f in files),
                      'destination':str(DEST),'remote_xo_paths':manifest['remote_xo_paths']}))

if __name__ == '__main__':
    main()
