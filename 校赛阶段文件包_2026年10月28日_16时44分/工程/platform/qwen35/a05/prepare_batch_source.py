"""Mechanical isolated extension to the already audited fixed-source graph hook."""
import difflib,hashlib,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[3]
src=Path('/home/member-a/qwen35-a05/source-v1');dst=Path('/home/member-a/qwen35-a05/source-v2')
shutil.copytree(src,dst)
p=dst/'src/llama-graph.cpp';old=p.read_text();needle='ggml_tensor * res = ggml_mul_mat(ctx0, w, cur);'
assert old.count(needle)==1
new=old.replace(needle,'ggml_tensor * res = sp_llama_stable_mm(ctx0, w, cur);')
p.write_text(new)
out=root/'eval/qwen35/a05/batch-fix-v1'
with (out/'stable-projections.patch').open('x') as f:f.writelines(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='source-v1/src/llama-graph.cpp',tofile='source-v2/src/llama-graph.cpp'))
with (out/'source-patch.json').open('x') as f:json.dump({'base':'81e39ad34368329b5db77620721510fd91107e80','previous_graph_sha256':hashlib.sha256(old.encode()).hexdigest(),'new_graph_sha256':hashlib.sha256(new.encode()).hexdigest()},f,indent=2)
print('Prepared new source-v2; prior source and binaries unchanged')
