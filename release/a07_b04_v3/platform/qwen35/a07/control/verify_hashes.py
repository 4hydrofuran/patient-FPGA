"""Verify delivery bytes including binaries; never execute target code."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
files=json.loads((root/'files.sha256.json').read_text())
for name,item in files.items():
    p=(root/name).resolve()
    assert p.is_relative_to(root) and p.is_file(),name
    assert p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],name
for p in root.rglob('*'):
    if not p.is_file():continue
    assert p.suffix.lower() not in ['.lic','.vhd','.vhdx','.wic','.pem','.key'],p
    if p.name in ['id_rsa','id_ed25519']:raise ValueError('private credential')
print(json.dumps({'status':'PASS_DELIVERY_BYTES','files':len(files),'BOARD':'NOT_TESTED'}))
