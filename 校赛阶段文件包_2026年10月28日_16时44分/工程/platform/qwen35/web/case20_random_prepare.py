"""Derive random twenty-case deployment from the actually running hotpath lineage."""
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
from fast_response_prepare_support import refresh_bundle_manifest
from case20_prepare import manifest

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare():
    base=ROOT/'release/a12_board_hotpath_20261027_v6/b601e69ca-verified-cache-t4'
    cases=ROOT/'release/a12_case20_natural_20261027_v1/case20-natural-t4'
    out=ROOT/'release/a12_case20_random_board_20261027_v1/case20-random-t4'
    shutil.copytree(base,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc','answer-cache','run-v1'))
    frontend=HERE/'integrated/B_601e69ca_A_case20_random_20261027/web_gateway'
    for kind in ('ordinary','continuous'):
        window=out/kind;bundle=window/'bundle'
        shutil.copytree(frontend,window/'web_gateway',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('fast_response_profile.py','verified_answer_cache.py','answer_cache_profile.py','natural_patient_prompt.py',
                     'answer_cache_serve_pc.py','answer_cache_paths.py','answer_cache_build.py'):
            shutil.copyfile(cases/kind/name,window/name)
        shutil.copyfile(HERE/'continuous_sessions.py',window/'continuous_sessions.py')
        shutil.copytree(ROOT/'system_qwen35/cases',bundle/'application/system_qwen35/cases',dirs_exist_ok=True)
        for name in ('domain.py','checking.py','planning.py'):
            shutil.copyfile(ROOT/'system_qwen35/app'/name,bundle/'application/system_qwen35/app'/name)
        cpu=window/'web_gateway/src/patient_web/stdio_cpu.py'
        cpu.write_text(cpu.read_text(encoding='utf-8').replace('max_tokens=24','max_tokens=32'),encoding='utf-8')
        if kind=='continuous':
            shutil.copyfile(cases/kind/'profile.json',window/'profile.json')
            for name in ('prefix-config.json','requests.json','window-spec.json'):
                shutil.copyfile(cases/kind/'bundle/control'/name,bundle/'control'/name)
            policy=bundle/'platform/qwen35/a12/resource_probe_policy.py'
            policy.write_text(policy.read_text(encoding='utf-8').replace(repr('short34-t4'),repr('natural-t4')),encoding='utf-8')
            shutil.copytree(cases/kind/'answer-cache',window/'answer-cache')
            config=read(window/'web-config.json')
            config.update(answer_cache=read(cases/kind/'web-config.json')['answer_cache'],verify_first=True,
                verify_continuous=False,browser_profile='/home/ubuntu/snap/firefox/common/a12-case20-random-20261027',
                natural_patient_policy='patient-natural-short-v1',case_selection='SERVER_RANDOM',profile_model_requests=False)
            save(window/'web-config.json',config)
            graphical=window/'verify_graphical.py';s=graphical.read_text(encoding='utf-8')
            s=s.replace("report=dict(status='RUNNING_REAL_GUI_VERIFICATION',case_id='SYN_CP_03')", "report=dict(status='RUNNING_REAL_GUI_VERIFICATION',case_selection='SERVER_RANDOM')")
            s=s.replace("document.getElementById('cases').options.length===3 && !document.getElementById('start').disabled", "!document.getElementById('cases') && !document.getElementById('start').disabled")
            s=s.replace("document.getElementById('cases').value='SYN_CP_03';document.getElementById('start').click();true", "document.getElementById('start').click();true")
            s=s.replace("question='每次疼痛持续多久？'", "question='疼痛在什么位置？'")
            s=s.replace("sid=http('/ui/v1/status')['current_session_id']", "sid=http('/ui/v1/status')['current_session_id']\n        report['case_id']=http('/ui/v1/sessions/'+sid)['case_id']")
            s=s.replace('        if ws:ws.s.close()', "        if ws:\n            try:ws.call('session.end',{})\n            finally:ws.s.close()")
            graphical.write_text(s,encoding='utf-8')
            interactive=window/'interactive_case.py';s=interactive.read_text(encoding='utf-8')
            s=s.replace('"webgl.disabled":True}', '"webgl.disabled":True,"layout.frame_rate":60}')
            s=s.replace('        time.sleep(seconds)\n        SERVER.should_exit=True', '        # Hardware already finalized: stop its HTTP view with the requested service.\n        SERVER.should_exit=True')
            interactive.write_text(s,encoding='utf-8')
        refresh_bundle_manifest(bundle)
    for name in ('PC_PREFIX_CONFIG.json','PC_DEPENDENCIES.json'):
        shutil.copyfile(cases/name,out/name)
    save(out/'CASE20_RANDOM_SOURCE.json',dict(base=str(base.relative_to(ROOT)),case_source=str(cases.relative_to(ROOT)),
        case_count=20,catalog_entries=1320,case_selection='SERVER_RANDOM_PER_SESSION',
        retries_and_refresh_keep_same_case=True,first_request='REAL_MODEL_FPGA_WITH_CACHE_DEFERRED',
        cache_after_probe=True,native_HLS_public_ABI_changed=False,BOARD='NOT_TESTED'))
    (out/'START_HERE.md').write_text('''# 二十例随机病例：板端候选

点击“随机抽取并开始”，服务端从20例中随机分配一例；刷新和请求重试不重新抽取，结束后可抽取新病例。
本包保留当前hotpath启动/恢复修复，接入已验证的1320条CPU模型答案目录及34-token共享前缀。
首次图形验证延后缓存，实际运行一次FPGA模型；通过后启用带明确来源的答案复用。
模型、native、HLS和公共ABI未修改。启动入口start_board.py默认仅显示计划。
''',encoding='utf-8')
    manifest(out)
    return out

if __name__=='__main__':print(prepare())
