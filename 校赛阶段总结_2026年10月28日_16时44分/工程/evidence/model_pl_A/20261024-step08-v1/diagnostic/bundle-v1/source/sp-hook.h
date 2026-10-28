#pragma once
#include "llama.h"
typedef ggml_tensor* (*sp_graph_hook_fn)(ggml_context*,ggml_tensor*,ggml_tensor*,void*);
typedef bool (*sp_weight_filter_fn)(const char*,void*);
extern "C" LLAMA_API void sp_llama_set_hook(sp_graph_hook_fn,void*);
extern "C" LLAMA_API void sp_llama_set_weight_filter(sp_weight_filter_fn,void*);
extern "C" LLAMA_API void sp_llama_set_stable_projections(bool);
ggml_tensor* sp_llama_stable_mm(ggml_context*,ggml_tensor*,ggml_tensor*);
bool sp_llama_external_weight(const char*);
ggml_tensor* sp_llama_try_hook(ggml_context*,ggml_tensor*,ggml_tensor*);
