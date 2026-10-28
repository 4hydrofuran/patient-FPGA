"""Bind the user's second explicit normal-reboot authorization to the failed window."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
r=json.loads((ROOT/'evidence/frontend_board_A/20261027-board-hotpath-opt-v1/drain-v4-command/stdout.txt').read_text(encoding='utf-8-sig'))['inventory']
assert r['status']=='NATIVE_NORMAL_EXIT0_PARENT_LEASE_RETAINED_FOR_AUTHORIZED_REBOOT' and r['exit_code']==0
p=Path(__file__).with_name('frontend_boot_once.ps1');s=p.read_text(encoding='utf-8')
lines=s.splitlines()
index=next(i for i,x in enumerate(lines) if x.startswith('    $guard='))
lines[index]="    $guard='set -e; test \"$(cat /proc/sys/kernel/random/boot_id)\" = a9dd0f40-016e-4234-b73b-13546d4a62b1; test \"$(uname -r)\" = 6.8.12-a10irq2; test \"$(sha256sum /etc/machine-id | cut -d '' '' -f1)\" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; test \"$(sha256sum /var/lock/kv260-a1/active/lease.json | cut -d '' '' -f1)\" = "+r['lease_sha256']+"; test \"$(cut -d '' '' -f3 /proc/13980/stat)\" = Z; test \"$(cut -d '' '' -f52 /proc/13980/stat)\" = 0; test \"$(sha256sum /boot/firmware/a10-candidate-irq2-20261021.fit | cut -d '' '' -f1)\" = e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'"
s='\n'.join(lines)+'\n'
s=s.replace('$(sha256sum /var/lock/kv260-a1/active/lease.json', '$(sudo -n sha256sum /var/lock/kv260-a1/active/lease.json')
# The retained lease is root-private; authenticate before reading its hash.
begin=s.index("    $tag='PREBOOT_'")
end=s.index("    $auth='AUTH_'",begin)
check=s[begin:end];s=s[:begin]+s[end:]
at=s.index("    $wire='( '")
s=s[:at]+check+s[at:]
s=s.replace('A12_B_LATEST_AUTHORIZED_NORMAL_IRQ2_BOOT_V1','A12_HOTPATH_SECOND_EXPLICIT_NORMAL_IRQ2_BOOT_V1')
s=s.replace('$watch.Elapsed.TotalSeconds -lt 100','$watch.Elapsed.TotalSeconds -lt 180')
out=p.with_name('frontend_hotpath_boot_once.ps1');out.write_text(s,encoding='utf-8');print(out)
