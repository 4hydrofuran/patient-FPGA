#pragma once
#include "json.hpp"
#include "ggml.h"
#include <array>
#include <chrono>
#include <cstdint>
#include <string>
#include <map>
#include <tuple>
#include <unordered_map>
#include <vector>

namespace s1 {
using json=nlohmann::json;
inline uint64_t tick_ns(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
struct OpTiming {
    uint64_t calls=0,failures=0,inclusive=0,gather=0,quant=0,cache_copy=0,run=0,output_copy=0,cache_hits=0;
    uint64_t first_execution=0,last_execution=0;int n=0,k=0;
};
struct PhaseTiming {uint64_t decode_calls=0,decode_failures=0,decode_wall=0,graph_calls=0,graph_failures=0,graph_wall=0;};

// Mutually exclusive elapsed-time owners. Semantic roles never own extra time.
enum class NodeCategory : size_t {
    MlpCustom, Matrix, Movement, Normalization, Activation, Elementwise,
    Attention, State, Convolution, Other, UnknownCustom, Unknown, Count
};
struct NodeIdentity {
    NodeCategory category=NodeCategory::Unknown;
    int op=GGML_OP_NONE, subop=-1, layer=-1, weight_type=-1;
    std::string role="unknown", family="unknown", basis="op_only", weight;
    std::array<int64_t,4> output{}, input{}, source{};
    std::array<size_t,4> output_stride{}, input_stride{};
    bool operator<(const NodeIdentity& b) const {
        return std::tie(category,op,subop,layer,weight_type,role,family,basis,weight,
                        output,input,source,output_stride,input_stride)
             < std::tie(b.category,b.op,b.subop,b.layer,b.weight_type,b.role,b.family,
                        b.basis,b.weight,b.output,b.input,b.source,b.output_stride,b.input_stride);
    }
};
struct NodeTiming {
    uint64_t groups=0, logical_nodes=0, fused_extra=0, us=0, fused_groups=0, fused_us=0;
    void add(int fused,uint64_t elapsed) {
        ++groups; logical_nodes+=uint64_t(fused)+1; fused_extra+=uint64_t(fused); us+=elapsed;
        if(fused) { ++fused_groups; fused_us+=elapsed; }
    }
};
struct NodeRecord {
    NodeIdentity identity;
    std::array<NodeTiming,2> timing{};
    std::array<std::array<uint64_t,GGML_OP_COUNT>,2> fused_members{};
};
struct PreparedNode {const ggml_tensor* tensor=nullptr;size_t record=0;int op=0;bool observed=false;};
struct NodePhase {
    std::array<NodeTiming,size_t(NodeCategory::Count)> categories{};
    std::array<uint64_t,GGML_OP_COUNT> member_ops{};
    uint64_t missing_metadata=0, invalid_fusion=0, duplicate_callbacks=0;
    uint64_t prepare_ns=0, finish_ns=0, prepares=0, prepare_failures=0, maximum_nodes=0;
};
struct PerRequestStats {
    bool enabled=false,detail=false,active=false,non_cpu=false;
    int phase=0;std::string session,request;uint64_t epoch=0;
    std::array<NodePhase,2> node_phases{};
    std::map<NodeIdentity,size_t> node_record_index;
    std::vector<NodeRecord> node_records;
    std::unordered_map<const ggml_tensor*,size_t> node_index;
    std::vector<PreparedNode> prepared_nodes;
    bool graph_active=false;
    uint64_t graph_generation=0, invalid_phase_callbacks=0, invalid_phase_us=0;
    uint64_t overlapping_graphs=0;
    std::array<PhaseTiming,2> phases{};
    std::array<OpTiming,2*24*3*9> ops{};
    void begin(bool on,bool detailed,std::string sid,std::string rid,uint64_t ep){
        enabled=on;detail=detailed;active=true;non_cpu=false;phase=0;session=std::move(sid);request=std::move(rid);epoch=ep;phases={};ops={};
        node_phases={};node_record_index.clear();node_records.clear();node_index.clear();prepared_nodes.clear();
        graph_active=false;graph_generation=0;invalid_phase_callbacks=invalid_phase_us=overlapping_graphs=0;
    }
    void add(int layer,int op,int t,int n,int k,uint64_t execution,const OpTiming&v){
        if(!enabled||layer<0||layer>=24||op<0||op>=3||t<0||t>8)return;
        auto&o=ops[((phase*24+layer)*3+op)*9+t];
        o.calls+=v.calls;o.failures+=v.failures;o.inclusive+=v.inclusive;o.gather+=v.gather;o.quant+=v.quant;
        o.cache_copy+=v.cache_copy;o.run+=v.run;o.output_copy+=v.output_copy;o.cache_hits+=v.cache_hits;
        o.n=n;o.k=k;if(!o.first_execution)o.first_execution=execution;o.last_execution=execution;
    }
    json report()const;
    json node_report()const;
    // Graph-owned pointers exist only during a synchronous CPU execution.
    bool prepare_nodes(ggml_cgraph*) noexcept;
    void finish_nodes() noexcept;
    static NodeIdentity classify_node(const ggml_tensor*);
    static void node_observed(const ggml_tensor*,int,uint64_t,void*);
};
struct NodeGraphScope {
    PerRequestStats& stats;bool owns=false;
    NodeGraphScope(PerRequestStats& s,ggml_cgraph* graph):stats(s){owns=stats.prepare_nodes(graph);}
    ~NodeGraphScope(){if(owns)stats.finish_nodes();}
    NodeGraphScope(const NodeGraphScope&)=delete;
    NodeGraphScope& operator=(const NodeGraphScope&)=delete;
};
// Installed only around a synchronous llama_decode invocation, never graph construction.
extern thread_local PerRequestStats* active_profile;
struct DecodeScope {
    PerRequestStats&s;uint64_t begin=0;int phase;int rc=-1;
    DecodeScope(PerRequestStats&stats,int p):s(stats),phase(p){s.phase=p;if(s.enabled){begin=tick_ns();active_profile=&s;}}
    ~DecodeScope(){if(s.enabled){active_profile=nullptr;auto&p=s.phases[phase];p.decode_wall+=tick_ns()-begin;++p.decode_calls;if(rc)++p.decode_failures;}}
};
struct OperationScope {
    PerRequestStats&s;OpTiming value;int layer,op,t,n,k;uint64_t execution,begin=0;bool ok=false;
    OperationScope(PerRequestStats&stats,int l,int o,int tt,int nn,int kk,uint64_t ex):s(stats),layer(l),op(o),t(tt),n(nn),k(kk),execution(ex){if(s.enabled)begin=tick_ns();}
    ~OperationScope(){if(s.enabled){value.inclusive=tick_ns()-begin;value.calls=1;value.failures=ok?0:1;s.add(layer,op,t,n,k,execution,value);}}
};
}
