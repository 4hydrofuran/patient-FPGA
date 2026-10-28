"""Exactly one ordinary PL R0/warm/hit probe; no diagnostic reader or retries."""
import copy
import json
import time
from resource_probe_policy import (BO_BYTES, BO_COUNT, WEIGHTS, IDS, OFF, ProbeBlocked,
    comparison_view, integer, ordinary_comparison, require, validate_plan, validate_request)
from resource_probe_observer import ResourceObserver


class SendGate:
    def __init__(self, worker, observer):
        self.worker, self.observer = worker, observer
        self.expected = None
        self.sent = False

    def arm(self, request):
        require(self.expected is None, 'previous request still active')
        self.expected = {k:v for k,v in request.items()
                         if 'application' not in request or k not in ('tokens', 'application')}
        self.sent = False

    def send(self, request):
        check = {k:v for k,v in request.items() if k != 'cache_binding_sha256'}
        validate_request(check, wire=True)
        require(request == self.expected and not self.sent, 'duplicate/foreign/changed send')
        self.observer.checkpoint('BEFORE_SEND_' + request['id'], prefix=request['id'] == 'warm_prefix')
        self.worker.send(request)
        self.sent = True

    def complete(self):
        require(self.sent, 'request was not sent')
        self.expected = None


def execute_case(worker, owner, path, *, real, api):
    require(real is True and worker.real is True, 'probe requires explicit real-PL worker; PC uses an injected control double')
    save, bundle, spec = api['save'], api['BUNDLE'], api['SPEC']
    requests = json.loads((bundle/'control/requests.json').read_text(encoding='utf-8'))
    validate_plan(requests, spec)
    get = lambda: api['receive'](worker, owner, path)
    observer = None
    try:
        ready = get()
        require(ready.get('type') == 'ready' and ready.get('execution_kind') == 'FPGA_REAL', 'wrong native ready')
        require(ready.get('physical_ubatch') == 8 and ready.get('prefix_cache', {}).get('enabled') is True,
                'prefix/physical microbatch not ready')
        route = ready['bridge']['a12_route']
        require(route.get('execution_kind') == 'FPGA_REAL' and
                route.get('kernel_build_id') == 0xB3030002, 'ready backend/build differs')
        spans = api['validate_bo'](route)
        require(worker.loads == WEIGHTS and worker.runs == route['host_verified_completions'] == 0,
                'ready weights/completions differ')
        owner.full_resident = True
        save(path/'ready.json', ready)
        save(path/'startup-timing.json', dict(process_launch_monotonic_ns=worker.task10_launch_ns,
             ready_received_monotonic_ns=time.monotonic_ns(), service_ready=False,
             reason='ordinary prefix resource probe has not completed'))
        factory = api.get('resource_observer', ResourceObserver)
        observer = factory(owner, worker, path)
        observer.checkpoint('READY_RESIDENT', prefix=True)
        gate = SendGate(worker, observer)
        binding = ready['prefix_cache']['binding_sha256']
        require(type(binding) is str and len(binding) == 64, 'prefix binding missing')
        reference = None
        previous = 0
        last = None
        for frozen in requests:
            request = copy.deepcopy(frozen)
            directory = path/request['id']
            directory.mkdir()
            if request['op'] == 'cache_create' or request['cache_policy'] != 'R0':
                request['cache_binding_sha256'] = binding
            save(directory/'request.json', request)
            gate.arm(request)
            if 'application' in request:
                result, events, begin, ended, clock = api['measure_application'](
                    gate, get, (bundle/'control/chat_template.jinja').read_text(encoding='utf-8'), request)
                # The frozen TT10-00 clock helper predates prefix support. Preserve
                # its clock boundaries, replace only the old hard-coded R0 label.
                clock['cache'] = copy.deepcopy(result['prefix_cache_request'])
                clock['cache_binding_sha256'] = binding
                save(directory/'application-timing.json', clock)
            else:
                begin = time.monotonic_ns()
                gate.send(request)
                result = get()
                ended = time.monotonic_ns()
                events = []
            save(directory/'result.json', result)
            if 'application' in request:
                require(clock['answer_source'] == 'MODEL' and clock['eos'] is True and
                        clock['candidate_check']['status'] == clock['final_check']['status'] == 'pass',
                        'ordinary answer failed original content/EOS checks')
            require(result.get('id') == request['id'] and result.get('status') == 'OK' and
                    result.get('type') == ('cache_created' if request['op'] == 'cache_create' else 'result'),
                    'native failed/foreign terminal result')
            require(result.get('state_cleared_before_response') is True and
                    result.get('state_position_after_clear') == -1, 'active state clear not proven')
            require(result['prefix_cache']['binding_sha256'] == binding, 'cache binding changed')
            route = result['bridge']['a12_route']
            require(route.get('execution_kind') == 'FPGA_REAL' and
                    route.get('kernel_build_id') == 0xB3030002, 'terminal backend/build differs')
            require(api['validate_bo'](route) == spans and route['a11_live_weights'] == ready['bridge']['a12_route']['a11_live_weights'],
                    'resident BO/weight inventory changed')
            if request['op'] == 'cache_create':
                entries = result['prefix_cache']['entries']
                require(len(entries) == 1 and entries[0]['tokens'] == spec['prefix_tokens'], 'wrong captured prefix')
                new, decode = len(request['tokens']), 0
            else:
                cache = result['prefix_cache_request']
                hit = request['id'] == 'app_hit'
                require(cache['hit'] is hit and cache['reused_tokens'] == (spec['prefix_tokens'] if hit else 0),
                        'R0/hit path not actually exercised')
                new, decode = cache['new_tokens'], result['decode_calls']
                require(new == len(request['tokens']) - (spec['prefix_tokens'] if hit else 0), 'new-token count differs')
                require(integer(decode, 0, request['max_tokens']-1), 'decode exceeds output bound')
            expected = 72 * ((new+7)//8 + decode)
            require(route['host_verified_completions'] == worker.runs == previous + expected and
                    worker.loads == WEIGHTS and not worker.quarantined and not worker.delivery_cancelled,
                    'actual permission/completion/residency differs')
            previous = worker.runs
            gate.complete()
            # Save exact ordinary result, not full-position/trace bytes. Preserve failures before any comparison.
            save(directory/'actual-work.json', dict(new_prefill_tokens=new, decode_calls=decode,
                 request_calls=expected, cumulative_calls=previous, hardware_global_count=None))
            save(directory/'client-timing.json', dict(begin_monotonic_ns=begin, end_monotonic_ns=ended,
                 result_wall_ms=(ended-begin)/1e6, token_events=events))
            observer.checkpoint('AFTER_RESULT_' + request['id'])
            if request['id'] == 'app_R0':
                reference = comparison_view(result)
            elif request['id'] == 'app_hit':
                save(path/'ordinary-pair-comparison.json', ordinary_comparison(reference, result))
            owner.platform.emit('CASE_FINISHED', case_id=request['id'], real=True,
                                permission_runs=worker.runs, weight_loads=worker.loads)
            last = result
        observer.checkpoint('BEFORE_NORMAL_CLOSE')
        require(worker.close(timeout=15) and worker.closed and worker.process.returncode == 0,
                'normal PL worker exit not proven; retain owner')
        save(path/'exit.json', dict(exit_code=0, permission_runs=worker.runs, weight_loads=worker.loads))
        save(path/'resource-probe-summary.json', dict(status='ORDINARY_PAIR_COMPLETE_PENDING_INDEPENDENT_PLATFORM_RESTORE',
             actual_requests=list(IDS), actual_calls=worker.runs, sampled_minimum_kib=observer.minimum,
             observation_rows=observer.rows, observation_bytes=observer.bytes, continuous_peak_memory=None,
             capture_restore_internal_peak_memory=None, heavy_diagnostics=False, full_numeric_acceptance='NOT_PERFORMED',
             final_performance_acceptance='NOT_PERFORMED', platform_restore='PENDING_MANAGER_RELEASE_GATES',
             scope='EXPLORATORY_ORDINARY_PATH_ONLY'))
        return last
    except BaseException as exc:
        owner.platform.health_schedule.blocked = True
        if observer:
            observer.latch(exc)
        save(path/'PROBE_FAILURE.json', dict(status='FAIL_RETAIN_OWNER', original_failure=type(exc).__name__+': '+str(exc),
             resource_failure=observer.reason if observer else None, retry=False, forced_close=False,
             hardware_operations_by_case_adapter=0, original_records_preserved=True))
        raise
    finally:
        if observer:
            observer.close()
