"""Seal partial A11 PC results and actual read-only boot observation, not acceptance."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/mlp_board_A/20261023-preparation-v1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readj(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def writej(p,data):
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)


def main():
    passed=['contracts_01','config_01','intake_01','freeze_02','build_pc_02','build_arm_01','metadata_01','boundary_01']
    for name in passed:
        if readj(OUT/(name+'.json'))['exit_code']!=0:raise ValueError('expected command did not pass: '+name)
    release=ROOT/'release/a07_b04_v3'
    dependencies={}
    for rel in ('modules/linear_A/xrt/host_contract.cpp','modules/linear_A/xrt/host_contract.hpp',
                'modules/linear_A/xrt/release_gate.hpp','contracts/qwen35/sp_linear_v1.h'):
        if (release/rel).read_bytes()!=(ROOT/rel).read_bytes():raise ValueError('build dependency differs from A07: '+rel)
        dependencies[rel]=sha(ROOT/rel)
    pinned=readj(release/'files.sha256.json')['third_party/nlohmann/json.hpp']
    expected=pinned['sha256'] if isinstance(pinned,dict) else pinned
    if sha(release/'third_party/nlohmann/json.hpp')!=expected:raise ValueError('vendor header differs')
    dependencies['release/a07_b04_v3/third_party/nlohmann/json.hpp']=expected
    # ARM v1 and successful PC v2 are built from the identical derivative.
    arm_source=OUT/'pc-build-v1/derived/backend.cpp';pc_source=OUT/'pc-build-v2/derived/backend.cpp'
    if arm_source.read_bytes()!=pc_source.read_bytes():raise ValueError('PC/ARM source mismatch')
    vectors=OUT/'vectors-v2';manifest=readj(vectors/'manifest.json')
    for ident,info in manifest['weights'].items():
        for name,meta in info['files'].items():
            p=vectors/'inputs'/ident/name
            if sha(p)!=meta['sha256'] or p.stat().st_size!=meta['bytes']:raise ValueError('frozen weight changed')
    for ident,info in manifest['cases'].items():
        for section,folder in (('files','inputs'),('golden','pc_reference')):
            for name,meta in info[section].items():
                p=vectors/folder/ident/name
                if sha(p)!=meta['sha256'] or p.stat().st_size!=meta['bytes']:raise ValueError('frozen case changed')
    uart=readj(OUT/'board_preflight_01.json')
    if uart['status']!='COLLECTED_REVIEW_REQUIRED' or uart['closed'] is not True:raise ValueError('UART receipt incomplete')
    clean={}
    for r in uart['records']:
        if r['exit_code']!=0 or not r['completion_marker']:raise ValueError('readonly command incomplete')
        raw=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',r['raw']).replace('\r','')
        m=re.search(r'(?m)^A10_([0-9a-f]+)_BEGIN\n(.*?)\nA10_\1_END:0$',raw,re.S)
        if not m:raise ValueError('unframed UART body')
        clean[r['name']]=m.group(2)
    health=clean['health'];kernel=health.splitlines()[0];boot=health.splitlines()[1]
    temps=[int(x) for x in re.findall(r'temp\d+_input: (\d+)',health)]
    memory={k:int(v) for k,v in re.findall(r'(MemTotal|MemAvailable|CmaTotal|CmaFree):\s+(\d+) kB',health)}
    locks=json.loads(clean['lease_and_lock_metadata'])
    report=dict(schema='A11_PC_PREPARATION_PARTIAL_V1',A11='NOT_PASSED',A12='NOT_ELIGIBLE',
        branch='member-a/a11-preparation-20261023',PROJECT_ROOT=str(ROOT),
        passed_commands=passed,build_dependencies=dependencies,derived_source_sha256=sha(pc_source),
        arm64_library_sha256=sha(OUT/'pc-build-v1/libsp_linear_a11_trial.so'),
        pc_control=readj(OUT/'pc-build-v2/control-results/SUMMARY.json'),
        pc_unit_methods=dict(data_and_actual_linux_flock=9,process_boundary=9),
        frozen_vectors_manifest_sha256=sha(vectors/'manifest.json'),
        fresh_authorization=dict(received=True,scope='Conditional A11 <=23 submissions; no reboot/boot changes',
                                 boot_change_authorized=False,compute_window_entered=False),
        board=dict(domain='BOARD_READONLY_ONLY',kernel=kernel,boot_id=boot,temperatures_mC=temps,memory_kib=memory,
            default_pl_applied='k26-starter-kits_image_1/status: applied' in clean['default_and_network'],
            zocl_absent='ZOCL_ABSENT' in clean['default_and_network'],active_lease=locks['active_exists'],
            kernel_taint_raw=clean['default_and_network'].splitlines()[-1],
            kernel_taint_review='NOT_DONE_NO_MLP_LOADING_ALLOWED',
            compute_submissions=0,explicit_compute_bo_allocations=0,pl_loads=0,system_writes=0,
            COM5_released=True,source='board_preflight_01.json'),
        block='Current kernel is not A10-accepted irq2; separate temporary-boot approval required',
        integration_remaining=['MLP overlay/bit.bin generation and base-DT dry-run audit',
            'Full native multi-call worker and fresh-lease management entry integration plus PC end-to-end tests',
            'Granular end-to-end quant/copy/service accounting and worker raw output persistence',
            'Fresh irq2/platform/log/ABI reads, actual BO limit/address checks, 23-call numerical/timing/release trial'],
        completed_components=['A07/A10 source/evidence intake','XRT218 exported-symbol coverage (not ABI proof)',
            'frozen real layer/captured activation/reference matrix','private no-unlock inherited lock helper',
            'bounded trial backend and host component timers','A10 no-kill/release boundary reuse component'],
        P2=dict(large_memory='NOT_IMPLEMENTED_SAFETY_EXCLUDED',long_stability='NOT_IMPLEMENTED_SAFETY_EXCLUDED',
                HLS_architecture_search='NOT_IMPLEMENTED_OUT_OF_SCOPE',new_hardware_counters='NOT_IMPLEMENTED_OUT_OF_SCOPE'),
        board_service_times=None,bottleneck=None,speedup=None,pure_PL_bandwidth=None,
        preserved_failures={'freeze_01':'hand fixture assumed exact division by 7; fixed exact-representable input, unchanged tolerance',
                            'build_pc_01':'wrong nlohmann include location; use existing pinned A07 vendor header'},
        optimization='NONE; no measured bottleneck yet',history='A00-A17 and all A10 evidence retained')
    if kernel=='6.8.12-a10irq2':raise ValueError('this partial stop summary requires the observed kernel mismatch')
    writej(OUT/'REPORT.json',report)
    snap=OUT/'source_snapshot';snap.mkdir()
    for p in (ROOT/'platform/qwen35/a11').iterdir():
        if p.is_file():shutil.copyfile(p,snap/p.name)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in OUT.rglob('*') if p.is_file()}
    writej(OUT/'seal_01.json',dict(scope='partial PC + read-only observations; NOT A11 board acceptance',files=files))
    print(json.dumps(dict(A11='NOT_PASSED',BOARD_compute=0,current_kernel=kernel,files=len(files),
                         new_boot_approval_required=True)))


if __name__=='__main__':main()
