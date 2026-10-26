// A01 native CPU harness. No XRT, network, vision projector or speculative model.
#include "llama.h"
#include "json.hpp"
#include <chrono>
#include <csignal>
#include <cstring>
#include <cmath>
#include <map>
#include <iostream>
#include <stdexcept>
#include <sys/resource.h>
#include <vector>
using json = nlohmann::json;
using Clock = std::chrono::steady_clock;
static volatile std::sig_atomic_t cancelled = 0;
static void cancel_signal(int) { cancelled = 1; }
static bool abort_decode(void *) { return cancelled != 0; }
static double ms(Clock::time_point start) { return std::chrono::duration<double,std::milli>(Clock::now()-start).count(); }
static void emit(const json &j) { std::cout << j.dump(-1,' ',false,json::error_handler_t::replace) << std::endl; }
static long peak_kib() { rusage r{}; getrusage(RUSAGE_SELF,&r); return r.ru_maxrss; }
// Diagnostic mode fences EVERY graph node, changing scheduling/fusion. Never
// present these instrumented durations as production throughput. No tensor copies.
struct NodeStats { double elapsed_ms=0; uint64_t calls=0; int64_t rows=0; };
struct Profile {
    bool enabled=false;
    std::string phase="initialization";
    Clock::time_point begin;
    std::map<std::string,NodeStats> nodes;
    void clear() { nodes.clear(); }
    json report() const {
        json result=json::object();
        for(const auto &kv:nodes) result[kv.first]={{"ms",kv.second.elapsed_ms},{"calls",kv.second.calls},{"output_rows",kv.second.rows}};
        return result;
    }
};
static bool profile_node(ggml_tensor *t, bool ask, void *data) {
    auto &p=*static_cast<Profile *>(data);
    if(ask){p.begin=Clock::now();return true;}
    const double duration=ms(p.begin);
    const std::string src=t->src[0]?t->src[0]->name:"";
    auto &s=p.nodes[p.phase+"|"+t->name+"|"+src+"|"+std::to_string(t->op)];
    s.elapsed_ms+=duration;++s.calls;s.rows+=t->ne[1];
    return true;
}
static uint64_t logits_hash(const float *p, int n) {
    uint64_t h=1469598103934665603ULL;
    for(int i=0;i<n;++i) { uint32_t b; std::memcpy(&b,p+i,4); for(int j=0;j<4;++j) {h^=(b>>(j*8))&255;h*=1099511628211ULL;} }
    return h;
}
int main(int argc,char **argv) {
    if(argc!=4 && !(argc==5 && std::string(argv[4])=="--profile-nodes")) { std::cerr<<"usage: qwen35-cpu MODEL THREADS CONTEXT [--profile-nodes]\n";return 2; }
    int threads=std::stoi(argv[2]), context=std::stoi(argv[3]);
    if(threads<1||threads>16||context<256||context>4096) return 2;
    std::signal(SIGUSR1,cancel_signal);
    llama_backend_init();
    auto start=Clock::now(); auto mp=llama_model_default_params();mp.n_gpu_layers=0;
    auto *model=llama_model_load_from_file(argv[1],mp);if(!model)return 3;
    double load_ms=ms(start);start=Clock::now();
    Profile profile;profile.enabled=argc==5;
    auto cp=llama_context_default_params();cp.n_ctx=context;cp.n_batch=256;cp.n_ubatch=256;
    cp.n_threads=threads;cp.n_threads_batch=threads;cp.n_seq_max=1;
    cp.n_rs_seq=0; // R0: one active sequence, zero rollback snapshots.
    if(profile.enabled){cp.cb_eval=profile_node;cp.cb_eval_user_data=&profile;}
    cp.abort_callback=abort_decode;cp.abort_callback_data=nullptr;
    auto *ctx=llama_init_from_model(model,cp);if(!ctx){llama_model_free(model);return 4;}
    auto *vocab=llama_model_get_vocab(model);
    emit({{"type","ready"},{"domain","PC"},{"execution_kind","CPU_REFERENCE"},{"model_load_ms",load_ms},
          {"context_init_ms",ms(start)},{"threads",threads},{"context",context},{"peak_rss_kib",peak_kib()},
          {"n_seq_max",llama_n_seq_max(ctx)},{"n_rs_seq",llama_n_rs_seq(ctx)},
          {"cache_policy","R0_CLEAR_ALL_REPLAY"},{"profile_nodes",profile.enabled}});
    std::vector<float> diagnostic_reference; // Explicit diagnostics only, not a state checkpoint.
    std::string line;
    while(std::getline(std::cin,line)) {
        std::string id;
        try {
            auto req=json::parse(line);id=req.value("id","");auto op=req.value("op","generate");
            if(op=="shutdown")break;
            if(op=="reset") {cancelled=0;llama_memory_clear(llama_get_memory(ctx),true);emit({{"type","reset"},{"id",id}});continue;}
            std::vector<llama_token> tokens;
            if(req.contains("tokens")) tokens=req.at("tokens").get<std::vector<llama_token>>();
            else {
                auto prompt=req.at("prompt").get<std::string>();
                int n=llama_tokenize(vocab,prompt.data(),prompt.size(),nullptr,0,true,true);
                if(n>=0) throw std::runtime_error("Unexpected tokenizer size query");
                tokens.resize(-n); n=llama_tokenize(vocab,prompt.data(),prompt.size(),tokens.data(),tokens.size(),true,true);
                if(n<0)throw std::runtime_error("Tokenizer failed");
                tokens.resize(n);
            }
            if(op=="tokenize"){emit({{"type","tokens"},{"id",id},{"tokens",tokens}});continue;}
            if(op!="generate")throw std::runtime_error("Unknown operation");
            int limit=req.value("max_tokens",32);
            if(tokens.empty()||limit<1||limit>1024||tokens.size()+limit>static_cast<size_t>(context))throw std::runtime_error("Invalid context/token limit");
            for(auto t:tokens)if(t<0||t>=llama_vocab_n_tokens(vocab))throw std::runtime_error("Invalid token");
            const auto logits_mode=req.value("logits_mode",std::string("final"));
            if(logits_mode!="final" && logits_mode!="all" && logits_mode!="legacy_chunk_last")throw std::runtime_error("Invalid logits_mode");
            if(logits_mode=="all" && tokens.size()>256)throw std::runtime_error("Full logits diagnostic limited to 256 prompt tokens");
            if(req.value("compare_logits",false) && diagnostic_reference.empty())throw std::runtime_error("No diagnostic reference");
            // Reset both recurrent/convolution state and KV data, not just positions.
            cancelled=0;start=Clock::now();llama_memory_clear(llama_get_memory(ctx),true);double reset_ms=ms(start);
            profile.clear();profile.phase="prefill";
            start=Clock::now();bool failed=false;int rc=0;size_t requested_logits=0;
            for(size_t pos=0;pos<tokens.size();pos+=256) {
                int count=std::min<size_t>(256,tokens.size()-pos);
                auto batch=llama_batch_get_one(tokens.data()+pos,count);
                std::vector<int8_t> flags(count,logits_mode=="all"?1:0);
                if(logits_mode=="legacy_chunk_last" || pos+count==tokens.size())flags.back()=1;
                for(auto f:flags)requested_logits+=f!=0;
                batch.logits=flags.data();rc=llama_decode(ctx,batch);
                if(rc!=0||cancelled){failed=true;break;}
            }
            double prefill_ms=ms(start),ttft_ms=0,decode_ms=0;uint64_t hash=0;
            std::vector<llama_token> output;std::string text;int decode_calls=0;
            auto *sampler=llama_sampler_init_greedy();
            json comparison=nullptr;
            if(!failed){
                const auto *logits=llama_get_logits_ith(ctx,-1);const int nv=llama_vocab_n_tokens(vocab);
                hash=logits_hash(logits,nv);
                if(req.value("compare_logits",false)){
                    double max_abs=0,sq=0;int failures=0;
                    for(int i=0;i<nv;++i){double error=std::abs(double(logits[i])-diagnostic_reference[i]);
                        max_abs=std::max(max_abs,error);sq+=error*error;
                        if(!std::isfinite(logits[i])||error>0.002+0.0002*std::abs(diagnostic_reference[i]))++failures;
                    }
                    comparison={{"elements",nv},{"max_abs",max_abs},{"rmse",std::sqrt(sq/nv)},
                                {"failures",failures},{"atol",0.002},{"rtol",0.0002}};
                }
                if(req.value("save_logits_reference",false))diagnostic_reference.assign(logits,logits+nv);
            }
            profile.phase="decode";
            bool eos=false;
            for(int i=0;!failed&&i<limit&&!cancelled;++i) {
                auto token=llama_sampler_sample(sampler,ctx,-1);
                if(i==0)ttft_ms=ms(start);
                if(llama_vocab_is_eog(vocab,token)){eos=true;break;}
                output.push_back(token);
                char buf[256];int n=llama_token_to_piece(vocab,token,buf,sizeof(buf),0,true);
                if(n<0){failed=true;rc=-99;break;}text.append(buf,n);
                emit({{"type","token"},{"id",id},{"index",i},{"token",token}});
                if(i+1<limit&&!cancelled) {
                    auto d=Clock::now();auto batch=llama_batch_get_one(&token,1);rc=llama_decode(ctx,batch);
                    decode_ms+=ms(d);++decode_calls;if(rc!=0){failed=true;break;}
                }
            }
            llama_sampler_free(sampler);
            std::string status=cancelled?"CANCELLED":(failed?"ERROR":"OK");
            emit({{"type","result"},{"id",id},{"status",status},{"decode_rc",rc},{"prompt_tokens",tokens.size()},
                  {"output_tokens",output},{"text",text},{"eos",eos},{"prefill_ms",prefill_ms},{"ttft_ms",ttft_ms},
                  {"decode_ms",decode_ms},{"decode_calls",decode_calls},{"reset_ms",reset_ms},
                  {"last_prompt_logits_fnv64",hash},{"peak_rss_kib",peak_kib()},{"threads",threads},
                  {"logits_mode",logits_mode},{"prefill_requested_logits",requested_logits},{"logits_comparison",comparison},
                  {"node_profile",profile.report()},{"profile_nodes",profile.enabled},
                  {"gpu_layers",0},{"domain","PC"},{"partial_output_usable",status=="OK"}});
            if(failed||cancelled)llama_memory_clear(llama_get_memory(ctx),true);
        } catch(const std::exception &e){emit({{"type","error"},{"id",id},{"message",e.what()}});}
    }
    llama_free(ctx);llama_model_free(model);llama_backend_free();return 0;
}
