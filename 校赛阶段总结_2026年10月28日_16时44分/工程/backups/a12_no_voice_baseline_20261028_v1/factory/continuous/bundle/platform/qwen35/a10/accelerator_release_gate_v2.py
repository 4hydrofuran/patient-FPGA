"""Read-only release precondition, derived from the 20261023 peer gate.

No device opens, module/PL operations, signals, or kernel-error exemptions.
A snapshot is not an atomic exclusion mechanism: the caller must continuously
own the maintenance lease/locks and isolate other accelerator consumers.
Unknown/vanished/inaccessible process data is deliberately NOT a clean scan.
"""
import os
from pathlib import Path
import stat
import time


SCHEMA = "a10-accelerator-scan-v2"
PS_DISPLAY = '/dev/dri/card0'


def file_identity(info):
    return dict(mode=info.st_mode, device=info.st_dev, rdev=info.st_rdev,
                inode=info.st_ino, uid=info.st_uid)


def ps_display_identity():
    """Identify only the observed fixed PS display, never by card number alone.

    All accesses are stat/readlink/sysfs reads, not device opens. Any missing,
    changed or unexpected binding refuses the scan instead of excluding it.
    """
    node = Path(PS_DISPLAY)
    drm = Path('/sys/class/drm/card0')
    driver = str((drm / 'device/driver').resolve(strict=True))
    device = str((drm / 'device').resolve(strict=True))
    dev = (drm / 'dev').read_text().strip()
    info = node.lstat()
    if (driver != '/sys/bus/platform/drivers/zynqmp-display' or
            device != '/sys/devices/platform/axi/fd4a0000.display' or dev != '226:0' or
            not stat.S_ISCHR(info.st_mode) or info.st_uid != 0 or
            (os.major(info.st_rdev), os.minor(info.st_rdev)) != (226, 0) or
            Path('/sys/dev/char/226:0').resolve(strict=True) != drm.resolve(strict=True)):
        raise ValueError('PS_DISPLAY_BINDING_NOT_PROVEN')
    return dict(path=PS_DISPLAY, driver=driver, sys_device=device, dev=dev,
                identity=file_identity(info))


def is_ps_display_fd(target, identity, proof):
    return proof is not None and target == PS_DISPLAY and identity == proof['identity']


def is_ps_display_map(row, proof):
    fields = row.split(None, 5)
    if proof is None or len(fields) != 6 or fields[5] != PS_DISPLAY:
        return False  # deleted nodes and aliases remain blocking
    device = tuple(int(x, 16) for x in fields[3].split(':'))
    info = proof['identity']
    return device == (os.major(info['device']), os.minor(info['device'])) and int(fields[4]) == info['inode']


def accelerator_path(path, cards=()):
    name = path.removesuffix(" (deleted)")
    # Include primary DRM nodes, not only render nodes. A closed fd does not
    # imply that an mmap disappeared when a native XRT library stays loaded.
    return name.startswith(("/dev/dri/", "/dev/zocl", "/dev/uio", "/dev/vfio/")) or name in cards


def mapped_accelerators(raw, cards=()):
    found = []
    for line in raw.splitlines():
        fields = line.split(None, 5)
        if len(fields) < 5:
            raise ValueError("MALFORMED_MAPS_ROW")
        if len(fields) == 6 and accelerator_path(fields[5], cards):
            found.append(line)
    return found


def start_ticks(proc):
    # comm can contain spaces and ')'; fields after the final ')' start at 3.
    return int((proc / "stat").read_text().rsplit(")", 1)[1].split()[19])


