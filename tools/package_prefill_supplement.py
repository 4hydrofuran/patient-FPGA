"""Build one self-contained A06 supplement without changing the frozen candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(args):
    additions = set()
    for folder in ('fixtures', 'vectors/b03_double', 'vectors/b03_double_real', 'evidence/b03/initial_runner', 'evidence/b03/supplement'):
        additions.update(p for p in (ROOT / folder).rglob('*') if p.is_file())
    groups = ('smoke','gate_t1','gate_t8','down_t1','down_t8','stall_basic','stall_lifecycle','stall_tail','stall_max_k','stall_max_n')
    for group in groups:
        additions.update(p for p in (ROOT / f'evidence/b03/batches/double/{group}/tv').rglob('*') if p.is_file())
    additions.update((ROOT / 'reports/b03').glob('supplement*.json'))
    additions.update(ROOT / name for name in ('tests/numerical/replay_archived_rtl.cpp', 'tools/replay_prefill_delivery.py',
                    'tools/check_prefill_supplement.py', 'tools/prepare_prefill_supplement.py', 'tools/package_prefill_supplement.py',
                    'tools/refresh_prefill_baseline_provenance.ps1', 'docs/b03/A06_SUPPLEMENT.md', '.gitattributes'))
    if any(not p.is_file() for p in additions):
        raise RuntimeError('Missing mandatory supplement file')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    files = {}
    with zipfile.ZipFile(args.base) as base, zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        recorded = json.loads(base.read('B03_package_manifest.json'))
        for name, entry in recorded['files'].items():
            data = base.read(name)
            if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
                raise RuntimeError('Original base package hash mismatch: ' + name)
            files[name] = data
        for path in additions:
            if path.suffix in ('.exe', '.obj', '.wdb') or '__pycache__' in path.parts:
                raise RuntimeError('Unexpected build executable/wave in supplement')
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
        if sum(name.endswith('.xo') for name in files) != 1 or sha(files['artifact/b03_candidate/w4a8_linear_v1.xo']) != '96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23':
            raise RuntimeError('Frozen unique candidate changed')
        payload = {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in sorted(files.items())}
        for name, data in sorted(files.items()):
            output.writestr(name, data)
        matrix = {'B06-01': 'XO/source/config/kernel.xml/SHA included; actual ZIP must be transferred to A',
                  'B06-02': 'All selected nominal/stall TV + independent expected + buildable portable replay included',
                  'B06-03': 'Selected current inputs resolved; fresh frozen-baseline Csim50/synth included; old unavailable TB explicitly marked historical',
                  'B06-04': 'Full candidate reports, generated overlap/AXI RTL and buffer/FIFO applicability note included; internal AXI FIFO occupancy unmeasured',
                  'B06-05': 'Fixed synthetic/real replay vectors, original weights/license and per-file SHA included'}
        supplement = {'candidate': 'double', 'status': 'READY_FOR_A_INDEPENDENT_REVIEW', 'A_acceptance': 'NOT_SIGNED_BY_B',
                      'base_package_sha256': sha(args.base.read_bytes()), 'rtl_tv_files': sum('/tv/' in n for n in payload),
                      'rtl_replay_transactions': 66, 'fixed_pc_vector_files': sum(n.startswith('vectors/b03_double/') for n in payload),
                      'fixed_real_vector_files': sum(n.startswith('vectors/b03_double_real/') for n in payload),
                      'checklist': matrix, 'read_first': 'docs/b03/A06_SUPPLEMENT.md'}
        output.writestr('B03_package_manifest.json', json.dumps({'candidate': 'double', 'kind': 'A06_COMPLETE_SUPPLEMENT', 'files': payload,
                         'raw_tv': 'All 270 selected nominal and stall raw TV files included', 'raw_wdb': 'Retained on original host; not required for independent Y/meta replay'}, indent=2))
        output.writestr('B03_supplement_manifest.json', json.dumps(supplement, ensure_ascii=False, indent=2))
    digest = sha(args.output.read_bytes())
    args.output.with_suffix('.sha256.txt').write_text(f'{digest}  {args.output.name}\n', encoding='utf-8')
    print(json.dumps({'status': 'PACKAGED_NOT_YET_CLEAN_VERIFIED', 'path': str(args.output), 'bytes': args.output.stat().st_size,
                      'sha256': digest, 'payload_members': len(payload), **supplement}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
