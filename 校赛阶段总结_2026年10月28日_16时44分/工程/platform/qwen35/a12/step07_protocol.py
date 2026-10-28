"""Native Linux executable/DSO reproducer and phase/replay/limit regression."""
import json
import os
from pathlib import Path
import subprocess
import time
from common import ROOT,save
from supervisor import OwnedWorker as OldWorker
from step07_supervisor import OwnedWorker,PermissionOrder

OUT=ROOT/'evidence/model_pl_A/20261023-step07-single-v1'


def main():
    out=OUT/'protocol-v1';out.mkdir(exist_ok=False)
    inc=ROOT/'runtime/qwen35_w4a8/a12'
    vendor=Path('/home/member-a/qwen35-a05/source-v3/vendor/nlohmann')
    (out/'backend.cpp').write_text('''#include "supervisor_gate.hpp"
extern "C" void backend_permits(){a12::permit("device_open",0);a12::permit("weight_load",1);a12::permit("submit",1);}
''')
    (out/'app.cpp').write_text('''#include "supervisor_gate.hpp"
#include <dlfcn.h>
#include <iostream>
int main(int argc,char**argv){try{a12::permit("router_open",0);void*h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!h)return 3;
auto call=(void(*)())dlsym(h,"backend_permits");call();a12::permit("router_close",0);
std::cout<<"{\\"type\\":\\"done\\"}"<<std::endl;return 0;}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
''')
    (out/'private.map').write_text('{global:backend_permits;local:*;};\n')
    commands=[['g++','-std=c++17','-O2','-fPIC','-shared',str(out/'backend.cpp'),'-I'+str(inc),'-I'+str(vendor),'-Wl,--version-script='+str(out/'private.map'),'-o',str(out/'libbackend.so')],
              ['g++','-std=c++17','-O2',str(out/'app.cpp'),'-I'+str(inc),'-I'+str(vendor),'-ldl','-o',str(out/'app')]]
    for c in commands:
        r=subprocess.run(c,capture_output=True,text=True);assert r.returncode==0,r.stderr
    rows=[]
    for name,cls,expected in (('old',OldWorker,1),('fixed',OwnedWorker,0)):
        w=cls([str(out/'app'),str(out/'libbackend.so')],directory=out/name,env=os.environ,
            health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+10)
        rc=w.process.wait(timeout=5);w.permission_thread.join(1);w.reader_thread.join(1)
        events=[json.loads(l) for l in (out/name/'events.jsonl').read_text().splitlines()]
        assert rc==expected
        if name=='fixed':assert w.close(timeout=2) and w.runs==w.loads==1
        else:
            assert w.quarantined and any(e['event']=='PERMISSION_FAULT_RETAIN_OWNER' for e in events)
            # PC harness exited itself after denied request; no kill, device, or lease.
            w.stderr.close();w.process.stdin.close();w.process.stdout.close();w.manager_sock.close()
        rows.append(dict(case=name,exit_code=rc,events=events))
    checks=0
    valid=[('router_open',1,0),('device_open',1,0),('weight_load',2,1),('submit',3,1),('router_close',2,0)]
    for index in range(len(valid)):
        o=PermissionOrder()
        for phase,seq,job in valid[:index]:r=dict(phase=phase,sequence=seq,job=job,pid=123);o.check(r,123);o.commit(r)
        phase,seq,job=valid[index]
        for field,value in (('pid',999),('sequence',0),('phase','unknown')):
            bad=dict(phase=phase,sequence=seq,job=job,pid=123);bad[field]=value
            try:o.check(bad,123)
            except ValueError:checks+=1
            else:raise AssertionError('bad request accepted')
    for invalid in [dict(phase='submit',sequence=1,job=1,pid=123),dict(phase='device_open',sequence=1,job=0,pid=123)]:
        try:PermissionOrder().check(invalid,123)
        except ValueError:checks+=1
        else:raise AssertionError('phase order accepted')
    save(OUT/'PROTOCOL_REGRESSION.json',dict(status='PASS_NATIVE_DSO_REPRO_AND_FIXED_MANAGER',
         old_bug='exe/router sequence1 then private DSO/backend sequence1, old global sequence gate rejects',
         ARM_artifacts_changed=False,PC_negative_checks=checks,commands=commands,runs=rows))
    print(json.dumps(dict(status='PASS_NATIVE_DSO_REPRO_AND_FIXED_MANAGER',checks=checks)))


if __name__=='__main__':main()
