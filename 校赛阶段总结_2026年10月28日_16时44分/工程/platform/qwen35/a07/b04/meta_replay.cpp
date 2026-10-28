#include "host_contract.hpp"
#include "release_gate.hpp"
#include <fstream>
#include <iostream>
#include <vector>
#include <filesystem>
using json=nlohmann::json;
static std::vector<uint8_t> read(const std::filesystem::path&p){
    std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("missing fixture");
    return {std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>()};
}
int main(int argc,char**argv)try{
    if(argc!=2)return 2;
    std::filesystem::path root=argv[1];json m;std::ifstream(root/"manifest.json")>>m;
    unsigned cases=0,tampers=0;
    for(const auto&c:m.at("cases")){
        auto actual=read(root/c["files"]["actual.bin"]["path"].get<std::string>());
        auto expected=read(root/c["files"]["expected.bin"]["path"].get<std::string>());
        if(actual!=expected||actual.size()!=40)throw std::runtime_error("original fixture mismatch");
        auto job=c["job_id"].get<uint64_t>(),seed=c["previous_count"].get<uint64_t>(),w=c["dimension_weight_bytes"].get<uint64_t>();
        const unsigned status=c["expected_private_status"];
        // Independent B golden tells expected private status; literal public mapping.
        constexpr int expected_public[]={0,2,1,3,1,9};
        if(status>5||a07::validate_meta(actual.data(),40,0xB3030002,job,seed,w)!=expected_public[status])
            throw std::runtime_error("production parser differs: "+c["id"].get<std::string>());
        ++cases;
        for(unsigned off:{0u,4u,8u,20u,24u,32u}){
            auto changed=actual;changed[off]^=1;
            const int want=off<16?SP_CONTRACT_MISMATCH:SP_DEVICE_ERROR;
            if(a07::validate_meta(changed.data(),40,0xB3030002,job,seed,w)!=want)
                throw std::runtime_error("tampered completion accepted");
            ++tampers;
        }
    }
    if(a07::selected_build(json{{"selected_build_id","0xB3030002"}})!=0xB3030002) return 1;
    unsigned rejected=0;
    for(auto value:{"B3030002","0x00000000","0xB303000Z","0x100000000"}){
        try{a07::selected_build(json{{"selected_build_id",value}});}catch(...){++rejected;}
    }
    if(rejected!=4||cases!=66)return 1;
    std::cout<<json{{"domain","PC_ARCHIVED_RTL_META_REPLAY"},{"actual_meta_records",cases},
        {"tamper_rejections",tampers},{"bad_build_ids",rejected},{"new_RTL_simulation",false},
        {"device_calls",0},{"BOARD","NOT_TESTED"}}.dump()<<'\n';
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
