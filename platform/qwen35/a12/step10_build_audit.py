"""Record real PC/cross-build artifacts and copy only private build outputs."""
import json,os
from pathlib import Path
import shutil
import subprocess
from common import sha, save
from step10_common import OUT

if __name__ == '__main__':
    version=int(os.environ.get('A12_SOURCE_VERSION','1'))
    work=Path.cwd();dest=OUT/('arm-bin' if version==1 else f'arm-bin-v{version}');dest.mkdir();rows={}
    paths=[work/'model/qwen35-a12',work/'model/libsp_linear_cpu.so',work/'libsp_linear_a12_trial.so']
    paths += [work/'arm-llama/bin'/name for name in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so')]
    for path in paths:
        header=subprocess.check_output(['readelf','-h',str(path)],text=True);assert 'AArch64' in header
        dynamic=subprocess.check_output(['readelf','-d',str(path)],text=True)
        target=dest/path.name;shutil.copyfile(path,target)
        rows[path.name]=dict(path=str(path),bytes=target.stat().st_size,sha256=sha(target),header=header,dynamic=dynamic)
    for stem in ('libllama','libggml','libggml-base','libggml-cpu'):
        shutil.copyfile(dest/(stem+'.so'),dest/(stem+'.so.0'))
    symbols=subprocess.check_output(['nm','-D','--defined-only',str(dest/'libsp_linear_a12_trial.so')],text=True)
    assert sum(' sp_linear_' in line for line in symbols.splitlines())==6
    assert ' sp_a12_completion_report_v1' in symbols
    cpu_symbols=subprocess.check_output(['nm','-D','--defined-only',str(dest/'libggml-cpu.so')],text=True)
    assert ' sp_a12_set_node_profile_v1' in cpu_symbols
    save(OUT/('BUILD.json' if version==1 else f'BUILD-v{version}.json'),dict(status='PASS_PC_AND_A53_CROSS_BUILD_NOT_BOARD',workspace=str(work),
         pc=str(work/'pc/qwen35-a12'),files=rows,sdk='2026.1',cpu='cortex-a53',native=False,
         private_completion_symbol=True,public_SP_LINEAR_symbols=6,private_node_timer=True))
    print(json.dumps(dict(status='TASK10_BUILD_READY',files=len(rows))))
