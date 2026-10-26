"""Small successor adapter: one PL load, existing PCM path, no hot restore."""
import json
from pathlib import Path
import time

from control import CloseRequested


class FastAdapter:
    def __init__(self, core, link):
        self.core, self.link = core, link
        core.CONTROL = link
        self.finished = []

    def apply_overlay(self, target, source):
        c = self.core
        c.lease()
        # Log release/close separately: configfs can commit in release().
        c.event('OVERLAY_MKDIR_ENTER', target=str(target))
        target.mkdir()
        c.event('OVERLAY_MKDIR_RETURN', target=str(target))
        c.event('OVERLAY_OPEN_ENTER', target=str(target))
        stream = (target / 'dtbo').open('wb')
        c.event('OVERLAY_OPEN_RETURN', target=str(target))
        try:
            c.event('OVERLAY_WRITE_ENTER', source=source.name)
            data = source.read_bytes()
            count = stream.write(data)
            if count != len(data):
                raise OSError('Short configfs write')
            c.event('OVERLAY_WRITE_RETURN', bytes=count)
        finally:
            c.event('OVERLAY_CLOSE_COMMIT_ENTER', target=str(target))
            stream.close()
        c.event('OVERLAY_CLOSE_COMMIT_RETURN', target=str(target))
        status = (target / 'status').read_text().strip()
        if status != 'applied':
            raise RuntimeError('Overlay not applied: ' + status)
        c.event('OVERLAY_APPLIED_VERIFIED', target=str(target))

    def action(self, name):
        c = self.core
        if name in ('prepare', 'install', 'bind'):
            getattr(c, 'candidate_' + name)()
        elif name == 'remove_default':
            c.lease()
            c.event('DEFAULT_REMOVE_ENTER')
            c.DEFAULT.rmdir()
            c.event('DEFAULT_REMOVE_RETURN')
            if c.platform_state():
                raise RuntimeError('Unexpected overlay after default removal')
        elif name == 'apply_pl':
            self.apply_overlay(c.PL, c.OUT / 'pl-load.dtbo')
            if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() != 'operating':
                raise RuntimeError('FPGA not operating')
            driver = Path('/sys/bus/platform/devices/a13muted-afi/driver')
            if not driver.is_symlink() or driver.resolve().name != 'afi-fpga':
                raise RuntimeError('AFI/reset setup not bound; do not publish audio devices')
            c.raw = c.kernel_transition('after-pl-load', c.raw)
        elif name == 'apply_audio':
            self.apply_overlay(c.MUTED, c.OUT / 'audio-muted.dtbo')
            if c.platform_state() != {c.PL.name: 'applied', c.MUTED.name: 'applied'}:
                raise RuntimeError('Unexpected overlay state')
            c.raw = c.kernel_transition('after-audio-devices', c.raw)
        elif name == 'short':
            c.pcm_cycle(1, 'drop', c.device, c.paths)
            c.raw = c.kernel_transition('after-short-zero', c.raw)
        elif name == 'full':
            c.pcm_cycle(2, 'drain', c.device, c.paths)
            c.raw = c.kernel_transition('after-full-zero', c.raw)
        else:
            raise ValueError('Unsupported step')
        self.finished.append(name)

    def idle(self):
        c = self.core
        if 'bind' not in self.finished or any(p.poll() != 0 for p in c.CHILDREN):
            raise RuntimeError('No stopped/bound state proven; keep quarantine')
        c.lease()
        state = c.states(c.paths)
        return dict(status='AUDIO_IDLE_RESERVED', states=state,
                    owner_retained=True, default_restored=False, safe_release=False,
                    hot_restore=False, audible_test=False, recording=False)

    def checked_close(self, failed_step, reason):
        # Never remove overlays, unload modules, restore PL, or unlock here.
        # PCM normally closes in its own child. A blocked/failed child is retained.
        return self.idle()


STEPS = ('prepare', 'install', 'remove_default', 'apply_pl', 'apply_audio',
         'bind', 'short', 'full')


def run(adapter, link, park=None):
    phase = 'NOT_STARTED'
    try:
        for phase in STEPS:
            link.checkpoint()
            link.publish('EXECUTING', step=phase)
            adapter.action(phase)
            link.publish('IDLE_BOUNDARY', step=phase)
        result = adapter.idle()
        adapter.core.save('result.json', result)
        link.publish('AUDIO_IDLE_RESERVED', default_restored=False, owner_retained=True)
    except Exception as exc:
        # If even prepare never acquired ownership, returning does not drop a lease.
        if not adapter.core.FDS and adapter.core.LEASE_SHA is None:
            link.publish('STOPPED_BEFORE_OWNERSHIP', error=str(exc)[:500])
            return 2
        link.publish('QUARANTINED_OWNER_RETAINED', step=phase,
                     error=(type(exc).__name__ + ': ' + str(exc))[:600])
    if park is not None:  # PC fixture supplies a finite owner loop.
        return park(adapter, phase)
    close_handled = False
    while True:
        if link.close_event.is_set() and not close_handled:
            close_handled = True
            link.cleaning = True
            try:
                result = adapter.checked_close(phase, 'cooperative close')
                adapter.core.save('close-idle.json', result)
                link.publish('CLOSED_TO_AUDIO_IDLE_OWNER_RETAINED', default_restored=False)
            except Exception as exc:
                link.publish('CLOSE_STOPPED_QUARANTINE_NO_RETRY', error=str(exc)[:500])
        time.sleep(.05)


def worker_entry(config, link):
    import candidate_core as c
    r = config['request']
    c.REQUEST, c.ARTIFACTS = r, config['assets']
    c.BUNDLE = Path(config['bundle'])
    c.BOOT, c.BASELINE = r['boot_id'], r['kernel_log_sha256']
    c.OUT = Path('/var/lib/kv260-a13') / r['window']
    c.FW = Path('/lib/firmware/xilinx') / r['window']
    c.MUTED = c.OVERLAYS / r['window']
    c.PL = c.OVERLAYS / (r['window'] + '-pl')
    return run(FastAdapter(c, link), link)
