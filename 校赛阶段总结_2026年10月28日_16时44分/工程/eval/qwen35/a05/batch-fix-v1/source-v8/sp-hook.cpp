#include "sp-hook.h"
// One process/model/context, configured before context creation; no runtime switching.
static sp_graph_hook_fn hook=nullptr;static void* user=nullptr;
static sp_weight_filter_fn weight_filter=nullptr;static void*weight_user=nullptr;
static bool stable_projections=false;
extern "C" void sp_llama_set_stable_projections(bool enabled){stable_projections=enabled;}
ggml_tensor* sp_llama_stable_mm(ggml_context*c,ggml_tensor*w,ggml_tensor*x){
    // Zero output positions are legal on non-final prefill microbatches.
    // Preserve upstream empty-tensor semantics instead of returning nullptr.
    if(!stable_projections||x->ne[1]<=1)return ggml_mul_mat(c,w,x);
    // Keep the mature SIMD GEMV arithmetic/activation conversion for each token
    // of non-MLP projections. Only graph scheduling changes; no weights/scales
    // are reinterpreted. The separate SP_LINEAR MLP hook still receives real T.
    GGML_ASSERT(w->ne[2]==1&&w->ne[3]==1&&x->ne[2]==1&&x->ne[3]==1);
    GGML_ASSERT(x->type==GGML_TYPE_F32&&x->nb[0]==sizeof(float));
    ggml_tensor* result=nullptr;
    for(int64_t t=0;t<x->ne[1];++t){
        auto*row=ggml_view_2d(c,x,x->ne[0],1,x->nb[1],t*x->nb[1]);
        auto*y=ggml_mul_mat(c,w,row);
        result=result?ggml_concat(c,result,y,1):y;
    }
    return result;
}
extern "C" void sp_llama_set_weight_filter(sp_weight_filter_fn f,void*u){weight_filter=f;weight_user=u;}
bool sp_llama_external_weight(const char*name){return weight_filter&&weight_filter(name,weight_user);}
extern "C" void sp_llama_set_hook(sp_graph_hook_fn f,void*u){hook=f;user=u;}
ggml_tensor* sp_llama_try_hook(ggml_context*c,ggml_tensor*w,ggml_tensor*x){return hook?hook(c,w,x,user):nullptr;}
