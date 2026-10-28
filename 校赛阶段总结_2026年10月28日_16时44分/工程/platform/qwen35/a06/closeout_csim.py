"""Exact received double kernel + original A04 reference; real local Vitis Csim.

No license edits, alternate device, or license-check bypass. This runner only
uses the supplied official license and records an unsuccessful checkout as such.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

R = Path(__file__).resolve().parents[3]
B = R / 'hw/linear_B_received/B03-supplement-e227297-20261003/payload'
E = R / 'evidence/A06_acceptance/a-owned-closeout-v1'
sys.path.insert(0, str(R / 'platform/a1'))
from record import run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--license', type=Path, help='Official user-supplied license; never rewritten')
    args = ap.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+', args.label):
        raise ValueError('Unsafe label')
    args.work.mkdir(parents=True, exist_ok=False)
    out = E / args.label
    out.mkdir(exist_ok=False)
    cfg_text = (R / 'evidence/A06_acceptance/supplement-v1/tests/acceptance.cfg').read_text()
    cfg_text = cfg_text.replace('/mnt/c/Patientqwen', R.as_posix())
    cfg = args.work / 'acceptance.cfg'
    cfg.write_text(cfg_text, encoding='utf-8', newline='\n')
    (out / cfg.name).write_bytes(cfg.read_bytes())
    manifest = json.loads((B / 'B03_package_manifest.json').read_text())
    for name, entry in manifest['files'].items():
        if hashlib.sha256((B / name).read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Changed B original: ' + name)
    tool = ('D:/AMDDesignTools/2026.1/Vitis/bin/vitis-run.bat' if os.name == 'nt'
            else '/home/member-a/AMDDesignTools/2026.1/Vitis/bin/vitis-run')
    lic = args.license or (Path('D:/EdgeDownload/Xilinx (1).lic') if os.name == 'nt'
                          else Path('/home/member-a/.Xilinx/kv260-a-rehost-20261003.lic'))
    raw = lic.read_bytes()
    ids = sorted(set(re.findall(r'HOSTID=([0-9a-fA-F]{12})(?:\s|\\|$)', raw.decode(errors='replace'))))
    env = os.environ.copy()
    env['XILINXD_LICENSE_FILE'] = str(lic)
    env.pop('LM_LICENSE_FILE', None)
    identity = {'platform': sys.platform, 'license_path': str(lic),
                'license_sha256': hashlib.sha256(raw).hexdigest(), 'licensed_hostids': ids,
                'actions': 'READ_ONLY_LICENSE; no identity or signature changes'}
    identity['input_sha256'] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), cfg, B / 'src/w4a8_prefill_v1.cpp',
                  B / 'src/w4a8_linear_v1.hpp', R / 'quant/reference/w4a8.cpp',
                  R / 'quant/reference/w4a8.hpp', R / 'platform/qwen35/a06/acceptance.cpp']}
    if os.name != 'nt':
        identity['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        identity['interfaces'] = {p.parent.name: p.read_text().strip()
                                  for p in Path('/sys/class/net').glob('*/address')}
    (out / 'host.json').write_text(json.dumps(identity, indent=2))
    code = run([tool, '--mode', 'hls', '--csim', '--config', cfg.as_posix(),
                '--work_dir', (args.work / 'csim').as_posix()], out / 'csim.json', cwd=args.work, env=env)
    receipt = json.loads((out / 'csim.json').read_text())
    text = receipt.get('stdout', '') + receipt.get('stderr', '')
    summaries = [json.loads(s) for s in re.findall(r'^SUMMARY (\{.*\})\s*$', text, re.M)]
    passed = (code == 0 and 'CSim done with 0 errors' in text and len(summaries) == 1
              and summaries[0]['status'] == 'PASS' and summaries[0]['checks'] == 2800022
              and summaries[0]['cases'] == 61)
    (out / 'result.json').write_text(json.dumps({'exit_code': code, 'numerical_Csim_pass': passed,
          'tool': tool, 'BOARD': 'NOT_TESTED', 'work': str(args.work)}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
