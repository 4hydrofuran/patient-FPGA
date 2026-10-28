"""Pin this actual CPU build/dependencies; no hardware/deployment assertions."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
paths=[Path('/home/member-a/qwen35-a05/build-v3')/x for x in ('qwen35-s1','libsp_linear_cpu.so')]
paths+=list(Path('/home/member-a/qwen35-a05/llama-build-v1/bin').glob('*.so'))
files={str(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}
obj={'schema_version':1,'api_version':1,'owner':'A','backend_id':'A_CPU_W4A8_V1','execution_kind':'CPU_REFERENCE','contract_sha256':'83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6','status':'PC_REAL_RUNTIME_VALIDATED_APPLICATION_REGRESSION_IN_PROGRESS','config':'modules/linear_A/cpu_config.json','native_entry':'/home/member-a/qwen35-a05/build-v3/qwen35-s1','shared_library':'/home/member-a/qwen35-a05/build-v3/libsp_linear_cpu.so','files':files,'physical_ubatch':1,'R1':'DISABLED','fallback':'disabled','board':'NOT_TESTED','fpga_available':False,'deployment_budget_bytes':None,'note':'Existing WSL paths, not portable installation package. These are CPU host artifacts, never an FPGA candidate.'}
with (ROOT/'modules/linear_A/manifest.json').open('x') as f:json.dump(obj,f,indent=2)
source={str(p.relative_to(ROOT)):sha(p) for base in ('runtime/qwen35_w4a8','modules/linear_A','platform/qwen35/a05') for p in (ROOT/base).glob('*') if p.is_file()}
with (ROOT/'eval/qwen35/a05/runtime-build-v3.json').open('x') as f:json.dump({'files':files,'source_files':source,'llama_commit':'81e39ad34368329b5db77620721510fd91107e80','instruction_set':'AVX2 runtime-dispatched integer lanes on measured PC, portable CPU path otherwise','fp_flags':['-O3','-fno-fast-math','-ffp-contract=off'],'BOARD':'NOT_TESTED'},f,indent=2)
print(json.dumps({'artifacts':len(files),'source_files':len(source),'domain':'PC'}))
