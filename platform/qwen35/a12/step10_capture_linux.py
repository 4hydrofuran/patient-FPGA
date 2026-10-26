"""Copy real build logs and the changed pinned CPU source into the evidence batch."""
import json,shutil
from pathlib import Path
from common import ROOT,sha,save
from step10_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))
if __name__=='__main__':
    dest=OUT/'build-logs';dest.mkdir();rows={}
    for i in (1,2):
        job=j(OUT/f'build_submit_0{i}.json')['stdout'].strip()
        base=Path('/home/member-a/kv260-build/ra02-coordinator')
        for path in (base/'work'/job/'stdout.txt',base/'work'/job/'stderr.txt',base/'results'/(job+'.json')):
            name=f'v{i}-'+path.name;shutil.copyfile(path,dest/name);rows[name]=sha(path)
    first=Path(j(OUT/'BUILD-v1.json')['workspace']);second=Path(j(OUT/'BUILD-v2.json')['workspace'])
    c=first/'llama-source/ggml/src/ggml-cpu/ggml-cpu.c';pin=j(OUT/'LLAMA_DERIVATION.json')['changes']['ggml/src/ggml-cpu/ggml-cpu.c']['after']
    assert sha(c)==pin;shutil.copyfile(c,dest/'ggml-cpu-timing.c')
    for label,path in [('arm-llama',first/'arm-llama/CMakeCache.txt'),('pc-llama',first/'pc-llama/CMakeCache.txt'),
                       ('arm-model',second/'model/CMakeCache.txt'),('pc-model',second/'pc/CMakeCache.txt')]:
        shutil.copyfile(path,dest/(label+'-CMakeCache.txt'))
    save(OUT/'BUILD_LOG_CAPTURE.json',dict(status='ACTUAL_QUEUE_LOGS_AND_SOURCE_CAPTURED',files=rows,changed_ggml_cpu_sha256=pin))
