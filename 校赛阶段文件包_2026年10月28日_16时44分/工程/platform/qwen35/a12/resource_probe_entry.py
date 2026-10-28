"""Portable package audit. This unbound deliverable has no execute command."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def validate_bundle(bundle):
    from resource_probe_policy import require, validate_plan
    bundle = Path(bundle)
    manifest = json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    require(manifest['module_id'] == 'A12_ORDINARY_RESOURCE_PROBE_V1' and
            manifest['authorization_included'] is False, 'not an unbound probe package')
    seen = set()
    for row in manifest['files']:
        name = row['path']
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts and
                '\\' not in name and ':' not in name and name not in seen and name != 'manifest.json',
                'unsafe/duplicate manifest path')
        seen.add(name)
        path = bundle.joinpath(*relative.parts)
        require(all(not p.is_symlink() for p in [path, *path.parents] if p != bundle.parent), 'symlink in payload')
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'package payload differs: ' + name)
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    require(actual == seen | {'manifest.json'}, 'unlisted/missing package files')
    spec = json.loads((bundle/'control/window-spec.json').read_text(encoding='utf-8'))
    requests = json.loads((bundle/'control/requests.json').read_text(encoding='utf-8'))
    worst = validate_plan(requests, spec)
    activation = json.loads((bundle/'control/activation.json').read_text(encoding='utf-8'))
    require(activation == dict(status='UNBOUND_WAITING_RECOVERY_AND_NEW_AUTHORIZATION',
                              execution_enabled=False, authorization_included=False), 'activation differs')
    preflight = json.loads((bundle/'control/preflight.json').read_text(encoding='utf-8'))
    require(preflight == dict(status='FRESH_PREFLIGHT_REQUIRED', boot_id=None, kernel_raw=None), 'stale preflight carried forward')
    backend = json.loads((bundle/'config/backend.pending.json').read_text(encoding='utf-8'))
    require(backend['allow_device_access'] is False, 'backend device access enabled')
    return dict(status='PLAN_ONLY_UNBOUND_PACKAGE_VERIFIED', files=len(seen),
                request_order=[r['id'] for r in requests], calculated_worst_case=worst,
                heavy_diagnostics=False, authorization_included=False, BOARD='NOT_TESTED',
                requires=['current fault recovered', 'independent safe release', 'fresh reviewed preflight',
                          'new explicit compute authorization', 'separate bound driver review'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--plan-only', action='store_true', help='default; local hashes and policy only')
    args = parser.parse_args()
    print(json.dumps(validate_bundle(args.bundle), indent=2))


if __name__ == '__main__':
    main()
