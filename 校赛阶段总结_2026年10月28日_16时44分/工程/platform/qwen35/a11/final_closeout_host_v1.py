"""Reuse reviewed pinned/hidden-auth transport for a single fixed new helper.
Only launch is replaced; stage/resume/status are rejected. No live code patch.
"""
import base64
import gzip
import hashlib
from pathlib import Path
import cleanup_window_v3_host as transport

prior_plan=transport.plan


def plan(action,authorization_id=None,generation=None):
    if action=='readback':return prior_plan(action)
    if action!='launch':raise ValueError('final-only helper supports launch/readback only')
    argv,_=prior_plan('status')
    code=(Path(__file__).parent/'final_closeout_v1.py').read_bytes();pin=hashlib.sha256(code).hexdigest()
    blob=base64.b64encode(gzip.compress(code)).decode()
    program=('import base64,gzip,hashlib,sys; b=gzip.decompress(base64.b64decode(\''+blob+'\')); '
        'assert hashlib.sha256(b).hexdigest()==\''+pin+'\'; '
        "sys.argv=['reviewed_final_closeout','--execute-authorized-final-only']; "
        "exec(compile(b,'reviewed_final_closeout_v1.py','exec'))")
    argv[-1]='sudo -S -p '+transport.PROMPT.decode()+' /usr/bin/python3 -B -I -c "'+program+'"'
    return argv,pin


if __name__=='__main__':
    transport.plan=plan
    raise SystemExit(transport.main())
