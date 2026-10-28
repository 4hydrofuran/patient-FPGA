"""Small offline review package; no installer, board enable or diagnostic originals."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from pl_auth_evidence import ROOT,OUT,WORK,read,save,sha,pin

def main():
    r=read(OUT/'ARTIFACT_REVIEW.json');assert r['PC_cases']==41 and not r['production_enabled']
    work=WORK.with_name(WORK.name[:-1]+'4');base=work/'package';os.umask(0o077);base.mkdir(mode=0o700)
    shutil.copytree(work/'source',base/'source-pc-control-only');shutil.copytree(work/'arm-source',base/'source-a53-unbound')
    (base/'binaries').mkdir();shutil.copyfile(work/'pl-auth-control',base/'binaries/pc-control-test')
    shutil.copyfile(work/'liba12_pl_auth_unbound.so',base/'binaries/liba12_pl_auth_unbound.so')
    shutil.copyfile(work/'pl_auth_portable_probe.o',base/'binaries/pl_auth_portable_probe.o')
    (base/'fixtures').mkdir()
    for name in ('config.json','profile.json','source.json','not-a-bitstream'):shutil.copyfile(work/'cases/normal'/name,base/'fixtures'/name)
    (base/'README.md').write_text('''# A12 PL authorization offline candidate v1

OFFLINE REVIEW ONLY. BOARD NOT_TESTED. NOT DEPLOYABLE. Production activation is
hard disabled before device_open in the A53 backend, and the private attach API
is unsupported outside PC control builds. Editing JSON cannot enable it.

The ordinary resource probe bundle-v2.zip remains the first future board baseline
(SHA256 acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa).
This independent package does not replace that bundle or authorize any board run.

source-pc-control-only includes XRT control doubles, with a fixed zero output
sentinel. It is not a numerical model, HLS simulation, FPGA emulation or timing
benchmark. The fixture is visibly synthetic; not-a-bitstream is NOT an xclbin.
The pc-control-test binary runs only those doubles. source-a53-unbound has no
stub headers; it compiled against the existing official 2026.1 common SDK with
-mcpu=cortex-a53. The portable probe object forces the entire atomic gate to
compile even though board open is disabled. Neither A53 artifact was executed.

Private ownership is reserved before BO transfer, with a single shared debit
and start intent, and checked again directly before run.start. Exact original
meta/finite-Y/timeout/ERT validation precedes completion and caller Y commit.
Unknown transfer/start keeps BO owners and poison state. No release, reset,
takeover, automatic retry, replay or hardware-count fabrication is implemented.

Host atomics cannot atomically cancel a device submission. Revocation after the
last local check may race one start; the explicit start-entry-revoke test rejects
output and retains ownership. This is not a claim of zero DMA after revocation.
The RW page assumes a trusted controlled worker, not hostile-writer isolation.

Still required OFFLINE: real PL manager/legacy router lane integration, bounded
microbatch grant and request journal wiring, independent device-generation /
lease / dual-lock binding, PL mode coordinator integration and end-to-end faults.
Current context facts and random open nonce are diagnostic identity, UNBOUND to
board-generation approval. No board resource or latency saving is measured.
''',encoding='utf-8')
    files=[dict(path=p.relative_to(base).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(base.rglob('*')) if p.is_file()]
    save(base/'manifest.json',dict(schema='A12_PL_AUTH_OFFLINE_UNBOUND_V1',files=files,BOARD='NOT_TESTED',
        production_enabled=False,real_manager_protocol='NOT_IMPLEMENTED',hardware_latency_s=None))
    archive=OUT/'pl-auth-offline-unbound-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(base.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(base).as_posix())
    restored=work/'package-roundtrip';restored.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p=Path(info.filename);assert not p.is_absolute() and '..' not in p.parts
        assert z.testzip() is None;z.extractall(restored)
    manifest=read(restored/'manifest.json')
    for row in manifest['files']:assert sha(restored/row['path'])==row['sha256']
    binary=restored/'binaries/pc-control-test';binary.chmod(0o700)
    cmd=[str(binary),'normal','config.json'];run=subprocess.run(cmd,cwd=restored/'fixtures',capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_ZIP_ROUNDTRIP_AND_EXTRACTED_PC_DOUBLE',
        archive=pin(archive),entries=len(manifest['files'])+1,manifest_sha256=sha(restored/'manifest.json'),
        extracted_PC_command=cmd,exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr,
        total_uncompressed_bytes=sum(row['bytes'] for row in files),BOARD='NOT_TESTED',ARM_executed=False,
        ordinary_probe_replaced=False,production_enabled=False))
    print('PASS_ZIP_ROUNDTRIP_AND_EXTRACTED_PC_DOUBLE')
if __name__=='__main__':main()
