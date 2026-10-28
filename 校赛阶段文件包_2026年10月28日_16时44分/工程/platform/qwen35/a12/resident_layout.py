"""Prepare a pinned fixed-root review layout on PC, never install on Board."""
import os
from pathlib import Path
import shutil
from resident_evidence import ROOT,OUT,WORK,read,save,sha,pin
from resident_board_prepare import relocate


def main():
    assert os.name=='posix';os.umask(0o077)
    prepared=read(OUT/'BOARD_BUILD-v1-review-only.json');root=WORK/'board-review-layout-v1';root.mkdir()
    assets={'prefix_template','kernel_source','xclbin','resident_policy','chat_template'}
    for dirname in ('bin','assets','resident-app','ordinary-resource-probe'):(root/dirname).mkdir()
    for row in prepared['runtime_artifacts']+prepared['auxiliary_artifacts']:
        source=Path(row['path']);assert sha(source)==row['sha256']
        target=root/('assets' if row['role'] in assets else 'bin')/source.name
        assert not target.exists();shutil.copyfile(source,target);assert sha(target)==row['sha256']
    policy=read(prepared['resident_policy'])
    for row in policy['files']:
        source=Path(prepared['resident_app'])/row['path'];assert sha(source)==row['sha256']
        target=root/'resident-app'/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for alias in prepared['loader_aliases']:
        path=root/'bin'/alias['name'];target=root/'bin'/alias['target_basename']
        assert sha(target)==alias['sha256']
        if path!=target:path.symlink_to(target.name)
    manifest=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2/manifest.json'
    shutil.copyfile(manifest,root/'ordinary-resource-probe/manifest.json')
    verified=relocate(prepared,root)
    def target_paths(value):
        if isinstance(value,str) and (value==str(root) or value.startswith(str(root)+'/')):
            return '/opt/patient-qwen'+value[len(str(root)):]
        if isinstance(value,list):return [target_paths(q) for q in value]
        if isinstance(value,dict):return {k:target_paths(v) for k,v in value.items()}
        return value
    planned=target_paths(verified)
    planned.update(layout_state='PINNED_TARGET_CONFIG_ACTUAL_BOARD_PLACEMENT_NOT_TESTED',
                   application_factory='TYPED_ORIGINAL_OWNER_ONLY_NO_CLI_OR_AUTO_ENABLE',
                   authorization_included=False,physical_release_allowed=False,production_enabled=False)
    save(OUT/'BOARD_BUILD-fixed-root-v1.json',planned)
    save(OUT/'BOARD_LAYOUT_REVIEW.json',dict(status='PC_STAGED_REAL_A53_BYTES_AND_ORIGINAL_APP_FIXED_ROOT_CONFIG_VERIFIED',
         actual_files=[dict(path=p.relative_to(root).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(root.rglob('*')) if p.is_file()],
         build=pin(OUT/'BOARD_BUILD-fixed-root-v1.json'),staged_root=str(root),target_root='/opt/patient-qwen',
         model_copied=False,weights_copied=False,ordinary_bundle_copied=False,ordinary_manifest_unchanged=True,
         actual_Board_placement_verified=False,ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED',
         remaining='original pinned model/weights and full ordinary bundle must already exist; actual placed bytes and fresh Owner review checked only in separate Board window'))
    print('PASS_PC_STAGED_A53_BYTES_AND_FIXED_ROOT_TARGET_CONFIG_NO_BOARD')


if __name__=='__main__':main()