def collect(proc_root=Path("/proc"), cards=(), *, allow_ps_display=False):
    """One bounded-by-process-count observation; no retries or silent skips.

    Production use requires root, a reviewed Linux /proc, a fresh boot/lease,
    exclusive consumers and a controller deadline. No hardware access here.
    Custom device aliases must be supplied in cards; this does not establish
    that arbitrary aliases or uncooperative external consumers are impossible.
    """
    root = Path(proc_root)
    result = dict(schema=SCHEMA, scan_started_ns=time.monotonic_ns(),
                  scan_finished_ns=None, boot_id=None, boot_id_after=None,
                  scan_complete=False, device_holders=[], device_mappings=[],
                  scan_issues=[], inspected_processes=[], ps_display_before=None,
                  ps_display_after=None, ps_display_holders=[], ps_display_mappings=[])

    def pids():
        return sorted(p.name for p in root.iterdir() if p.name.isdecimal())

    def descriptors(proc):
        entries_by_fd = {}
        # Keep the directory iterator alive while resolving entries. Listing
        # /proc/self/fd and resolving names AFTER closing the iterator creates
        # a false missing-fd failure for the scanner's own directory fd.
        with os.scandir(proc / 'fd') as entries:
            for entry in entries:
                target = os.readlink(entry.path)
                if proc.name == str(os.getpid()) and target == str((proc / 'fd').resolve()):
                    # A known read-only proc directory fd, never a device fd.
                    continue
                identity = file_identity(os.stat(entry.path)) if accelerator_path(target, cards) else None
                entries_by_fd[entry.name] = (target, identity)
        return entries_by_fd

    try:
        result["boot_id"] = (root / "sys/kernel/random/boot_id").read_text().strip()
        display = ps_display_identity() if allow_ps_display else None
        result['ps_display_before'] = display
        before = pids()
        for pid in before:
            proc = root / pid
            try:
                started = start_ticks(proc)
                fds = descriptors(proc)
                for fd, (target, identity) in fds.items():
                    if accelerator_path(target, cards):
                        key = 'ps_display_holders' if is_ps_display_fd(target, identity, display) else 'device_holders'
                        result[key].append(dict(pid=int(pid), fd=fd, target=target, identity=identity))
                for row in mapped_accelerators((proc / "maps").read_text(), cards):
                    key = 'ps_display_mappings' if is_ps_display_map(row, display) else 'device_mappings'
                    result[key].append(dict(pid=int(pid), map=row))
                if started != start_ticks(proc) or fds != descriptors(proc):
                    raise ValueError("PROCESS_OR_FD_TABLE_CHANGED")
                result["inspected_processes"].append(dict(pid=int(pid), start_ticks=started))
            except (OSError, ValueError, IndexError, UnicodeError) as exc:
                result["scan_issues"].append(dict(pid=int(pid), reason=type(exc).__name__ + ": " + str(exc)))
        if before != pids():
            result["scan_issues"].append(dict(reason="PROCESS_SET_CHANGED"))
        result['ps_display_after'] = ps_display_identity() if allow_ps_display else None
        if display != result['ps_display_after']:
            result['scan_issues'].append(dict(reason='PS_DISPLAY_BINDING_CHANGED'))
        result["boot_id_after"] = (root / "sys/kernel/random/boot_id").read_text().strip()
        if not before or result["boot_id"] != result["boot_id_after"]:
            result["scan_issues"].append(dict(reason="EMPTY_PROCESS_SET_OR_BOOT_CHANGED"))
        result["scan_complete"] = not result["scan_issues"]
    except (OSError, ValueError, UnicodeError) as exc:
        result["scan_issues"].append(dict(reason=type(exc).__name__ + ": " + str(exc)))
    result["scan_finished_ns"] = time.monotonic_ns()
    return result


def require_no_users(snapshot, kernel_gate_allowed, *, boot_id):
    """Complete process scan gate, also usable when ZOCL is genuinely absent."""
    if kernel_gate_allowed is not True:
        raise RuntimeError("KERNEL_GATE_BLOCKED_OR_UNKNOWN")
    if (snapshot.get("schema") != SCHEMA or snapshot.get("scan_complete") is not True or
            snapshot.get("boot_id") != boot_id or snapshot.get("boot_id_after") != boot_id):
        raise RuntimeError("PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT")
    for key in ("scan_issues", "device_holders", "device_mappings", "inspected_processes"):
        if type(snapshot.get(key)) is not list:
            raise RuntimeError("PROCESS_SCAN_MISSING_FIELDS")
    if snapshot["scan_issues"] or not snapshot["inspected_processes"]:
        raise RuntimeError("PROCESS_SCAN_INCOMPLETE")
    if snapshot.get('ps_display_holders') or snapshot.get('ps_display_mappings'):
        proof = snapshot.get('ps_display_before')
        if not proof or proof != snapshot.get('ps_display_after'):
            raise RuntimeError('PS_DISPLAY_PROOF_MISSING_OR_CHANGED')
        if not all(is_ps_display_fd(row['target'], row['identity'], proof)
                   for row in snapshot.get('ps_display_holders', [])) or not all(
                       is_ps_display_map(row['map'], proof) for row in snapshot.get('ps_display_mappings', [])):
            raise RuntimeError('PS_DISPLAY_CLASSIFICATION_DIFFERS')
    if snapshot["device_holders"]:
        raise RuntimeError("ACCELERATOR_DESCRIPTOR_STILL_OPEN")
    if snapshot["device_mappings"]:
        raise RuntimeError("ACCELERATOR_VMA_STILL_MAPPED")


def require_release(snapshot, module_refcount, kernel_gate_allowed, *, boot_id):
    """Fail closed on incomplete/malformed observations. Does NOT unload."""
    require_no_users(snapshot, kernel_gate_allowed, boot_id=boot_id)
    if type(module_refcount) is not int or module_refcount != 0:
        raise RuntimeError("MODULE_REFERENCE_HELD_OR_UNKNOWN")

