"""Receive only B04 interface materials from a fixed Git object, never merge B."""
import hashlib, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
REV = '9a75600e0df8816f4b9134b5c39d67965310dcd3'
DEST = ROOT / 'hw/linear_B_received/B04-scope-9a75600-20261003'
SCOPES = ['docs/b04', 'config/b04/kernel_profile.json', 'vectors/b04_meta',
          'tools/b04_a_preflight.py', 'tools/b04_common.py', 'contracts/sp_linear_v1.h']

def main():
    names = subprocess.check_output(['git','ls-tree','-r','--name-only',REV,'--',*SCOPES], cwd=ROOT).decode().splitlines()
    DEST.mkdir(exist_ok=False, parents=True)
    manifest = {}
    for name in names:
        target = DEST / name
        if not target.resolve().is_relative_to(DEST.resolve()):
            raise ValueError(name)
        raw = subprocess.check_output(['git','show',REV+':'+name], cwd=ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        manifest[name] = {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    (DEST/'RECEIPT.json').write_text(json.dumps({'source_commit':REV,'files':manifest,
        'scope':'B04 interface/meta/preflight only; no B whole-tree merge',
        'acceptance':'NOT_SIGNED','BOARD':'NOT_TESTED'},indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'files':len(manifest),'destination':str(DEST)}))
if __name__ == '__main__': main()
