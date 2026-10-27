"""Closeout-only policy: no hardware calls; identity-bound retirement after quiescence."""
import os
import select
import signal
import time


def validate_retirement(s,e,now_ns=None):
    now_ns=time.monotonic_ns() if now_ns is None else now_ns
    for key in ('boot_id','machine_sha256','manager_pid','manager_start_ticks','lease_sha256','manifest_sha256'):
        if s.get(key)!=e[key]:raise RuntimeError('retirement identity differs: '+key)
    if not 0<=now_ns-s['observed_monotonic_ns']<=5_000_000_000:raise RuntimeError('stale retirement observation')
    for key in ('no_device_users','no_manager_devices','no_manager_XRT','no_manager_children',
                'single_sleeping_thread','source_pins_match','workers_normal_exit','default_restored',
                'kernel_allowed','old_manager_owns_both_locks','known_parked_code'):
        if s.get(key) is not True:raise RuntimeError('retirement gate refused: '+key)
    if s.get('ZOCL_absent') is not True or s.get('module_refcount') is not None:
        raise RuntimeError('module not absent')
    return True


def retire_once(pidfd,s,e,record):
    """Only a verified no-device waiting owner. Caller pins pidfd BEFORE observation."""
    validate_retirement(s,e)
    record('EXACT_PARKED_OWNER_RETIRE_RESERVED',pid=e['manager_pid'],start_ticks=e['manager_start_ticks'],
           signal=int(signal.SIGKILL),reason='old code masks normal stop signals and has no recovery IPC; workers/devices already closed',
           normal_manager_exit=False,hardware_operations=0)
    signal.pidfd_send_signal(pidfd,signal.SIGKILL,None,0)
    record('EXACT_PARKED_OWNER_SIGNAL_SENT',pid=e['manager_pid'],signal=int(signal.SIGKILL))
    poll=select.poll();poll.register(pidfd,select.POLLIN)
    if not poll.poll(5000):raise RuntimeError('retired manager exit not proven; no second signal')
    record('EXACT_PARKED_OWNER_EXIT_PROVEN_BY_PIDFD',normal_manager_exit=False)


def transient_scan(scan,boot):
    """A retry is only another observation; it never promotes an incomplete scan."""
    if scan.get('boot_id')!=boot or scan.get('boot_id_after')!=boot:return False
    if scan.get('device_holders') or scan.get('device_mappings'):return False
    issues=scan.get('scan_issues',[])
    if not issues:return False
    import re
    for row in issues:
        reason=row.get('reason','')
        if reason in ('PROCESS_SET_CHANGED','ValueError: PROCESS_OR_FD_TABLE_CHANGED'):continue
        m=re.fullmatch(r"FileNotFoundError: \[Errno 2\] No such file or directory: '/proc/(\d+)/(?:stat|maps|fd(?:/\d+)?)'",reason)
        if not m or row.get('pid')!=int(m.group(1)):return False
    return True


def complete_scan(collect,require_no_users,boot,kernel_check,record,*,attempts=4,pause=time.sleep):
    for i in range(attempts):
        allowed=kernel_check();s=collect(allow_ps_display=True)
        record('FULL_PROCESS_OBSERVATION',attempt=i+1,kernel_allowed=allowed,scan=s)
        try:require_no_users(s,allowed,boot_id=boot)
        except RuntimeError:
            if allowed is not True or not transient_scan(s,boot) or i+1==attempts:raise
            pause(.15)
        else:return s
    raise RuntimeError('complete scan not established')
