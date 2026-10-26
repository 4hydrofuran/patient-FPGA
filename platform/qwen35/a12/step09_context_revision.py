"""Add real ARM pre-device failure checks only to the not-yet-run context window."""
import json,shutil
from common import ROOT,sha,save
from step09_common import OUT

if __name__=='__main__':
    assert not (OUT/'context').exists()
    p=ROOT/'platform/qwen35/a12'
    s=(p/'step09_manager.py').read_text();shutil.copyfile(p/'step09_manager.py',OUT/'short-manager-source.py')
    old="        s1=run/'s1';s1.mkdir()"
    assert s.count(old)==1
    s=s.replace(old,"        if SPEC['variant']=='context':\n            from step09_negative import startup_negatives\n            startup_negatives(BUNDLE,owner,p,run)\n"+old)
    (p/'step09_manager.py').write_text(s,encoding='utf-8',newline='\n')
    # Inject the new helper into the future context bundle. Existing short manifest is immutable.
    s=(p/'step09_package.py').read_text();old="'step09_window.py','step09_supervisor.py'):"
    assert s.count(old)==1
    (p/'step09_package.py').write_text(s.replace(old,"'step09_window.py','step09_supervisor.py','step09_negative.py'):"),encoding='utf-8',newline='\n')
    save(OUT/'CONTEXT_SCOPE_SUPPLEMENT.json',dict(status='FROZEN_BEFORE_CONTEXT_PACKAGE_OR_EXECUTION',negative_child_limit=2,expected_exit_code=2,per_child_wait_seconds=180,max_hardware_permissions=0,manager_source_sha256=sha(p/'step09_manager.py'),negative_source_sha256=sha(p/'step09_negative.py'),no_math_or_threshold_change=True,existing_short_bundle_unchanged=True))
    print('TASK09_CONTEXT_ARM_NEGATIVE_SCOPE_FROZEN')
