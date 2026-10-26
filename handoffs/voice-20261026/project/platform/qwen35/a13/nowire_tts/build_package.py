"""Prepare an isolated ARM64 file-TTS package from existing hashed wheels only.

No pip, target install, dependency upgrade, network or board operation. Wheel
RECORD and AArch64 ELF validation do not prove target imports or ISA execution.
"""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261024-audio-nowire-tts-v1'
OUT = E / 'package-arm64-file-only'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    assert sha(source) == sha(target)


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def safe_member(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts or ':' in name:
        raise ValueError('unsafe archive member')
    return p


def extract_wheel(path, site):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert len(set(names)) == len(names)
        records = [name for name in names if name.endswith('.dist-info/RECORD')]
        assert len(records) == 1
        record = {row[0]: row[1:] for row in csv.reader(io.StringIO(archive.read(records[0]).decode()))}
        for info in archive.infolist():
            relative = safe_member(info.filename)
            assert not any(part.endswith('.data') for part in relative.parts), 'wheel scheme mapping requires explicit review'
            assert (info.external_attr >> 16) & 0o170000 != 0o120000, 'wheel symlink refused'
            if info.is_dir():
                continue
            raw = archive.read(info)
            if info.filename != records[0]:
                digest, size = record[info.filename]
                assert digest.startswith('sha256=') and int(size) == len(raw)
                actual = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
                assert actual == digest.split('=', 1)[1], info.filename
            dest = site / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                assert dest.read_bytes() == raw, ('nonidentical wheel collision', info.filename)
            else:
                with dest.open('xb') as stream:
                    stream.write(raw)


def audit_elf(path):
    with path.open('rb') as stream:
        head = stream.read(64)
    if not head.startswith(b'\x7fELF'):
        return None
    assert head[4:6] == b'\x02\x01' and struct.unpack_from('<H', head, 18)[0] == 183, str(path)
    result = subprocess.run(['/usr/bin/readelf', '-d', '-V', '--wide', str(path)],
                            capture_output=True, text=True, check=True)
    return {'path': path.relative_to(OUT).as_posix(), 'machine': 'AArch64',
            'needed': sorted(set(re.findall(r'\(NEEDED\).*?\[(.*?)\]', result.stdout))),
            'soname': re.findall(r'\(SONAME\).*?\[(.*?)\]', result.stdout),
            'required_versions': sorted(set(re.findall(r'Name: ((?:GLIBC|GLIBCXX|CXXABI)_[\d.]+)', result.stdout)))}


def main():
    assert sys.platform == 'linux', 'local WSL package audit only'
    OUT.mkdir(exist_ok=False)
    inventory = json.loads((ROOT / 'evidence/a13_A/20261024-steps01-02-v3/VOICE_ASSETS.json').read_text())
    chosen = [x for x in inventory['arm64_candidates'] if x['package'] in ['numpy', 'scipy', 'sherpa_onnx', 'sherpa-onnx-core']]
    assert len(chosen) == 4
    site = OUT / 'site-packages'
    wheel_manifest = []
    for entry in chosen:
        wheel = ROOT / entry['path']
        assert sha(wheel) == entry['sha256'] == entry['expected_sha256']
        assert wheel.stat().st_size == entry['bytes']
        copy(wheel, OUT / 'wheels' / wheel.name)
        extract_wheel(wheel, site)
        wheel_manifest.append({key: entry[key] for key in ['path', 'package', 'version', 'sha256', 'bytes', 'requires_dist']})
    lock = json.loads((ROOT / 'modules/voice_A/resources.lock.json').read_text())
    assets = {name: digest for name, digest in lock['files'].items() if
              name.startswith('artifacts/voice_A/matcha-icefall-zh-baker/') or name == 'artifacts/voice_A/vocos-22khz-univ.onnx'}
    assert len(assets) == 19
    for name, digest in assets.items():
        assert sha(ROOT / name) == digest
        copy(ROOT / name, OUT / name)
    copy(ROOT / 'modules/voice_A/resources.lock.json', OUT / 'modules/voice_A/resources.lock.json')
    for path in (ROOT / 'modules/voice_A/file_tts').glob('*.py'):
        copy(path, OUT / 'code/modules/voice_A/file_tts' / path.name)
    copy(Path(__file__).with_name('run-file-tts.sh'), OUT / 'run-file-tts.sh')
    # Internal-only assets keep the existing license restrictions, no upload.
    copy(ROOT / 'modules/voice_A/README.md', OUT / 'UPSTREAM_VOICE_LICENSE_AND_LIMITATIONS.md')
    elf = []
    for path in sorted(site.rglob('*')):
        if path.is_file():
            record = audit_elf(path)
            if record:
                elf.append(record)
    assert elf
    provided = {path.name for path in site.rglob('*') if path.is_file()}
    provided.update(name for entry in elf for name in entry['soname'])
    external = sorted({name for entry in elf for name in entry['needed'] if name not in provided})
    old_env = json.loads((ROOT / 'evidence/a13_A/20261024-step03-v1/BOARD_ENV.json').read_text())
    save(OUT / 'PACKAGE.json', {
        'status': 'PREPARED_OFFLINE_NOT_INSTALLED_NOT_BOARD_VALIDATED',
        'scope': 'TTS_MODEL_TO_FILES_ONLY_NO_DEVICE_API_NO_SP_VOICE_REPLACEMENT',
        'target': {'architecture': 'aarch64', 'python': '3.12', 'glibc_observed_prior': '2.39',
                   'source': '20261024-step03-v1 snapshot; fresh target check required',
                   'prior_SOABI': old_env['python']['soabi']},
        'wheels': wheel_manifest, 'TTS_assets': len(assets),
        'asset_bytes': sum((ROOT / name).stat().st_size for name in assets),
        'elf_count': len(elf), 'elf': elf, 'external_library_names_to_recheck_on_board': external,
        'dependency_closure': 'four selected wheel distributions; scipy->numpy, sherpa_onnx->sherpa-onnx-core; no audio-device packages',
        'target_import_and_symbol_resolution': 'NOT_TESTED', 'A53_instruction_execution': 'NOT_TESTED',
        'BOARD': 'NOT_TESTED', 'playback_allowed': False, 'redistribution_allowed': False,
        'supply_V_now': 3.3, 'total_current_limit_mA_now': 100, 'measured_current_mA': None,
        'runtime_download': False, 'installed': False})
    files = {p.relative_to(OUT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT / 'MANIFEST.json', {'files': files, 'total_bytes': sum(x['bytes'] for x in files.values()),
                                'BOARD': 'NOT_TESTED', 'redistribution_allowed': False})
    print(json.dumps({'status': 'PREPARED_OFFLINE', 'files': len(files),
                      'bytes': sum(x['bytes'] for x in files.values()), 'elf_count': len(elf),
                      'external_libraries': external, 'installed': False, 'BOARD': 'NOT_TESTED'}))


if __name__ == '__main__':
    main()
