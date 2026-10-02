"""Actual worker process memory; lifetime peaks, not per-model allocations."""
import os
import sys


def memory_snapshot():
    result = dict(current_rss_bytes=None, peak_rss_bytes=None,
                  memory_scope='WORKER_PROCESS_LIFETIME_PEAK', memory_method=None)
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in
                    ['PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                     'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                     'PagefileUsage', 'PeakPagefileUsage']]

            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            c = Counters()
            c.cb = ctypes.sizeof(c)
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb):
                raise OSError('Memory counters unavailable')
            result.update(current_rss_bytes=c.WorkingSetSize, peak_rss_bytes=c.PeakWorkingSetSize,
                          memory_method='Windows GetProcessMemoryInfo')
        else:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            result.update(peak_rss_bytes=int(peak if sys.platform == 'darwin' else peak * 1024),
                          memory_method='resource.RUSAGE_SELF')
            status = '/proc/self/status'
            if os.path.isfile(status):
                with open(status, encoding='ascii') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            result['current_rss_bytes'] = int(line.split()[1]) * 1024
    except (OSError, ImportError, ValueError):
        result['memory_method'] = 'UNAVAILABLE'
    return result
