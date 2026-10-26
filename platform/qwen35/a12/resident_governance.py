"""Append new evidence state while preserving every existing governance value."""
from resident_evidence import ROOT,OUT,read,save,pin
import json


def main():
    review=read(OUT/'TECHNICAL_REVIEW.json')
    paths={name:ROOT/'docs'/name for name in ('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')}
    before={name:path.read_bytes() for name,path in paths.items()}
    for name,raw in before.items():
        path=OUT/(name+'.before-finalization');assert not path.exists();path.write_bytes(raw)
    old=json.loads(before['PROJECT_STATUS.json']);state=dict(old)
    key='a12_bounded_resident_no_board_20261026';assert key not in state
    state[key]=dict(status='NOBOARD_BOUNDED_RESIDENT_CANDIDATE_REVIEWED',no_board_candidate_work_complete=True,
                    bounded_PC_software_test_ready=True,SERVICE_ready=False,BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',
                    production_enabled=False,physical_release_allowed=False,actual_PL_results_consumed=False,
                    fixed_cohort_model_answers=25,policy_inputs_without_model=7,current_normal_windows=11,targeted_fault_windows=9,
                    PC_application_s=review['PC_application_s'],PC_pipe_complete_s=review['PC_pipe_complete_s'],
                    typed_Board_factory='PREPARED_ORIGINAL_OWNER_ONLY_NOT_EXECUTED',
                    fixed_root_target_build='evidence/model_pl_A/20261026-resident-v1/BOARD_BUILD-fixed-root-v1.json',
                    evidence='docs/handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md',
                    ordinary_probe_unchanged=True,public_ABI_changed=False,whole_A12_goal_achieved=False,
                    Board_CMA=None,Board_latency_saving_s=None,medical_review='NOT_PERFORMED')
    paths['PROJECT_STATUS.json'].write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    append={
      'DESIGN_GAP.md':'本轮必要无板候选工作已收口：原Session/可信历史/病例/内容门槛、同进程分词与公共warm、有界多请求及最终应用交付门槛已接通。typed Board应用工厂及固定/opt目标配置已准备，实际放置/授权/执行未做。整体A12/Board资源与性能、医学及生产验收继续未完成。',
      'DECISIONS.md':'常驻只是一段最多1warm+8模型请求的有界软件试验窗口，保留原5000总预算/1800秒Owner上限及250ms健康门槛。最坏24-token输出预留可提前拒绝；实测6回答后第7次计算前拒绝。应用END持久化后另取fresh票据；PC文本ACK不进入学生输入通道。Board工厂不创建Owner、租约或自动释放。',
      'TEST_MATRIX.md':'最终25固定输入/7窗口、同会话追问与换病例、7策略零模型、容量及并发共11正常窗口，9故障窗零应用交付及原件审计通过；20项Python、真实私有Control9请求/第10拒绝和45状态标志普通+sanitizer通过。PC应用中位1.438949619秒；CLI完整stdout两次1.512574873/1.381635450秒。BOARD/A53执行、真实CMA/时延/医学未测，失败保留。',
      'AI_ASSISTANCE.md':'主代理完成常驻核心、Board准备、原件审计和最终验收判断；用户授权并行后，Sol子任务仅实现PC CLI和使用文档，主代理检查并运行真实CPU验证。DeepSeek仅整理给定分工表，无文件/命令权限。实际模型/effort无法核实，unknown。无板卡连接、恢复/释放、部署或整体远端发布。'
    }
    for name,text in append.items():
        assert paths[name].read_bytes()==before[name]
        extra=('\n\n## 2026-10-26 A12 有界常驻无板收口\n\n'+text+'\n\n交接 `docs/handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md`；证据 `evidence/model_pl_A/20261026-resident-v1/FINAL_REVIEW.json`。\n').encode()
        with paths[name].open('ab') as f:f.write(extra)
        assert paths[name].read_bytes().startswith(before[name])
    current=read(paths['PROJECT_STATUS.json']);assert {k:v for k,v in current.items() if k!=key}==old
    save(OUT/'GOVERNANCE_PRESERVATION.json',dict(status='ALL_PREEXISTING_KEYS_AND_MARKDOWN_PREFIXES_PRESERVED',
         old_status_keys=len(old),new_status_keys=len(current),new_key=key,files=[pin(p) for p in paths.values()]))
    print('APPENDED_GOVERNANCE_WITHOUT_REPLACING_OLD_STATE',len(old),len(current))


if __name__=='__main__':main()
