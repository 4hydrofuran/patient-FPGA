"""Preserve upstream SIMD attention, fix only batch-dependent reduction selection."""
import difflib,hashlib,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=root/'eval/qwen35/a05/batch-fix-v1'
src=Path('/home/member-a/qwen35-a05/source-v2');dst=Path('/home/member-a/qwen35-a05/source-v3');shutil.copytree(src,dst)
p=dst/'ggml/src/ggml-cpu/ops.cpp';old=p.read_text();needle='    const bool use_ref = params->use_ref;'
assert old.count(needle)==1
replacement='''    // A05 private CPU profile. Retain upstream SIMD per-query math and thread
    // distribution, but avoid changing the FP reduction tree at N=1/KV>=512
    // or a query tile threshold. The host sets this once before context init.
    static const bool sp_stable_attn = []() {
        const char * value = getenv("SP_QWEN35_STABLE_ATTN");
        return value && strcmp(value, "1") == 0;
    }();
    const bool use_ref = params->use_ref || sp_stable_attn;'''
new=old.replace(needle,replacement);p.write_text(new)
with (out/'stable-attention.patch').open('x') as f:f.writelines(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='source-v2/ggml/src/ggml-cpu/ops.cpp',tofile='source-v3/ggml/src/ggml-cpu/ops.cpp'))
with (out/'attention-source-patch.json').open('x') as f:json.dump({'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'kernel_math_rewritten':False,'scope':'only flash_attn dispatch in isolated CPU library'},f,indent=2)
print('Prepared isolated source-v3; old failed binaries/library files unchanged')
