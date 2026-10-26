"""Bind an isolated PC build to the exact live-board header tree and sealed drivers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from fingerprint import fingerprint

ROOT=Path(__file__).resolve().parents[4]
E=ROOT/'evidence/a13_A/20261025-muted-kernel1036-v1'
BASE=Path('/home/member-a/a13-muted-headers1036-20261025-v1')
NAMES=('a13_muted_dma.c','a13_muted_serial.c','a13_muted_codec.c','a13_muted_card.c',
       'internal_dmaengine.h','muted_policy.h','Makefile')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',type=int,required=True);args=ap.parse_args()
    receipt=json.loads((E/'header-tree-uart.json').read_text(encoding='utf-8-sig'))
    assert receipt['closed'] and receipt['status']=='READONLY_CAPTURE_COMPLETE_REVIEW_REQUIRED'
    board=receipt['result'];original=BASE/'original/usr/src';actual=fingerprint(original)
    assert all(actual[k]==board[k] for k in actual), 'Extracted headers differ from running board headers'
    out=BASE/f'build-{args.attempt:02d}';out.mkdir(exist_ok=False)
    shutil.copytree(original,out/'headers',symlinks=True)
    modules=out/'modules';modules.mkdir()
    checkpoint=json.loads((ROOT/'evidence/a13_A/20261025-audio-muted-bringup-v1/CHECKPOINT_SEAL.json').read_text())
    pins={}
    for name in NAMES:
        source=ROOT/'evidence/a13_A/20261025-audio-muted-bringup-v1/build-04/modules'/name
        pin=hashlib.sha256(source.read_bytes()).hexdigest()
        assert checkpoint['files'][str(source.relative_to(ROOT)).replace('\\','/')]['sha256']==pin
        shutil.copyfile(source,modules/name);pins[name]=pin
    result={'status':'PC_BUILD_PREPARED_NOT_INSTALLED','attempt':args.attempt,'build_dir':str(out),
        'kernel':'6.8.0-1036-xilinx','package_version':'6.8.0-1036.37','header_tree':actual,
        'header_tree_matches_live_board':True,'driver_source_sha256':pins,'audible_output':False,
        'board_headers_sha256':board['selected_hashes'],'BOARD':'NOT_TESTED'}
    with (out/'INPUTS.json').open('x') as stream:json.dump(result,stream,indent=2)
    with (E/f'build-{args.attempt:02d}-INPUTS.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
