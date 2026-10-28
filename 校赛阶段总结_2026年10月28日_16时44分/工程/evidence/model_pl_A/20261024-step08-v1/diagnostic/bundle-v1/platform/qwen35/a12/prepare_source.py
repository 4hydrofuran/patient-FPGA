"""Create isolated model integration sources from the current snapshotted A05."""
import argparse
from pathlib import Path
import shutil
from common import ROOT, sha, save
from derive import derive


def prepare(out):
    out=Path(out);derive(out)
    changes={}
    def patch(name, replacements):
        p=out/name;text=p.read_text();before=sha(p)
        for old,new in replacements:
            if text.count(old)!=1:raise ValueError('nonunique '+name+': '+old[:100])
            text=text.replace(old,new)
        p.write_text(text,encoding='utf-8');changes[name]=dict(before=before,after=sha(p))
    for p in (ROOT/'runtime/qwen35_w4a8/a12').glob('*'):
        if p.is_file():shutil.copyfile(p,out/p.name)
    patch('bridge.hpp',[
        ('#include "request_profile.hpp"','#include "request_profile.hpp"\n#include "route.hpp"'),
        ('uint64_t handle=0,calls=0,tokens=0;','bool pl=false;uint64_t handle=0,calls=0,tokens=0;'),
        ('    PerRequestStats request_stats;','    a12::Route route;\n    PerRequestStats request_stats;')])
    patch('bridge.cpp',[
        ('    try{for(const auto&e:m["entries"]){','    route.init();\n    try{for(const auto&e:m["entries"]){'),
        ('if(!selected(scope,l,op))continue;','if(!selected(scope,l,op))continue;'),
        ('if(sp_linear_load_v1(cpu,v.n,v.k,w.data(),w.size(),sw.data(),sw.size()*4,&v.handle)!=SP_OK)',
         'v.pl=route.selects(l,op);\n        if((v.pl?route.load(v.n,v.k,w.data(),w.size(),sw.data(),sw.size()*4,&v.handle):sp_linear_load_v1(cpu,v.n,v.k,w.data(),w.size(),sw.data(),sw.size()*4,&v.handle))!=SP_OK)'),
        ('Bridge::~Bridge(){if(cpu)sp_linear_close_v1(cpu);}',
         'Bridge::~Bridge(){try{route.close_checked();}catch(...){route.park_if_unsafe();}if(cpu)sp_linear_close_v1(cpu);}'),
        ('int rc=sp_linear_run_v1(b.cpu,e.handle,count,cache.q.data()+start*k,count*k,cache.sx.data()+start,count*4,b.y.data(),count*n*4,++b.job,30000);',
         'auto job=++b.job;\n            int rc=e.pl?b.route.run(e.handle,count,cache.q.data()+start*k,count*k,cache.sx.data()+start,count*4,b.y.data(),count*n*4,job,30000):sp_linear_run_v1(b.cpu,e.handle,count,cache.q.data()+start*k,count*k,cache.sx.data()+start,count*4,b.y.data(),count*n*4,job,30000);'),
        ('            if(prof)tv.output_copy+=tick_ns()-cp;',
         '''            if(e.pl)b.route.returned(dst,start,count,n,job,b.y.data(),e.layer,e.op,b.epoch,b.execution);
#ifdef SP_A12_PC_TEST
            if(e.pl&&std::getenv("SP_A12_TEST_DROP_OUTPUT"))for(int row=0;row<count;++row)std::memset(static_cast<char*>(dst->data)+(start+row)*dst->nb[1],0,n*4);
#endif
            if(prof)tv.output_copy+=tick_ns()-cp;'''),
        ('    j["residency_measurement"]=diagnostic?',
         '    j["a12_route"]=route.report();\n    j["residency_measurement"]=diagnostic?')])
    patch('main.cpp',[
        ('bool selected=self.active&&t->type', 'bool selected=self.active&&!self.dir.empty()&&t->type'),
        ('bool active=false;std::string error;', 's1::Bridge*bridge=nullptr;bool active=false;std::string error;'),
        ('        if(ask)return selected;if(!selected)return true;',
         '        bool a12_trace=self.bridge&&self.bridge->route.enabled&&self.active;\n        if(ask){if(a12_trace){try{self.bridge->route.observe(t,false);}catch(const std::exception&e){self.error=e.what();return true;}}return selected||a12_trace;}\n        if(a12_trace){try{self.bridge->route.observe(t,true);}catch(const std::exception&e){self.error=e.what();return false;}}\n        if(!selected)return true;'),
        ('    NodeTrace trace;', '    NodeTrace trace;trace.bridge=&bridge;'),
        ('        trace.records=json::array();trace.dir=diag;trace.error.clear();',
         '        bridge.route.set_trace(req.value("a12_consumer_trace",false));\n        trace.records=json::array();trace.dir=diag;trace.error.clear();'),
        ('trace.active=pos==0&&!diag.empty()&&req.value("diagnostic_nodes",false);',
         'trace.active=req.value("a12_consumer_trace",false)||(pos==0&&!diag.empty()&&req.value("diagnostic_nodes",false));'),
        ('            if(!trace.error.empty())throw std::runtime_error("Node diagnostic: "+trace.error);',
         '            if(!trace.error.empty())throw std::runtime_error("Node diagnostic: "+trace.error);\n            bridge.route.finish_execution();'),
        ('        trace.active=false;\n        if(!trace.records.empty())',
         '        trace.active=req.value("a12_consumer_trace",false);\n        if(!trace.records.empty())'),
        ('                decode_ms+=ms(begin);++calls;',
         '                if(!trace.error.empty())throw std::runtime_error("A12 consumer: "+trace.error);\n                bridge.route.finish_execution();\n                decode_ms+=ms(begin);++calls;'),
        ('    llama_free(ctx);sp_llama_set_hook',
         '    bridge.route.close_checked();\n    llama_free(ctx);sp_llama_set_hook')])
    # A12 identity is explicit at top level; CPU accounting stays in its own subreport.
    main=out/'main.cpp';text=main.read_text()
    text=text.replace('{"execution_kind","CPU_REFERENCE"}',
                      '{"execution_kind",bridge.route.enabled?(bridge.route.real?"FPGA_REAL":"PC_MATH_DOUBLE"):"CPU_REFERENCE"}')
    text=text.replace('{"domain","PC"}', '{"domain",bridge.route.real?"BOARD":"PC"}')
    text=text.replace('"S1_W4A8_MLP":', '"A12_W4A8_MLP":')
    main.write_text(text,encoding='utf-8')
    save(out/'MODEL_DERIVATION.json',dict(changes=changes,main_final_sha256=sha(main),
        scope='all model MLPs remain W4A8; selected subset routed to explicit PL candidate',
        preserved_A05_sources=True,BOARD='NOT_TESTED'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);prepare(p.parse_args().out)
