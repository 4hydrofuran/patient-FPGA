"""Derive per-call evidence only; preserve S1 math, source-v4 and B hardware."""
import json
import shutil
from common import ROOT,sha,save
from step07_protocol import OUT


def main():
    src=OUT/'source-v1';shutil.copytree(ROOT/'evidence/model_pl_A/20261023-preboard-v1/source-v4',src)
    changes={}
    def patch(name,pairs):
        p=src/name;s=p.read_text(encoding='utf-8');before=sha(p)
        for old,new in pairs:
            assert s.count(old)==1,(name,old);s=s.replace(old,new)
        p.write_text(s,encoding='utf-8',newline='\n');changes[name]=dict(before=before,after=sha(p))
    patch('backend.cpp',[
      ('        for(;;){auto state=c->run.state();if(state==ERT_CMD_STATE_COMPLETED)break;',
       '        uint32_t observed_ert=0;\n        for(;;){auto state=c->run.state();observed_ert=uint32_t(state);if(state==ERT_CMD_STATE_COMPLETED)break;'),
      ('        auto meta_checked=Clock::now();','        auto meta_checked=Clock::now();\n        std::ostringstream raw_meta;for(size_t i=0;i<64;++i)raw_meta<<std::hex<<std::setw(2)<<std::setfill(\'0\')<<unsigned(c->meta.map<const uint8_t*>()[i]);'),
      ('        c->last={{"last_status_code",SP_OK},','        c->last={{"a12_observed_ert_state",observed_ert},{"a12_raw_meta_hex",raw_meta.str()},{"last_status_code",SP_OK},')])
    patch('route.cpp',[
      ('    pending[dst].push_back(ledger.size()-1);',
       '    auto completion=report();completion.erase("a12_trace");\n    ledger.back()["backend_completion"]=completion;\n    pending[dst].push_back(ledger.size()-1);')])
    save(OUT/'SOURCE_DERIVATION.json',dict(status='PER_CALL_EVIDENCE_ONLY_NOT_MATH_CHANGE',changes=changes,
        preserved_files={p.name:sha(p) for p in src.iterdir() if p.is_file() and p.name not in changes},
        provider='B',maintainer='A',B_core_changed=False,contract_changed=False,math_changed=False))
    print(json.dumps(dict(status='PER_CALL_EVIDENCE_ONLY_SOURCE_READY',changes=list(changes))))


if __name__=='__main__':main()
