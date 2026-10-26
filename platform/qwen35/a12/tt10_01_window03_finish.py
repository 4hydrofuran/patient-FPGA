"""One local extraction, strict audit, and evidence summary after the authorized v3 window."""
import argparse
import ast
import base64
import datetime
import json
import traceback
from pathlib import Path
from tt10_01_common import ROOT, OUT, sha, save

W = OUT / 'window-20261025-v3'
E = W / 'execution-01'


def j(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def extract(parked=False):
    source = (ROOT / 'platform/qwen35/a12/tt10_01_window02_extract.py').read_text(encoding='utf-8')
    source = source.replace('tt10-01-v1/window-20261025-v2', 'tt10-01-v1/window-20261025-v3')
    # The source uses OUT relative paths.
    source = source.replace("OUT/'window-20261025-v2/execution-01'", "OUT/'window-20261025-v3/execution-01'")
    if parked:
        source = source.replace('readback-01','parked-extracted-01').replace('READBACK_FILES.json','PARKED_READBACK_FILES.json')
        source = source.replace('board-01/stdout.txt','parked-readback-01/stdout.txt')
    ns = {'__name__':'v3_exact_readback_extractor'}
    exec(compile(source, 'v3_exact_readback_extractor', 'exec'), ns)
    ns['main']()


def strict_success_audit():
    source = (ROOT / 'platform/qwen35/a12/tt10_01_analyze.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    body = '\n'.join(source.splitlines()[node.lineno-1:node.end_lineno]) + '\n'
    original = "directory,files=extract();run=directory/'run-v1';bundle=OUT/'candidate/bundle-v2'"
    assert body.count(original) == 1
    body = body.replace(original, "directory=E/'readback-01';files=j(E/'READBACK_FILES.json')['files'];run=directory/'run-v1';bundle=W/'bundle-v4'")
    original = "numbers[side+'_legacy_R0']=compare_cases(old,root/'diag_exact')"
    assert body.count(original) == 1
    body = body.replace(original, "numbers[side+'_legacy_R0']=compare_legacy_case(old,root/'diag_exact');assert numbers[side+'_legacy_R0']['historical_comparison_pass']")
    body = body.replace("save(OUT/", "save(E/")
    body = body.replace("j(OUT/'PACKAGE-02.json')['remote']", "'/var/lib/kv260-a12/tt10-01-20261025-v3'")
    body = body.replace("(OUT/'readback-v1.tar.gz')", "(E/'readback-01.tar.gz')")
    header = '''from pathlib import Path
import json
from tt10_01_common import ROOT,OUT,FROZEN,j,save,sha
from tt10_01_numeric import same_result
from tt10_01_legacy_compare import compare_legacy_case
from cpu01_numeric import compare_cases
from cpu01_profile import audit_profile
from cpu01b_analyze import accounting
'''
    derived = header + body
    with (E / 'strict_success_audit.py').open('x', encoding='utf-8') as f:
        f.write(derived)
    ns = {'__name__':'v3_strict_independent_audit', 'E':E, 'W':W}
    exec(compile(derived, 'v3_strict_independent_audit', 'exec'), ns)
    ns['main']()


def publish_local_report(summary):
    """Generate the local handoff and merge one status entry; no external publication."""
    raw = E / summary.get('local_readback','readback-01')
    errors = (raw / 'manager.stderr.txt').read_text(encoding='utf-8') if (raw / 'manager.stderr.txt').exists() else ''
    failure = summary['result'].get('original_failure') if summary['result'] else 'Manager result unavailable'
    lines = [
        '# TT10-01 v3 独立板测实际结果（2026-10-25）', '',
        '用户授权“现在按照精简后流程执行实板验证”，仅执行本次唯一v3窗口。原v2失败及所有原件保持。', '',
        f"实际状态：{summary['status']}。TT10-01 complete={summary['task01_complete']}；实际PL调用={summary['actual_PL_calls']}；独立恢复后检={summary['independent_normal_restore']}。",
        f"原始管理器结果：{json.dumps(summary['result'], ensure_ascii=False)}。", '',
        '新鲜身份/boot、内核基线、资源和真实锁探测通过后才执行。主机密钥仍固定；认证仅在用户授权的会话内存处理。',
        '原生source-04、公共数学/ABI、关闭通道、各后端六项请求和严格新R0/hit比较保持不变；source-03及已通过模型PC工作未重做。', '',
        '## 实际完成请求', '',
    ]
    for side, cases in summary['completed_cases'].items():
        lines.append(f"- {side}：" + (', '.join(f"{k}={v['status']}" for k,v in cases.items()) or '无完成结果'))
    lines += ['', '## 普通应用时钟', '']
    for row in summary['ordinary_application_timings']:
        lines.append(f"- {row['backend']}/{row['request']}：应用TTFT={row['TTFT_app_s']:.6f}秒，完整响应={row['complete_app_s']:.6f}秒，cache={json.dumps(row['cache'],ensure_ascii=False)}。")
    if not summary['ordinary_application_timings']:
        lines.append('尚未取得普通应用实板时钟，TTFT=null，≤10秒未验收。')
    lines += ['', '## 证据与限制', '',
        f"精确回读文件数={summary['readback_files']}，原始压缩包SHA256={summary['raw_archive_sha256']}。板端原件保留。",
        '实际stage manifest/preflight/receipt、原始结果及资源/权限记录统一回传、校验和解包；缺项保持未证明。',
        '旧格式桥接明确保留历史终态SHA不可用的限制；不补造旧SHA，不放宽新R0/hit比较，不追认v2失败。',
        '本窗口单次、无自动重跑；无重启/刷写/强杀。是否恢复成功以独立后检记录为准。',
        '应用性能为每后端R0/hit各一次；≤10秒最终验收和100请求验收不能由这一窗口替代。教师审核PENDING、V07/V08拒绝及A13保留。',
        f"严格完整审查异常：{summary['strict_audit_failure']}。原始失败：{failure}。", '',
        '## 管理器原始错误末尾', '', '```text', errors[-6000:], '```', '',
        'DeepSeek未参与调试或证据验收；实际会话模型设置unknown。', '']
    report = '\n'.join(lines)
    with (E / 'REPORT.md').open('x', encoding='utf-8') as f:f.write(report)
    handoff = ROOT / 'docs/handoffs/A12_TT10_01_WINDOW03_BOARD_20261025.md'
    with handoff.open('x', encoding='utf-8') as f:f.write(report)
    shared = ['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md',
              'docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']
    receipts = {}
    for name in shared:
        p = ROOT / name; data = p.read_bytes(); dest = E / 'shared-before' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as f:f.write(data)
        receipts[name] = dict(before_sha256=sha(p))
    status = j(ROOT / shared[0]); key = 'a12_ttft10_01_in_progress_20261025'
    others = {k:v for k,v in status.items() if k != key}
    entry = status[key]
    entry.update(status=summary['status'],updated_beijing=summary['updated_beijing'],
        report=str((E / 'REPORT.md').relative_to(ROOT)).replace('\\','/'),
        window03_board_execution=summary,task01_complete=summary['task01_complete'])
    entry['BOARD'].update(status=summary['status'],actual_PL_calls=summary['actual_PL_calls'],
        TTFT_app_s=summary['TTFT_board_s'],normal_release_and_GDM_restore=summary['independent_normal_restore'],
        latest_compute_authorization='V3_USED_ONCE_NO_AUTOMATIC_RETRY',
        reason=summary['result']['status'] if summary['result'] else 'No manager result',
        last_manager_pid=summary['manager'].get('pid') if summary['manager'] else None,
        last_manager_exit_code=summary['manager'].get('exit_code') if summary['manager'] else None,
        lease_archived=bool(summary['independent_normal_restore']=='PASS'),
        lease_retained=bool(summary['independent_normal_restore']!='PASS'))
    identity = raw / 'run-v1/s1/identity.json'
    cpu_exit = raw / 'run-v1/s1/exit.json'
    if identity.exists():entry['BOARD']['last_CPU_worker_pid'] = j(identity)['pid']
    if cpu_exit.exists():entry['BOARD']['last_CPU_worker_exit_code'] = j(cpu_exit)['exit_code']
    entry['source04'].update(BOARD=summary['status'],deployed=True,deployed_window=summary['window_id'])
    if summary['independent_normal_restore']=='PASS':
        entry['BOARD'].update(manager_pid=None,cpu_worker_pid=None)
    entry['next'] = ['Inspect actual v3 result and retained failure before any new compute window',
        'TTFT<=10s final acceptance and teacher review remain separate and unverified']
    assert others == {k:v for k,v in status.items() if k != key}
    p = ROOT / shared[0]; assert sha(p) == receipts[shared[0]]['before_sha256']
    p.write_text(json.dumps(status, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    paragraph = '\n'.join(lines[:7]) + '\n\n详见 `docs/handoffs/A12_TT10_01_WINDOW03_BOARD_20261025.md` 与对应 execution-01/REPORT.md。全部失败保留、无自动重跑；普通应用数值/计时未完成的项保持未测，≤10秒最终验收仍未证明。\n\n'
    for name in shared[1:]:
        p = ROOT / name; assert sha(p) == receipts[name]['before_sha256']
        p.write_text(paragraph + p.read_text(encoding='utf-8'), encoding='utf-8')
    for name in shared:receipts[name]['after_sha256'] = sha(ROOT / name)
    save(E / 'SHARED_STATUS_RECEIPT.json',dict(files=receipts,other_project_status_entries_unchanged=True))


def parked_main():
    receipt=j(E/'parked-readback-01/receipt.json')
    assert receipt['exit_code']==0 and receipt['payload_sent']
    assert receipt['script_sha256']==sha(ROOT/'platform/qwen35/a12/tt10_01_window03_parked_readback.py')
    extract(parked=True)
    root=E/'parked-extracted-01';run=root/'run-v1';snapshot=j(root/'PARKED_SNAPSHOT.json')
    inventory=snapshot['inventory'];stable=not snapshot['changed_after_inventory'] and all(x['stable_while_hashed'] for x in inventory.values())
    assert stable and snapshot['owner_lease_unchanged']
    for name,item in inventory.items():
        p=root/name
        if p.is_file():assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],name
    expected={x['path']:x for x in j(W/'bundle-v4/manifest.json')['files']}
    actual={x['path']:x for x in j(root/'manifest.json')['files']}
    assert expected.keys()==actual.keys() and all(expected[k]==actual[k] for k in expected if k!='control/preflight.json')
    assert sha(root/'manifest.json')==j(root/'stage-receipt.json')['manifest_sha256']
    assert sha(root/'control/preflight.json')==actual['control/preflight.json']['sha256']
    from tt10_01_legacy_compare import compare_legacy_case
    from tt10_01_numeric import same_result
    numbers={};cases={};timings=[]
    from tt10_01_common import FROZEN
    for side in ('s1','s2'):
        d=run/side;cases[side]={}
        numbers[side+'_legacy']=compare_legacy_case(FROZEN/'cpu02/readback-v1/run-v1'/side/'diag_exact',d/'diag_exact')
        assert numbers[side+'_legacy']['historical_comparison_pass']
        gate=j(d/'diag_hit/prefix-numerical-gate.json')
        assert gate['result']['equal'] and gate['all_bytes']['equal']
        assert gate['all_bytes']['reference_projection_sha256']==gate['all_bytes']['restored_projection_sha256']
        assert gate['all_bytes']['reference_logits_sha256']==gate['all_bytes']['restored_logits_sha256']
        numbers[side+'_prefix']=gate
        for request in j(W/'bundle-v4/control/requests.json'):
            p=d/request['id']
            if (p/'result.json').is_file():
                value=j(p/'result.json');cases[side][request['id']]={k:value.get(k) for k in ('type','status','eos','decode_calls')}
            if (p/'application-timing.json').is_file():
                a=j(p/'application-timing.json');assert a['eos'] and a['answer_source']=='MODEL'
                assert a['candidate_check']['status']==a['final_check']['status']=='pass'
                timings.append(dict(backend=side,request=request['id'],TTFT_app_s=a['TTFT_app_ms']/1000,complete_app_s=a['complete_app_ms']/1000,cache=a['cache'],eos=a['eos']))
    assert numbers['s1_prefix']==numbers['s2_prefix']
    for name in ('diag_exact','diag_full_R0','diag_hit'):
        assert same_result(j(run/'s1'/name/'result.json'),j(run/'s2'/name/'result.json'))['equal']
    assert same_result(j(run/'s1/app_R0/result.json'),j(run/'s1/app_hit/result.json'))['equal']
    counts={};faults=[]
    for line in (run/'s2/worker/events.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['event']=='PERMISSION':
            assert row['allow'] is True
            phase=row['request']['phase'];counts[phase]=counts.get(phase,0)+1
        elif row['event']=='PERMISSION_FAULT_RETAIN_OWNER':faults.append(row)
    calls=counts.get('submit',0)
    work=sum(j(run/'s2'/name/'actual-work.json')['request_actual_calls'] for name in ('diag_exact','warm_prefix','diag_full_R0','diag_hit'))
    assert calls==work==j(run/'s2/diag_hit/result.json')['bridge']['a12_route']['host_verified_completions']
    refusals=[j(p) for p in run.glob('cpu-close-health-refusal-*.json')]
    assert refusals and refusals[-1]['memory_kib']['CmaFree']<refusals[-1]['required_CmaFree_kib']
    save(E/'NUMERICAL_BOARD_PARTIAL.json',dict(status='PASS_EXECUTED_CPU_PL_PREFIX_GATES_ONLY',comparisons=numbers,
        CPU_ordinary_R0_hit='PASS',PL_ordinary_R0_hit='NOT_COMPLETED',historical_terminal_SHA='NOT_AVAILABLE',actual_PL_calls=calls))
    save(E/'PARKED_RESOURCE_FAILURE.json',dict(status='FAILED_CMA_ORIGINAL_GATE_RETAINED',samples=refusals,
        permission_counts=counts,permission_faults=faults,lease=snapshot['lease'],
        lease_sha256=snapshot['lease_sha256'],processes=snapshot['processes'],normal_exit_proven=False,
        original_inventory_stable=True,raw_inventory_files=len(inventory)))
    summary=dict(status='V3_FAILED_CMA_AFTER_PREFIX_GATES_PL_OWNER_RETAINED',
        updated_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        task01_complete=False,window_id='a12-tt10-01-20261025-v3',local_readback='parked-extracted-01',
        transport_exit=None,manager=dict(pid=snapshot['lease']['pid'],exit_code=None),
        result=dict(status='ISOLATED_PL_FAILURE',original_failure=snapshot['isolated']['reason'],
            root_refusal='CmaFree below unchanged 98304 KiB gate',
            observed_CmaFree_kib=refusals[-1]['memory_kib']['CmaFree'],required_CmaFree_kib=98304,
            worker_exit_code=None,lease_retained=True),
        completed_cases=cases,actual_PL_calls=calls,independent_normal_restore='NOT_PERFORMED_OWNER_RETAINED',
        ordinary_application_timings=timings,TTFT_board_s=None,PL_TTFT_app_s=None,
        CPU_TTFT_app_s={x['request']:x['TTFT_app_s'] for x in timings if x['backend']=='s1'},
        TTFT_le_10s='NOT_VERIFIED',strict_audit_failure='Full audit not eligible: PL application pair and normal restore missing',
        readback_files=len(j(E/'PARKED_READBACK_FILES.json')['files']),raw_archive_sha256=j(E/'PARKED_READBACK_FILES.json')['archive_sha256'],
        source03_repeated=False,model_settings='unknown',DeepSeek_used=False,original_failures_preserved=True,automatic_retry=False,
        canonical_locks_retained=True,PL_module_and_overlay_retained=True,read_only_capture_complete=True)
    save(E/'SUMMARY.json',summary);publish_local_report(summary)
    print(json.dumps(summary,ensure_ascii=False))
    return 2


def main():
    receipt = j(E / 'board-01/receipt.json')
    assert receipt['payload_sent'] and receipt['script_sha256'] == sha(E / 'execute_bound.py')
    extract()
    r = E / 'readback-01'
    result = j(r / 'run-v1/result.json') if (r / 'run-v1/result.json').exists() else None
    manager = j(r / 'manager-exit.json') if (r / 'manager-exit.json').exists() else None
    post = j(r / 'run-v1/outer-independent-postcheck.json') if (r / 'run-v1/outer-independent-postcheck.json').exists() else None
    provenance = j(r / 'run-v1/outer-provenance.json')
    dest = E / 'staged-provenance'
    dest.mkdir()
    for name, item in provenance['files'].items():
        assert Path(name).name == name
        data = base64.b64decode(item['base64'], validate=True)
        assert len(data) == item['bytes']
        import hashlib
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        with (dest / name).open('xb') as f:
            f.write(data)
    assert sha(dest / 'actual-manifest.json') == j(dest / 'actual-stage-receipt.json')['manifest_sha256']
    expected = {x['path']:x for x in j(W / 'bundle-v4/manifest.json')['files']}
    actual = {x['path']:x for x in j(dest / 'actual-manifest.json')['files']}
    assert actual.keys() == expected.keys()
    assert all(actual[k] == expected[k] for k in actual if k != 'control/preflight.json')
    assert sha(dest / 'actual-preflight.json') == actual['control/preflight.json']['sha256']
    close_pass = bool(post and post['active_lease'] is None
        and all(x and not x['matching_rows'] for x in post['canonical_locks'].values())
        and post.get('release_scan',{}).get('scan_complete')
        and not post['release_scan']['device_holders'] and not post['release_scan']['device_mappings']
        and post['gdm']['exit_code'] == 0 and post['gdm']['stdout'].strip() == 'active'
        and post['overlays'] == {'k26-starter-kits_image_1':'applied\n'}
        and not post['module_present'] and post['manager_kernel_all_allowed']
        and post['independent_postexit_kernel_gate']['allowed'] and post['window_archive'])
    cases = {}; timings = []; calls = 0
    for side in ('s1','s2'):
        cases[side] = {}
        for request in j(W / 'bundle-v4/control/requests.json'):
            path = r / 'run-v1' / side / request['id']
            if (path / 'result.json').exists():
                value = j(path / 'result.json')
                cases[side][request['id']] = {k:value.get(k) for k in ('status','type','eos','decode_calls')}
                if side == 's2':
                    calls = max(calls,value.get('bridge',{}).get('a12_route',{}).get('host_verified_completions',0))
            if (path / 'application-timing.json').exists():
                clock = j(path / 'application-timing.json')
                timings.append(dict(backend=side,request=request['id'],TTFT_app_s=clock['TTFT_app_ms']/1000,
                    complete_app_s=clock['complete_app_ms']/1000,cache=clock['cache'],eos=clock['eos']))
    audit_error = None; full_pass = False
    if receipt['exit_code'] == 0 and manager and manager['exit_code'] == 0 and close_pass:
        try:
            strict_success_audit()
            full_pass = j(E / 'BOARD_AUDIT.json')['task01_complete'] is True
        except BaseException as exc:
            audit_error = type(exc).__name__ + ': ' + str(exc)
            save(E / 'STRICT_AUDIT_FAILURE.json', dict(error=audit_error,traceback=traceback.format_exc()))
    events = []
    with (E / 'board-01/stdout.txt').open(encoding='utf-8') as stream:
        for line in stream:
            item = json.loads(line)
            if item.get('event') != 'READBACK':events.append(item)
    save(E / 'BOARD_TRANSPORT_EVENTS.json', events)
    summary = dict(status='PASS_TT10_01_WINDOW03_AUDIT' if full_pass else 'V3_INCOMPLETE_OR_FAILED_PRESERVED',
        updated_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        task01_complete=full_pass,window_id='a12-tt10-01-20261025-v3',
        transport_exit=receipt['exit_code'],manager=manager,result=result,completed_cases=cases,
        actual_PL_calls=calls,independent_normal_restore='PASS' if close_pass else 'NOT_PROVEN',
        ordinary_application_timings=timings,
        TTFT_board_s={x['backend']+'/'+x['request']:x['TTFT_app_s'] for x in timings} or None,
        TTFT_le_10s='NOT_FINAL_ACCEPTANCE',strict_audit_failure=audit_error,
        readback_files=len(j(E / 'READBACK_FILES.json')['files']),
        raw_archive_sha256=j(E / 'READBACK_FILES.json')['archive_sha256'],
        source03_repeated=False,model_settings='unknown',DeepSeek_used=False,
        original_failures_preserved=True,automatic_retry=False)
    save(E / 'SUMMARY.json', summary)
    publish_local_report(summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if full_pass else 2


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--parked',action='store_true')
    raise SystemExit(parked_main() if parser.parse_args().parked else main())
