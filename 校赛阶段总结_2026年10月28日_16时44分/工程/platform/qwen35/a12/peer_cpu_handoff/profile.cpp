// Characterizes the real baseline observer, including its known catch-all gap.
#include "request_profile.hpp"
#include "ggml.h"
#include <iostream>
#include <stdexcept>
#include <cstring>
static void need(bool v, const char * s) { if (!v) throw std::runtime_error(s); }
int main() {
    try {
        s1::PerRequestStats s; s.begin(true, false, "synthetic", "profile-component", 1);
        auto * c = ggml_init({2u * 1024u * 1024u, nullptr, false});
        need(c != nullptr, "context");
        auto * w = ggml_new_tensor_2d(c, GGML_TYPE_F32, 32, 32);
        auto * x = ggml_new_tensor_2d(c, GGML_TYPE_F32, 32, 1);
        ggml_set_name(w, "blk.0.attn_gate.weight");
        auto * mm = ggml_mul_mat(c, w, x); ggml_set_name(mm, "opaque_projection");
        s1::PerRequestStats::node_observed(mm, 0, 100, &s);
        auto * norm = ggml_rms_norm(c, x, 1e-6f); ggml_set_name(norm, "norm-0");
        s1::PerRequestStats::node_observed(norm, 1, 50, &s);
        auto * custom = ggml_new_tensor_2d(c, GGML_TYPE_F32, 32, 1);
        custom->op = GGML_OP_CUSTOM; ggml_set_name(custom, "ffn_out-0");
        s1::PerRequestStats::node_observed(custom, 0, 20, &s);
        auto p = s.node_report()["phases"]["prefill"];
        need(p["other_norm_activation_residual"]["calls"] == 2, "known baseline catch-all");
        need(p["other_norm_activation_residual"]["fused_extra_nodes"] == 1, "fusion count");
        need(p["other_norm_activation_residual"]["wall_ms"] == 0.15, "no fusion double count");
        need(p["mlp_custom"]["calls"] == 1, "ffn_out bug remains fixed");
        s.phase = 1; s1::PerRequestStats::node_observed(mm, 0, 70, &s);
        need(s.node_report()["phases"]["decode"]["other_norm_activation_residual"]["calls"] == 1,
             "phase separation");
        s.begin(false, false, "", "disabled", 2);
        s1::PerRequestStats::node_observed(mm, 0, 999, &s);
        need(s.node_report()["phases"]["prefill"]["other_norm_activation_residual"]["calls"] == 0,
             "disabled observer");
        ggml_free(c);
        std::cout << "{\"status\":\"PASS_BASELINE_CHARACTERIZATION\",\"checks\":6,"
                     "\"known_unclassified_matmul\":true,\"candidate_classifier\":\"NOT_IMPLEMENTED\","
                     "\"BOARD\":\"NOT_TESTED\"}\n";
        return 0;
    } catch (const std::exception & e) { std::cerr << e.what() << '\n'; return 1; }
}
