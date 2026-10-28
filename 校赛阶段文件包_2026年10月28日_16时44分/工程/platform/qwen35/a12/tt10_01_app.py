"""Frozen TT10-00 application timing with actual native prefix metrics."""
from tt10_00_app import measure as original_measure


def measure(worker,receive,template,frozen):
    r,events,begin,end,clock=original_measure(worker,receive,template,frozen)
    clock['cache']=dict(r['prefix_cache_request'])
    clock['cache']['snapshot_entries']=r['prefix_cache']['entries']
    clock['cache']['binding_sha256']=r['prefix_cache']['binding_sha256']
    return r,events,begin,end,clock
