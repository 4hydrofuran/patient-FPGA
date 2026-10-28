"""Prepare only a Python web overlay; never connect to or start the board."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    files = {
        'web_managed.py': ROOT/'system_qwen35/app/web_managed.py',
        'web.pending.json': ROOT/'config/qwen35/web.pending.json',
        'README.md': Path(__file__).with_name('README.md'),
    }
    for name, source in files.items():
        shutil.copyfile(source, destination/name)
    board_sources = json.loads((ROOT/'evidence/frontend_board_A/20261026-inspect-v1/board-sources.json').read_text(encoding='utf-8'))
    reference = board_sources['web_gateway/src/patient_web/managed.py'].encode('utf-8')
    metadata = dict(schema='A_WEB_PYTHON_OVERLAY_V1', status='LOCAL_PREPARED_NOT_DEPLOYED',
                    requires='Accepted PL baseline and completed board handover; bind inside a fresh PS owner window',
                    changes_hardware=False, changes_frontend_reference=False,
                    creates_owner=False, compute_authorization_included=False,
                    original_native_pl_sha256=sha(ROOT/'system_qwen35/app/native_pl.py'),
                    observed_frontend_managed_sha256=hashlib.sha256(reference).hexdigest(),
                    files={name:dict(bytes=(destination/name).stat().st_size, sha256=sha(destination/name)) for name in files})
    (destination/'manifest.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    archive = destination.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name in (*files, 'manifest.json'):
            z.write(destination/name, name)
    return dict(status=metadata['status'], archive=str(archive), bytes=archive.stat().st_size,
                sha256=sha(archive), board_contact=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().output), indent=2))
