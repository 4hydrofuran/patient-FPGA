#include "request_profile.hpp"
#include "ggml-backend.h"
#if !defined(_WIN32) && !defined(S1_PROFILE_NO_INTERPOSE)
#include <dlfcn.h>
#endif
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace s1 {
thread_local PerRequestStats* active_profile=nullptr;
json PerRequestStats::report()const{
    json result={{"schema","N02_REQUEST_PROFILE_V1"},{"enabled",enabled},{"detail",detail},
        {"session_id",session},{"request_id",request},{"session_epoch",epoch},
        {"scope","CURRENT_REQUEST_NOT_LAST_OPERATION_OR_LIFETIME"},{"BOARD","NOT_TESTED"}};
    if(!enabled){result["phases"]=nullptr;return result;}
    result["phases"]=json::object();result["layers"]=detail?json::array():json(nullptr);bool valid=!non_cpu;
    for(int p=0;p<2;++p){OpTiming sum;json shapes=json::object();
        for(int l=0;l<24;++l)for(int op=0;op<3;++op)for(int t=0;t<9;++t){
            const auto&o=ops[((p*24+l)*3+op)*9+t];if(!o.calls)continue;
            sum.calls+=o.calls;sum.failures+=o.failures;sum.inclusive+=o.inclusive;sum.gather+=o.gather;sum.quant+=o.quant;
            sum.cache_copy+=o.cache_copy;sum.run+=o.run;sum.output_copy+=o.output_copy;sum.cache_hits+=o.cache_hits;
            shapes[std::to_string(t)]=shapes.value(std::to_string(t),uint64_t(0))+o.calls;
            if(detail)result["layers"].push_back({{"phase",p?"decode":"prefill"},{"layer",l},{"op",op==0?"gate":op==1?"up":"down"},
                {"N",o.n},{"K",o.k},{"T",t},{"calls",o.calls},{"failures",o.failures},{"first_execution",o.first_execution},
                {"last_execution",o.last_execution},{"wall_ms",o.inclusive/1e6},{"linear_service_ms",o.run/1e6},
                {"gather_ms",o.gather/1e6},{"activation_quant_ms",o.quant/1e6},{"activation_cache_copy_ms",o.cache_copy/1e6},
                {"output_copy_ms",o.output_copy/1e6},{"gate_up_cache_hits",o.cache_hits}});
        }
        const auto&x=phases[p];double other=(double(x.graph_wall)-sum.inclusive)/1e6;
        double host=(double(x.decode_wall)-x.graph_wall)/1e6;
        double overhead=(double(sum.inclusive)-sum.gather-sum.quant-sum.cache_copy-sum.run-sum.output_copy)/1e6;
        if(other<0||host<0||overhead<0||(x.decode_calls&&!x.graph_calls))valid=false;
        result["phases"][p?"decode":"prefill"]={{"llama_decode_wall_ms",x.decode_wall/1e6},{"decode_calls",x.decode_calls},{"decode_failures",x.decode_failures},
            {"cpu_graph_wall_ms",x.graph_wall/1e6},{"graph_calls",x.graph_calls},{"graph_failures",x.graph_failures},
            {"mlp_inclusive_wall_ms",sum.inclusive/1e6},{"mlp_calls",sum.calls},{"mlp_failures",sum.failures},
            {"linear_service_wall_ms",sum.run/1e6},{"activation_gather_ms",sum.gather/1e6},{"activation_quant_ms",sum.quant/1e6},
            {"activation_cache_copy_ms",sum.cache_copy/1e6},{"output_copy_ms",sum.output_copy/1e6},{"bridge_other_ms",overhead},
            {"non_mlp_cpu_graph_ms",other},{"host_graph_prepare_schedule_ms",host},{"physical_T_calls",shapes},
            {"gate_up_cache_hits",sum.cache_hits}};
    }
    result["accounting_valid"]=valid;
    result["non_mlp_scope"]="CPU backend graph wall minus nested MLP custom callbacks; includes other ops, backend planning, thread scheduling/barriers, not pure attention FLOPs";
    result["nesting"]="llama_decode = cpu_graph + host_prepare_schedule; cpu_graph = MLP_inclusive + non_MLP; MLP = linear_service + quant/gather/cache/output_copy + bridge_other; never sum parents with children";
    return result;
}
}

