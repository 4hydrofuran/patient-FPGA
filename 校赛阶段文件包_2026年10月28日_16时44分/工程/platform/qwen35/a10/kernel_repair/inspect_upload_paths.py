"""Bounded read-only diagnosis for the Windows/remote-path regression."""
import json
from pathlib import Path
import subprocess
import base64
import argparse

ROOT = Path(__file__).resolve().parents[4]
CODE = """
from pathlib import Path
import json,hashlib
root=Path('/home/ubuntu')
rows=[]
for p in root.iterdir():
    if 'a10-kernel-trial-20261020-v1' in p.name:
        r={'path':str(p),'symlink':p.is_symlink(),'directory':p.is_dir(),'files':[]}
        if p.is_dir() and not p.is_symlink():
            for x in p.iterdir():
                s={'name':x.name,'symlink':x.is_symlink(),'bytes':x.lstat().st_size}
                if x.is_file() and not x.is_symlink() and x.stat().st_size < 110000000:
                    with x.open('rb') as f:s['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
                r['files'].append(s)
        rows.append(r)
print(json.dumps(rows))
"""
if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage-state",action="store_true")
    args0=parser.parse_args()
    name="upload_path_diagnosis_01.json"
    if args0.stage_state:
        name="candidate_stage_independent_readback_01.json"
        CODE=r"""
from pathlib import Path
import json,hashlib
root=Path('/home/ubuntu/a10-kernel-trial-20261020-v1')
log=root/'stage-result.jsonl'
raw=log.read_text()
rows=[json.loads(s) for s in raw.splitlines()]
files={}
for name in ('image.fit','boot.scr.uimg','a10-candidate-20261020.fit'):
    p=Path('/boot/firmware')/name
    if p.is_file():
        with p.open('rb') as f:files[name]=hashlib.file_digest(f,'sha256').hexdigest()
pids=[]
for p in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        b=p.read_bytes()
        if b'/usr/bin/python3\\x00-B\\x00stage_candidate_board.py\\x00' in b:pids.append(p.parent.name)
    except (OSError,PermissionError):pass
print(json.dumps(dict(raw_stage_jsonl=raw,last_event=rows[-1] if rows else None,
    active_stage_pids=pids,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
    module_directory=Path('/usr/lib/modules/6.8.12-a10irq1').is_dir(),boot_hashes=files)))
"""
    record = ROOT / ("evidence/board_platform/A10_20261018_intake/"+name)
    with record.open("x") as output:
        args = ["C:/Windows/System32/OpenSSH/ssh.exe", "-T",
                "-o", "BindAddress=192.168.2.1",
                "-o", f"UserKnownHostsFile={(ROOT / 'platform/qwen35/a10/board_ssh_known_hosts').as_posix()}",
                "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
                "-o", "NumberOfPasswordPrompts=1", "-o", "PubkeyAuthentication=no",
                "ubuntu@192.168.2.2", "nice -n 19 python3 -c \"import base64;exec(base64.b64decode('"+
                base64.b64encode(CODE.encode()).decode()+"'))\""]
        r = subprocess.run(args, stdout=subprocess.PIPE, text=True, timeout=90)
        report = dict(argv=args,exit_code=r.returncode,stdout=r.stdout,board_writes=False)
        json.dump(report,output,indent=2)
    if args0.stage_state and r.returncode == 0:
        data=json.loads(r.stdout)
        data.pop("raw_stage_jsonl",None)
        print(json.dumps(dict(exit_code=r.returncode,summary=data,receipt=str(record))))
    else:
        print(json.dumps(report))
    raise SystemExit(r.returncode)
