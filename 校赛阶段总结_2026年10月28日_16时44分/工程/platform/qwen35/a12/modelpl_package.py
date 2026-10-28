"""Offline source/artifact review bundle; no model assets, deployment or Board enable."""
from pathlib import Path
import hashlib
import shutil
import zipfile
from modelpl_evidence import ROOT,OUT,read,save,sha,pin
def main():
    review=read(OUT/'ARTIFACT_REVIEW.json');assert review['status']=='PASS_ACTUAL_MODEL_PRIVATE_HOOKS_PC_AND_A53_COMPILE_ONLY'
    b=read(OUT/'BUILD-v5.json');a=read(OUT/'ARM_BUILD-v5.json');w=Path(b['workspace']);base=w/'review-package-v1';base.mkdir(mode=0o700)
    shutil.copytree(w/'source',base/'source-native-and-PC-adapter');shutil.copytree(w/'arm-private-backend',base/'source-A53-XRT-unbound')
    (base/'control-review').mkdir();(base/'artifacts').mkdir()
    for name in ('modelpl_manager.py','modelpl_run.py','modelpl_derive.py','modelpl_build.py','modelpl_arm.py','modelpl_evidence.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,base/'control-review'/name)
    for row in [r for r in b['runtime_artifacts'] if r['role'] in ('native','adapter')]+a['artifacts']:
        assert sha(row['path'])==row['sha256'];tag='A53-' if row in a['artifacts'] else 'PC-'
        shutil.copyfile(row['path'],base/'artifacts'/(tag+Path(row['path']).name))
    save(base/'MATH_REFERENCES.json',dict(existing_math_libraries=b['math_libraries_before_and_after'],PC_quant_object=b['imported_quant_object'],
        A53_math_references=a['original_math_before_and_after'],recompiled=False,assets_included=False))
    (base/'README.md').write_text('''# Actual Qwen frontend/Route private-control OFFLINE REVIEW candidate

BOARD NOT_TESTED. NOT DEPLOYABLE. This package contains private frontend/Route
request hooks, a CPU-only mathematical reference adapter, and A53 compile-only
frontend plus hard-disabled XRT backend. No model/sidecar, real bitstream or
board login/recovery/release/installer script is included.

PC validation ran the actual pinned Qwen model, original CPU mathematical DSOs
and original quantization object. It is not a zero-sentinel control probe and
does not claim real PL numerical results. Public six-function ABI and mathematics
were not changed. A separate A12_PLM_PRIVATE_V1 ABI exposes begin/end/abort;
existing private completion reporting remains. The A53 backend still returns
UNSUPPORTED before device_open and refuses positive private begin/end on ARM.
JSON cannot activate it. No A53 artifact was executed.

The actual Route owns legacy open/close permits, binds request digest, validates
private completion and checks each copied matrix output in the graph buffer.
Successful terminal packets follow private end and actual state cleanup. The
manager then requires numerical/content/counter/cleanup checks, END fsync,
receipt fsync and a fresh health delivery fence. Failed/unknown work remains
revoked/dirty, with no automatic retry, replay, unpoison or release.

The acceptance window is still the bounded frozen R0/warm/hit sequence. It is
not an unlimited-request production service. The original ordinary resource
probe bundle is unchanged and remains first for a separately authorized safe
future board window (SHA256 acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa).

This is a review bundle, not a standalone runtime: Python needs repository
dependencies and frozen policy fixtures; binaries retain private build paths
and require pinned mathematical libraries/assets referenced in MATH_REFERENCES.
Reconstructing or running it is not permission to operate a device.

Still required offline: independently checked live Board generation/lease/
dual-lock/driver/kernel/BO approval consumption and PL mode coordination. Actual
PL result consumption, final numerical/long-run/medical acceptance and Board
input-to-answer latency/CMA remain unverified. PC timings are tiny descriptive
samples, exclude startup/UI/voice/network, and are not Board promises.
''',encoding='utf-8')
    files=[dict(path=p.relative_to(base).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(base.rglob('*')) if p.is_file()]
    save(base/'manifest.json',dict(schema='A12_ACTUAL_MODEL_ROUTE_OFFLINE_REVIEW_V1',files=files,BOARD='NOT_TESTED',production_enabled=False,
        real_PL_results_consumed=False,ARM_execution='NOT_EXECUTED',standalone_deployable=False))
    archive=OUT/'actual-model-route-offline-unbound-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(base.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(base).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in files:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_REVIEW_ZIP_ALL_BYTES_ROUNDTRIP',archive=pin(archive),entries=len(files)+1,
        total_uncompressed_bytes=sum(row['bytes'] for row in files),BOARD='NOT_TESTED',production_enabled=False,original_probe_replaced=False))
    print('PASS_REVIEW_ZIP_ALL_BYTES_ROUNDTRIP')
if __name__=='__main__':main()
