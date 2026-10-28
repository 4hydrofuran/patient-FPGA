"""Small ABBA PC exploration after known builds stop; no p95/Board forecast."""
import argparse
import statistics
import subprocess
import sys
from modelpl_evidence import ROOT,OUT,read,save
from modelpl_build import run
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args()
    processes=subprocess.run(['ps','-eo','pid=,ppid=,comm='],capture_output=True,text=True);assert processes.returncode==0
    busy=[]
    for row in processes.stdout.splitlines():
        parts=row.split()
        if len(parts)==3 and (parts[2] in ('cc1plus','cc1','cmake','ninja','make','g++','gcc','qwen35-a12') or parts[2].startswith('aarch64-amd')):busy.append(row)
    save(OUT/'PERF_PRECONDITION.json',dict(command=['ps','-eo','pid=,ppid=,comm='],exit_code=0,known_compiler_or_native_processes=busy,
        scope='OWN_WSL_BUILD_NATIVE_NAMES_ONLY_HOST_LOAD_NOT_CONTROLLED',BOARD='NOT_TESTED'));assert not busy,busy
    order=[1,72,72,1];samples=[]
    for index,cap in enumerate(order):
        tag='perf-'+str(index+1)+'-cap'+str(cap)
        run([sys.executable,'-B',ROOT/'platform/qwen35/a12/modelpl_run.py','--tag',tag,'--revision',str(a.revision),'--cap',str(cap)],'RUN-'+tag,ROOT,300)
        result=read(OUT/tag/'RESULT.json');assert result['status']=='PASS_ACTUAL_QWEN_PLM_CPU_WINDOW_NOT_BOARD'
        values={name:read(OUT/tag/(name+'-MODEL_RESULT.json'))['summary'] for name in ('app_R0','warm_prefix','app_hit')}
        samples.append(dict(tag=tag,cap=cap,requests=values))
    stats={}
    for mode in (1,72):
        stats[str(mode)]={name:dict(n=2,gate_latency_s=[s['requests'][name]['send_to_validated_result_s'] for s in samples if s['cap']==mode],
            mean_gate_latency_s=statistics.mean(s['requests'][name]['send_to_validated_result_s'] for s in samples if s['cap']==mode),
            raw_native_first_token_s=[s['requests'][name]['raw_native_first_token_s'] for s in samples if s['cap']==mode]) for name in ('app_R0','warm_prefix','app_hit')}
    save(OUT/'PERF_PC_EXPLORATION.json',dict(status='PC_ABBA_EXPLORATION_ONLY',order=order,samples=samples,descriptive=stats,
        scope='SEND_TO_CONTENT_STATE_END_RECEIPT_FRESH_FENCE; excludes later audit-JSON write, startup, UI, voice and network',
        sample_warning='TWO_WINDOWS_PER_MODE_NO_P95_OR_SIGNIFICANCE_HOST_LOAD_NOT_CONTROLLED',hardware_latency_saving_s=None,BOARD='NOT_TESTED',real_PL_results_consumed=False))
    print('PC_ABBA_EXPLORATION_ONLY')
if __name__=='__main__':main()
