"""Generate local CPU candidate manifest from actual files; no stage-pass claim."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];out=ROOT/'eval/qwen35/a05/batch-fix-v1'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
version=sys.argv[1] if len(sys.argv)>1 else 'v6';assert version in ('v6','v7','v8')
lib_version={'v6':'v2','v7':'v3','v8':'v4'}[version]
paths=[Path('/home/member-a/qwen35-a05/build-'+version)/x for x in ('qwen35-s1','libsp_linear_cpu.so')]
paths+=list(Path('/home/member-a/qwen35-a05/llama-build-'+lib_version+'/bin').glob('*.so'))
files={str(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}
assert sha(paths[1])=='d46bd1cc785c56d718e7b2782ced73bd7b3ab9a3510177df0bb0bbeacf69ee90'
previous=json.loads((out/'before/modules/linear_A/manifest.json').read_text())
obj=dict(previous,files=files,native_entry=str(paths[0]),shared_library=str(paths[1]),physical_ubatch=8,
 status='PC_BATCH_FIX_CANDIDATE_FINAL_REGRESSION_IN_PROGRESS',non_mlp_projection_schedule='STABLE_PER_TOKEN_SIMD_GEMV')
if version=='v8':obj['attention_schedule']='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING'
shutil.copytree(ROOT/'runtime/qwen35_w4a8',out/('source-'+version))
sources={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'runtime/qwen35_w4a8').glob('*') if p.is_file()}
with (out/('runtime-build-'+version+'.json')).open('x') as f:json.dump({'files':files,'source_files':sources,'base_commit':'81e39ad34368329b5db77620721510fd91107e80',
 'physical_ubatch':8,'same_SP_LIBRARY_as_v3':True,'BOARD':'NOT_TESTED'},f,indent=2)
# Machine-generated module manifest; original is preserved and sealed above.
(ROOT/'modules/linear_A/manifest.json').write_text(json.dumps(obj,indent=2)+'\n')
print(json.dumps({'candidate':str(paths[0]),'sha256':files[str(paths[0])]['sha256'],'same_cpu_ABI_binary':True}))
