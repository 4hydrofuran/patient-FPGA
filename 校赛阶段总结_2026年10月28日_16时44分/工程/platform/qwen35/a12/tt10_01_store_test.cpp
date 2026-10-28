#include "prefix_cache.hpp"
#include <cassert>
#include <iostream>
int main(){
    using namespace tt10;int checks=0;
    auto ok=[&](bool b){assert(b);++checks;};
    auto refused=[&](auto f){try{f();}catch(const std::exception&){++checks;return;}throw std::runtime_error("expected refusal");};
    ok(digest(std::string("abc"))=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    PrefixStore s(json{{"schema","TT10_01_CONFIG_V1"},{"max_slots",2},{"max_slot_bytes",67108864},{"identity",{{"test","synthetic component only"}}},{"allowed_prefixes",{{1,2}}}});
    json req={{"cache_id","a"},{"cache_binding_sha256",s.key()},{"confirmed_prefix",true}};
    auto snapshot=[](){Snapshot v;v.tokens={1,2};v.position=1;v.state={1,2,3};v.logits={0.5f,1.0f};v.owner={{"kind","public_neutral"}};v.sequence_sha="synthetic";return v;};
    s.reserve_create(req,{1,2});s.commit("a",snapshot());std::string why;
    ok(s.lookup(req,{1,2,3},why)!=nullptr&&why=="EXACT_FULL_STATE_HIT");
    ok(!s.lookup(req,{1,3,3},why)&&why=="TOKEN_PREFIX_MISMATCH");
    ok(!s.lookup(req,{1},why));
    refused([&]{s.reserve_create(req,{2,3});});
    refused([&]{auto q=req;q["confirmed_prefix"]=false;s.reserve_create(q,{1,2});});
    auto q=req;q["cache_id"]="b";s.reserve_create(q,{1,2});s.commit("b",snapshot());
    q["cache_id"]="c";refused([&]{s.reserve_create(q,{1,2});});
    s.drop("b");ok(s.report()["entries"].size()==1);
    q=req;q["cache_binding_sha256"]="bad";ok(!s.lookup(q,{1,2},why)&&why=="VERSION_BINDING_MISMATCH"&&s.report()["entries"].empty());
    refused([&]{PrefixStore::owner_of(json{{"cache_owner",{{"kind","public_neutral"},{"case_id","private"}}}});});
    refused([&]{PrefixStore::owner_of(json{{"cache_owner",{{"kind","case_session"}}}});});
    s.reserve_create(req,{1,2});auto v=snapshot();v.state.resize(PrefixStore::SLOT_BYTES);refused([&]{s.commit("a",std::move(v));});
    s.reserve_create(req,{1,2});s.commit("a",snapshot());s.damage("a","digest");ok(!s.lookup(req,{1,2},why)&&why=="CORRUPT_SNAPSHOT");
    auto private_owner=json{{"kind","case_session"},{"case_id","A"},{"case_sha256",std::string(64,'a')},{"session_id","A"},{"epoch",uint64_t(0)}};
    q=req;q["cache_owner"]=private_owner;s.reserve_create(q,{1,2});v=snapshot();v.owner=private_owner;s.commit("a",std::move(v));
    ok(s.lookup(q,{1,2},why)!=nullptr);private_owner["epoch"]=uint64_t(1);s.owner_changed(private_owner);ok(s.report()["entries"].empty());
    std::cout<<json{{"status","PASS_COMPONENT_STORE"},{"checks",checks},{"model_execution",false}}.dump()<<std::endl;
}
