"""Fresh BOARD entry, invoked only by an explicit execute-board command."""
import importlib.util
import json
import os
from pathlib import Path
import sys

from fast_response_profile import load_profile, builder


def run_board(window, kind, window_id):
    window=Path(window).resolve();bundle=window/'bundle'
    if os.uname().machine!='aarch64' or os.uname().release!='6.8.12-a10irq2':
        raise RuntimeError('BOARD requires the accepted aarch64 irq2 kernel')
    if not window_id or not all(c.isalnum() or c=='-' for c in window_id) or window_id.startswith('UNBOUND'):
        raise ValueError('fresh independent window id required')
    if (bundle/'run-v1').exists():raise RuntimeError('window already consumed; do not reset it')
    for p in (window/'web_gateway/src',window):sys.path.insert(0,str(p))
    # All imports/profile/prompt resolution happen before Owner or PL mutation.
    from fast_response_prepare_support import refresh_bundle_manifest
    from fast_response_preflight import preflight
    preflight(window)
    profile=load_profile(window/'profile.json');builder(profile)
    spec_path=bundle/'control/window-spec.json'
    spec=json.loads(spec_path.read_text(encoding='utf-8'))
    if spec['authorization_included'] is not False:raise ValueError('workload contains authority')
    spec['window_id']=window_id
    spec_path.write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
    if kind=='continuous':
        import interactive_entry
        interactive_entry.ROOT=window;interactive_entry.BUNDLE=bundle;interactive_entry.FRONT=window
        interactive_entry.main()
        return
    if kind!='ordinary':raise ValueError('unknown window kind')
    # Ordinary mode reuses the original strict manager/case/restore path.
    import subprocess
    from board_entry import prepared_main
    preflight=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                   kernel_raw=subprocess.check_output(['dmesg','--raw']).decode())
    (bundle/'control/preflight.json').write_text(json.dumps(preflight),encoding='utf-8')
    refresh_bundle_manifest(bundle)
    path=bundle/'control/resource_probe_manager.py'
    module_spec=importlib.util.spec_from_file_location('fast_response_original_manager',path)
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    from resource_probe_binding import require_manager_api
    require_manager_api(module)
    exec(prepared_main(path.read_text(encoding='utf-8')),module.__dict__)
    module.run_web_bound()
