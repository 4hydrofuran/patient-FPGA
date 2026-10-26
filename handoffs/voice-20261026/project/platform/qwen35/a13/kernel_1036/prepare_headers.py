"""PC-only exact-version download/extract; no install or dependency upgrade."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
from fingerprint import fingerprint

ROOT=Path(__file__).resolve().parents[4]
E=ROOT/'evidence/a13_A/20261025-muted-kernel1036-v1'
OUT=Path('/home/member-a/a13-muted-headers1036-20261025-v1')
BASE='https://ports.ubuntu.com/ubuntu-ports/pool/universe/l/linux-xilinx/'
PACKAGES=('linux-xilinx-headers-6.8.0-1036_6.8.0-1036.37_all.deb',
          'linux-headers-6.8.0-1036-xilinx_6.8.0-1036.37_arm64.deb')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare-board-proof',action='store_true');args=ap.parse_args()
    E.mkdir(parents=True,exist_ok=True)
    if args.prepare_board_proof:
        raw=Path(__file__).with_name('fingerprint.py').read_bytes()
        payload=raw+b'\nboard_main()\n';ast.parse(payload)
        with (E/'headers-readonly-payload.py').open('xb') as stream:stream.write(payload)
        print(json.dumps({'payload_sha256':hashlib.sha256(payload).hexdigest(),'board_writes':0}));return
    assert sys.platform=='linux'
    OUT.mkdir(exist_ok=False);cache=OUT/'cache';cache.mkdir();extracted=OUT/'original';extracted.mkdir()
    entries=[]
    for name in PACKAGES:
        path=cache/name;url=BASE+name
        with urllib.request.urlopen(url,timeout=30) as incoming,path.open('xb') as stream:
            count=0
            while True:
                chunk=incoming.read(1048576)
                if not chunk:break
                count+=len(chunk);assert count<67108864;stream.write(chunk)
        fields=subprocess.check_output(['dpkg-deb','-f',str(path),'Package','Version','Architecture'],text=True)
        assert '6.8.0-1036.37' in fields
        subprocess.run(['dpkg-deb','-x',str(path),str(extracted)],check=True)
        entries.append({'url':url,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'control':fields})
    result={'status':'EXACT_HEADER_PACKAGES_EXTRACTED_NOT_INSTALLED','packages':entries,
        'tree':fingerprint(extracted/'usr/src'),'signature_chain':'NOT_CHECKED_USING_INDEPENDENT_LIVE_BOARD_TREE_MATCH_BEFORE_BUILD',
        'board_contact':False,'global_install':False,'kernel_change':False,'original_root':str(extracted)}
    with (E/'download-extract.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
