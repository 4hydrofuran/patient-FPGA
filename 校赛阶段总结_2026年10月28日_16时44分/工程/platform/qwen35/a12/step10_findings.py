"""Rank non-overlapping measured costs and explain the practical speed result."""
import json
from common import ROOT,save
from step10_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    summary=j(OUT/'SUMMARY.json');findings=[]
    labels=dict(permission_wait='管理许可等待（包含新鲜检查与持久记录）',completion_report='完成报告序列化/解析',
        submit_wait='提交至确认完成的主机等待',sync_copy_validation='BO同步/复制、参数与结果校验',
        route_call_other='线性调用其余主机开销',quant_copy_bridge='激活量化/复制与MLP桥接其余开销',
        non_mlp_graph='线性回调以外的CPU图（含注意力/激活/状态等）',graph_prepare='CPU图准备/调度')
    for name in ('natural_profile','context1024_profile'):
        path=OUT/'optimized/readback-v1/run-v1/s2'/name
        r=j(path/'result.json');p=r['request_profile'];phases=p['phases'].values();pl=p['pl_profile']['phases'].values()
        linear=sum(v['linear_service_wall_ms'] for v in phases)
        permission=sum(v['backend']['a12_permission_wait_ms'] for v in pl)
        service=sum(v['backend']['service_ms'] for v in pl)
        report=sum(v['completion_report_wall_ms'] for v in pl)
        wait=sum(v['backend']['a11_submit_to_confirmed_completion_ms'] for v in pl)
        mlp=sum(v['mlp_inclusive_wall_ms'] for v in phases)
        parts=dict(permission_wait=permission,completion_report=report,submit_wait=wait,
            sync_copy_validation=service-wait,route_call_other=linear-permission-service-report,
            quant_copy_bridge=mlp-linear,non_mlp_graph=sum(v['non_mlp_cpu_graph_ms'] for v in phases),
            graph_prepare=sum(v['host_graph_prepare_schedule_ms'] for v in phases))
        total=sum(v['llama_decode_wall_ms'] for v in phases)
        assert all(v>=0 for v in parts.values()) and abs(sum(parts.values())-total)<1e-5
        rank=[dict(component=k,label=labels[k],wall_s=v/1000,fraction=v/total) for k,v in sorted(parts.items(),key=lambda kv:kv[1],reverse=True)]
        findings.append(dict(id=name,total_model_decode_s=total/1000,exclusive_costs=rank,dominant=rank[:3],
            nested_intervals_not_double_counted=True))
    natural=next(r for r in summary['normal_mode'] if r['id']=='natural_plain')
    result=dict(status='MEASURED_BOTTLENECKS_RANKED',findings=findings,normal_natural=natural,
        interpretation='Measured same-board text inference path; fixed sample/order only; no voice or statistical extrapolation',
        R0_full_replay_is_real_cost=True,default_FPGA_enabled=False)
    save(OUT/'BOTTLENECK_FINDINGS.json',result)
    intro=['## 速度与主要瓶颈的直接结论','',
      f"本次自然回答（107输入、{natural['pl']['output_tokens']}输出token，已到EOS），CPU首token/完成为{natural['cpu']['client_first_token_s']:.3f}/{natural['cpu']['client_complete_s']:.3f}秒；修复后PL为{natural['pl']['client_first_token_s']:.3f}/{natural['pl']['client_complete_s']:.3f}秒。这里只代表本次文字推理样本。",'']
    for f in findings:
        intro.append(f"{f['id']}修复后的主要区间："+'；'.join(f"{r['label']} {r['wall_s']:.3f}秒（{r['fraction']:.1%}）" for r in f['dominant'])+'。')
    reads=summary['health_read_micro']['components']
    intro+=['',f"计算结束后的独立只读复测中，三路温度读取均值{reads['temperatures_total_ms']['mean_ms']:.3f}毫秒/组，内核日志读取均值{reads['kernel_read_ms']['mean_ms']:.3f}毫秒。这帮助定位健康门禁的读取成本；它不等同于模型请求中的整段门禁时间。",
      '', '因此，去掉重复报告/日志的改善与剩余计算/许可成本需要分别看待；当前默认R0长输入仍要完整重算，不能用短输入速度承诺长对话体验。完整独占区间分解见BOTTLENECK_FINDINGS.json，所有分项之和已与模型计算墙时校核。','']
    path=OUT/'REPORT.md';text=path.read_text(encoding='utf-8');title,rest=text.split('\n',1)
    path.write_text(title+'\n\n'+'\n'.join(intro)+rest,encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP10_COMPLETE_20261024.md'
    handoff.write_text(path.read_text(encoding='utf-8')+'\n下一步仅任务11总收口。既有重启/冷启动专项票据均已消费，本轮无新增电源、重启或刷写授权。\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=True,indent=2))
