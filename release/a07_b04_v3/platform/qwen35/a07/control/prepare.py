"""Preserve A07 sources before changes; redact official license diagnostics."""
import hashlib,json,re,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[4]
E=R/'evidence/A07_closeout/20261004-v1'
out=E/'before';out.mkdir(exist_ok=False)
files={}
for folder in ['modules/linear_A/xrt']:
    for p in (R/folder).glob('*'):
        if p.is_file():
            q=out/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
            files[p.relative_to(R).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['docs/PROJECT_STATUS.json','hw/linear_A/KERNEL_SOURCE.json']:
    p=R/name;q=out/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
(out/'sha256.json').write_text(json.dumps(files,indent=2)+'\n')
adapters={p.parent.name:p.read_text().strip().replace(':','').lower() for p in Path('/sys/class/net').glob('*/address') if p.parent.name!='lo'}
licenses=[]
for name in ['kv260-a-2026.1.lic','kv260-a-rehost-20261003.lic']:
    p=Path('/home/member-a/.Xilinx')/name
    if not p.is_file():continue
    raw=p.read_bytes();text=raw.decode(errors='replace')
    ids=sorted(set(re.findall(r'HOSTID=([0-9a-fA-F]{12})(?:\s|\\|$)',text)))
    licenses.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'hostids':ids,
        'matches_current_adapter':any(i.lower() in adapters.values() for i in ids)})
result={'action':'READ_ONLY_NO_NETWORK_OR_LICENSE_CHANGE','adapters':adapters,'official_known_licenses':licenses,'BOARD':'NOT_TESTED'}
(E/'license-readonly.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
