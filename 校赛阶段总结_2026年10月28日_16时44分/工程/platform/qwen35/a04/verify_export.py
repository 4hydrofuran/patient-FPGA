"""Independently C++ quantize every raw BF16 matrix and check both exports."""
import hashlib,json,resource,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from quant.export_w4a8.loader import Sidecar


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'eval/qwen35/a04/export-cross-v1';out.mkdir(exist_ok=False)
    first=ROOT/'models/sidecar_A/qwen35-v1';second=ROOT/'models/sidecar_A/qwen35-repro-v1'
    a=Sidecar(first);b=Sidecar(second);mp=json.loads((ROOT/'quant/qwen35_tensor_map.json').read_text())
    check=[];commands=[];start=time.monotonic()
    for t in mp['mlp']:
        ident=f"l{t['layer']:02d}_{t['op']}";e=a.entries[ident];w,sw=a.load(ident)
        argv=['/home/member-a/qwen35-a04/build-v1/w4ref','pack-bf16',str(e['N']),str(e['K']),
              str(ROOT/'artifacts/qwen35-0.8b/source'/t['source_file']),str(t['absolute_offset']),str(out/ident)]
        r=subprocess.run(argv,capture_output=True,text=True)
        commands.append({'argv':argv,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        ok=r.returncode==0
        if ok:
            ok=all(sha(out/ident/key)==e['files'][key]['sha256']==sha(second/e['files'][key]['file']) for key in ('w.bin','sw.bin'))
        check.append({'id':ident,'passed':ok,'mmap_readonly':not w.flags.writeable and not sw.flags.writeable})
        del w,sw
    equal=sha(first/'manifest.json')==sha(second/'manifest.json')
    result={'domain':'PC','checks':check,'commands':commands,'manifests_identical':equal,
        'passed':equal and all(x['passed'] and x['mmap_readonly'] for x in check),
        'elapsed_s':time.monotonic()-start,'parent_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'note':'Every raw BF16 matrix independently quantized in C++; producer not called to form expected bytes. Loader maps only one matrix at a time.',
        'payload_bytes':a.manifest['payload_bytes'],'manifest_bytes':(first/'manifest.json').stat().st_size,'BOARD':'NOT_TESTED'}
    with (out/'summary.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','commands')}))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
