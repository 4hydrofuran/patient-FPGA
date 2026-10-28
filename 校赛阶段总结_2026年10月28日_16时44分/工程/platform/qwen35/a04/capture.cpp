// A04 observation only, separate executable; does NOT replace any graph operator.
#include "llama.h"
#include "ggml-backend.h"
#include "json.hpp"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <sys/resource.h>
using json=nlohmann::json;namespace fs=std::filesystem;
struct Observer {
    fs::path out;bool enabled=false;std::string phase;std::string error;
    std::map<std::string,std::pair<int,std::string>> target;
    json records=json::array();
};
static json tensor_save(ggml_tensor*t,const fs::path&p,int count){
    if(t->type!=GGML_TYPE_F32||t->ne[2]!=1||t->ne[3]!=1||t->ne[1]<count)throw std::runtime_error("capture type/shape");
    const int64_t cols=t->ne[0],start=t->ne[1]-count;std::vector<float> v(cols*count);
    for(int row=0;row<count;++row){
        if(t->nb[0]==4)ggml_backend_tensor_get(t,v.data()+row*cols,(start+row)*t->nb[1],cols*4);
        else for(int64_t c=0;c<cols;++c)ggml_backend_tensor_get(t,v.data()+row*cols+c,(start+row)*t->nb[1]+c*t->nb[0],4);
    }
    if(fs::exists(p))throw std::runtime_error("capture overwrite");
    std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*4);if(!f)throw std::runtime_error("capture write");
    return {{"file",p.filename().string()},{"shape_TK",{count,cols}},{"dtype","float32_le"},
        {"ggml_name",t->name},{"ggml_ne",{t->ne[0],t->ne[1],t->ne[2],t->ne[3]}},
        {"ggml_nb",{t->nb[0],t->nb[1],t->nb[2],t->nb[3]}},{"selected_row_start",start},{"bytes",v.size()*4}};
}
static bool observe(ggml_tensor*t,bool ask,void*data){
    auto &o=*static_cast<Observer*>(data);
    if(!o.enabled||t->op!=GGML_OP_MUL_MAT||!t->src[0])return ask?false:true;
    const auto it=o.target.find(t->src[0]->name);if(it==o.target.end())return ask?false:true;
    if(ask)return true; // Request callback only after actual backend execution.
    try{
        auto [layer,op]=it->second;const int n=op=="down"?1024:3584,k=op=="down"?3584:1024;
        if(t->src[0]->ne[0]!=k||t->src[0]->ne[1]!=n||t->src[1]->ne[0]!=k||t->ne[0]!=n)throw std::runtime_error("mapping shape mismatch");
        const int rows=o.phase=="prefill"?8:1;
        std::string id=o.phase+"_l"+(layer<10?"0":"")+std::to_string(layer)+"_"+op;
        auto input=tensor_save(t->src[1],o.out/(id+".x.f32"),rows);
        auto output=tensor_save(t,o.out/(id+".y.f32"),rows);
        o.records.push_back({{"id",id},{"layer",layer},{"op",op},{"phase",o.phase},{"T",rows},{"N",n},{"K",k},
            {"weight_name",t->src[0]->name},{"weight_type",ggml_type_name(t->src[0]->type)},
            {"input",input},{"output",output},{"execution_point","post-backend cb_eval; observation only"}});
    }catch(const std::exception&e){o.error=e.what();return false;}
    return true;
}
int main(int argc,char**argv){try{
    if(argc!=4)throw std::runtime_error("capture MODEL tokens.json new_output");
    Observer o;o.out=argv[3];if(!fs::create_directory(o.out))throw std::runtime_error("new output required");
    for(int l:{0,3,4,23})for(auto op:{"gate","up","down"})o.target["blk."+std::to_string(l)+".ffn_"+op+".weight"]={l,op};
    std::ifstream input(argv[2]);json j;input>>j;auto ids=j.at("tokens").get<std::vector<llama_token>>();
    if(ids.size()!=256)throw std::runtime_error("exact 256 prompt tokens required");
    llama_backend_init();auto mp=llama_model_default_params();mp.n_gpu_layers=0;
    auto*m=llama_model_load_from_file(argv[1],mp);if(!m)throw std::runtime_error("model load");
    auto cp=llama_context_default_params();cp.n_ctx=512;cp.n_batch=256;cp.n_ubatch=256;
    cp.n_threads=4;cp.n_threads_batch=4;cp.n_seq_max=1;cp.n_rs_seq=0;cp.cb_eval=observe;cp.cb_eval_user_data=&o;
    auto*c=llama_init_from_model(m,cp);if(!c)throw std::runtime_error("context load");
    llama_memory_clear(llama_get_memory(c),true);o.enabled=true;o.phase="prefill";
    auto batch=llama_batch_get_one(ids.data(),ids.size());std::vector<int8_t> flags(256,0);std::fill(flags.end()-8,flags.end(),1);batch.logits=flags.data();
    if(llama_decode(c,batch)!=0||!o.error.empty())throw std::runtime_error("prefill capture: "+o.error);
    auto logits=llama_get_logits_ith(c,-1);int nv=llama_vocab_n_tokens(llama_model_get_vocab(m));
    llama_token tok=std::max_element(logits,logits+nv)-logits;
    o.phase="decode";auto next=llama_batch_get_one(&tok,1);
    if(llama_decode(c,next)!=0||!o.error.empty())throw std::runtime_error("decode capture: "+o.error);
    if(o.records.size()!=24)throw std::runtime_error("expected 24 actual projection observations");
    rusage r{};getrusage(RUSAGE_SELF,&r);
    json result={{"records",o.records},{"model_file",argv[1]},{"threads",4},{"gpu_layers",0},{"domain","PC"},
        {"prompt_tokens",ids},{"prefill_positions",{248,249,250,251,252,253,254,255}},
        {"decode_position",256},{"decode_input_token",tok},{"peak_rss_kib",r.ru_maxrss},
        {"vision",false},{"MTP",false},{"instrumented_not_performance",true},{"BOARD","NOT_TESTED"}};
    std::ofstream out(o.out/"capture.json");out<<result.dump(2);if(!out)throw std::runtime_error("manifest write");
    llama_free(c);llama_model_free(m);llama_backend_free();std::cout<<"24 projection captures completed\n";return 0;
}catch(const std::exception&e){std::cerr<<"CAPTURE_FAILURE: "<<e.what()<<"\n";return 2;}}
