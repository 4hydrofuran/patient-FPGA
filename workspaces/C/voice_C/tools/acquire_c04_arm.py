"""Prepare pinned Linux aarch64 wheels from public PyPI, never install them here."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/c04/arm'
VERSIONS = {'numpy':'2.5.3', 'sherpa-onnx':'1.13.8', 'sherpa-onnx-core':'1.13.8'}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent':'C04-public-pinned-wheel-preparation'})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        for package, version in VERSIONS.items():
            url = f'https://pypi.org/pypi/{package}/{version}/json'
            raw = fetch(url)
            (OUT/f'{package}.pypi.json').write_bytes(raw)
            data = json.loads(raw)
            matches = [r for r in data['urls'] if r['filename'].endswith('.whl') and
                       'aarch64' in r['filename'] and 'manylinux' in r['filename'] and
                       ('cp312-cp312' in r['filename'] if package != 'sherpa-onnx-core' else 'py3-none' in r['filename'])]
            if len(matches) != 1:
                raise ValueError(f'Expected one pinned CPython 3.12 GNU/Linux ARM64 wheel for {package}, found {len(matches)}')
            r = matches[0]
            path = OUT/r['filename']
            if not path.exists():
                payload = fetch(r['url'])
                if hashlib.sha256(payload).hexdigest() != r['digests']['sha256']:
                    raise ValueError('Publisher wheel SHA256 mismatch')
                path.write_bytes(payload)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == r['digests']['sha256']
            records.append(dict(package=package, version=version, filename=r['filename'], url=r['url'],
                metadata_url=url, bytes=path.stat().st_size, sha256=r['digests']['sha256'],
                requires_python=data['info'].get('requires_python'), declared_license=data['info'].get('license'),
                license_expression=data['info'].get('license_expression')))
            print(package, r['filename'], 'HASH_PASS', flush=True)
    except Exception as exc:
        # Distinct attempt records; retain the first restricted-network failure.
        name = 'acquisition_failure_01.json'
        i = 1
        while (OUT/name).exists():
            i += 1; name = f'acquisition_failure_{i:02}.json'
        (OUT/name).write_text(json.dumps(dict(type=type(exc).__name__, message=str(exc), completed=records), indent=2), encoding='utf-8')
        raise
    (OUT/'wheels.lock.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
    (OUT/'requirements-aarch64.lock.txt').write_text(''.join(f'{r["package"]}=={r["version"]} --hash=sha256:{r["sha256"]}\n' for r in records), encoding='utf-8')


if __name__ == '__main__': main()
