// Synthetic component characterization of the unchanged A05/A12 stable hook.
// This is not a model, hardware test, or independent quantization golden.
#include "sp-hook.h"
#include "ggml-cpu.h"
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void need(bool v, const char * s) { if (!v) throw std::runtime_error(s); }
static float value(size_t i) { return float(int((i * 37 + 19) % 251) - 125) / 128.0f; }
static void compute(ggml_context * c, ggml_tensor * y, int threads) {
    auto * g = ggml_new_graph_custom(c, 512, false);
    ggml_build_forward_expand(g, y);
    need(ggml_graph_compute_with_ctx(c, g, threads) == GGML_STATUS_SUCCESS, "compute failed");
}
static void one(ggml_type type, int k, int n, int t, bool strided, int threads) {
    auto * c = ggml_init({128u * 1024u * 1024u, nullptr, false});
    need(c != nullptr, "context allocation");
    try {
        auto * w = ggml_new_tensor_2d(c, type, k, n);
        ggml_set_name(w, "blk.0.attn_gate.weight");
        std::vector<float> wf(size_t(k) * n);
        for (size_t i = 0; i < wf.size(); ++i) wf[i] = value(i);
        if (type == GGML_TYPE_F32) std::memcpy(w->data, wf.data(), wf.size() * 4);
        else need(ggml_quantize_chunk(type, wf.data(), w->data, 0, n, k, nullptr)
                  == ggml_nbytes(w), "quantized weight size");
        auto * backing = ggml_new_tensor_2d(c, GGML_TYPE_F32, k + (strided ? 16 : 0), t);
        auto * x = strided ? ggml_view_2d(c, backing, k, t, backing->nb[1], 0) : backing;
        for (int row = 0; row < t; ++row) for (int col = 0; col < k; ++col) {
            float v = value(size_t(row) * k + col + 173);
            std::memcpy(static_cast<char *>(x->data) + row * x->nb[1] + col * 4, &v, 4);
        }
        sp_llama_set_stable_projections(true);
        auto * y = sp_llama_stable_mm(c, w, x);
        need(y && y->ne[0] == n && y->ne[1] == t, "output shape including empty T");
        if (t > 0) {
            compute(c, y, threads);
            std::vector<float> actual(size_t(t) * n);
            for (int row = 0; row < t; ++row)
                std::memcpy(actual.data() + size_t(row) * n,
                            static_cast<char *>(y->data) + row * y->nb[1], n * 4);
            // Reference uses exactly the existing single-token primitive, no batching.
            for (int row = 0; row < t; ++row) {
                auto * xr = ggml_view_2d(c, x, k, 1, x->nb[1], row * x->nb[1]);
                auto * yr = ggml_mul_mat(c, w, xr);
                compute(c, yr, threads);
                need(std::memcmp(actual.data() + size_t(row) * n, yr->data, n * 4) == 0,
                     "hook differs from same-ISA per-token primitive");
            }
        }
        std::cout << "{\"type\":\"" << ggml_type_name(type) << "\",\"K\":" << k
                  << ",\"N\":" << n << ",\"T\":" << t << ",\"strided\":"
                  << (strided ? "true" : "false") << ",\"threads\":" << threads
                  << ",\"status\":\"PASS_COMPONENT_SAME_ISA\"}\n";
        ggml_free(c);
    } catch (...) { ggml_free(c); throw; }
}
int main(int argc, char ** argv) {
    try {
        bool full = argc == 2 && std::string(argv[1]) == "--full-shapes";
        int cases = 0;
        for (auto type : {GGML_TYPE_F32, GGML_TYPE_Q4_K, GGML_TYPE_Q6_K})
            for (int threads : {1, 2}) for (bool stride : {false, true})
                for (int t = 0; t <= 8; ++t) { one(type, 256, 64, t, stride, threads); ++cases; }
        if (full) {
            // Additional real dimension families, still synthetic weights/activations.
            for (auto shape : {std::pair<int,int>{1024,6144}, {1024,2048},
                               {1024,16}, {2048,1024}, {1024,4096}, {1024,512}})
                for (int t : {1,3,8}) {
                    one(GGML_TYPE_Q4_K, shape.first, shape.second, t, true, 2); ++cases;
                }
        }
        ggml_quantize_free();
        std::cout << "{\"summary\":true,\"cases\":" << cases
                  << ",\"full_shapes\":" << (full ? "true" : "false")
                  << ",\"BOARD\":\"NOT_TESTED\",\"full_model\":\"NOT_TESTED\"}\n";
        return 0;
    } catch (const std::exception & e) { std::cerr << e.what() << '\n'; return 1; }
}
