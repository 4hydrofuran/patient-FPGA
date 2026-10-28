"""Preserve both actual native PC builds, including the first failed timing version."""
import json,shutil
from pathlib import Path
from common import sha,save
from step10_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))
if __name__=='__main__':
    first=Path(j(OUT/'BUILD-v1.json')['workspace']);records={}
    for version in (1,2):
        build=j(OUT/f'BUILD-v{version}.json');binary=Path(build['pc']);dest=OUT/f'pc-artifacts-v{version}';dest.mkdir()
        paths=[binary,binary.parent/'libsp_linear_cpu.so']
        paths += [first/'pc-llama/bin'/name for name in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so')]
        rows={}
        for path in paths:
            shutil.copyfile(path,dest/path.name)
            rows[path.name]=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))
        for stem in ('libllama','libggml','libggml-base','libggml-cpu'):shutil.copyfile(dest/(stem+'.so'),dest/(stem+'.so.0'))
        records[str(version)]=rows
    save(OUT/'PC_BUILD_ARTIFACTS.json',dict(status='ACTUAL_INITIAL_AND_CORRECTED_PC_BINARIES_PRESERVED',versions=records))
