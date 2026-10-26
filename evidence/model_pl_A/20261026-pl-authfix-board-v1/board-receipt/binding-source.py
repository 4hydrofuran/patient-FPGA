"""Bind a workload to a window without embedding compute authority in its spec."""
import copy

from resource_probe_policy import require, validate_plan


def bind_workload(requests, spec, *, window_id, max_session_seconds=1800):
    # This is a workload flag, not the separately issued Owner review permission.
    validate_plan(requests, spec)
    bound = copy.deepcopy(spec)
    bound.update(window_id=window_id, authorization_included=False,
                 max_session_seconds=max_session_seconds)
    require(type(window_id) is str and bool(window_id), 'window id required')
    require(type(max_session_seconds) is int and
            0 < max_session_seconds <= spec['max_session_seconds'],
            'session cannot exceed original window cap')
    validate_plan(requests, bound)
    return bound
