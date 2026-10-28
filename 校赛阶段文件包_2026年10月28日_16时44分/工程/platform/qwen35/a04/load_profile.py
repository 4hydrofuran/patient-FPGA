"""Fault in ALL sidecar mappings, no GGUF/raw model, no repacking or BO."""
import argparse,json,resource,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from quant.export_w4a8.loader import Sidecar
import numpy as np


def memory():
    result={}
    for path in ('/proc/self/status','/proc/self/smaps_rollup'):
        for line in Path(path).read_text().splitlines():
            key,_,value=line.partition(':')
            if key in ('VmRSS','VmHWM','RssAnon','RssFile','RssShmem','Rss','Pss','Anonymous','Private_Clean','Private_Dirty','Shared_Clean','Shared_Dirty'):
                result[path+':'+key]=value.strip()
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='eval/qwen35/a04/load-profile.json');args=parser.parse_args()
    before=memory();start=time.monotonic();s=Sidecar(ROOT/'models/sidecar_A/qwen35-v1');resident=[];checksum=0
    for ident in s.entries:
        w,sw=s.load(ident);resident.extend((w,sw))
        checksum+=int(np.sum(w,dtype=np.uint64));checksum+=float(np.sum(sw,dtype=np.float64))
    after=memory();rusage_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    observed=[rusage_peak]+[int(after[k].split()[0]) for k in ('/proc/self/status:VmHWM','/proc/self/status:VmRSS','/proc/self/smaps_rollup:Rss')]
    report={'domain':'PC','scenario':'all 72 sidecars mmap read-only, checksum touches every byte; no raw/GGUF/BO loaded',
        'payload_bytes':sum(x.nbytes for x in resident),'mappings':len(resident),'elapsed_s':time.monotonic()-start,
        'peak_rss_kib':max(observed),'rusage_peak_rss_kib':rusage_peak,'before':before,'after':after,'checksum':checksum,
        'sampling_note':'Maximum of rusage and post-touch VmHWM/VmRSS/smaps RSS; sequential observations, includes measurement overhead. v1 sampled rusage before proc and is retained, not the final peak.',
        'peak_includes':'Python/NumPy runtime + transient hash bytes + file-backed sidecar pages; not KV260 budget',
        'repack_copy_bytes':0,'raw_GGUF_pages_in_this_process':0,'raw_weight_pages_in_this_process':0,'resident_BO_bytes':None,
        'threads':1,'BOARD':'NOT_TESTED'}
    with (ROOT/args.output).open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
