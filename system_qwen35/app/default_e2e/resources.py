"""Linux per-process resident accounting, sampled not inferred from model sizes."""
import json, os, threading, time
from pathlib import Path

def spool_usage(spool):
    # Session reset may remove a directory during traversal. Count omissions,
    # not a fictitious zero-sized successful sample. Other errors remain errors.
    missing=0;total=0;count=0
    def onerror(error):
        nonlocal missing
        if isinstance(error,FileNotFoundError):missing+=1
        else:raise error
    for base,dirs,files in os.walk(spool,onerror=onerror,followlinks=False):
        for name in files:
            p=Path(base)/name
            if p.is_symlink():continue
            try:total+=p.stat().st_size;count+=1
            except FileNotFoundError:missing+=1
    return total,count,missing

def process_memory(pid):
    root=Path('/proc')/str(pid);r={'pid':pid,'status':{},'rollup':{}}
    for name,dest in [('status','status'),('smaps_rollup','rollup')]:
        try:
            for line in (root/name).read_text().splitlines():
                key,sep,value=line.partition(':')
                if sep and key in ('VmRSS','VmHWM','VmSwap','RssAnon','RssFile','RssShmem','Threads','Rss','Pss','Pss_Anon','Pss_File','Pss_Shmem','Private_Dirty','Shared_Clean'):
                    r[dest][key]=int(value.strip().split()[0])
        except (FileNotFoundError,PermissionError,ProcessLookupError):r['unavailable']=True
    return r

def mapping_memory(pid):
    """Actual smaps pages for GGUF and sidecar; heap copies stay anonymous."""
    result={key:{'Size':0,'Rss':0,'Pss':0} for key in ('GGUF','SIDECAR','OTHER_FILE','ANONYMOUS')}
    key='ANONYMOUS'
    for line in (Path('/proc')/str(pid)/'smaps').read_text().splitlines():
        if line and '-' in line.split()[0]:
            key='GGUF' if '.gguf' in line else 'SIDECAR' if '/sidecar_A/' in line else 'OTHER_FILE' if '/' in line else 'ANONYMOUS'
        elif ':' in line:
            name,value=line.split(':',1)
            if name in result[key]:result[key][name]+=int(value.strip().split()[0])
    return {'units':'KiB','groups':result,'note':'Heap-loaded sidecar and rearrangements are included in anonymous RSS, not double-counted as mapped pages.'}

class Sampler:
    def __init__(self,path,pids,spool,phase):
        self.pids=pids;self.spool=Path(spool);self.phase=phase;self.stop=threading.Event()
        self.f=Path(path).open('x');self.peak=dict.fromkeys(('rss_kib','pss_kib','spool_bytes','spool_files'));self.error=None
        self.incomplete_samples=0;self.failed_samples=0
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def sample(self):
        processes={name:process_memory(pid) for name,pid in self.pids().items() if pid}
        total,count,missing=spool_usage(self.spool)
        memory=aggregate_memory(processes)
        if memory['sample_status']!='COMPLETE' or missing:self.incomplete_samples+=1
        r={'monotonic_ns':time.monotonic_ns(),'phase':self.phase(),'processes':processes,**memory,
           'spool_bytes':total if not missing else None,'spool_files':count if not missing else None,
           'spool_observed_bytes':total,'spool_observed_files':count,'spool_disappeared_during_sample':missing,
           'host_thermal_throttling':None,'thermal_reason':'WSL does not expose validated physical host thermal/throttling telemetry'}
        r['vm_swap_counters']={k:int(v) for k,v in (line.split() for line in Path('/proc/vmstat').read_text().splitlines()) if k in ('pswpin','pswpout')}
        for key in self.peak:
            if r[key] is not None:self.peak[key]=r[key] if self.peak[key] is None else max(self.peak[key],r[key])
        self.f.write(json.dumps(r)+'\n');self.f.flush()
    def run(self):
        while not self.stop.is_set():
            try:self.sample()
            except Exception as e:
                self.error=repr(e);self.failed_samples+=1
                self.f.write(json.dumps({'monotonic_ns':time.monotonic_ns(),'phase':self.phase(),
                    'sample_status':'ERROR','error':self.error,'processes':{},'rss_kib':None,'pss_kib':None,
                    'spool_bytes':None,'spool_files':None,'process_swap_kib':None,'vm_swap_counters':{}})+'\n');self.f.flush()
            self.stop.wait(.5)
    def close(self):
        self.stop.set();self.thread.join(3);self.f.close()

def aggregate_memory(processes):
    """An observed subtotal is not the total when a live/just-exited PID is unreadable."""
    result={};missing={}
    for name,group,key in [('rss_kib','rollup','Rss'),('pss_kib','rollup','Pss'),('process_swap_kib','status','VmSwap')]:
        absent=[label for label,p in processes.items() if key not in p[group]]
        values=[p[group][key] for p in processes.values() if key in p[group]]
        result[name]=sum(values) if processes and not absent else None
        result['observed_'+name]=sum(values) if values else None
        missing[name]=absent
    result['missing_process_metrics']=missing
    result['sample_status']='COMPLETE' if processes and not any(missing.values()) else 'INCOMPLETE'
    return result
