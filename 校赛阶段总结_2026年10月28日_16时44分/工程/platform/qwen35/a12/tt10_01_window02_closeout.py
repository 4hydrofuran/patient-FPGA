"""Preserve the failed v2 experiment, real closeout proof, and unexecuted v3 proposal."""
import base64,datetime,hashlib,json
from pathlib import Path
from tt10_01_common import ROOT,OUT,FROZEN,sha,save
from tt10_01_numeric import same_result
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def text(p,value):
    with Path(p).open('x',encoding='utf-8') as f:f.write(value)
def main():
    window=OUT/'window-20261025-v2';e=window/'execution-01';r=e/'readback-01';future=OUT/'window-20261025-v3'
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    result=j(r/'run-v1/result.json');exit_=j(r/'manager-exit.json');post=j(e/'independent-postcheck-01/stdout.txt')
    assert result['status']=='FAIL_CPU_STAGE_NORMAL_FINALIZED' and result['compute_pass'] is False
    assert exit_['exit_code']==1 and result['worker_exit_code']==0 and result['new_PL_calls']==0
    assert post['active_lease'] is None and all(not x['matching_rows'] for x in post['canonical_locks'].values())
    assert post['release_scan']['scan_complete'] and not post['release_scan']['device_holders'] and not post['release_scan']['device_mappings']
    assert post['gdm']['exit_code']==0 and post['independent_postexit_kernel_gate']['allowed']
    assert post['window_archive']['value']['window']=='a12-tt10-01-20261025-v2'
    data=j(e/'provenance-01/stdout.txt');dest=e/'staged-provenance';dest.mkdir()
    for name,item in data['files'].items():
        raw=base64.b64decode(item['base64'],validate=True)
        assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    assert sha(dest/'manifest.json')==j(dest/'stage-receipt.json')['manifest_sha256']
    old=FROZEN/'cpu02/readback-v1/run-v1/s1/diag_exact';new=r/'run-v1/s1/diag_exact'
    a=j(old/'result.json');b=j(new/'result.json');strict=same_result(a,b)
    assert set(strict['differences'])=={'last_prompt_logits_sha256','state_fingerprint'}
    rows={}
    assert {p.name for p in (old/'diag').iterdir()}=={p.name for p in (new/'diag').iterdir()}
    for p in sorted((old/'diag').iterdir()):
        other=new/'diag'/p.name;assert p.stat().st_size==other.stat().st_size and sha(p)==sha(other)
        rows[p.name]=dict(bytes=p.stat().st_size,reference_sha256=sha(p),actual_sha256=sha(other))
    assert len(rows)==444
    save(e/'LEGACY_FAILURE_DIAGNOSIS.json',dict(original_gate='FAILED_PRESERVED',strict_result=strict,
        reference_result_sha256=sha(old/'result.json'),actual_result_sha256=sha(new/'result.json'),raw_files=rows,
        prefill_state_bytes=(old/'diag/hybrid-state.bin').stat().st_size,terminal_fingerprint_bytes=a['state_fingerprint']['bytes'],
        historical_terminal_SHA='NOT_AVAILABLE_NOT_DERIVABLE_FROM_PREFILL_STATE',numeric_tolerance_used=False,
        interpretation='Missing additive digest fields in old schema; all original raw files exactly equal. No original result is promoted.'))
    events=[json.loads(line) for line in (r/'run-v1/s2/finalization-events.jsonl').read_text(encoding='utf-8').splitlines()]
    scans=[x for x in events if x['event']=='FULL_PROCESS_OBSERVATION']
    assert len(scans)==2 and scans[-1]['scan']['scan_complete']
    prepared=j(future/'PREPARED.json')
    summary=dict(status='FAILED_V2_CPU_LEGACY_SCHEMA_NORMAL_FINALIZED_V3_PC_PREPARED',updated_beijing=now,
        task01_complete=False,window_id='a12-tt10-01-20261025-v2',boot_id=post['boot_id'],kernel=post['kernel'],
        authorization='AUTHORIZATION.json',fresh_gates='PASS',baseline='COMPUTE_BASELINE_REVIEW.json',
        initial_resources=j(e/'preflight-03/stdout.txt')['resource_review'],
        manager_pid=4112,manager_exit_code=1,CPU_worker_pid=4211,CPU_worker_exit_code=0,
        original_failure='AssertionError: old result lacks new logits SHA and terminal fingerprint SHA fields',
        original_result_status=result['status'],compute_pass=False,original_failure_promoted=False,
        real_board_CPU_failure_close=dict(status='PASS_THIS_FAILURE_PATH_ONLY',cooperative_signal='SIGUSR1',stdin_shutdown=True,
            forced_kill=False,compute_latch_reset=False,lease_archived=True,archive=post['window_archive']['path'],
            lease_sha256=post['window_archive']['sha256'],full_scan_attempts=2,first_incomplete_scan_retained=True,
            independent_full_scan_complete=True,locks_unheld=True,active_lease=False,GDM='active',default_overlay='applied',ZOCL='absent',
            independent_kernel_gate_allowed=True),
        preserved_readback=dict(files=len(j(e/'READBACK_FILES.json')['files']),archive_bytes=j(e/'READBACK_FILES.json')['archive_bytes'],
            archive_sha256=j(e/'READBACK_FILES.json')['archive_sha256'],all_444_actual_raw_files_local=True,remote_originals_retained=True),
        retrospective_legacy_review=dict(raw_files_equal=444,old_present_fields_equal=True,historical_terminal_SHA='NOT_AVAILABLE',
            original_gate_still_failed=True,PC_bridge_checks=14,models_rerun=0),
        new_PL_calls=0,PL_stage='NOT_REACHED',ordinary_application_R0_hit='NOT_REACHED',TTFT_board_s=None,
        original_CMA_failure_point_reached=False,TTFT_le_10s='NOT_VERIFIED',v3=prepared,
        authentication='USER_AUTHORIZED_SESSION_MEMORY_ONLY_NO_GUI_NO_SECRET_PERSISTENCE',
        DeepSeek_used=False,actual_model_settings='unknown')
    save(e/'SUMMARY.json',summary)
    report='''# 20261025-v2：CPU旧格式比较失败，关闭与独立后检通过

用户明确授权按v2计划先检查再执行。此前两次GUI认证失败payload_sent=false、板端脚本未发送；后续按用户指示改为本会话内存认证，SSH/sudo已实际成功，不再弹窗。未把凭据写入文件、argv或环境变量，未取消SSH服务器认证或固定主机密钥校验。

## 实际执行与通过项

新鲜基线/资源/命名空间及实际双锁探测通过，boot1d0499ab-f1f9-438c-969a-3e701a0d806f、6.8.12-a10irq2；完整内核原始字节SHA e6c899a5780c7c6c6549ff11fa8940654665ba699e4c5e85c088fbb5f401069e与前次已审查记录完全相同。已知启动限制保持OPEN，新增诊断不豁免。初次MemAvailable=3246400 KiB、CmaFree=782832 KiB；执行入口再次检查3262064/779456 KiB，均通过原门槛。协调锁、部署锁和设备规范锁均真实非阻塞取得并释放；随后新管理器建立唯一新租约。

只执行这一个v2窗口。管理器4112/CPU worker4211已在板上运行source-04原生程序（SHA115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab）。CPU第一个diag_exact产生正常OK结果，随后旧结果格式严格比较断言失败，未进入warm_prefix和实际PL阶段。原管理器exit1、外层驱动exit2保持失败；run-v1/result.json为FAIL_CPU_STAGE_NORMAL_FINALIZED，compute_pass=false。

CPU关闭通道在真实板上完成已登记身份/FD/maps复核、合作SIGUSR1与stdin shutdown、worker正常exit0、独立关闭健康观察、默认平台/GDM复核及租约归档。计算失败锁存和最后计算成功时间未重置，没有强杀、重启或PL操作。关闭第一次完整扫描因PID1的FD/进程集合变化不完整，原记录保留；按原有有界观测规则第二次扫描完整通过，没有把不完整扫描当PASS。管理器自然exit1保留失败。

额外独立SSH只读后检exit0，确认无活动租约、双规范锁无持有者、完整FD/VMA扫描通过、内核连续性允许、默认overlay applied、GDM active、ZOCL absent。此处通过的是本次CPU故障关闭/释放路径，不是TT10-01计算BOARD验收。

## 失败原因与严格证据

本次444个诊断原始文件与TT10-00 CPU旧对照文件名、长度、SHA全部相同，包括全部投影、logits和prefill hybrid-state.bin。旧结果没有last_prompt_logits_sha256，旧state_fingerprint只有bytes/FNV64；新版新增SHA字段，通用严格same_result因此按缺项拒绝。没有数值容差，也没有改写这个失败。

旧末次prompt logits SHA可从旧logits-prefill-8.f32独立重算；旧终态指纹是decode后的20325212字节，prefill hybrid-state.bin为20312900字节，不能拿prefill字节冒充旧终态或填造旧终态SHA。缺失项明确NOT_AVAILABLE。LEGACY_FAILURE_DIAGNOSIS.json逐件保留444个参考/实测哈希及严格比较差异。

原始回读40630741字节，SHA f3fcc36102a67da2e29ad9354e23e197eeda02ad3dc847407e09442b19f9dd15，473个文件独占解包并校验，包含全部已执行诊断原件及关闭/权限/健康记录；板端原件也保留。原stage preflight、manifest、stage receipt、归档租约另按base64/长度/SHA完整取回，未从候选数据补造旧参考。

## 后续修订，只在电脑端准备

独立v3包window-20261025-v3/bundle-v4已准备，未部署、未执行。旧格式桥接只核对旧参考确实存在的全部必需字段、原终态bytes/FNV64及全部444原始文件，并从旧raw独立推导末次prompt logits SHA。旧终态SHA仍标记无法核验，不追认；新R0/hit完整SHA/状态比较函数原字节保持不变，缺项/不一致仍拒绝。原生程序、管理器关闭通道、数学/ABI、6请求、资源门槛与5000硬上限/4752最坏预算不变。只新增桥接模块、修改legacy分支与新window ID；legacy-case.patch可审查。

以本次保存的真实ARM原件及字段损坏/缺项负例完成14项PC检查，v3隔离导入、默认PLAN_ONLY及清单检查通过；模型运行0，source-03未重跑。它是事后兼容层修订，不把v2原断言或计算状态改记PASS。v2为已消费窗口，按其计划“不能因退出1自动重跑”；若继续，需另行明确授权这一具体v3独立窗口并重新检查现场。

## 未通过或尚未执行

PL阶段、普通应用R0/hit、70/107token诊断下的实际CMA余量及真实少算/TTFT均未执行到，不能宣称原CMA问题实板解决。旧终态SHA历史证据缺口保留；V07/V08质量拒绝与教师审核PENDING保持。TT10-01仍未完成，新增PL调用0，实板应用TTFT=null，≤10秒未验收，TT10-02未开始、A12第11步PENDING。DeepSeek未参与调试或证据验收，实际模型设置unknown。
'''
    text(e/'REPORT.md',report)
    shared=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']
    backup=e/'shared-before';backup.mkdir();receipts={}
    for name in shared:
        raw=(ROOT/name).read_bytes();p=backup/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        receipts[name]=dict(before_sha256=hashlib.sha256(raw).hexdigest())
    status=j(ROOT/shared[0]);key='a12_ttft10_01_in_progress_20261025';other={k:v for k,v in status.items() if k!=key};s=status[key]
    s.update(status=summary['status'],updated_beijing=now,report='evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v2/execution-01/REPORT.md')
    s['window02_board_execution']=summary
    s['window03_prepared']=prepared
    s['BOARD'].update(status='V2_FAILED_CPU_LEGACY_SCHEMA_CLOSED_NO_PL',reason=summary['original_failure'],actual_PL_calls=0,TTFT_app_s=None,
        manager_pid=None,cpu_worker_pid=None,last_manager_pid=4112,last_manager_exit_code=1,last_CPU_worker_pid=4211,last_CPU_worker_exit_code=0,
        lease_retained=False,lease_archived=True,normal_release_and_GDM_restore='PASS_V2_CPU_FAILURE_CLOSE_AND_INDEPENDENT_POSTCHECK',
        latest_compute_authorization='V2_USED_ONCE_V3_NOT_AUTHORIZED',current_boot_id=post['boot_id'],current_kernel=post['kernel'])
    s['source04'].update(BOARD='PARTIAL_CPU_DIAG_EXECUTED_LEGACY_SCHEMA_GATE_FAILED_NO_PL',deployed=True,
        deployed_window='a12-tt10-01-20261025-v2',BOARD_native_sha256='115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab')
    s['cpu_close_pc']['real_board_validation_window02']=summary['real_board_CPU_failure_close']
    s['next']=['Explicit scoped v3 authorization after reviewing legacy bridge limitation/patch',
        'Fresh baseline/resources/namespace/locks, then one independent v3 window; never replay consumed v2',
        'PL numerical/R0-hit/CMA/timing and TT10-01 completion remain unverified']
    assert other=={k:v for k,v in status.items() if k!=key}
    assert sha(ROOT/shared[0])==receipts[shared[0]]['before_sha256']
    (ROOT/shared[0]).write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paragraph='''## 2026-10-25 TT10-01 v2 CPU旧格式断言失败，实板CPU关闭及独立后检通过

用户授权v2执行；新鲜基线/资源/真实双锁探测通过，唯一新窗口已消费。source-04 CPU首个diag_exact结果OK，444原始文件与旧对照全同；旧结果缺新增logits SHA和终态SHA，严格same_result拒绝，原失败保留。CPU worker合作关闭exit0，manager自然exit1、外层exit2；计算锁存不重置，租约归档。完整扫描先因进程变化不完整、后按原有有界规则完整通过，额外独立后检证实双锁空/无活动租约/默认平台与GDM正常。没有PL、重启或强杀。

旧终态SHA没有原始终态字节，不能从prefill状态补造；缺口保持NOT_AVAILABLE。独立v3旧格式桥接14项PC检查通过，旧必需字段/FNV与444原件仍严格比对，新R0/hit完整SHA比较原样保留。v3包未部署/执行，须另行授权并新鲜检查；不能重跑已消费v2。PL/CMA后续点、普通应用R0-hit和TTFT未执行到，TT10-01未完成、新增PL=0、实板TTFT=null、≤10秒未验收。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v2/execution-01/REPORT.md`，后续具体计划 `evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v3/PLAN.md`。本轮无DeepSeek调试/验收委派，模型设置unknown；原PC通过/失败与A13条目保留。认证按用户指示仅用会话内存自动传递，不保存密码或修改SSH服务器认证。

'''
    for name in shared[1:]:
        p=ROOT/name;assert sha(p)==receipts[name]['before_sha256'];oldtext=p.read_text(encoding='utf-8');p.write_text(paragraph+oldtext,encoding='utf-8')
    for name in shared:receipts[name]['after_sha256']=sha(ROOT/name)
    save(e/'SHARED_STATUS_RECEIPT.json',dict(files=receipts,other_project_status_entries_unchanged=True))
    text(ROOT/'docs/handoffs/A12_TT10_01_WINDOW02_FAILURE_AND_WINDOW03_20261025.md',report)
    print(json.dumps(dict(status=summary['status'],new_PL_calls=0,TTFT_board_s=None,report=str(e/'REPORT.md'))))
if __name__=='__main__':main()
