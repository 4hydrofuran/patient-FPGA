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


def require_manager_api(manager):
    """Resolve adapter dependencies before creating Owner or loading PL."""
    for name in ('save', 'receive', 'validate_bo', 'measure_application'):
        require(callable(getattr(manager, name, None)), 'missing manager adapter: '+name)


def adapt_initial_scan(source):
    """Use the existing bounded complete-scan policy at initial admission too."""
    anchor='        snapshot = collect(allow_ps_display=True)'
    require(source.count(anchor) == 2, 'initial scan anchor differs')
    replacement='        snapshot = complete_scan(collect, require_no_users, self.boot, self._kernel_ok, self._finalize_record)'
    result=source.replace(anchor,replacement,1)
    compile(result,'resource_probe_bound_window','exec')
    return result
