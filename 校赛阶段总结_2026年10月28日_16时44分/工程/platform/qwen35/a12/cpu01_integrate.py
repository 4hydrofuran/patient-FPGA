"""Independent A integration; immutable peer payload and mathematical sources."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'
PEER = ROOT/'evidence/model_pl_A/20261024-cpu-peer01a-review-v1/received'
BASE = ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'


def pin(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source = OUT/'source'
    shutil.copytree(BASE/'source', source)
    for name in ('request_profile.cpp', 'request_profile.hpp'):
        shutil.copyfile(PEER/'source/profile'/name, source/name)
    path = source/'request_profile.cpp'
    before = path.read_text(encoding='utf-8')
    anchor = 'if(weight_role(t->src[0]->name,role,family,layer)){'
    assert before.count(anchor) == 1
    # Only the pinned tied output projection is added. GET_ROWS embedding use
    # never reaches this MUL_MAT-only branch, and malformed dimensions stay unknown.
    after = before.replace(anchor, '''const auto* weight=t->src[0];
                const bool tied_head=std::strcmp(weight->name,"token_embd.weight")==0 &&
                    weight->ne[0]==1024 && weight->ne[1]==248320 &&
                    weight->type==GGML_TYPE_Q6_K && projection_shape(t);
                if(tied_head){role="output_head";family="unknown";}
                if(tied_head || weight_role(weight->name,role,family,layer)){''')
    after = after.replace('id.weight_type=t->src[0]->type;id.basis="source_weight_name_and_shape";',
        'id.weight_type=t->src[0]->type;id.basis=tied_head?"pinned_tied_embedding_output_weight_and_shape":"source_weight_name_and_shape";')
    path.write_text(after, encoding='utf-8', newline='\n')
    (OUT/'tied-head.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='peer/request_profile.cpp', tofile='A/request_profile.cpp')), encoding='utf-8')
    shutil.copytree(PEER/'tests/profile', OUT/'component-tests')
    shutil.copyfile(ROOT/'platform/qwen35/a12/cpu01_profile.py', OUT/'cpu01_profile.py')
    rows = {p.name:dict(sha256=pin(p), baseline_sha256=pin(BASE/'source'/p.name), changed=pin(p)!=pin(BASE/'source'/p.name)) for p in source.iterdir() if p.is_file()}
    assert {n for n,r in rows.items() if r['changed']} == {'request_profile.cpp','request_profile.hpp'}
    (OUT/'DERIVATION.json').write_text(json.dumps(dict(status='A_DERIVED_PEER01A_PLUS_UNCHANGED_01B', maintainer='A', provider='B', peer_manifest_sha256=pin(PEER/'MANIFEST.json'), sources=rows, mathematical_sources_changed=False, public_contract_changed=False, task03_changed=False, original_peer_changed=False, actual_model_settings='unknown'),indent=2)+'\n',encoding='utf-8')
    print('INDEPENDENT_SOURCE_DERIVED')


if __name__ == '__main__': main()
