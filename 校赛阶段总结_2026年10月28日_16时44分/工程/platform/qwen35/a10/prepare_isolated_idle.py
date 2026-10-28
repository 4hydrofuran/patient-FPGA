"""PC-only packaging of an idle candidate. No board, no executable review yet."""
import argparse
import json
from pathlib import Path
import shutil

from isolated_idle_policy import ASSETS, SCOPE, SOURCES, digest, need, verify_bundle


def prepare(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    inputs = {name: root / 'platform/local/a10-minimal-20261021-v1' / name for name in ASSETS}
    inputs['zocl.refcount.ko'] = root / 'A10_refcount_交付包_20261023/A10_refcount_handoff_20261023/reference_artifact/zocl.refcount.ko'
    for name, path in inputs.items():
        need(digest(path) == ASSETS[name], 'input hardware asset mismatch: ' + name)
    output.mkdir()  # refuse any existing path; preserve all older attempts
    for name, path in inputs.items():
        shutil.copyfile(path, output / name)
    for name in SOURCES:
        shutil.copyfile(root / 'platform/qwen35/a10' / name, output / name)
    with (output / 'shell.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(shell_type='XRT_FLAT', num_pl_slots=1, num_aie_slots=0), stream)
    files = {p.name: dict(bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(output.iterdir())}
    manifest = dict(schema='A10_ISOLATED_IDLE_BUNDLE_V1', scope=SCOPE, compute_authorized=False,
                    files=files, review_included=False, board_accepted=False)
    with (output / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
    sha = digest(output / 'manifest.json')
    verify_bundle(output, sha)
    return dict(status='PC_BUNDLE_VERIFIED_NOT_DEPLOYED', source=str(output), files=len(files),
                bytes=sum(f['bytes'] for f in files.values()), manifest_sha256=sha,
                review='MISSING_BY_DESIGN_FRESH_BOARD_REVIEW_REQUIRED', board_access=False)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(prepare(args.project_root, args.output), indent=2))
