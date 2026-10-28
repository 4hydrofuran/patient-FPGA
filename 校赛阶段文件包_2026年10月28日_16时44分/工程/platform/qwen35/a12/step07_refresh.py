"""Refresh a never-uploaded local draft after ready-message schema review."""
import json
from pathlib import Path
import shutil
import tarfile
from common import ROOT,sha,save
from step07_protocol import OUT


if __name__=='__main__':
    assert not any((OUT/n).exists() for n in ('upload_01.json','stage_01','launch_01'))
    draft=OUT/'unexecuted-draft-v1';draft.mkdir()
    target=OUT/'bundle-v1';old=json.loads((OUT/'UPLOAD.json').read_text())
    for name in ('single-gate.tar','UPLOAD.json','stage_reviewed.py','launch_reviewed.py','readback_reviewed.py'):
        (OUT/name).rename(draft/name)
    for name in ('manifest.json','control/step07_manager.py'):
        p=draft/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(target/name,p)
    shutil.copyfile(ROOT/'platform/qwen35/a12/step07_manager.py',target/'control/step07_manager.py')
    manifest=json.loads((target/'manifest.json').read_text())
    manifest['files']=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                       for p in sorted(target.rglob('*')) if p.is_file() and p!=target/'manifest.json']
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=OUT/'single-gate.tar'
    with tarfile.open(archive,'w') as tar:
        for p in sorted(target.rglob('*')):
            if p.is_file():tar.add(p,arcname=p.relative_to(target).as_posix(),recursive=False)
    up=dict(old,bytes=archive.stat().st_size,sha256=sha(archive),manifest_sha256=sha(target/'manifest.json'))
    save(OUT/'UPLOAD.json',up)
    stage=(draft/'stage_reviewed.py').read_text();assert repr(old) in stage
    (OUT/'stage_reviewed.py').write_text(stage.replace(repr(old),repr(up)))
    launch=(draft/'launch_reviewed.py').read_text();assert old['manifest_sha256'] in launch
    (OUT/'launch_reviewed.py').write_text(launch.replace(old['manifest_sha256'],up['manifest_sha256']))
    shutil.copyfile(draft/'readback_reviewed.py',OUT/'readback_reviewed.py')
    save(OUT/'UNEXECUTED_DRAFT_REVIEW.json',dict(status='CORRECTED_BEFORE_BOARD_DISPATCH',
       finding='ready message has no gpu_layers; check gpu_layers on actual result instead',
       original_draft='unexecuted-draft-v1',old_upload=old,new_upload=up,hardware_attempts=0))
    print(json.dumps(dict(status='REVIEWED_SINGLE_GATE_DRAFT_REFRESHED',**up)))
