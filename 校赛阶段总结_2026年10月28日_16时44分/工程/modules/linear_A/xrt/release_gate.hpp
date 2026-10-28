#pragma once
#include "host_contract.hpp"
#include "json.hpp"
#include <limits>
namespace a07 {
// KERNEL_SOURCE uses selected_build_id (hex string); a board profile uses uint32.
// Keep this explicit instead of accidentally looking for a nonexistent source field.
inline uint32_t selected_build(const nlohmann::json& source) {
    const auto text=source.at("selected_build_id").get<std::string>();
    if(text.size()!=10||text.substr(0,2)!="0x")throw std::invalid_argument("selected_build_id");
    size_t consumed=0;auto value=std::stoull(text.substr(2),&consumed,16);
    if(consumed!=8||!value||value>std::numeric_limits<uint32_t>::max())throw std::invalid_argument("selected_build_id");
    return uint32_t(value);
}
// Pure policy predicate shared by production open() and PC tests; no device stub.
inline int release_gate(const nlohmann::json&cfg,const nlohmann::json&source) noexcept {
    try {
        if(cfg.at("api_version")!=1||cfg.at("contract_sha256")!=contract_sha||
           cfg.at("fallback")!="disabled"||cfg.at("backend_id")!="A_XRT_B_KERNEL_V1")return SP_CONTRACT_MISMATCH;
        for(auto key:{"accepted","frozen","production_or_A07_link_allowed"})
            if(!source.contains(key)||!source[key].is_boolean()||!source[key].get<bool>())return SP_UNSUPPORTED;
        if(source.at("provider")!="B")return SP_CONTRACT_MISMATCH;
        if(!cfg.contains("allow_device_access")||!cfg["allow_device_access"].is_boolean()||!cfg["allow_device_access"].get<bool>())return SP_UNSUPPORTED;
        return SP_OK;
    }catch(...){return SP_BAD_ARGUMENT;}
}
}
