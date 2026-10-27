#pragma once
// Private TT10 prefix checkpoints. Never snapshot device ownership, jobs or permits.
#include "json.hpp"
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

// Reuse the installed libcrypto ABI, as the existing route does; no dev package install.
extern "C" {
struct evp_md_ctx_st;struct evp_md_st;struct engine_st;
unsigned char* SHA256(const unsigned char*,size_t,unsigned char*);
evp_md_ctx_st* EVP_MD_CTX_new(void);
void EVP_MD_CTX_free(evp_md_ctx_st*);
const evp_md_st* EVP_sha256(void);
int EVP_DigestInit_ex(evp_md_ctx_st*,const evp_md_st*,engine_st*);
int EVP_DigestUpdate(evp_md_ctx_st*,const void*,size_t);
int EVP_DigestFinal_ex(evp_md_ctx_st*,unsigned char*,unsigned int*);
}

namespace tt10 {
using json=nlohmann::json;
inline std::string digest(const void* p,size_t n) {
    unsigned char out[32];unsigned int len=32;
    if(!SHA256(static_cast<const unsigned char*>(p),n,out))throw std::runtime_error("snapshot digest failed");
    const char* hex="0123456789abcdef";std::string s;
    for(unsigned i=0;i<len;++i){s+=hex[out[i]>>4];s+=hex[out[i]&15];}return s;
}
inline std::string digest(const std::string& s){return digest(s.data(),s.size());}
inline std::string file_digest(const std::filesystem::path& path) {
    std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("identity file unreadable");
    auto* ctx=EVP_MD_CTX_new();if(!ctx)throw std::bad_alloc();
    bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)==1;char buf[65536];
    while(ok&&f){f.read(buf,sizeof(buf));if(f.gcount())ok=EVP_DigestUpdate(ctx,buf,size_t(f.gcount()))==1;}
    unsigned char out[64];unsigned int n=0;ok=ok&&f.eof()&&EVP_DigestFinal_ex(ctx,out,&n)==1;EVP_MD_CTX_free(ctx);
    if(!ok)throw std::runtime_error("identity file digest failed");
    const char* hex="0123456789abcdef";std::string s;for(unsigned i=0;i<n;++i){s+=hex[out[i]>>4];s+=hex[out[i]&15];}return s;
}
struct Snapshot {
    std::vector<uint8_t> state;
    std::vector<float> logits; // Pinned state_get_data implementation omits outputs.
    std::vector<int32_t> tokens;
    json owner;
    std::string binding,state_sha,logits_sha,sequence_sha;
    int position=-1;
    size_t bytes()const{return state.size()+logits.size()*sizeof(float)+tokens.size()*sizeof(int32_t)+owner.dump().size()+512;}
};
class PrefixStore {
    std::map<std::string,Snapshot> slots;
    json config,base;
    std::string binding;
    bool enabled=false;
public:
    static constexpr size_t SLOT_LIMIT=2, SLOT_BYTES=64*1024*1024, SCRATCH_BYTES=64*1024*1024;
    PrefixStore()=default;
    explicit PrefixStore(json cfg):config(std::move(cfg)),base(config.at("identity")),enabled(true){
        if(config.at("schema")!="TT10_01_CONFIG_V1")throw std::runtime_error("unknown snapshot config");
        if(config.at("max_slots")!=SLOT_LIMIT||config.at("max_slot_bytes")!=SLOT_BYTES)throw std::runtime_error("unreviewed snapshot limits");
        binding=digest(base.dump());
    }
    static PrefixStore load(const char* model,const char* executable,const std::string& mode,int threads,int kernel_threads,int context,int physical) {
        const char* path=std::getenv("SP_TT10_CONFIG");if(!path)return PrefixStore();
        if(std::filesystem::file_size(path)>65536)throw std::runtime_error("snapshot config size");
        std::ifstream f(path);json cfg;f>>cfg;
        auto& id=cfg.at("identity");
        if(file_digest(model)!=id.at("model_sha256")||file_digest(executable)!=id.at("executable_sha256"))throw std::runtime_error("snapshot model/executable identity differs");
        if(id.at("threads")!=threads||id.at("kernel_threads")!=kernel_threads||id.at("context")!=context||id.at("physical_ubatch")!=physical||id.at("sampler")!="fresh_greedy_v1")throw std::runtime_error("snapshot runtime configuration differs");
        std::ifstream maps("/proc/self/maps");std::string line;std::map<std::string,std::string> loaded;
        while(std::getline(maps,line)){
            auto slash=line.find('/');if(slash==std::string::npos)continue;
            auto p=std::filesystem::path(line.substr(slash));auto name=p.filename().string();
            auto suffix=name.find(".so.");if(suffix!=std::string::npos)name.resize(suffix+3);
            if(id.at("libraries").contains(name)&&!loaded.count(name)){
                auto h=file_digest(p);if(h!=id.at("libraries").at(name))throw std::runtime_error("snapshot loaded library identity differs: "+name);loaded[name]=h;
            }
        }
        for(const auto* name:{"libllama.so","libggml-base.so","libggml-cpu.so","libsp_linear_cpu.so"})if(!loaded.count(name))throw std::runtime_error("snapshot required loaded library missing: "+std::string(name));
        if(mode=="FPGA_REAL"&&!loaded.count("libsp_linear_a12_trial.so"))throw std::runtime_error("snapshot PL library missing");
        id["execution_kind"]=mode;id["verified_loaded_libraries"]=loaded;
        return PrefixStore(std::move(cfg));
    }
    bool active()const{return enabled;}
    const std::string& key()const{return binding;}
    static json owner_of(const json& req) {
        auto owner=req.value("cache_owner",json{{"kind","public_neutral"}});
        if(owner.at("kind")=="public_neutral"){
            if(owner.size()!=1)throw std::runtime_error("public prefix cannot contain case/session data");
        }else if(owner.at("kind")=="case_session"){
            if(owner.size()!=5||owner.at("case_id").get<std::string>().empty()||owner.at("case_sha256").get<std::string>().size()!=64||owner.at("session_id").get<std::string>().empty()||!owner.at("epoch").is_number_unsigned())throw std::runtime_error("incomplete private checkpoint owner");
        }else throw std::runtime_error("unknown snapshot namespace");
        if(owner.dump().size()>1024)throw std::runtime_error("checkpoint owner too large");return owner;
    }
    void owner_changed(const json& owner) {
        for(auto i=slots.begin();i!=slots.end();)if(i->second.owner.at("kind")=="case_session"&&i->second.owner!=owner)i=slots.erase(i);else ++i;
    }
    void clear_private(){for(auto i=slots.begin();i!=slots.end();)if(i->second.owner.at("kind")=="case_session")i=slots.erase(i);else ++i;}
    void clear(){slots.clear();}
    void drop(const std::string& id){slots.erase(id);}
    void reserve_create(const json& req,const std::vector<int32_t>& tokens) {
        if(!enabled||!req.value("confirmed_prefix",false)||req.at("cache_binding_sha256")!=binding)throw std::runtime_error("unconfirmed or mismatched checkpoint identity");
        auto id=req.at("cache_id").get<std::string>();if(id.empty()||id.size()>80)throw std::runtime_error("checkpoint name size");
        auto owner=owner_of(req);owner_changed(owner);
        bool allowed=false;for(const auto& prefix:config.at("allowed_prefixes"))if(prefix.get<std::vector<int32_t>>()==tokens)allowed=true;
        if(tokens.empty()||tokens.size()>128||!allowed)throw std::runtime_error("prefix is not in reviewed token allowlist");
        if(!slots.count(id)&&slots.size()>=SLOT_LIMIT)throw std::runtime_error("checkpoint slot limit");
        // Replacement is explicit eviction before capture; failed capture cannot retain a half-new checkpoint.
        slots.erase(id);
    }
    void commit(const std::string& id,Snapshot snapshot) {
        if(snapshot.bytes()>SLOT_BYTES||slots.size()>=SLOT_LIMIT||slots.count(id))throw std::runtime_error("checkpoint memory/slot limit");
        if(snapshot.state.empty()||snapshot.logits.empty()||snapshot.position!=int(snapshot.tokens.size())-1)throw std::runtime_error("incomplete checkpoint");
        snapshot.binding=binding;snapshot.state_sha=digest(snapshot.state.data(),snapshot.state.size());
        snapshot.logits_sha=digest(snapshot.logits.data(),snapshot.logits.size()*sizeof(float));
        slots.emplace(id,std::move(snapshot));
    }
    const Snapshot* lookup(const json& req,const std::vector<int32_t>& tokens,std::string& reason) {
        reason="CACHE_DISABLED";if(!enabled)return nullptr;
        auto owner=owner_of(req);owner_changed(owner);
        if(req.value("cache_binding_sha256",std::string())!=binding){clear();reason="VERSION_BINDING_MISMATCH";return nullptr;}
        auto id=req.value("cache_id",std::string());auto i=slots.find(id);reason="NOT_FOUND";if(i==slots.end())return nullptr;
        const auto& s=i->second;
        if(s.binding!=binding||s.owner!=owner){slots.erase(i);reason="OWNER_OR_BINDING_MISMATCH";return nullptr;}
        if(tokens.size()<s.tokens.size()||!std::equal(s.tokens.begin(),s.tokens.end(),tokens.begin())){reason="TOKEN_PREFIX_MISMATCH";return nullptr;}
        if(digest(s.state.data(),s.state.size())!=s.state_sha||digest(s.logits.data(),s.logits.size()*sizeof(float))!=s.logits_sha){slots.erase(i);reason="CORRUPT_SNAPSHOT";return nullptr;}
        reason="EXACT_FULL_STATE_HIT";return &s;
    }
    json report()const {
        json entries=json::array();size_t bytes=0;
        for(const auto& [id,s]:slots){bytes+=s.bytes();entries.push_back({{"id",id},{"owner",s.owner},{"tokens",s.tokens.size()},{"position",s.position},{"state_bytes",s.state.size()},{"logits_bytes",s.logits.size()*sizeof(float)},{"charged_bytes",s.bytes()},{"state_sha256",s.state_sha},{"logits_sha256",s.logits_sha},{"sequence_sha256",s.sequence_sha}});}
        return {{"enabled",enabled},{"schema","TT10_FULL_PREFIX_V1"},{"binding_sha256",binding},{"identity",base},{"max_slots",SLOT_LIMIT},{"max_slot_bytes",SLOT_BYTES},{"scratch_limit_bytes",SCRATCH_BYTES},{"retained_bytes",bytes},{"entries",entries},{"sampling","fresh stateless greedy; logits stored separately from pinned memory-only state API"}};
    }
#ifdef SP_A12_PC_TEST
    void damage(const std::string& id,const std::string& kind) {
        auto& s=slots.at(id);
        if(kind=="digest")s.state.at(0)^=1;
        else if(kind=="partial_restore"){s.state.resize(s.state.size()/2);s.state_sha=digest(s.state.data(),s.state.size());}
        else throw std::runtime_error("unknown test damage");
    }
#endif
};
}
