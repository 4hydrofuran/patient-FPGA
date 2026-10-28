"""Linux build-local copy of pinned llama; add optional clocks around unchanged fused work."""
import json
from pathlib import Path
import shutil
from common import ROOT, sha, save
from step10_common import OUT

if __name__ == '__main__':
    original = Path('/home/member-a/qwen35-a05/source-v3')
    prior = json.loads((ROOT / 'evidence/model_pl_A/20261023-preboard-v1/ARM_BUILD.json').read_text())
    for name, pin in prior['final_sources'].items():
        assert sha(original / name) == pin, name
    dest = Path.cwd() / 'llama-source'
    shutil.copytree(original, dest, symlinks=True, ignore=shutil.ignore_patterns('.git'))
    p = dest / 'ggml/src/ggml-cpu/ggml-cpu.c'
    before = sha(p)
    text = p.read_text()
    pairs = [
        ('static thread_ret_t ggml_graph_compute_thread(void * data) {', '''// A12 optional observation only; existing computation, fusion and barriers unchanged.
static void (*sp_a12_node_cb)(const struct ggml_tensor*,int,uint64_t,void*) = NULL;
static void * sp_a12_node_user = NULL;
__attribute__((visibility("default"))) void sp_a12_set_node_profile_v1(
    void (*cb)(const struct ggml_tensor*,int,uint64_t,void*), void * user) {
    sp_a12_node_cb=cb;sp_a12_node_user=user;
}
static thread_ret_t ggml_graph_compute_thread(void * data) {'''),
        ('    for (int node_n = 0; node_n < cgraph->n_nodes &&', '''    uint64_t sp_a12_last_begin=0;const struct ggml_tensor*sp_a12_last_node=NULL;int sp_a12_last_fused=0;
    for (int node_n = 0; node_n < cgraph->n_nodes &&'''),
        ('        // TODO: move fused-op detection', '''        const uint64_t sp_a12_begin=state->ith==0&&sp_a12_node_cb?(uint64_t)ggml_time_us():0;
        // TODO: move fused-op detection'''),
        ('''        if (node_n + 1 < cgraph->n_nodes) {
            ggml_barrier(state->threadpool);
        }
    }''', '''        if (node_n + 1 < cgraph->n_nodes) {
            ggml_barrier(state->threadpool);
            if(sp_a12_begin)sp_a12_node_cb(node,n_fused,(uint64_t)ggml_time_us()-sp_a12_begin,sp_a12_node_user);
        }else if(sp_a12_begin){sp_a12_last_begin=sp_a12_begin;sp_a12_last_node=node;sp_a12_last_fused=n_fused;}
    }'''),
        ('''    ggml_barrier(state->threadpool);

#ifdef GGML_USE_CPU_RISCV64_SPACEMIT
    ggml_backend_cpu_riscv64_spacemit_clear_numa_thread_affinity_threaded''', '''    ggml_barrier(state->threadpool);
    if(sp_a12_last_begin)sp_a12_node_cb(sp_a12_last_node,sp_a12_last_fused,(uint64_t)ggml_time_us()-sp_a12_last_begin,sp_a12_node_user);

#ifdef GGML_USE_CPU_RISCV64_SPACEMIT
    ggml_backend_cpu_riscv64_spacemit_clear_numa_thread_affinity_threaded''')]
    for a, b in pairs:
        assert text.count(a) == 1, a
        text = text.replace(a, b)
    p.write_text(text)
    save(OUT / 'LLAMA_DERIVATION.json', dict(source=str(original), derived=str(dest),
         pinned_runtime_commit='81e39ad34368329b5db77620721510fd91107e80',
         changes={str(p.relative_to(dest)): dict(before=before, after=sha(p))},
         unchanged_source_pins=prior['final_sources'], mathematics_changed=False,
         fusion_changed=False, barriers_added=0, node_dump=False))
