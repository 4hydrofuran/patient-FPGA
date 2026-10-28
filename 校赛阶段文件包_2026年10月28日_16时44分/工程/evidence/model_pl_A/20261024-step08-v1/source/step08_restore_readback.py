"""Read retained normal-reboot records and current immutable boot/network proof."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
root=Path('/var/lib/kv260-a12/step08-restore-20261024-v1');records={}
for name in ('pre-reboot.json','reboot-command.json'):
    b=(root/name).read_bytes();records[name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),base64=base64.b64encode(b).decode())
pins={'/boot/firmware/image.fit':'23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e',
    '/boot/firmware/boot.scr.uimg':'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685',
    '/boot/firmware/a10-candidate-irq2-20261021.fit':'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'}
for name,pin in pins.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==pin
uuid='7f647045-31b0-4f1f-ae1b-4c265047a108'
path=subprocess.check_output(['busctl','--timeout=3','call','org.freedesktop.NetworkManager','/org/freedesktop/NetworkManager/Settings',
    'org.freedesktop.NetworkManager.Settings','GetConnectionByUuid','s',uuid],text=True,timeout=4).strip()
assert path.startswith('o "/org/freedesktop/NetworkManager/Settings/')
unsaved=subprocess.check_output(['busctl','--timeout=3','get-property','org.freedesktop.NetworkManager',path[3:-1],
    'org.freedesktop.NetworkManager.Settings.Connection','Unsaved'],text=True,timeout=4).strip();assert unsaved=='b true'
print(json.dumps(dict(status='RESTORE_RECORDS_DEFAULT_BOOT_PINS_AND_UNSAVED_NETWORK_VERIFIED',records=records,pins=pins,
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,unsaved=unsaved,
    eth0=json.loads(subprocess.check_output(['ip','-j','addr','show','dev','eth0'])),signals=0,configuration_changes=0)),flush=True)
