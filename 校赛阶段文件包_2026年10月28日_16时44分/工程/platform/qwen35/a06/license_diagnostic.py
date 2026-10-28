"""Read-only local license diagnosis; never emit keys, signatures, or identity fields."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

p=Path('/home/member-a/.Xilinx/kv260-a-2026.1.lic')
raw=p.read_bytes()
text=raw.decode('utf-8',errors='replace')
ids=sorted(set(re.findall(r'HOSTID=([0-9a-fA-F]{12})(?:\s|\\|$)',text)))
adapters=[]
for address in sorted(Path('/sys/class/net').glob('*/address')):
    value=address.read_text().strip()
    if address.parent.name!='lo':adapters.append({'interface':address.parent.name,'mac':value})
value={'license_path':str(p),'license_sha256':hashlib.sha256(raw).hexdigest(),
       'license_ethernet_host_ids':ids,'current_adapters':adapters,
       'host_id_matches':any(v['mac'].replace(':','').lower() in [i.lower() for i in ids] for v in adapters),
       'license_env_present':{k:bool(os.environ.get(k)) for k in ('XILINXD_LICENSE_FILE','LM_LICENSE_FILE')},
       'features':re.findall(r'^INCREMENT\s+(\S+)',text,re.M),
       'hostname':subprocess.check_output(['hostname'],text=True).strip(),
       'actions':'READ_ONLY; no MAC/license/OS changes, no login',
       'recovery':'Owner rehosts/regenerates official node-locked license for actual build-host ID; then A reruns only failed Csim'}
print(json.dumps(value,indent=2))
