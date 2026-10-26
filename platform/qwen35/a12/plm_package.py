"""Separate offline REVIEW bundle. No installer, board enable, model or bitstream."""
from pathlib import Path
import shutil
import zipfile
from plm_evidence import ROOT,OUT,read,save,sha,pin
def main():
    review=read(OUT/'ARTIFACT_REVIEW.json');assert review['status']=='PASS_PLM_PC_PROTOCOL_AND_A53_COMPILE_ONLY'
    b=read(OUT/'BUILD-v4.json');w=Path(b['workspace']);base=w/'review-package-v1';base.mkdir(mode=0o700)
    shutil.copytree(w/'source',base/'PC-source');shutil.copytree(w/'arm-source',base/'A53-source');(base/'control-review').mkdir();(base/'artifacts').mkdir()
    shutil.copyfile(w/'observer-exports-v2.map',base/'PC-source/observer-exports.map')
    for name in ('plm_manager.py','plm_page.py','plm_journal.py','plm_run.py','plm_evidence.py','plm_derive.py','plm_build.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,base/'control-review'/name)
    for row in b['artifacts']:
        if Path(row['path']).name=='libplm_observer_ro.so':continue # extra STL exports kept only as old evidence
        shutil.copyfile(row['path'],base/'artifacts'/Path(row['path']).name)
    for row in b['ARM_artifacts']:shutil.copyfile(row['path'],base/'artifacts'/Path(row['path']).name)
    observer=read(OUT/'OBSERVER_REVIEWED-v2.json');armobserver=read(OUT/'OBSERVER_ARM-v2.json.receipt')
    for row in (observer,armobserver):
        assert sha(row['library'])==row['sha256'];shutil.copyfile(row['library'],base/'artifacts'/Path(row['library']).name)
    (base/'README.md').write_text('''# A12 PL manager protocol OFFLINE REVIEW candidate

BOARD NOT_TESTED. NOT DEPLOYABLE. No model inference, mathematical acceptance or
hardware latency result is contained in these CONTROL tests. The probe runs the
actual derived backend ABI against XRT control doubles with fixed zero output,
72 small synthetic weights and a fixed control call plan. It is not Qwen inference.

The original ordinary R0/warm/hit resource probe remains unchanged and first for a
future separately authorized safe board window. Original bundle-v2.zip SHA256:
acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa

The A53 backend hard returns UNSUPPORTED before device_open; private request
APIs are unsupported on ARM. JSON cannot enable it. A53 backend/writer/full
protocol object and RO observer were only cross-compiled, never executed.

The legacy router/open/load permission BODY is preserved and exercised in
separate DSOs. A separate private lane binds actual control-context facts, a
real inherited atomic page, per-request digest/generation and grants of at most
72 jobs. Every transfer/start rechecks authority locally; cached credits keep
the granted T. The request/grant log is bounded to 4096 records and 4 MiB, with
full fresh history checks at request boundaries, not per projection. END plus
durable receipt plus fresh delivery fence is required for control-result return.

This package is for review and source comparison, not a standalone runtime or
installer: Python sources require the repository's pinned modules and frozen
request/config fixtures; ELF RPATHs retain the original private WSL build paths.
Unzipping or executing an artifact is not permission to operate a device.

It includes no real weights, FPGA bitstream, heavy projection/state diagnostics,
board login/recovery/release scripts or real-patient data. On fault, unknown
ownership, dirty state and failed records are retained; no automatic close,
release, reset, replay or platform takeover is authorized. A PC process exit
cannot prove board DMA quiescence. RW authority assumes a trusted worker.

Still incomplete: actual Qwen route/frontend request hooks and private bootstrap,
independent live Board boot/lease/dual-lock/driver/kernel/BO-generation approval,
and PL mode coordinator integration and associated end-to-end acceptance.
No Board CMA or input-to-answer latency saving is measured or promised.
''',encoding='utf-8')
    files=[dict(path=p.relative_to(base).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(base.rglob('*')) if p.is_file()]
    save(base/'manifest.json',dict(schema='A12_PLM_OFFLINE_REVIEW_UNBOUND_V1',files=files,BOARD='NOT_TESTED',production_enabled=False,
        model_or_math_acceptance=False,board_latency_saving_s=None,standalone_deployment_package=False))
    archive=OUT/'plm-control-offline-unbound-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(base.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(base).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in files:
            import hashlib
            assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_REVIEW_ZIP_ALL_BYTES_ROUNDTRIP',archive=pin(archive),entries=len(files)+1,
        total_uncompressed_bytes=sum(x['bytes'] for x in files),BOARD='NOT_TESTED',production_enabled=False,ordinary_probe_replaced=False,standalone_deployable=False))
    print('PASS_REVIEW_ZIP_ALL_BYTES_ROUNDTRIP')
if __name__=='__main__':main()
