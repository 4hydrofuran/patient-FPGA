"""PC-only one-call candidate package. No authorization, board access or execution."""
import argparse
import json
from pathlib import Path
import shutil

from single_compute_policy import ASSETS, SCOPE, SOURCES, digest, need, vector, verify_bundle


def prepare(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    idle = root/'platform/local/a10-isolated-idle-20261023-v4'
    need(digest(idle/'manifest.json') == '726723f471aa6bb3f6902b5a65a543402be0cf94202c25e169f89b9703867b06',
         'tested idle source package differs')
    for name, sha in ASSETS.items():
        need(digest(idle/name) == sha, 'hardware asset differs')
    output.mkdir()  # no overwrite/replay
    for name in ASSETS:
        shutil.copyfile(idle/name, output/name)
    for name in SOURCES:
        shutil.copyfile(root/'platform/qwen35/a10'/name, output/name)
    shutil.copyfile(idle/'shell.json', output/'shell.json')
    shutil.copyfile(root/'evidence/board_platform/A10_20261023_isolated_idle_v4/audit_01.json',
                    output/'prior-idle-audit.json')
    with (output/'vector.json').open('x', encoding='utf-8') as stream:
        json.dump(vector(), stream, sort_keys=True, indent=2)
    files = {p.name: dict(bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(output.iterdir())}
    manifest = dict(schema='A10_ISOLATED_SINGLE_BUNDLE_V1', scope=SCOPE, authorization_included=False,
                    max_submissions=1, files=files, board_accepted=False)
    with (output/'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
    pin = digest(output/'manifest.json')
    verify_bundle(output, pin)
    return dict(status='PC_SINGLE_CANDIDATE_PACKAGED_NOT_AUTHORIZED_OR_DEPLOYED',
                files=len(files)+1, payload_bytes=sum(p['bytes'] for p in files.values()),
                manifest_sha256=pin, board_contact=False, compute_submissions=0)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(prepare(args.project_root, args.output)))
