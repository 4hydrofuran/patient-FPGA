"""Apply only two pinned changes to a fresh extracted private driver tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def apply(bundle, source):
    manifest = json.loads((bundle/'manifest.json').read_text())
    patch = bundle/'repair.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != manifest['patch_sha256']:
        raise ValueError('Patch hash mismatch')
    def check(kind):
        for name, row in manifest['files'].items():
            if hashlib.sha256((source/name).read_bytes()).hexdigest() != row[kind+'_sha256']:
                raise ValueError('Driver source mismatch: '+kind+' '+name)
    check('original')
    subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-d',str(source),'-i',str(patch)],check=True)
    check('candidate')
    subprocess.run(['patch','--batch','--reverse','--dry-run','--fuzz=0','-p1','-d',str(source),'-i',str(patch)],check=True)
    print('Two-file candidate hashes and reverse dry-run PASS; originals retained')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    a=p.parse_args()
    apply(a.bundle.resolve(),a.source.resolve())
