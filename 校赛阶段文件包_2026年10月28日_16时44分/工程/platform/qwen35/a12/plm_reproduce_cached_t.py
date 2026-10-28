"""Keep a real counterexample against v2; never treat its window PASS as acceptance."""
import os
from pathlib import Path
import subprocess
import sys
from plm_evidence import ROOT,OUT,WORK,read,save,sha
from plm_build import run
def main():
    os.umask(0o077);old=read(OUT/'BUILD-v2.json');new=read(OUT/'BUILD-v4.json');work=WORK.with_name(WORK.name[:-1]+'6-counterexample');work.mkdir(mode=0o700)
    src=Path(new['workspace'])/'source';probe=work/'plm-control-probe-old-backend';libdir=Path(old['workspace'])
    argv=['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'plm_probe.cpp'),
        '-L'+str(libdir),'-lplm_backend_pc_control','-Wl,-rpath,'+str(libdir),'-ldl','-o',str(probe)]
    run(argv,'CACHED_T_REPRO_PROBE_BUILD',work)
    artifacts=[dict(row) for row in old['artifacts'] if Path(row['path']).name!='plm-control-probe']
    artifacts.append(dict(path=str(probe),sha256=sha(probe),bytes=probe.stat().st_size))
    save(OUT/'BUILD-v6.json',dict(domain='PC_XRT_CONTROL_ONLY_A53_UNBOUND',purpose='REPRODUCE_V2_MISSING_CACHED_T_CHECK_NOT_ACCEPTED',
        workspace=str(work),revision=6,probe=str(probe),backend_library=old['backend_library'],router_library=old['router_library'],
        writer_library=old['writer_library'],writer_sha256=old['writer_sha256'],observer_library=new['observer_library'],artifacts=artifacts,
        sanitizers=dict(probe_backend_router='NONE',manager_writer='NONE',leak_check=False),ARM_artifacts=[],production_enabled=False,BOARD='NOT_TESTED'))
    cmd=[sys.executable,'-B',str(ROOT/'platform/qwen35/a12/plm_run.py'),'--revision','6','--tag','counterexample-cached-T','--fault','cached_T']
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);save(OUT/'CACHED_T_COUNTEREXAMPLE_COMMAND.json',dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    result=read(OUT/'counterexample-cached-T/RESULT.json')
    assert r.returncode==1 and result['status']=='PASS_PC_XRT_MANAGER_WINDOW_NOT_MODEL' and result['control_results']==3
    repaired=read(OUT/'suite02-cached-T/RESULT.json')
    assert repaired['control_results']==0 and repaired['page']['claims']==1 and repaired['last_native_message']['caller_y_unchanged'] is True
    save(OUT/'CACHED_T_COUNTEREXAMPLE.json',dict(status='CONFIRMED_V2_COUNTEREXAMPLE_AND_V4_REJECTION',
        old_backend_sha256=sha(old['backend_library']),new_backend_sha256=sha(new['backend_library']),
        defect='v2 cached credit did not recheck T within the 72-job range; changed second projection T silently passed the synthetic window',
        original_test_exit_code=1,old_control_window_report_must_not_be_accepted=True,
        repaired_claims=1,repaired_stub_starts=1,repaired_control_results=0,BOARD='NOT_TESTED',release_allowed=False))
    print('CONFIRMED_V2_COUNTEREXAMPLE_AND_V4_REJECTION')
if __name__=='__main__':main()
