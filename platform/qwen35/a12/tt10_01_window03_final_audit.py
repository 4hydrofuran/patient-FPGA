"""Verify archived partial v3 evidence and accurately record its still-owned scene."""
import base64
import hashlib
import json
from tt10_01_common import ROOT, OUT, sha, save


def j(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    e=OUT/'window-20261025-v3/execution-01';r=e/'parked-extracted-01';run=r/'run-v1'
    summary=j(e/'SUMMARY.json');snapshot=j(r/'PARKED_SNAPSHOT.json')
    assert summary['task01_complete'] is False and summary['actual_PL_calls']==2376
    assert summary['PL_TTFT_app_s'] is None and summary['TTFT_board_s'] is None
    assert summary['canonical_locks_retained'] and summary['PL_module_and_overlay_retained']
    files=j(e/'PARKED_READBACK_FILES.json')
    assert sha(e/'parked-extracted-01.tar.gz')==files['archive_sha256']
    for name,item in files['files'].items():
        p=r/name;assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],name
    result=j(run/'s2/diag_hit/result.json');route=result['bridge']['a12_route']
    assert route['host_verified_completions']==2376 and route['weight_load_count']==72
    assert route['owned_bo_charged_bytes']==140591104 and route['a11_explicit_bo_allocations_host_counter']==148
    meta=bytes.fromhex(route['a12_raw_meta_hex']);assert len(meta)==64
    le=lambda i,n:int.from_bytes(meta[i:i+n],'little')
    assert le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==2376
    assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and route['a12_observed_ert_state']==4
    count=0
    for line in (run/'s2/worker/events.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['event']!='PERMISSION':continue
        assert row['allow'] and row['health_observation']['kernel']['allowed']
        health=row['health_observation']['live_health']
        assert health['memory_kib']['CmaFree']>=98304 and health['memory_kib']['MemAvailable']>=1114112
        if row['request']['phase']=='submit':count+=1
    assert count==2376
    for line in (run/'lifecycle.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['event']=='KERNEL_LOG_GATE':assert row['allowed']
    scene=dict(manager=snapshot['processes'][0]['pid'],worker=snapshot['processes'][1]['pid'],
        process_states=[x['state'] for x in snapshot['processes']],
        worker_wchan=snapshot['processes'][1]['wchan'],module_refcount=int(snapshot['module_refcount']),
        overlays=snapshot['overlays'],GDM=snapshot['gdm'].strip(),active_lease_retained=True,
        lease_sha256=snapshot['lease_sha256'],snapshot_finished_monotonic_ns=snapshot['finished_monotonic_ns'],
        normal_exit_proven=False,default_restore_proven=False,
        outer_collector='Existing one-shot SSH collector waits at most its original 2100s; it cannot retry compute or clear ownership')
    save(e/'RETAINED_SCENE.json',scene)
    path=ROOT/'docs/PROJECT_STATUS.json';before=path.read_bytes();status=j(path)
    key='a12_ttft10_01_in_progress_20261025';others={k:v for k,v in status.items() if k!=key}
    backup=e/'project-status-before-scene.json'
    with backup.open('xb') as f:f.write(before)
    status[key]['BOARD'].update(manager_pid=scene['manager'],cpu_worker_pid=None,pl_worker_pid=scene['worker'],
        lease_retained=True,lease_archived=False,current_scene=scene,TTFT_app_s=None)
    status[key]['next']=[
        'No new compute: current v3 manager/PL worker, active lease, locks, test overlay and ZOCL remain retained',
        'Prepare and separately review a maintenance recovery with proven PL drain/exit; CPU-only close does not apply',
        'Investigate diagnostic page-cache contribution to CMA pressure and validate selective fsync/fadvise without deleting evidence or lowering gates',
        'After explicit maintenance/retest scope, execute the missing PL ordinary R0/hit and normal restore; TTFT<=10s remains unverified']
    assert others=={k:v for k,v in status.items() if k!=key}
    assert hashlib.sha256(before).hexdigest()==sha(path)
    path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(e/'STATUS_SCENE_RECEIPT.json',dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=sha(path),other_entries_unchanged=True))
    receipt=j(e/'SHARED_STATUS_RECEIPT.json')
    assert receipt['files']['docs/PROJECT_STATUS.json']['after_sha256']==hashlib.sha256(before).hexdigest()
    for name,item in receipt['files'].items():
        if name!='docs/PROJECT_STATUS.json':assert sha(ROOT/name)==item['after_sha256']
    note='\n## 保留现场补充\n\n已核对：manager=6365、PL worker=7023（pipe_read），活动租约和锁保留；ZOCL refcount=1，测试overlay applied，GDM inactive。尚无正常退出或默认平台恢复证明。已完成2376次PL提交，权限日志与原始64字节meta计数一致；所有获准提交使用原资源门槛。原件清单10078个文件、1249970395字节，采集期间无变化；1019个选择性回传文件均已校验，板端完整原件保留。缓存占用是待核验的CMA压力来源，不能把推测当已定位。现有外层采集器至原2100秒上限结束观察，不会自动重跑、释放租约或操作硬件。\n'
    for p in (e/'REPORT.md',ROOT/'docs/handoffs/A12_TT10_01_WINDOW03_BOARD_20261025.md'):
        with p.open('a',encoding='utf-8') as f:f.write(note)
    audit=dict(status='PASS_INTEGRITY_AND_PARTIAL_EVIDENCE_AUDIT_NOT_FULL_BOARD',
        readback_files=len(files['files']),remote_inventory_files=len(snapshot['inventory']),
        actual_PL_calls=2376,meta_and_permissions_equal=True,all_granted_health_checks_retained=True,
        CPU_PL_prefix_numeric='PASS_EXECUTED_GATES',CPU_ordinary_R0_hit='PASS',
        PL_ordinary_R0_hit='NOT_COMPLETED',normal_restore='NOT_PERFORMED_OWNER_RETAINED',
        task01_complete=False,PL_TTFT_app_s=None,TTFT_le_10s='NOT_VERIFIED',
        other_project_status_entries_unchanged=True,session_auth='CLOSED_REQUESTS_10_NO_SECRET_PERSISTED',
        source03_repeated=False,new_computation_in_audit=0)
    save(e/'FINAL_AUDIT.json',audit);print(json.dumps(audit))


if __name__=='__main__':main()
