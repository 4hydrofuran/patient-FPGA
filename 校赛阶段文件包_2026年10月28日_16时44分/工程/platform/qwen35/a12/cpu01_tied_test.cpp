#include "request_profile.hpp"
#include <cstring>
#include <iostream>
#include <stdexcept>
int main(){
    auto* c=ggml_init({4u*1024u*1024u,nullptr,true});
    int checks=0;
    auto need=[&](bool v){++checks;if(!v)throw std::runtime_error("tied output identity regression");};
    auto matrix=[&](const char* name,int k,int n,ggml_type type){
        auto* w=ggml_new_tensor_2d(c,type,k,n);ggml_set_name(w,name);
        auto* x=ggml_new_tensor_2d(c,GGML_TYPE_F32,k,1);
        return ggml_mul_mat(c,w,x);
    };
    auto* y=matrix("token_embd.weight",1024,248320,GGML_TYPE_Q6_K);
    auto id=s1::PerRequestStats::classify_node(y);
    need(id.role=="output_head");need(id.basis=="pinned_tied_embedding_output_weight_and_shape");
    need(id.category==s1::NodeCategory::Matrix);
    auto* indexes=ggml_new_tensor_1d(c,GGML_TYPE_I32,1);
    need(s1::PerRequestStats::classify_node(ggml_get_rows(c,y->src[0],indexes)).category==s1::NodeCategory::Movement);
    for(auto* bad:{matrix("token_embd.weight",1024,320,GGML_TYPE_Q6_K),
                  matrix("token_embd.weight",1024,248320,GGML_TYPE_F32),
                  matrix("unknown.weight",1024,248320,GGML_TYPE_Q6_K)})
        need(s1::PerRequestStats::classify_node(bad).role=="matrix_unknown_identity");
    y->ne[0]=7;need(s1::PerRequestStats::classify_node(y).role=="matrix_unknown_identity");
    need(s1::PerRequestStats::classify_node(matrix("output.weight",32,64,GGML_TYPE_F32)).role=="output_head");
    ggml_free(c);std::cout<<"{\"status\":\"PASS\",\"checks\":"<<checks<<"}\n";
}
