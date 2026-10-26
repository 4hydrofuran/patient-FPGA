"""Compile/run PC private control boundary, ordinary and ASan/UBSan only."""
import os
import argparse
from pathlib import Path
from resident_evidence import ROOT,OUT,WORK,save
from resident_native import run
import shutil


def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args()
    assert os.name=='posix';folder=WORK/('control-boundary-v'+str(a.revision));folder.mkdir()
    original=ROOT/'platform/qwen35/a12/resident_control_boundary.cpp'
    source=folder/'resident_control_boundary.cpp';shutil.copyfile(original,source)
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root')
    for kind in ('ordinary','sanitizer'):
        binary=folder/kind
        flags=['g++','-std=c++17','-O1','-g','-pthread','-I'+str(WORK/'control-v1/pc-source'),
               '-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu')]
        if kind=='sanitizer':flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
        run(flags+[source,'-l:libcrypto.so.3','-o',binary],'CONTROL_BOUNDARY_COMPILE-'+kind+'-v'+str(a.revision),folder)
        run([binary],'CONTROL_BOUNDARY_RUN-'+kind+'-v'+str(a.revision),folder)
    save(OUT/'CONTROL_BOUNDARY.json',dict(status='PASS_REAL_PC_CONTROL_NINE_NOOP_REQUESTS_AND_SANITIZERS',
        zero_math_calls=True,unknown_flags='SYNTHETIC_SHARED_PAGE_FLAG_FIXTURES_ONLY',BOARD='NOT_TESTED',actual_FPGA_calls=None))


if __name__=='__main__':main()
