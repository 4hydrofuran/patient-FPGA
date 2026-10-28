"""Linux executable/private DSO: allow 72 loads; reject every compute permit."""
import json
import os
from pathlib import Path
import subprocess
import time
from common import ROOT,sha,save
from review06_common import OUT
from review06_loadonly_supervisor import OwnedWorker,PermissionOrder

def main():
    out=OUT/'loadonly-pc-v1';out.mkdir()
    inc=ROOT/'runtime/qwen35_w4a8/a12';vendor=Path('/home/member-a/qwen35-a05/source-v3/vendor/nlohmann')
    (out/'backend.cpp').write_text('''#include "supervisor_gate.hpp"
extern "C" void allocate_only(int bad){a12::permit("device_open",0);for(int i=1;i<=72;++i)a12::permit("weight_load",i);if(bad)a12::permit("submit",1);}
''')
    (out/'app.cpp').write_text('''#include "supervisor_gate.hpp"
#include <dlfcn.h>
#include <iostream>
int main(int argc,char**argv){try{a12::permit("router_open",0);void*h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!h)return 3;
auto call=(void(*)(int))dlsym(h,"allocate_only");call(argc>2);a12::permit("router_close",0);
std::cout<<"{\\"type\\":\\"ready\\"}"<<std::endl;std::string s;std::getline(std::cin,s);return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
''')
    (out/'private.map').write_text('{global:allocate_only;local:*;};\n')
    commands=[['g++','-std=c++17','-O2','-fPIC','-shared',str(out/'backend.cpp'),'-I'+str(inc),'-I'+str(vendor),'-Wl,--version-script='+str(out/'private.map'),'-o',str(out/'libload.so')],
        ['g++','-std=c++17','-O2',str(out/'app.cpp'),'-I'+str(inc),'-I'+str(vendor),'-ldl','-o',str(out/'app')]]
    for i,c in enumerate(commands):
        r=subprocess.run(c,capture_output=True,text=True);save(out/f'build-{i}.json',dict(argv=c,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    rows=[]
    for name,bad in (('load-only',False),('submit-rejected',True)):
        argv=[str(out/'app'),str(out/'libload.so')]+(['bad'] if bad else [])
        w=OwnedWorker(argv,directory=out/name,env=os.environ,health=lambda:None,max_runs=1224,max_loads=72,expires=time.monotonic()+20)
        if bad:
            assert w.process.wait(timeout=5)==1
            w.permission_thread.join(1);w.reader_thread.join(1)
            assert w.quarantined and w.runs==0 and w.loads==72
            w.stderr.close();w.process.stdin.close();w.process.stdout.close();w.manager_sock.close()
        else:
            assert w.get(10)['type']=='ready' and w.close(timeout=3) and w.runs==0 and w.loads==72
        ev=[json.loads(l) for l in (out/name/'events.jsonl').read_text().splitlines()]
        assert not any(e.get('request',{}).get('phase')=='submit' and e.get('allow') for e in ev)
        rows.append(dict(case=name,exit_code=w.process.returncode,loads=w.loads,runs=w.runs,events=ev))
    o=PermissionOrder()
    for phase,seq,job in [('router_open',1,0),('device_open',1,0)]+[('weight_load',i+1,i) for i in range(1,73)]:
        r=dict(phase=phase,sequence=seq,job=job,pid=123);o.check(r,123);o.commit(r)
    for seq in (0,1,74,75):
        try:o.check(dict(phase='submit',sequence=seq,job=1,pid=123),123)
        except ValueError as e:assert 'LOAD_ONLY' in str(e)
        else:raise AssertionError('compute permit accepted')
    save(OUT/'LOAD_ONLY_PC.json',dict(status='PASS_LINUX_NATIVE_DSO_72_LOADS_ALL_SUBMITS_DENIED',
       tested_source_sha256=sha(ROOT/'platform/qwen35/a12/review06_loadonly_supervisor.py'),runs=rows,
       real_device_runs=0,BOARD='NOT_TESTED',signals=0))
    t=(ROOT/'platform/qwen35/a12/step07_finalize_window_test.py').read_text()
    t=t.replace('import window_closeout_v2 as window','import window_capacity_only as window')
    t=t.replace("OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'","from review06_common import OUT")
    t=t.replace("sha(ROOT/'platform/qwen35/a12/window_closeout_v2.py')","sha(ROOT/'platform/qwen35/a12/window_capacity_only.py')")
    script=out/'window-test.py';script.write_text(t)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'platform/qwen35/a12'))
    r=subprocess.run(['/usr/bin/python3','-B',str(script)],env=env,capture_output=True,text=True)
    save(out/'window-test-command.json',dict(argv=['/usr/bin/python3','-B',str(script)],exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0,r.stderr
    print('PASS_LOAD_ONLY_NATIVE_PERMISSIONS_AND_7_WINDOW_FLOCK_TESTS')

if __name__=='__main__':main()
