"""A11 offline intake/ELF audit. No board/network access or ARM execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT/'evidence/mlp_board_A/20261023-preparation-v1'
XRT = Path('/home/member-a/a10-driver-audit-20261018/xrt-userspace')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def capture(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError(f'{argv!r}: exit {p.returncode}: {p.stderr}')
    return dict(argv=argv, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)


def symbols(text, undefined):
    result = set()
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 8 and f[0].rstrip(':').isdigit() and ((f[6] == 'UND') == undefined):
            if f[4] in ('GLOBAL', 'WEAK'):
                result.add(f[7].split('@')[0])
    return result


def run():
    out = EVIDENCE/'intake'
    out.mkdir(parents=True, exist_ok=False)
    before = out/'docs_before'
    before.mkdir()
    for name in ('AGENTS.md','docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md',
                 'docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md'):
        dest = before/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
    release = ROOT/'release/a07_b04_v3'
    manifest = json.loads((release/'files.sha256.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('A07 manifest schema differs')
    rows = {}
    for name in ('artifacts/libsp_linear_xrt_candidate.so','artifacts/w4a8.xclbin',
                 'artifacts/MPSoC_ext_platform.bit','artifacts/MPSoC_ext_platform.hwh',
                 'modules/linear_A/xrt/backend.cpp','modules/linear_A/xrt/host_contract.cpp'):
        p = release/name
        entry = manifest[name]
        expected = entry['sha256'] if isinstance(entry,dict) else entry
        if sha(p) != expected:
            raise ValueError('A07 frozen input mismatch: '+name)
        rows[name] = dict(sha256=sha(p), bytes=p.stat().st_size)
    seal = json.loads((ROOT/'evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json').read_text())
    for name, entry in seal['files'].items():
        if sha(ROOT/name) != entry['sha256']:
            raise ValueError('A10 evidence changed: '+name)
    so = release/'artifacts/libsp_linear_xrt_candidate.so'
    xrt = XRT/'usr/lib/libxrt_coreutil.so.2.18.0'
    dyn = capture(['readelf','--dyn-syms','--wide',str(so)])
    provider = capture(['readelf','--dyn-syms','--wide',str(xrt)])
    dynamic = capture(['readelf','-d','--wide',str(so)])
    versions = capture(['readelf','-V','--wide',str(so)])
    wanted = {s for s in symbols(dyn['stdout'], True) if 'xrt' in s}
    exports = symbols(provider['stdout'], False)
    missing = sorted(wanted-exports)
    save(out/'elf_commands.json', dict(consumer=dyn,provider=provider,dynamic=dynamic,versions=versions))
    report = dict(domain='PC_STATIC_NOT_ARM_EXECUTION', A11='NOT_PASSED',
        board_contact=False, board_authorization=False, A07=rows, A10_seal_files=len(seal['files']),
        xrt218_package_library=dict(path=str(xrt),sha256=sha(xrt)),
        xrt223_consumer_symbols=sorted(wanted), missing_xrt218_symbols=missing,
        xrt_symbol_coverage='FAIL' if missing else 'PASS_STATIC_ONLY',
        caution='Export presence is not C++ ABI/layout or runtime compatibility proof. Cached package is not silently equated to current board library.',
        required_runtime_checks=['fresh exact board XRT and kernel identity','ARM loader/linkage',
            'MLP overlay compatibility','bounded BO allocation/address checks','real numerical/release trial'],
        integration_gaps=['A10 manager holds device flock; unmodified A07 independently reacquires it and conflicts',
            'A07 profile is disabled/pending; no fabricated BOARD_VERIFIED profile',
            'A07 timings combine copy/sync and omit final caller copy from service end; A11 must measure full service externally',
            'A07 has no exposed integer debug output; BOARD integer sums remain null'],
        versions=re.findall(r'Name: ([A-Za-z0-9_.]+)',versions['stdout']))
    save(out/'REPORT.json',report)
    print(json.dumps({k:report[k] for k in ('domain','A11','board_contact','xrt_symbol_coverage','missing_xrt218_symbols')}))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
