#include "bridge.hpp"
#include "w4a8.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <sys/mman.h>
#include <unistd.h>
// Use the installed OpenSSL 3 one-shot C ABI; no context struct ABI or new packages.
extern "C" unsigned char* SHA256(const unsigned char*,size_t,unsigned char*);
namespace s1 {
using Clock=std::chrono::steady_clock;
static std::string hash(const std::filesystem::path&p){
    auto size=std::filesystem::file_size(p);if(size>8*1024*1024)throw std::runtime_error("bounded manifest/tensor hash input");
    std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("missing hash input");std::vector<unsigned char>data(size);f.read(reinterpret_cast<char*>(data.data()),size);if(!f)throw std::runtime_error("hash read");unsigned char out[32];if(!SHA256(data.data(),data.size(),out))throw std::runtime_error("hash failed");
    std::ostringstream s;for(auto x:out)s<<std::hex<<std::setw(2)<<std::setfill('0')<<int(x);return s.str();
}
static json readj(const std::filesystem::path&p){std::ifstream f(p);json j;f>>j;return j;}
template<class T>static std::vector<T> read(const std::filesystem::path&root,const json&e){
    std::string name=e.at("file");if(name.empty()||name.find_first_of("/\\:")!=std::string::npos)throw std::runtime_error("unsafe sidecar path");
    auto p=root/name;size_t bytes=e.at("bytes");if(std::filesystem::is_symlink(p)||std::filesystem::file_size(p)!=bytes||bytes%sizeof(T)||hash(p)!=e.at("sha256"))throw std::runtime_error("sidecar hash/length");
    std::vector<T> v(bytes/sizeof(T));std::ifstream f(p,std::ios::binary);f.read(reinterpret_cast<char*>(v.data()),bytes);if(!f)throw std::runtime_error("sidecar read");return v;
}
static bool selected(const std::string&scope,int l,const std::string&o){return scope=="all"||(scope=="l0"&&l==0)||(scope=="l0_"+o&&l==0);}
Bridge::Bridge(const std::filesystem::path&root,std::string scope_,std::string algorithm,int threads):scope(std::move(scope_)){
    if(scope!="all"&&scope!="none"&&scope!="l0"&&scope!="l0_gate"&&scope!="l0_up"&&scope!="l0_down")throw std::runtime_error("unknown scope");
    auto base=root/"models/sidecar_A/qwen35-v1";auto m=readj(base/"manifest.json");
    if(hash(base/"manifest.json")!="cdb2a04dbd95d426ea8967cda0adb219a769d3630107a2af72d6ddf2d5285688"||m["entries"].size()!=72)throw std::runtime_error("unapproved sidecar");
    if(hash(root/"models/model.lock.json")!=m.at("model_lock_sha256")||hash(root/"quant/qwen35_tensor_map.json")!=m.at("tensor_map_sha256"))throw std::runtime_error("model mapping changed");
    auto config=root/"modules/linear_A/cpu_config.json";
    if(algorithm!="TILED"&&algorithm!="SCALAR")throw std::runtime_error("algorithm");
    // Scalar and thread overrides are separate trusted test configurations prepared by A05.
    if(algorithm=="SCALAR")config=root/"modules/linear_A/cpu_scalar_config.json";
    else if(threads==1)config=root/"modules/linear_A/cpu_single_config.json";
    else if(threads==2)config=root/"modules/linear_A/cpu_threads2_config.json";
    else if(threads==3)config=root/"modules/linear_A/cpu_threads3_config.json";
    if(sp_linear_open_v1(config.c_str(),&cpu)!=SP_OK)throw std::runtime_error("CPU backend open");
    try{for(const auto&e:m["entries"]){int l=e.at("layer");std::string op=e.at("op");if(!selected(scope,l,op))continue;
        Entry v;v.owner=this;v.id=e.at("id");v.name="blk."+std::to_string(l)+".ffn_"+op+".weight";v.op=op;v.layer=l;v.n=e.at("N");v.k=e.at("K");
        auto w=read<uint8_t>(base,e["files"]["w.bin"]);auto sw=read<float>(base,e["files"]["sw.bin"]);
        if(sp_linear_load_v1(cpu,v.n,v.k,w.data(),w.size(),sw.data(),sw.size()*4,&v.handle)!=SP_OK)throw std::runtime_error("CPU weight load");
        entries.emplace(v.name,std::move(v)); // backend owns copies; transient file arrays are released here.
    }}catch(...){sp_linear_close_v1(cpu);cpu=nullptr;throw;}
    scratch.reserve(8*4864);y.reserve(8*4864);qx.reserve(8*4864);sx.reserve(8);
}
Bridge::~Bridge(){if(cpu)sp_linear_close_v1(cpu);}
void Bridge::reset(){++epoch;execution=0;cache.valid=false;error.clear();quantizations=cache_hits=0;quant_ms=copy_ms=0;physical_t_calls.fill(0);dumps=json::array();for(auto&v:entries){v.second.calls=0;v.second.tokens=0;}}
void Bridge::begin_execution(){++execution;cache.valid=false;}
void Bridge::set_diagnostic(const std::string&p){diagnostic=p;if(!p.empty()&&!std::filesystem::create_directory(diagnostic))throw std::runtime_error("new diagnostic directory required");}
void Bridge::protect_unused_weight(ggml_tensor*w,Entry&e){
    if(gguf_ranges.count(e.name))return;
    uintptr_t ptr=reinterpret_cast<uintptr_t>(w->data);size_t size=ggml_nbytes(w),page=sysconf(_SC_PAGESIZE);
    uintptr_t lo=(ptr+page-1)/page*page,hi=(ptr+size)/page*page;
    bool mapped=false;std::ifstream maps("/proc/self/maps");std::string line;
    while(std::getline(maps,line)){unsigned long a,b;char perms[5];if(std::sscanf(line.c_str(),"%lx-%lx %4s",&a,&b,perms)==3&&ptr>=a&&ptr+size<=b&&line.find("qwen35-text-")!=std::string::npos&&line.find(".gguf")!=std::string::npos&&perms[1]!='w'){mapped=true;break;}}
    if(!mapped)throw std::runtime_error("Selected GGUF weight must be direct read-only file mapping, not a repacked copy");
    if(hi>lo&&(madvise(reinterpret_cast<void*>(lo),hi-lo,MADV_DONTNEED)||mprotect(reinterpret_cast<void*>(lo),hi-lo,PROT_NONE)))throw std::runtime_error("GGUF selected-page discard/protect failed");
    gguf_ranges[e.name]={{"address_begin",lo},{"address_end",hi},{"gguf_tensor_bytes",size},{"protected_discarded_bytes",hi-lo},{"boundary_bytes_not_discarded",size-(hi-lo)},
                        {"policy","MADV_DONTNEED then PROT_NONE on interior full pages; original file unchanged"}};
}
ggml_tensor* Bridge::graph(ggml_context*c,ggml_tensor*w,ggml_tensor*x,void*u){
    auto&b=*static_cast<Bridge*>(u);auto found=b.entries.find(w->name);if(found==b.entries.end())return nullptr;auto&e=found->second;
    if(w->ne[0]!=e.k||w->ne[1]!=e.n||w->ne[2]!=1||w->ne[3]!=1||x->ne[0]!=e.k||x->ne[2]!=1||x->ne[3]!=1||x->type!=GGML_TYPE_F32||x->ne[1]>256)throw std::runtime_error("Exact MLP identity/shape/stride contract");
    b.protect_unused_weight(w,e);ggml_tensor*args[]={x};
    return ggml_custom_4d(c,GGML_TYPE_F32,e.n,x->ne[1],1,1,args,1,compute,1,&e);
}
void Bridge::compute(ggml_tensor*dst,int ith,int,void*u){
    if(ith)return;auto&e=*static_cast<Entry*>(u);auto&b=*e.owner;
    OperationScope timing(b.request_stats,e.layer,e.op=="gate"?0:e.op=="up"?1:2,int(dst->src[0]->ne[1]),e.n,e.k,b.execution);
    auto&tv=timing.value;const bool prof=b.request_stats.enabled;
    try{if(!b.error.empty())throw std::runtime_error(b.error);auto*x=dst->src[0];const int t=int(x->ne[1]),k=e.k,n=e.n;
        std::array<size_t,4> strides;std::copy(x->nb,x->nb+4,strides.begin());const int bit=e.op=="up"?1:2;
        const bool shared=e.op!="down";auto&cache=b.cache;
        bool hit=shared&&cache.valid&&cache.epoch==b.epoch&&cache.execution==b.execution&&cache.layer==e.layer&&cache.k==k&&cache.t==t&&cache.tensor==x&&cache.strides==strides&&!(cache.mask&bit);
        auto begin=Clock::now();
        if(!hit){cache.q.resize(t*k);cache.sx.resize(t);
            for(int start=0;start<t;start+=8){int count=std::min(8,t-start);b.scratch.resize(count*k);
                uint64_t pt=prof?tick_ns():0;
                for(int row=0;row<count;++row)for(int col=0;col<k;++col)std::memcpy(&b.scratch[row*k+col],static_cast<const char*>(x->data)+(start+row)*x->nb[1]+col*x->nb[0],4);
                if(prof){tv.gather+=tick_ns()-pt;pt=tick_ns();}
                a04::activation(a04::Shape(n,k,count),b.scratch,b.qx,b.sx);
                if(prof){tv.quant+=tick_ns()-pt;pt=tick_ns();}
                std::copy(b.qx.begin(),b.qx.end(),cache.q.begin()+start*k);std::copy(b.sx.begin(),b.sx.end(),cache.sx.begin()+start);++b.quantizations;
                if(prof)tv.cache_copy+=tick_ns()-pt;
            }
            cache.valid=shared;cache.epoch=b.epoch;cache.execution=b.execution;cache.layer=e.layer;cache.k=k;cache.t=t;cache.tensor=x;cache.strides=strides;cache.mask=0;
        }else {++b.cache_hits;tv.cache_hits=1;}
        b.quant_ms+=std::chrono::duration<double,std::milli>(Clock::now()-begin).count();cache.mask|=bit;if(cache.mask==3||!shared)cache.valid=false;
        for(int start=0;start<t;start+=8){int count=std::min(8,t-start);b.y.resize(count*n);
            uint64_t run_start=prof?tick_ns():0;
            int rc=sp_linear_run_v1(b.cpu,e.handle,count,cache.q.data()+start*k,count*k,cache.sx.data()+start,count*4,b.y.data(),count*n*4,++b.job,30000);
            if(prof)tv.run+=tick_ns()-run_start;
            if(rc!=SP_OK)throw std::runtime_error("SP_LINEAR run rejected: "+std::to_string(rc));
            ++b.physical_t_calls[count];
            auto copy_begin=Clock::now();uint64_t cp=prof?tick_ns():0;for(int row=0;row<count;++row)std::memcpy(static_cast<char*>(dst->data)+(start+row)*dst->nb[1],b.y.data()+row*n,n*4);
            if(prof)tv.output_copy+=tick_ns()-cp;
            b.copy_ms+=std::chrono::duration<double,std::milli>(Clock::now()-copy_begin).count();++e.calls;e.tokens+=count;
        }
        if(!b.diagnostic.empty()&&(b.diagnostic_all_layers||e.layer==0||e.layer==3||e.layer==4||e.layer==23)){
            std::string prefix=std::to_string(b.execution)+"_"+std::to_string(e.calls)+"_"+e.id;
            std::vector<float> xx(t*k),yy(t*n);
            for(int row=0;row<t;++row){for(int col=0;col<k;++col)std::memcpy(&xx[row*k+col],static_cast<char*>(x->data)+row*x->nb[1]+col*x->nb[0],4);std::memcpy(yy.data()+row*n,static_cast<char*>(dst->data)+row*dst->nb[1],n*4);}
            auto save=[&](std::string suffix,const std::vector<float>&v){auto p=b.diagnostic/(prefix+suffix);if(std::filesystem::exists(p))throw std::runtime_error("duplicate dump");std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*4);if(!f)throw std::runtime_error("dump failed");};save(".x.bin",xx);save(".y.bin",yy);
            b.dumps.push_back({{"id",e.id},{"execution",b.execution},{"epoch",b.epoch},{"N",n},{"K",k},{"T",t},{"input",prefix+".x.bin"},{"output",prefix+".y.bin"},{"input_strides",strides},{"op","GGML_OP_CUSTOM"}});
        }
        timing.ok=true;
    }catch(const std::exception&ex){b.error=ex.what();std::fill_n(static_cast<float*>(dst->data),ggml_nelements(dst),NAN);b.cache.valid=false;}
}
json Bridge::report(bool diagnostic)const{
    uint64_t size=0;if(sp_linear_report_v1(cpu,nullptr,0,&size)!=SP_OK)throw std::runtime_error("CPU report query");std::vector<char>text(size);if(sp_linear_report_v1(cpu,text.data(),size,&size)!=SP_OK)throw std::runtime_error("CPU report");
    json j=json::parse(text.data());j["scope"]=scope;j["epoch"]=epoch;j["executions"]=execution;j["quantization_blocks"]=quantizations;j["gate_up_cache_hits"]=cache_hits;j["runtime_quant_and_gather_ms"]=quant_ms;j["runtime_output_copy_ms"]=copy_ms;
    j["weights"]=nullptr;if(diagnostic){j["weights"]=json::object();for(const auto&kv:entries)j["weights"][kv.second.id]={{"calls",kv.second.calls},{"tokens",kv.second.tokens},{"handle",kv.second.handle}};}
    j["gguf_target_ranges"]=diagnostic?json(gguf_ranges):json(nullptr);j["error"]=error;j["no_weight_quantization_at_runtime"]=true;j["board"]="NOT_TESTED";
    j["physical_cpu_calls_by_T"]=json::object();for(size_t t=1;t<physical_t_calls.size();++t)if(physical_t_calls[t])j["physical_cpu_calls_by_T"][std::to_string(t)]=physical_t_calls[t];
    // smaps is a measured per-process residency view, not a system file-cache claim.
    uint64_t protected_rss_kib=0,protected_vma_bytes=0;std::ifstream smaps;if(diagnostic)smaps.open("/proc/self/smaps");std::string line;bool selected_vma=false;
    while(std::getline(smaps,line)){unsigned long lo,hi;char perms[5];
        if(std::sscanf(line.c_str(),"%lx-%lx %4s",&lo,&hi,perms)==3){selected_vma=false;
            if(perms[0]=='-'&&perms[1]=='-'&&perms[2]=='-'&&line.find(".gguf")!=std::string::npos){
                for(const auto&r:gguf_ranges)if(lo<uint64_t(r.second["address_end"])&&hi>uint64_t(r.second["address_begin"]))selected_vma=true;
                if(selected_vma)protected_vma_bytes+=hi-lo;}}
        else if(selected_vma&&line.rfind("Rss:",0)==0){std::istringstream s(line.substr(4));uint64_t kb;s>>kb;protected_rss_kib+=kb;}}
    j["protected_gguf_vma_bytes"]=diagnostic?json(protected_vma_bytes):json(nullptr);j["protected_gguf_rss_kib"]=diagnostic?json(protected_rss_kib):json(nullptr);
    j["residency_measurement"]=diagnostic?"SMAPS_DIAGNOSTIC":"NOT_SAMPLED_PERFORMANCE_MODE";
    j["runtime_buffer_capacity_bytes"]=scratch.capacity()*4+y.capacity()*4+qx.capacity()+sx.capacity()*4+cache.q.capacity()+cache.sx.capacity()*4;
    return j;
}
}
