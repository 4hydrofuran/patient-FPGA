"""Run actual derived backend against control doubles; compare private/public completion gates."""
from common import ROOT
from step10_common import OUT

if __name__=='__main__':
    text=(ROOT/'platform/qwen35/a12/test_control.py').read_text(encoding='utf-8')
    anchor="    (out/'test_api.cpp').write_text(test)"
    insertion='''    test=test.replace('static unsigned checks=0;', 'extern "C" int32_t sp_a12_completion_report_v1(sp_linear_context*,char*,uint64_t,uint64_t*);\\nstatic unsigned checks=0;')
    test=test.replace('    return j;', r\'''    uint64_t pn=0;check(sp_a12_completion_report_v1(c,nullptr,0,&pn)==0&&pn>1,"private completion query");
    std::vector<char>pb(pn,'!');uint64_t actual=0;
    check(sp_a12_completion_report_v1(c,pb.data(),pn-1,&actual)==SP_BUFFER_TOO_SMALL&&actual==pn,"private short report");
    check(std::all_of(pb.begin(),pb.end(),[](char v){return v=='!';}),"private short report no writes");
    check(sp_a12_completion_report_v1(c,pb.data(),pn,&actual)==0&&pb.back()==0,"private report NUL");
    auto pj=json::parse(pb.data());
    for(auto key:{"job_id","kernel_build_id","status","host_verified_completions","last_status_code","output_consumable","a12_observed_ert_state","a12_raw_meta_hex"})
        if(j.contains(key))check(pj.contains(key)&&pj[key]==j[key],"private/full completion gate equivalence");
    check(!pj.contains("a11_live_weights")&&!pj.contains("a11_io_bo_addresses"),"private completion excludes immutable inventory only");
    return j;\''')
    (out/'test_api.cpp').write_text(test)'''
    assert text.count(anchor)==1
    text=text.replace(anchor,insertion)
    p=OUT/'derived-control-runner.py';p.write_text(text,encoding='utf-8')
    namespace={'__name__':'task10_derived_control'};exec(compile(text,str(p),'exec'),namespace)
    namespace['main'](OUT/'source-v1',OUT/'pc-control')