// Linux ELF interposition of the existing exported API, pinned source audited:
// ggml-backend.cpp delegates to iface.graph_compute; the CPU implementation
// returns only after ggml_graph_compute completes. No extra sync, node split,
// callback selection, graph mutation, fusion change or tensor read is introduced.
// Fail closed for timing if the caller is not the single synchronous CPU backend.
#if !defined(_WIN32) && !defined(S1_PROFILE_NO_INTERPOSE)
extern "C" enum ggml_status ggml_backend_graph_compute_async(ggml_backend_t backend,ggml_cgraph* graph){
    using Fn=enum ggml_status(*)(ggml_backend_t,ggml_cgraph*);
    static Fn original=reinterpret_cast<Fn>(dlsym(RTLD_NEXT,"ggml_backend_graph_compute_async"));
    if(!original)std::abort();
    auto*s=s1::active_profile;
    if(!s||!s->enabled)return original(backend,graph);
    if(s->phase<0||s->phase>1){++s->invalid_phase_callbacks;return original(backend,graph);}
    if(std::strcmp(ggml_backend_name(backend),"CPU")!=0){
        s->non_cpu=true;
        return original(backend,graph); // Never retain pointers around an asynchronous backend.
    }
    s1::NodeGraphScope nodes(*s,graph);
    auto begin=s1::tick_ns();auto rc=original(backend,graph);
    auto&p=s->phases[s->phase];p.graph_wall+=s1::tick_ns()-begin;++p.graph_calls;if(rc!=GGML_STATUS_SUCCESS)++p.graph_failures;
    return rc;
}
#endif

