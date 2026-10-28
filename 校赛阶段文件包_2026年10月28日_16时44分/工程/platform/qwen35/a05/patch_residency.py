"""Keep ONLY replaced exact MLPs file-backed; preserve all other repack choices."""
import difflib,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];src=Path('/home/member-a/qwen35-a01/llama.cpp-81e39ad34368329b5db77620721510fd91107e80');dst=Path('/home/member-a/qwen35-a05/source-v1')
p=dst/'src/llama-model-loader.cpp';old=p.read_text();needle='                        buft = select_weight_buft(hparams, t_meta, op, buft_list_cpu);'
assert old.count(needle)==1
new='#include "sp-hook.h"\n'+old.replace(needle,'''                        buft = sp_llama_external_weight(t_meta->name)
                            ? overrides->buft
                            : select_weight_buft(hparams, t_meta, op, buft_list_cpu);''')
p.write_text(new)
files=['src/llama-graph.cpp','src/CMakeLists.txt','src/llama-model-loader.cpp'];patch='';identity={}
for name in files:
    a=(src/name).read_text();b=(dst/name).read_text();patch+=''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name));identity[name]={'before':hashlib.sha256(a.encode()).hexdigest(),'after':hashlib.sha256(b.encode()).hexdigest()}
out=ROOT/'eval/qwen35/a05'
with (out/'graph-v2.patch').open('x') as f:f.write(patch)
with (out/'source_patch_identity-v2.json').open('x') as f:json.dump(identity,f,indent=2)
print(json.dumps({'patched':files,'scope':'Only registered externally computed tensor avoids CPU_REPACK'}))
