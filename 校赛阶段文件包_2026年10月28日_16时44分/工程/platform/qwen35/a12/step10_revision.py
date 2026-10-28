"""Preserve the first build/failure; correct only the timing bucket name."""
import json,shutil
from common import ROOT,sha,save
from step10_common import OUT

if __name__=='__main__':
    assert json.loads((OUT/'pc_native_01.json').read_text())['exit_code']==1
    shutil.copyfile(OUT/'BUILD.json',OUT/'BUILD-v1.json')
    src=OUT/'source-v2';shutil.copytree(OUT/'source-v1',src)
    p=src/'request_profile.cpp';old=p.read_text();new=old.replace('std::strstr(n,"ffn_down")','std::strstr(n,"ffn_down")||std::strstr(n,"ffn_out")')
    assert new!=old;p.write_text(new,encoding='utf-8',newline='\n')
    # Profiling a PC math double must not require FPGA-only report fields.
    p=src/'route.cpp';old=p.read_text();new=old.replace('if(profile_on){auto&m=metrics[profile_phase];','if(profile_on&&real){auto&m=metrics[profile_phase];')
    assert new!=old;p.write_text(new,encoding='utf-8',newline='\n')
    save(OUT/'SOURCE_REVISION_V2.json',dict(reason='Actual down node is ffn_out; first PC timing assertion correctly failed',
         first_failure='pc_native_01.json',math_changed=False,
         changes={n:dict(before=sha(OUT/'source-v1'/n),after=sha(src/n)) for n in ('request_profile.cpp','route.cpp')}))
