"""After successful windows, register the installed diagnostic version while idle."""
import base64
import contextlib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import time

DATA=None


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert os.geteuid()==0
    output=io.StringIO()
    with contextlib.redirect_stdout(output):exec(compile(gzip.decompress(base64.b64decode(DATA['preflight'])),'cpu01_deployment_fresh_readonly_gate','exec'),{'__name__':'__main__'})
    fresh=json.loads(output.getvalue())
    assert fresh['machine_sha256']=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
    assert fresh['kernel']=='6.8.12-a10irq2' and fresh['scans'][-1]['no_users_gate']
    assert not fresh['active_lease_exists'] and not fresh['module_present'] and not any(fresh['locks'].values())
    assert fresh['overlays']=={'k26-starter-kits_image_1':'applied'} and fresh['gdm_state']=='active' and fresh['fpga_state']=='operating'
    root=Path('/var/lib/kv260-a12/cpu01-integrated-20261024-v1')
    manifest=json.loads((root/'manifest.json').read_text())
    for row in manifest['files']:
        path=root/row['path'];assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
    assert sha(root/'bin/qwen35-a12')==DATA['binary_sha256']
    assert json.loads((root/'manager-exit.json').read_text())['exit_code']==0
    assert all(json.loads((root/'run-v1'/side/'exit.json').read_text())['exit_code']==0 for side in ('s1','s2'))
    assert json.loads((root/'run-v1/s2/exit.json').read_text())['host_permission_runs']==3816
    payload=dict(status='INSTALLED_AND_BOARD_VERIFIED_CPU01_DIAGNOSTIC_VERSION',boot_id=fresh['boot_id'],registered_monotonic_ns=time.monotonic_ns(),
        directory=str(root),manifest_sha256=sha(root/'manifest.json'),program_sha256=DATA['binary_sha256'],
        same_board_old_new_numerics='BIT_EXACT',normal_restore=True,fresh_no_users_gate=True,
        rollback='/var/lib/kv260-a12/health-opt-20261024-v1',default_backend_changed=False,system_startup_changed=False,
        use='Derive a fresh reviewed maintenance package from this directory; consumed review/lease/run-v1 must not be replayed.')
    path=root/'deployment-receipt.json'
    with path.open('x',encoding='utf-8') as stream:json.dump(payload,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    descriptor=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    assert json.loads(path.read_text())==payload
    print(json.dumps(dict(deployment=payload,receipt_sha256=sha(path),fresh_postcheck=fresh)),flush=True)


if __name__=='__main__':main()
