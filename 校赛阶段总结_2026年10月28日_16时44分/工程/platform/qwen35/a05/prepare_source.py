"""Mechanically patch a NEW isolated copy; never mutate the pinned source tree."""
import difflib,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
src=Path('/home/member-a/qwen35-a01/llama.cpp-81e39ad34368329b5db77620721510fd91107e80')
dst=Path('/home/member-a/qwen35-a05/source-v1')
shutil.copytree(src,dst)
edits={}
p=dst/'src/llama-graph.cpp';old=p.read_text();new=old.replace('#include "llama-graph.h"','#include "llama-graph.h"\n#include "sp-hook.h"',1)
needle='    ggml_tensor * res = ggml_mul_mat(ctx0, w, cur);'
assert new.count(needle)==1
new=new.replace(needle,'''    if (auto * custom = sp_llama_try_hook(ctx0, w, cur)) {
        GGML_ASSERT(!w_s && loras->empty()); // Exact selected bias-free MLP only.
        return custom;
    }
'''+needle,1);p.write_text(new);edits['src/llama-graph.cpp']=(old,new)
p=dst/'src/CMakeLists.txt';old=p.read_text();new=old+'''
target_sources(llama PRIVATE /mnt/c/Patientqwen/runtime/qwen35_w4a8/sp-hook.cpp)
target_include_directories(llama PRIVATE /mnt/c/Patientqwen/runtime/qwen35_w4a8)
''';p.write_text(new);edits['src/CMakeLists.txt']=(old,new)
out=ROOT/'eval/qwen35/a05';patch=''.join(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name)) for name,(a,b) in edits.items())
with (out/'graph.patch').open('x') as f:f.write(patch)
with (out/'source_patch_identity.json').open('x') as f:json.dump({name:{'before':hashlib.sha256(a.encode()).hexdigest(),'after':hashlib.sha256(b.encode()).hexdigest()} for name,(a,b) in edits.items()},f,indent=2)
print(json.dumps({'base_commit':'81e39ad34368329b5db77620721510fd91107e80','isolated_source':str(dst),'changes':list(edits)}))
