"""Offline route selection only: never connects, signals, loads or restarts."""
import argparse
import json
from pathlib import Path
from cleanup_board_v3 import BOOT, WAITER, WAITER_TICKS


def choose(snapshot):
    result=dict(domain='PC_OFFLINE',board_actions=0,execution_authorized=False,
        fresh_readback_required=True,A11='NOT_PASSED',reason=None)
    boot=snapshot.get('boot_id')
    if not boot:
        return dict(result,route='READONLY_RECONCILE',reason='missing boot identity')
    if boot!=BOOT:
        return dict(result,route='NEW_BOOT_READONLY_REBUILD',reason='old PID/authorization/checkpoint cannot cross a boot')
    scan=snapshot.get('scan',{})
    if (scan.get('scan_complete') is not True or scan.get('scan_issues') != [] or
        scan.get('boot_id')!=BOOT or scan.get('boot_id_after')!=BOOT or
        scan.get('device_holders')!=[] or scan.get('device_mappings')!=[]):
        return dict(result,route='READONLY_RECONCILE',reason='resource evidence incomplete or occupied')
    overlay=snapshot.get('overlays')
    if overlay=={'k26-starter-kits_image_1':'applied'} and snapshot.get('module_present') is False:
        return dict(result,route='DEFAULT_READBACK_ONLY',reason='do not replay remove/load; verify graphics, leases, kernel and ownership')
    proc=snapshot.get('recovery_process',{})
    try:
        fields=proc['stat'].rsplit(')',1)[1].split()
        pinned=proc['pid']==WAITER and int(fields[19])==WAITER_TICKS and fields[0]=='S'
    except (KeyError,ValueError,IndexError,TypeError):pinned=False
    if (overlay=={'a11-mlp-20261023-v1_image_1':'applied'} and snapshot.get('module_refcount')=='0'
        and snapshot.get('module_present') is True and pinned and snapshot.get('cleanup_locks_owned')==[True,True]):
        return dict(result,route='SAME_BOOT_TAKEOVER_CANDIDATE',reason='last saved state matches; live pins/temperature/kernel/ownership and new scope still required')
    return dict(result,route='READONLY_RECONCILE',reason='not an approved starting state; do not infer completed operations')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',required=True,type=Path)
    a=p.parse_args();print(json.dumps(choose(json.loads(a.snapshot.read_bytes())),indent=2))


if __name__=='__main__':main()
