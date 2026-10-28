// Persistent per-turn IPC, in-process SP_LINEAR graph nodes. CPU only, R0 only.
#include "bridge.hpp"
#include "sp-hook.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <csignal>
#include <cstring>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sys/resource.h>
using json=nlohmann::json;using Clock=std::chrono::steady_clock;
static volatile std::sig_atomic_t cancelled=0;
static void signal_cancel(int){cancelled=1;}
static bool abort_graph(void*p){return cancelled||!static_cast<s1::Bridge*>(p)->error.empty();}
static void emit(const json&j){std::cout<<j.dump(-1,' ',false,json::error_handler_t::replace)<<std::endl;}
static double ms(Clock::time_point t){return std::chrono::duration<double,std::milli>(Clock::now()-t).count();}
static long rss(){rusage r{};getrusage(RUSAGE_SELF,&r);return r.ru_maxrss;}
static uint64_t fnv(const void*data,size_t size){uint64_t h=1469598103934665603ULL;auto*p=static_cast<const uint8_t*>(data);for(size_t i=0;i<size;++i){h^=p[i];h*=1099511628211ULL;}return h;}
static json memory(){
    json result;for(auto name:{"status","smaps_rollup"}){std::ifstream f(std::string("/proc/self/")+name);std::string line;while(std::getline(f,line))if(line.find("Rss:")==0||line.find("Pss:")==0||line.find("VmRSS:")==0||line.find("VmHWM:")==0||line.find("RssAnon:")==0||line.find("RssFile:")==0)result[name].push_back(line);}return result;
}
static void write_binary(const std::filesystem::path&p,const void*v,size_t bytes){if(std::filesystem::exists(p))throw std::runtime_error("diagnostic path already exists");std::ofstream f(p,std::ios::binary);f.write(static_cast<const char*>(v),bytes);if(!f)throw std::runtime_error("diagnostic write");}
struct NodeTrace {
    s1::Bridge*bridge=nullptr;bool active=false;std::string error;std::filesystem::path dir;json records=json::array();
    static bool eval(ggml_tensor*t,bool ask,void*u){
        auto&self=*static_cast<NodeTrace*>(u);std::string name=t->name;
        bool selected=self.active&&!self.dir.empty()&&t->type==GGML_TYPE_F32&&name.size()>2&&name.substr(name.size()-2)=="-0"&&ggml_nbytes(t)<8*1024*1024;
        bool a12_trace=self.bridge&&self.bridge->route.enabled&&self.active;
        if(ask){if(a12_trace){try{self.bridge->route.observe(t,false);}catch(const std::exception&e){self.error=e.what();return true;}}return selected||a12_trace;}
        if(a12_trace){try{self.bridge->route.observe(t,true);}catch(const std::exception&e){self.error=e.what();return false;}}
        if(!selected)return true;
        try { // Diagnostic only: preserve strides and shape, never feed data back.
        auto file="node-"+std::to_string(self.records.size())+".bin";std::vector<uint8_t>v(ggml_nbytes(t));ggml_backend_tensor_get(t,v.data(),0,v.size());
        write_binary(self.dir/file,v.data(),v.size());self.records.push_back({{"name",name},{"op",ggml_op_name(t->op)},{"shape",{t->ne[0],t->ne[1],t->ne[2],t->ne[3]}},{"strides",{t->nb[0],t->nb[1],t->nb[2],t->nb[3]}},{"file",file}});return true;
        }catch(const std::exception&e){self.error=e.what();return false;}
    }
};
int main(int argc,char**argv){try{
    if(argc<4||argc>8)throw std::runtime_error("qwen35-s1 MODEL THREADS CONTEXT [scope] [TILED|SCALAR] [kernel_threads] [physical_ubatch]");
    int threads=std::stoi(argv[2]),context=std::stoi(argv[3]),kernel_threads=argc>6?std::stoi(argv[6]):4;
    int physical=argc>7?std::stoi(argv[7]):8;
    if(physical!=1&&physical!=2&&physical!=4&&physical!=8&&physical!=256)throw std::runtime_error("physical batch range");
    if(threads<1||threads>16||context<256||context>4096||kernel_threads<1||kernel_threads>4)throw std::runtime_error("thread/context range");
    std::signal(SIGUSR1,signal_cancel);llama_backend_init();
    auto ready_start=Clock::now();s1::Bridge bridge(SP_PROJECT_ROOT,argc>4?argv[4]:"all",argc>5?argv[5]:"TILED",kernel_threads);double sidecar_ms=ms(ready_start);
    if(bridge.scope!="none"&&physical>8)throw std::runtime_error("S1 physical ubatch must be <=8");
    const std::string quantization=bridge.scope!="none"?"A12_W4A8_MLP":std::string(argv[1]).find("-f16.gguf")!=std::string::npos?"H0_F16":"S0_Q4_K_M";
    sp_llama_set_weight_filter([](const char*name,void*u){return static_cast<s1::Bridge*>(u)->entries.count(name)!=0;},&bridge);
    auto start=Clock::now();auto mp=llama_model_default_params();mp.n_gpu_layers=0;mp.load_mtp=false;
    auto *cpu_device=ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);if(!cpu_device)throw std::runtime_error("CPU device absent");
    llama_model_tensor_buft_override overrides[]={{"blk\\.[0-9]+\\.ffn_(gate|up|down)\\.weight",ggml_backend_dev_buffer_type(cpu_device)},{nullptr,nullptr}};
    mp.tensor_buft_overrides=overrides;
    auto *model=llama_model_load_from_file(argv[1],mp);if(!model)throw std::runtime_error("model load");double load_ms=ms(start);
    sp_llama_set_hook(s1::Bridge::graph,&bridge);
    sp_llama_set_stable_projections(bridge.scope!="none");
    // Private fixed-source CPU policy: use one SIMD query/KV reduction order
    // for all batch sizes. Do not let ambient environment change this profile.
    if(setenv("SP_QWEN35_STABLE_ATTN",bridge.scope=="none"?"0":"1",1))throw std::runtime_error("attention policy init");
    NodeTrace trace;trace.bridge=&bridge;
    auto cp=llama_context_default_params();cp.n_ctx=context;cp.n_batch=256;cp.n_ubatch=physical;cp.n_threads=threads;cp.n_threads_batch=threads;cp.n_seq_max=1;cp.n_rs_seq=0;
    cp.cb_eval=NodeTrace::eval;cp.cb_eval_user_data=&trace;
    cp.abort_callback=abort_graph;cp.abort_callback_data=&bridge;start=Clock::now();auto*ctx=llama_init_from_model(model,cp);if(!ctx)throw std::runtime_error("context init");
    auto *vocab=llama_model_get_vocab(model);int nv=llama_vocab_n_tokens(vocab);
    emit({{"type","ready"},{"domain",bridge.route.real?"BOARD":"PC"},{"execution_kind",bridge.route.enabled?(bridge.route.real?"FPGA_REAL":"PC_MATH_DOUBLE"):"CPU_REFERENCE"},{"quantization",quantization},{"model_file",argv[1]},
      {"model_load_ms",load_ms},{"sidecar_load_ms",sidecar_ms},{"context_init_ms",ms(start)},{"worker_ready_ms",ms(ready_start)},{"threads",threads},{"kernel_threads",kernel_threads},{"context",context},{"peak_rss_kib",rss()},
      {"n_seq_max",1},{"n_rs_seq",0},{"physical_ubatch",cp.n_ubatch},{"non_mlp_projection_schedule",bridge.scope=="none"?"UPSTREAM":"STABLE_PER_TOKEN_SIMD_GEMV"},{"attention_schedule",bridge.scope=="none"?"UPSTREAM":"SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING"},{"cache_policy","R0_CLEAR_ALL_REPLAY"},{"R1","DISABLED_NOT_VERIFIED"},{"bridge",bridge.report()},{"memory",memory()}});
    std::vector<float> reference;std::string line;
    while(std::getline(std::cin,line)){std::string id;auto request_start=Clock::now();bridge.request_stats.begin(false,false,"","",0);
      try{auto req=json::parse(line);id=req.value("id","");auto op=req.value("op","generate");if(op=="shutdown")break;
        bridge.request_stats.begin(req.value("profile",false),req.value("profile_detail",false),req.value("session_id",std::string()),id,req.value("session_epoch",uint64_t(0)));
        if(op=="reset"){cancelled=0;llama_memory_clear(llama_get_memory(ctx),true);bridge.reset();emit({{"type","reset"},{"id",id},{"epoch",bridge.epoch}});continue;}
        if(req.value("cache_policy",std::string("R0"))!="R0")throw std::runtime_error("Unverified R1/R2 is disabled; explicit R0 replay required");
        std::vector<llama_token> tokens;if(req.contains("tokens"))tokens=req.at("tokens").get<std::vector<llama_token>>();else{
            std::string p=req.at("prompt");int n=llama_tokenize(vocab,p.data(),p.size(),nullptr,0,true,true);if(n>=0)throw std::runtime_error("token size query");tokens.resize(-n);n=llama_tokenize(vocab,p.data(),p.size(),tokens.data(),tokens.size(),true,true);if(n<0)throw std::runtime_error("tokenization");tokens.resize(n);}
        if(op=="tokenize"){emit({{"type","tokens"},{"id",id},{"tokens",tokens}});continue;}if(op!="generate")throw std::runtime_error("operation");
        int limit=req.value("max_tokens",32),chunk=req.value("prefill_chunk",256);std::string lm=req.value("logits_mode",std::string("final"));
        if(tokens.empty()||limit<1||limit>1024||tokens.size()+limit>size_t(context))throw std::runtime_error("context/token limit");
        if(chunk!=1&&chunk!=2&&chunk!=4&&chunk!=8&&chunk!=256)throw std::runtime_error("prefill chunk");
        if(lm!="final"&&lm!="all")throw std::runtime_error("logits mode");if(lm=="all"&&tokens.size()>256)throw std::runtime_error("diagnostic all logits bound");
        std::vector<llama_token> forced=req.value("teacher_tokens",std::vector<llama_token>{});
        for(auto t:tokens)if(t<0||t>=nv)throw std::runtime_error("token ID");for(auto t:forced)if(t<0||t>=nv)throw std::runtime_error("teacher token ID");
        if(!forced.empty()&&int(forced.size())!=limit)throw std::runtime_error("teacher sequence length");
        std::string diag=req.value("diagnostic_dir",std::string());if(!diag.empty()&&(tokens.size()>256||limit>8))throw std::runtime_error("diagnostic bound");
        const bool report_diagnostic=req.value("diagnostic_report",false)||!diag.empty();
        auto cpu_before=bridge.report(false);
        if(req.value("compare_logits",false)&&reference.empty())throw std::runtime_error("missing logits reference");
        cancelled=0;start=Clock::now();llama_memory_clear(llama_get_memory(ctx),true);bridge.reset();double reset_ms=ms(start);bridge.set_diagnostic(diag);bridge.diagnostic_all_layers=req.value("diagnostic_all_layers",false);
        bridge.route.set_trace(req.value("a12_consumer_trace",false));
        trace.records=json::array();trace.dir=diag;trace.error.clear();
        start=Clock::now();int rc=0;bool failed=false;size_t requested=0;json logits_records=json::array();
        for(size_t pos=0;pos<tokens.size();pos+=chunk){int count=std::min<size_t>(chunk,tokens.size()-pos);auto batch=llama_batch_get_one(tokens.data()+pos,count);
            trace.active=req.value("a12_consumer_trace",false)||(pos==0&&!diag.empty()&&req.value("diagnostic_nodes",false));
            std::vector<int8_t>flags(count,lm=="all"?1:0);if(pos+count==tokens.size())flags.back()=1;batch.logits=flags.data();bridge.begin_execution();
            {s1::DecodeScope measured(bridge.request_stats,0);rc=llama_decode(ctx,batch);measured.rc=rc;}
            if(!trace.error.empty())throw std::runtime_error("Node diagnostic: "+trace.error);
            bridge.route.finish_execution();
            if(rc||cancelled||!bridge.error.empty()){failed=true;break;}
            for(int i=0;i<count;++i)if(flags[i]){++requested;if(!diag.empty()){auto name="logits-prefill-"+std::to_string(pos+i)+".f32";write_binary(std::filesystem::path(diag)/name,llama_get_logits_ith(ctx,i),nv*4);logits_records.push_back({{"position",pos+i},{"file",name}});}}
        }
        trace.active=req.value("a12_consumer_trace",false);
        if(!trace.records.empty()){std::ofstream f(std::filesystem::path(diag)/"nodes.json");f<<trace.records.dump(2);}
        double prefill_ms=ms(start),ttft_ms=0,decode_ms=0;int calls=0;uint64_t loghash=0;json comparison=nullptr;
        if(!failed){const float*l=llama_get_logits_ith(ctx,-1);loghash=fnv(l,nv*4);
            if(req.value("compare_logits",false)){double max=0,sq=0;int bad=0;for(int i=0;i<nv;++i){double d=double(l[i])-reference[i];max=std::max(max,std::abs(d));sq+=d*d;if(!std::isfinite(l[i])||std::abs(d)>0.002+0.0002*std::abs(reference[i]))++bad;}comparison={{"max_abs",max},{"rmse",std::sqrt(sq/nv)},{"failures",bad},{"atol",0.002},{"rtol",0.0002}};}
            if(req.value("save_logits_reference",false))reference.assign(l,l+nv);
            if(!diag.empty()&&req.value("dump_state",false)){size_t bytes=llama_state_seq_get_size(ctx,0);std::vector<uint8_t>s(bytes);if(llama_state_seq_get_data(ctx,s.data(),bytes,0)!=bytes)throw std::runtime_error("hybrid state dump");write_binary(std::filesystem::path(diag)/"hybrid-state.bin",s.data(),s.size());}
        }
        auto*sampler=llama_sampler_init_greedy();std::vector<llama_token>out;std::string text;bool eos=false;
        for(int i=0;!failed&&!cancelled&&i<limit;++i){auto tok=forced.empty()?llama_sampler_sample(sampler,ctx,-1):forced[i];if(i==0)ttft_ms=ms(start);
            if(forced.empty()&&llama_vocab_is_eog(vocab,tok)){eos=true;break;}out.push_back(tok);char buffer[256];int n=llama_token_to_piece(vocab,tok,buffer,sizeof(buffer),0,true);if(n<0){failed=true;rc=-99;break;}text.append(buffer,n);emit({{"type","token"},{"id",id},{"index",i},{"token",tok}});
            if(i+1<limit&&!cancelled){auto begin=Clock::now();auto batch=llama_batch_get_one(&tok,1);bridge.begin_execution();
                {s1::DecodeScope measured(bridge.request_stats,1);rc=llama_decode(ctx,batch);measured.rc=rc;}
                if(!trace.error.empty())throw std::runtime_error("A12 consumer: "+trace.error);
                bridge.route.finish_execution();
                decode_ms+=ms(begin);++calls;if(rc||!bridge.error.empty()){failed=true;break;}
                if(!diag.empty()){auto name="logits-decode-"+std::to_string(i)+".f32";write_binary(std::filesystem::path(diag)/name,llama_get_logits_ith(ctx,-1),nv*4);logits_records.push_back({{"position",tokens.size()+i},{"file",name}});}}
        }
        llama_sampler_free(sampler);std::string status=cancelled?"CANCELLED":failed?"ERROR":"OK";
        if(!diag.empty()){json manifest={{"projections",bridge.dumps},{"logits",logits_records},{"teacher_tokens",forced},{"prompt_tokens",tokens},{"prefill_chunk",chunk},{"scope",bridge.scope}};std::ofstream f(std::filesystem::path(diag)/"manifest.json");f<<manifest.dump(2);}
        auto bridge_report=bridge.report(report_diagnostic);auto pos=llama_memory_seq_pos_max(llama_get_memory(ctx),0);
        json state_fingerprint=nullptr;
        if(req.value("state_fingerprint",false)&&!failed&&!cancelled){auto size=llama_state_seq_get_size(ctx,0);std::vector<uint8_t>state(size);
            if(llama_state_seq_get_data(ctx,state.data(),state.size(),0)!=size)throw std::runtime_error("state fingerprint read");
            state_fingerprint={{"bytes",size},{"fnv64",fnv(state.data(),state.size())}};}
        // Rejects, unplayed candidates and cancellations cannot leave hidden recurrent/KV state.
        llama_memory_clear(llama_get_memory(ctx),true);bridge.cache.valid=false;
        auto request_profile=bridge.request_stats.report();bridge.request_stats.active=false;
        request_profile["native_request_wall_ms"]=ms(request_start);
        request_profile["cpu_counters"]={{"scope","DELTA_BETWEEN_REQUEST_BOUNDARIES_NOT_LAST_OP"},
            {"run_count_begin",cpu_before["cpu_run_count"]},{"run_count_end",bridge_report["cpu_run_count"]},
            {"run_count_delta",uint64_t(bridge_report["cpu_run_count"])-uint64_t(cpu_before["cpu_run_count"])},
            {"compute_ms_delta",double(bridge_report["cpu_compute_ms_process_total"])-double(cpu_before["cpu_compute_ms_process_total"])},
            {"service_ms_delta",double(bridge_report["cpu_service_ms_process_total"])-double(cpu_before["cpu_service_ms_process_total"])}};
        emit({{"type","result"},{"id",id},{"status",status},{"decode_rc",rc},{"prompt_tokens",tokens.size()},{"output_tokens",out},{"text",text},{"eos",eos},
          {"prefill_ms",prefill_ms},{"ttft_ms",ttft_ms},{"decode_ms",decode_ms},{"decode_calls",calls},{"reset_ms",reset_ms},{"last_prompt_logits_fnv64",loghash},
          {"peak_rss_kib",rss()},{"threads",threads},{"kernel_threads",kernel_threads},{"logits_mode",lm},{"prefill_requested_logits",requested},{"logits_comparison",comparison},
          {"teacher_forced",!forced.empty()},{"prefill_chunk",chunk},{"bridge",bridge_report},{"memory",report_diagnostic?memory():json(nullptr)},{"state_position_before_clear",pos},
          {"request_profile",request_profile},{"state_fingerprint",state_fingerprint},
          {"state_cleared_before_response",true},{"state_position_after_clear",llama_memory_seq_pos_max(llama_get_memory(ctx),0)},
          {"gpu_layers",0},{"domain",bridge.route.real?"BOARD":"PC"},{"partial_output_usable",status=="OK"},{"quantization",quantization},{"physical_ubatch",physical}});
      }catch(const std::exception&e){trace.active=false;llama_memory_clear(llama_get_memory(ctx),true);bridge.cache.valid=false;auto prof=bridge.request_stats.report();prof["native_request_wall_ms"]=ms(request_start);prof["incomplete"]=true;bridge.request_stats.active=false;emit({{"type","error"},{"id",id},{"message",e.what()},{"state_cleared",true},{"request_profile",prof}});}
    }
    bridge.route.close_checked();
    llama_free(ctx);sp_llama_set_hook(nullptr,nullptr);sp_llama_set_weight_filter(nullptr,nullptr);llama_model_free(model);llama_backend_free();return 0;
}catch(const std::exception&e){std::cerr<<"S1_FAILURE: "<<e.what()<<"\n";return 2;}}