namespace s1 {
namespace {
const char* category_names[]={"mlp_custom_linear","matrix","data_movement","normalization",
    "activation","elementwise","attention_kernel","state_kernel","convolution",
    "other_known_op","unknown_custom","unknown"};
static_assert(sizeof(category_names)/sizeof(*category_names)==size_t(NodeCategory::Count),"category schema");

bool parse_layer(const std::string& text,size_t begin,size_t end,int& layer){
    if(begin==end||end-begin>2)return false;
    int n=0;
    for(size_t i=begin;i<end;++i){if(text[i]<'0'||text[i]>'9')return false;n=n*10+text[i]-'0';}
    if(n>=24)return false;
    layer=n;return true;
}
bool weight_role(const char* name,std::string& role,std::string& family,int& layer){
    std::string n=name;
    if(n=="output.weight"){role="output_head";return true;}
    if(n.compare(0,4,"blk.")!=0)return false;
    auto dot=n.find('.',4);
    if(dot==std::string::npos||!parse_layer(n,4,dot,layer))return false;
    const std::string suffix=n.substr(dot+1);
    const char* full[]={"attn_q","attn_k","attn_v","attn_output"};
    const char* linear[]={"attn_qkv","attn_gate","ssm_alpha","ssm_beta","ssm_out"};
    for(const char* s:full)if(suffix==std::string(s)+".weight"){
        role=s;family="full_attention";return true;
    }
    for(const char* s:linear)if(suffix==std::string(s)+".weight"){
        role=s;family="linear_attention";return true;
    }
    for(const char* s:{"ffn_gate","ffn_up","ffn_down"})if(suffix==std::string(s)+".weight"){
        role=s;return true;
    }
    layer=-1;return false;
}
bool custom_role(const ggml_tensor* t,NodeIdentity& id){
    const std::string n=t->name;
    auto dash=n.rfind('-');int layer=-1;
    if(dash==std::string::npos||!parse_layer(n,dash+1,n.size(),layer))return false;
    auto stem=n.substr(0,dash);
    if(stem!="ffn_gate"&&stem!="ffn_up"&&stem!="ffn_down"&&stem!="ffn_out")return false;
    auto* x=t->src[0];
    if(!x||x->type!=GGML_TYPE_F32||t->type!=GGML_TYPE_F32||
       x->ne[0]<=0||t->ne[0]<=0||x->ne[1]<0||t->ne[1]!=x->ne[1]||
       x->ne[2]!=1||x->ne[3]!=1||t->ne[2]!=1||t->ne[3]!=1)return false;
    id.layer=layer;id.role=stem=="ffn_out"?"ffn_down":stem;
    // The pinned bridge exposes only activation as src[0]. This is explicitly
    // a legacy structural identity, NOT a recovered custom weight pointer.
    id.basis="pinned_custom_name_and_structure";return true;
}
bool projection_shape(const ggml_tensor* t){
    const auto* w=t->src[0];const auto* x=t->src[1];
    return w&&x&&w->op==GGML_OP_NONE&&w->ne[0]>0&&w->ne[1]>0&&w->ne[0]==x->ne[0]&&
        t->ne[0]==w->ne[1]&&t->ne[1]==x->ne[1]&&
        w->ne[2]==1&&w->ne[3]==1&&x->ne[2]==1&&x->ne[3]==1&&t->ne[2]==1&&t->ne[3]==1;
}
json timing_json(const NodeTiming& t){
    return {{"timed_groups",t.groups},{"logical_nodes",t.logical_nodes},
        {"fused_extra_nodes",t.fused_extra},{"wall_us",t.us},{"wall_ms",t.us/1000.0},
        {"single_node_groups",t.groups-t.fused_groups},{"single_node_wall_us",t.us-t.fused_us},
        {"fused_groups",t.fused_groups},{"fused_group_wall_us",t.fused_us},
        {"fused_suboperation_wall_us",nullptr}};
}
void merge_timing(NodeTiming& a,const NodeTiming& b){
    a.groups+=b.groups;a.logical_nodes+=b.logical_nodes;a.fused_extra+=b.fused_extra;
    a.us+=b.us;a.fused_groups+=b.fused_groups;a.fused_us+=b.fused_us;
}
json op_counts(const std::array<uint64_t,GGML_OP_COUNT>& counts){
    json result=json::object();
    for(int op=0;op<GGML_OP_COUNT;++op)if(counts[op])result[ggml_op_name(ggml_op(op))]=counts[op];
    return result;
}
} // namespace

NodeIdentity PerRequestStats::classify_node(const ggml_tensor* t){
    NodeIdentity id;if(!t)return id;
    id.op=t->op;
    std::copy(t->ne,t->ne+4,id.output.begin());std::copy(t->nb,t->nb+4,id.output_stride.begin());
    auto* input=t->src[t->op==GGML_OP_MUL_MAT?1:0];
    if(input){std::copy(input->ne,input->ne+4,id.input.begin());std::copy(input->nb,input->nb+4,id.input_stride.begin());}
    if(t->src[0])std::copy(t->src[0]->ne,t->src[0]->ne+4,id.source.begin());
    switch(t->op){
        case GGML_OP_MUL_MAT:case GGML_OP_MUL_MAT_ID:case GGML_OP_OUT_PROD:
            id.category=NodeCategory::Matrix;id.role="matrix_unknown_identity";
            if(t->op==GGML_OP_MUL_MAT&&t->src[0]){
                std::string role,family="unknown";int layer=-1;
                const auto* weight=t->src[0];
                const bool tied_head=std::strcmp(weight->name,"token_embd.weight")==0 &&
                    weight->ne[0]==1024 && weight->ne[1]==248320 &&
                    weight->type==GGML_TYPE_Q6_K && projection_shape(t);
                if(tied_head){role="output_head";family="unknown";}
                if(tied_head || weight_role(weight->name,role,family,layer)){
                    if(projection_shape(t)){
                        id.role=role;id.family=family;id.layer=layer;id.weight=t->src[0]->name;
                        id.weight_type=t->src[0]->type;id.basis=tied_head?"pinned_tied_embedding_output_weight_and_shape":"source_weight_name_and_shape";
                    }else id.basis="known_weight_name_shape_mismatch";
                }
            }
            break;
        case GGML_OP_CUSTOM:
            id.category=custom_role(t,id)?NodeCategory::MlpCustom:NodeCategory::UnknownCustom;break;
        case GGML_OP_CONCAT:case GGML_OP_CONT:case GGML_OP_CPY:case GGML_OP_DUP:
        case GGML_OP_GET_ROWS:case GGML_OP_SET_ROWS:case GGML_OP_SET:case GGML_OP_ACC:
        case GGML_OP_REPEAT:case GGML_OP_PAD:
            id.category=NodeCategory::Movement;break;
        case GGML_OP_NORM:case GGML_OP_RMS_NORM:case GGML_OP_L2_NORM:case GGML_OP_GROUP_NORM:
            id.category=NodeCategory::Normalization;break;
        case GGML_OP_GLU:
            id.category=NodeCategory::Activation;id.subop=ggml_get_glu_op(t);break;
        case GGML_OP_UNARY:
            id.category=NodeCategory::Activation;id.subop=ggml_get_unary_op(t);break;
        case GGML_OP_ADD:case GGML_OP_ADD1:case GGML_OP_SUB:case GGML_OP_MUL:case GGML_OP_DIV:
        case GGML_OP_SCALE:case GGML_OP_SQR:case GGML_OP_SQRT:case GGML_OP_LOG:
        case GGML_OP_SIN:case GGML_OP_COS:case GGML_OP_CLAMP:
            id.category=NodeCategory::Elementwise;break;
        case GGML_OP_FLASH_ATTN_EXT:case GGML_OP_FLASH_ATTN_BACK:
            id.category=NodeCategory::Attention;id.role="full_attention_kernel";id.family="full_attention";break;
        case GGML_OP_GATED_DELTA_NET:case GGML_OP_SSM_SCAN:case GGML_OP_GATED_LINEAR_ATTN:
            id.category=NodeCategory::State;id.role="fused_state_update";id.family="linear_attention";break;
        case GGML_OP_SSM_CONV:
            id.category=NodeCategory::Convolution;id.role="linear_convolution";id.family="linear_attention";break;
        case GGML_OP_MAP_CUSTOM1:case GGML_OP_MAP_CUSTOM2:case GGML_OP_MAP_CUSTOM3:
            id.category=NodeCategory::UnknownCustom;break;
        default:
            if(int(t->op)>GGML_OP_NONE&&int(t->op)<GGML_OP_COUNT)id.category=NodeCategory::Other;
            break;
    }
    return id;
}

bool PerRequestStats::prepare_nodes(ggml_cgraph* graph) noexcept{
    if(!enabled||!active||phase<0||phase>1)return false;
    if(graph_active){++overlapping_graphs;return false;}
    auto& p=node_phases[phase];const auto begin=tick_ns();++p.prepares;++graph_generation;
    try{
        node_index.clear();prepared_nodes.clear();
        if(!graph)throw std::runtime_error("null CPU graph");
        const int count=ggml_graph_n_nodes(graph);
        prepared_nodes.reserve(count);node_index.reserve(count);
        for(int i=0;i<count;++i){
            const auto* tensor=ggml_graph_node(graph,i);auto identity=classify_node(tensor);
            // Propagate semantic identity through assembly only when every input
            // has the same confirmed identity. Op category stays data_movement.
            if(identity.category==NodeCategory::Movement&&(tensor->op==GGML_OP_CONCAT||tensor->op==GGML_OP_CONT||tensor->op==GGML_OP_CPY)){
                const NodeIdentity* common=nullptr;bool consistent=true;
                const int sources=tensor->op==GGML_OP_CONCAT?2:1;
                for(int src=0;src<sources;++src){
                    auto found=node_index.find(tensor->src[src]);
                    if(found==node_index.end()){consistent=false;break;}
                    const auto& parent=node_records[prepared_nodes[found->second].record].identity;
                    if(parent.role=="unknown"||parent.role=="matrix_unknown_identity"){consistent=false;break;}
                    if(common&&(common->role!=parent.role||common->layer!=parent.layer||common->weight!=parent.weight)){
                        consistent=false;break;
                    }
                    common=&parent;
                }
                if(consistent&&common){
                    identity.role=common->role;identity.layer=common->layer;identity.family=common->family;
                    identity.weight=common->weight;identity.weight_type=common->weight_type;identity.basis="assembly_source_identity";
                }
            }
            auto inserted=node_record_index.emplace(identity,node_records.size());
            if(inserted.second){NodeRecord record;record.identity=std::move(identity);node_records.push_back(std::move(record));}
            if(!node_index.emplace(tensor,prepared_nodes.size()).second)throw std::runtime_error("duplicate graph pointer");
            prepared_nodes.push_back({tensor,inserted.first->second,int(tensor->op),false});
        }
        p.maximum_nodes=std::max(p.maximum_nodes,uint64_t(count));graph_active=true;
    }catch(...){
        ++p.prepare_failures;node_index.clear();prepared_nodes.clear();graph_active=false;
        for(auto it=node_record_index.begin();it!=node_record_index.end();){
            if(it->second>=node_records.size())it=node_record_index.erase(it);else ++it;
        }
    }
    p.prepare_ns+=tick_ns()-begin;return graph_active;
}
void PerRequestStats::finish_nodes() noexcept{
    if(!graph_active)return;
    const auto begin=tick_ns();node_index.clear();prepared_nodes.clear();graph_active=false;
    if(phase>=0&&phase<2)node_phases[phase].finish_ns+=tick_ns()-begin;
}

void PerRequestStats::node_observed(const ggml_tensor* t,int fused,uint64_t us,void* user){
    if(!user)return;
    auto& s=*static_cast<PerRequestStats*>(user);if(!s.enabled||!s.active)return;
    if(s.phase<0||s.phase>1){++s.invalid_phase_callbacks;s.invalid_phase_us+=us;return;}
    auto& p=s.node_phases[s.phase];
    const auto found=s.node_index.find(t);
    if(!s.graph_active||found==s.node_index.end()){
        ++p.missing_metadata;p.categories[size_t(NodeCategory::Unknown)].add(0,us);return;
    }
    const auto index=found->second;
    if(fused<0||size_t(fused)>=s.prepared_nodes.size()-index){
        ++p.invalid_fusion;p.categories[size_t(NodeCategory::Unknown)].add(0,us);return;
    }
    for(size_t i=index;i<=index+size_t(fused);++i)if(s.prepared_nodes[i].observed){
        ++p.duplicate_callbacks;p.categories[size_t(NodeCategory::Unknown)].add(0,us);return;
    }
    auto& record=s.node_records[s.prepared_nodes[index].record];
    record.timing[s.phase].add(fused,us);p.categories[size_t(record.identity.category)].add(fused,us);
    for(size_t i=index;i<=index+size_t(fused);++i){
        auto& member=s.prepared_nodes[i];member.observed=true;
        if(member.op>=0&&member.op<GGML_OP_COUNT){
            ++p.member_ops[member.op];if(fused)++record.fused_members[s.phase][member.op];
        }
    }
}
json PerRequestStats::node_report()const{
    json r={{"schema","A12_CPU_NODE_PROFILE_V2"},{"enabled",enabled},{"detail",detail},
      {"scope","thread0 elapsed including existing barrier; one interval per actual fused group; not CPU time"},
      {"attribution","exclusive category by head op; roles/shapes are alternate views, never additive"},
      {"nesting","MLP node wall and nested OperationScope are alternate scopes; never add them"},
      {"linear_attention_state_split","FUSED_GATED_DELTA_NET_STATE_UPDATE_NOT_SEPARATELY_TIMED"},
      {"custom_identity_limit","MLP custom uses pinned name+structure; no custom weight source exposed"},
      {"metadata_lifetime","one synchronous CPU execution; pointers cleared before graph ownership ends"},
      {"graph_generations",graph_generation},{"overlapping_graphs",overlapping_graphs},
      {"invalid_phase_callbacks",invalid_phase_callbacks},{"invalid_phase_wall_us",invalid_phase_us},
      {"BOARD","NOT_TESTED"}};
    if(!enabled){r["phases"]=nullptr;return r;}
    bool valid=!non_cpu&&!overlapping_graphs&&!invalid_phase_callbacks;
    r["phases"]=json::object();
    for(int phase=0;phase<2;++phase){
        const auto& p=node_phases[phase];NodeTiming total;json buckets=json::object();
        for(size_t c=0;c<size_t(NodeCategory::Count);++c){
            buckets[category_names[c]]=timing_json(p.categories[c]);merge_timing(total,p.categories[c]);
        }
        if(p.missing_metadata||p.invalid_fusion||p.duplicate_callbacks||p.prepare_failures)valid=false;
        // Serialization/merging happens after execution. The hot callback only
        // updates preallocated integers; normal output merges layer/stride IDs.
        std::map<NodeIdentity,NodeRecord> aggregates;
        for(const auto& record:node_records)if(record.timing[phase].groups){
            NodeIdentity key=record.identity;
            if(!detail){key.layer=-1;key.weight.clear();key.output_stride={};key.input_stride={};}
            auto& aggregate=aggregates[key];aggregate.identity=key;
            merge_timing(aggregate.timing[phase],record.timing[phase]);
            for(int op=0;op<GGML_OP_COUNT;++op)aggregate.fused_members[phase][op]+=record.fused_members[phase][op];
        }
        json rows=json::array();
        for(const auto& entry:aggregates){
            const auto& record=entry.second;const auto& id=record.identity;json row=timing_json(record.timing[phase]);
            row["category"]=category_names[size_t(id.category)];
            row["op"]=id.op>=0&&id.op<GGML_OP_COUNT?json(ggml_op_name(ggml_op(id.op))):json("INVALID");
            row["op_code"]=id.op;row["subop_code"]=id.subop<0?json(nullptr):json(id.subop);
            row["role"]=id.role;row["layer_family"]=id.family;row["identity_basis"]=id.basis;
            row["layer"]=detail&&id.layer>=0?json(id.layer):json(nullptr);
            row["weight"]=id.weight.empty()?json(nullptr):json(id.weight);
            row["weight_type"]=id.weight_type>=0?json(ggml_type_name(ggml_type(id.weight_type))):json(nullptr);
            row["output_ne"]=id.output;row["input_ne"]=id.input;row["source0_ne"]=id.source;
            row["output_nb"]=detail?json(id.output_stride):json(nullptr);
            row["input_nb"]=detail?json(id.input_stride):json(nullptr);
            row["fused_member_ops"]=op_counts(record.fused_members[phase]);rows.push_back(std::move(row));
        }
        r["phases"][phase?"decode":"prefill"]={{"categories",buckets},{"total",timing_json(total)},
            {"logical_op_counts",op_counts(p.member_ops)},{"aggregates",rows},
            {"metadata_prepare_ns",p.prepare_ns},{"metadata_release_ns",p.finish_ns},
            {"metadata_prepares",p.prepares},{"maximum_graph_nodes",p.maximum_nodes},
            {"metadata_prepare_failures",p.prepare_failures},{"missing_metadata_callbacks",p.missing_metadata},
            {"invalid_fusion_callbacks",p.invalid_fusion},{"duplicate_callbacks",p.duplicate_callbacks}};
    }
    r["accounting_valid"]=valid;
    return r;
}
}
