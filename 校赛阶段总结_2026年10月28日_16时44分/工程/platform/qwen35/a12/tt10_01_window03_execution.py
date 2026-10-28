"""Prepare/bind one authorized v3 window and collect postcheck/provenance in its readback."""
import argparse
import base64
import datetime
import gzip
import hashlib
import json
from pathlib import Path
from tt10_01_common import ROOT, OUT, sha, save

WINDOW = OUT / 'window-20261025-v3'
EXECUTION = WINDOW / 'execution-01'


def j(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def exclusive(path, data):
    compile(data, str(path), 'exec')
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(data)


def prepare():
    prepared = j(WINDOW / 'PREPARED.json')
    assert sha(WINDOW / 'board_driver_plan.py') == prepared['driver_sha256']
    bundle = WINDOW / prepared['local_bundle']
    assert sha(bundle / 'manifest.json') == prepared['bundle_manifest_sha256']
    for row in j(bundle / 'manifest.json')['files']:
        path = bundle / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    EXECUTION.mkdir(exist_ok=False)
    save(EXECUTION / 'AUTHORIZATION.json', dict(
        user_instruction='现在按照精简后流程执行实板验证',
        recorded_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        window_id=prepared['window_id'], plan_sha256=sha(WINDOW / 'PLAN.md'),
        lean_runbook_sha256=sha(WINDOW / 'LEAN_RUNBOOK.md'),
        bundle_manifest_sha256=prepared['bundle_manifest_sha256'],
        single_window=True, automatic_retry=False, requests_per_backend=6,
        max_runs=5000, max_session_seconds=1800, reboot=False, flash=False,
        raw_evidence_and_failures_retained=True, numerical_thresholds_unchanged=True,
        auth='EXISTING_USER_AUTHORIZED_SESSION_MEMORY_ONLY'))
    source = (OUT / 'window-20261025-v2/execution-01/fresh_preflight.py').read_text(encoding='utf-8')
    assert 'tt10-01-20261025-v2' in source
    exclusive(EXECUTION / 'fresh_preflight.py', source.replace('tt10-01-20261025-v2', 'tt10-01-20261025-v3'))
    print('V3_AUTHORIZED_PREPARED_NO_BOARD_CONTACT')


def bind():
    fresh = j(EXECUTION / 'preflight-01/stdout.txt')
    assert j(EXECUTION / 'preflight-01/receipt.json')['exit_code'] == 0
    assert fresh['probe_status'].startswith('PASS_') and fresh['lock_probe_released']
    assert len(fresh['lock_probe']) == 3 and all(x['exclusive_acquired'] for x in fresh['lock_probe'])
    raw = fresh['kernel_raw'].encode('utf-8')
    assert hashlib.sha256(raw).hexdigest() == fresh['kernel_sha256']
    previous = j(OUT / 'window-20261025-v2/execution-01/independent-postcheck-01/stdout.txt')
    assert raw == previous['kernel_log']['raw'].encode('utf-8'), 'New kernel bytes need explicit review'
    assert fresh['boot_id'] == previous['boot_id']
    save(EXECUTION / 'COMPUTE_BASELINE_REVIEW.json', dict(
        status='EXACT_LAST_INDEPENDENT_POSTCHECK_BYTES', boot_id=fresh['boot_id'],
        kernel_sha256=fresh['kernel_sha256'], raw_bytes=len(raw),
        known_startup_limitations_still_open=True, new_diagnostics=[],
        resource_review=fresh['resource_review'], lock_probe=fresh['lock_probe'],
        thresholds_changed=False, authorization_sha256=sha(EXECUTION / 'AUTHORIZATION.json')))
    # Reuse the reviewed binding structure. Only the window/package and baseline input change.
    source = (ROOT / 'platform/qwen35/a12/tt10_01_window02_bind.py').read_text(encoding='utf-8')
    start = source.index("    code='''") + len("    code='''")
    end = source.index("'''\n    code=", start)
    code = source[start:end].replace('window02', 'window03').replace('tt10-01-20261025-v2', 'tt10-01-20261025-v3')
    driver = WINDOW / 'board_driver_plan.py'
    prepared = j(WINDOW / 'PREPARED.json')
    assert sha(driver) == prepared['driver_sha256']
    code = code.replace('DRIVER_B64', repr(base64.b64encode(gzip.compress(driver.read_bytes())).decode()))
    code = code.replace('DRIVER_SHA', repr(prepared['driver_sha256']))
    code = code.replace('EXPECTED_BOOT', repr(fresh['boot_id'])).replace('EXPECTED_RAW_SHA', repr(fresh['kernel_sha256']))
    post = (ROOT / 'platform/qwen35/a12/tt10_01_window02_postcheck.py').read_text(encoding='utf-8').replace('tt10-01-20261025-v2', 'tt10-01-20261025-v3')
    exclusive(EXECUTION / 'independent_postcheck.py', post)
    collector = '''
# Read-only independent observation and exact provenance join the same run archive.
original_readback=ns['readback']
def collected_readback(root, mode):
    import contextlib,io
    capture=io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            exec(compile(POST_SOURCE,'independent_v3_postcheck','exec'),{'__name__':'__main__'})
        record=json.loads(capture.getvalue())
        ns['save'](root/'run-v1/outer-independent-postcheck.json',record)
    except BaseException as exc:
        ns['save'](root/'run-v1/outer-independent-postcheck-error.json',dict(error=type(exc).__name__+': '+str(exc),captured=capture.getvalue()))
    files={}
    for name,path in [('actual-preflight.json',root/'control/preflight.json'),
                      ('actual-manifest.json',root/'manifest.json'),
                      ('actual-stage-receipt.json',root/'stage-receipt.json'),
                      ('archived-lease.json',Path('/var/lock/kv260-a1/history/a12-tt10-01-20261025-v3/lease.json'))]:
        if path.is_file():
            raw=path.read_bytes()
            files[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
    ns['save'](root/'run-v1/outer-provenance.json',dict(files=files,read_only=True))
    original_readback(root,mode)
ns['readback']=collected_readback
'''.replace('POST_SOURCE', repr(post))
    sentinel = "raise SystemExit(ns['main']())"
    assert code.count(sentinel) == 1
    code = code.replace(sentinel, collector + '\n' + sentinel)
    exclusive(EXECUTION / 'execute_bound.py', code)
    save(EXECUTION / 'EXECUTION_BINDING.json', dict(
        window_id=prepared['window_id'], driver_sha256=sha(driver),
        bundle_manifest_sha256=prepared['bundle_manifest_sha256'],
        wrapper_sha256=sha(EXECUTION / 'execute_bound.py'),
        independent_postcheck_sha256=sha(EXECUTION / 'independent_postcheck.py'),
        compute_baseline_review_sha256=sha(EXECUTION / 'COMPUTE_BASELINE_REVIEW.json'),
        manager_and_requests_unchanged=True, combined_readback_provenance=True,
        single_attempt=True, automatic_retry=False, max_runs=5000))
    print('V3_EXACT_DRIVER_BOUND_WITH_READ_ONLY_COLLECTOR_NO_BOARD_CONTACT')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare','bind'])
    {'prepare':prepare,'bind':bind}[parser.parse_args().action]()
