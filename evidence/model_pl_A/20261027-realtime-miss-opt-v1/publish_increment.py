"""Copy the exact sealed increment and archives into the clean delivery worktree."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess

ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_realtime_model_draft_20261027_v1'
WORKTREE=Path('C:/Patientqwen_publish/a12_fast_response_cache_20261027')
BRANCH='codex/a12-realtime-model-opt-20261027'
BASE='d9ed467ea57700ad96edd86790ae1fb65cc112c9'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(WORKTREE),*args])
assert git('rev-parse','HEAD').decode().strip()==BASE
assert git('branch','--show-current').decode().strip()==BRANCH
assert not git('status','--porcelain')
assert read(EV/'COMPLETION.json')['status']=='PASS_ALL_REQUIRED_NO_BOARD_REALTIME_OPTIMIZATION'
assert read(EV/'archive-command/COMMAND.json')['exit_code']==0
paths={}
for row in read(RELEASE/'ENGINEERING_MANIFEST.json')['files']:
    p=ROOT/row['path'];assert sha(p)==row['sha256'],p
    paths[row['path']]=p
for name in ('ARCHIVES.json','COMPLETION.json','archive-command/COMMAND.json',
             'archive-command/stdout.txt','archive-command/stderr.txt','publish_increment.py'):
    p=EV/name;assert p.is_file();paths[p.relative_to(ROOT).as_posix()]=p
# GitHub displays README automatically, while the local START_HERE entry remains.
(RELEASE/'README.md').write_bytes((RELEASE/'START_HERE.md').read_bytes())
delivery=read(RELEASE/'DELIVERY.json');delivery.update(repository='https://github.com/4hydrofuran/patient-FPGA',branch=BRANCH,base_commit=BASE)
(RELEASE/'DELIVERY.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p in RELEASE.iterdir():
    if p.is_file():paths[p.relative_to(ROOT).as_posix()]=p
rows=[]
for name,p in sorted(paths.items()):
    relative=PurePosixPath(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    target=WORKTREE.joinpath(*relative.parts)
    assert target.resolve().is_relative_to(WORKTREE.resolve())
    data=p.read_bytes();assert len(data)<100*1024*1024
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    assert sha(target)==hashlib.sha256(data).hexdigest()
    rows.append(dict(path=name,bytes=len(data),sha256=sha(target)))
(EV/'PUBLISH_FILES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(EV/'PUBLISH_PATHS.nul').write_bytes(b''.join(r['path'].encode('utf-8')+b'\0' for r in rows))
print(json.dumps(dict(status='EXACT_SEALED_INCREMENT_COPIED',branch=BRANCH,base_commit=BASE,
                     copied_files=len(rows),original_workspace_index_touched=False),indent=2))
