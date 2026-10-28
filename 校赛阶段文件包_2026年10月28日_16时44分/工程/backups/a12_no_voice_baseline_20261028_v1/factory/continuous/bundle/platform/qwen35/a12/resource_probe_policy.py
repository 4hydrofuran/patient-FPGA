"""A-private ordinary-path probe policy. No device, recovery or diagnostic I/O."""
import copy

MEM_KIB = 1114112
CMA_KIB = 98304
PREFIX_RESERVE_KIB = 192 * 1024
BO_BYTES = 140591104
WEIGHTS = 72
BO_COUNT = 148
HARD_RUNS = 5000
CONTRACT = '83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'
IDS = ('app_R0', 'warm_prefix', 'app_hit')
OFF = ('profile', 'profile_detail', 'diagnostic_report', 'diagnostic_all_layers',
       'dump_state', 'state_fingerprint', 'a12_consumer_trace', 'diagnostic_nodes',
       'tt10_diagnostic', 'compare_logits')
FIELDS = {'id', 'op', 'tokens', 'prompt', 'application', 'max_tokens',
          'prefill_chunk', 'logits_mode', 'cache_policy', 'cache_id',
          'confirmed_prefix', *OFF}


class ProbeBlocked(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise ProbeBlocked(reason)


def integer(value, low=0, high=2**63-1):
    return type(value) is int and low <= value <= high


def admission(memory, *, prefix=False):
    for key in ('MemAvailable', 'CmaFree', 'CmaTotal', 'Cached', 'Dirty', 'Writeback'):
        require(integer(memory.get(key)), 'missing/invalid memory observation: ' + key)
    require(memory['CmaFree'] <= memory['CmaTotal'], 'CMA observation inconsistent')
    require(memory['MemAvailable'] >= MEM_KIB + (PREFIX_RESERVE_KIB if prefix else 0),
            'MemAvailable below unchanged probe/prefix admission')
    require(memory['CmaFree'] >= CMA_KIB, 'CmaFree below unchanged 98304 KiB gate')


def validate_request(request, *, wire=False):
    require(type(request) is dict and not (set(request) - FIELDS), 'unknown probe request field')
    require(request.get('id') in IDS, 'unknown probe request')
    require(request.get('logits_mode') == 'final', 'all-position logits forbidden')
    require(request.get('prefill_chunk') == 256, 'frozen chunk changed')
    for key in OFF:
        require(key not in request or request[key] is False, 'heavy/optional diagnostic forbidden: ' + key)
    require(request.get('cache_policy') in ('R0', 'TT10_REQUIRE_HIT'), 'cache policy changed')
    require(integer(request.get('max_tokens'), 1, 32), 'output limit changed')
    if 'tokens' in request:
        require(type(request['tokens']) is list and 1 <= len(request['tokens']) <= 1024 and
                all(integer(t, 0, 248319) for t in request['tokens']), 'invalid frozen tokens')
    else:
        require(type(request.get('prompt')) is str and request['prompt'], 'native prompt absent')
    warm = request['id'] == 'warm_prefix'
    require(request.get('op') == ('cache_create' if warm else 'generate'), 'operation differs')
    if warm:
        require(request['max_tokens'] == 1 and request.get('confirmed_prefix') is True and
                request.get('cache_id') == 'natural-t4' and request['cache_policy'] == 'R0' and
                'application' not in request, 'warm is not bounded neutral capture')
    else:
        if not wire:
            require(type(request.get('application')) is dict, 'ordinary application context missing')
        require(request['cache_policy'] == ('R0' if request['id'] == 'app_R0' else 'TT10_REQUIRE_HIT'),
                'ordinary R0/hit policy differs')
        if request['id'] == 'app_hit':
            require(request.get('cache_id') == 'natural-t4', 'wrong hit cache')


def validate_plan(requests, spec):
    require([r.get('id') for r in requests] == list(IDS), 'exact R0/warm/hit order required')
    for request in requests:
        validate_request(request)
        require('tokens' in request, 'package lacks frozen tokens')
    r0, warm, hit = requests
    n = spec.get('prefix_tokens')
    require(integer(n, 1, 127) and warm['tokens'] == r0['tokens'][:n], 'prefix tokens differ')
    require(hit['tokens'] == r0['tokens'] and len(hit['tokens']) > n, 'R0/hit tokens differ')
    require(hit['prompt'] == r0['prompt'] and hit['application'] == r0['application'], 'application drift')
    require(r0['max_tokens'] == hit['max_tokens'], 'generation limits differ')
    require(spec.get('request_limit') == 3 and spec.get('max_runs') == HARD_RUNS and
            spec.get('output_token_limit') == 32 and spec.get('prompt_token_limit') == 1024,
            'frozen window caps differ')
    require(spec.get('resource_probe') is True and spec.get('authorization_included') is False,
            'probe package cannot carry compute authorization')
    worst = 0
    for r in requests:
        new = len(r['tokens']) - (n if r['cache_policy'] == 'TT10_REQUIRE_HIT' else 0)
        decode = 0 if r['op'] == 'cache_create' else r['max_tokens'] - 1
        worst += 72 * ((new + 7) // 8 + decode)
    require(worst <= HARD_RUNS and spec.get('calculated_worst_case') == worst, 'submission budget differs')
    return worst


def ordinary_comparison(reference, actual):
    fields = ('status', 'output_tokens', 'text', 'eos', 'decode_calls',
              'last_prompt_logits_fnv64', 'last_prompt_logits_sha256',
              'state_position_before_clear', 'state_position_after_clear',
              'state_cleared_before_response')
    for result in (reference, actual):
        digest = result.get('last_prompt_logits_sha256')
        require(type(digest) is str and len(digest) == 64 and
                all(c in '0123456789abcdef' for c in digest), 'current-source final logits SHA missing')
        require(all(k in result for k in fields), 'ordinary result evidence missing')
    differences = [key for key in fields if reference[key] != actual[key]]
    require(not differences, 'ordinary R0/hit differs: ' + ','.join(differences))
    return dict(equal=True, compared_fields=list(fields), full_intermediate_state='NOT_TESTED',
                scope='ORDINARY_OUTPUT_AND_LAST_PREFILL_LOGITS_ONLY')


def comparison_view(result):
    keys = ('status', 'output_tokens', 'text', 'eos', 'decode_calls',
            'last_prompt_logits_fnv64', 'last_prompt_logits_sha256',
            'state_position_before_clear', 'state_position_after_clear', 'state_cleared_before_response')
    return {key: copy.deepcopy(result[key]) for key in keys}
