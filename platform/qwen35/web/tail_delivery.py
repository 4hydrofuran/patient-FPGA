"""Freeze a tested candidate and seal its deployment, sources, evidence and summary."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import zipfile

ROOT=Path(__file__).resolve().parents[3]
BJT=timezone(timedelta(hours=8))
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.now(BJT).isoformat()
def rel(p):return p.relative_to(ROOT).as_posix()


def freeze(a):
    from fast_response_prepare_support import verify_package
    e=a.evidence.resolve();report=read(e/'BROWSER_TAIL_REPORT.json')
    assert report['status']=='PASS_75_OF_75_REAL_MODEL_BELOW_1S'
    assert read(e/'scale-first-198/RESULT.json')['actual_same_input_serial_reference'] is True
    miss=read(e/'actual-severity-miss/RESULT.json');assert miss['actual_model_calls']==1 and miss['same_session_score']==20
    now=datetime.now(BJT);tag=now.strftime('%Y%m%d_%H%M')+'_BJT_v2'
    root=ROOT/'release'/('a12_realtime_tail_'+tag);root.mkdir()
    candidate=root/'dual-neutral34-43-t4-out32'
    verify_package(a.parent);shutil.copytree(a.parent,candidate,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    verify_package(candidate)
    save(root/'VERSION.json',dict(schema='A12_REALTIME_TAIL_DELIVERY_V2',tag=tag,frozen_at=now.isoformat(),timezone='Asia/Shanghai UTC+08:00',
        candidate=candidate.name,source_candidate=rel(a.parent.resolve()),source_manifest_sha256=sha(a.parent/'MANIFEST.json'),
        candidate_manifest_sha256=sha(candidate/'MANIFEST.json'),evidence=rel(e),BOARD='NOT_TESTED'))
    print(json.dumps(dict(root=rel(root),version=tag,frozen_at=now.isoformat()),indent=2))


def make_zip(path,items):
    expected={name:sha(source) for source,name in items}
    assert len(expected)==len(items)
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for source,name in items:z.write(source,name)
    with zipfile.ZipFile(path) as z:
        assert len(z.namelist())==len(items)
        for name,digest in expected.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    return dict(name=path.name,bytes=path.stat().st_size,sha256=sha(path),verified_payload_files=len(items),CRC_SHA_readback='PASS')


def summarize(a):
    root=a.root.resolve();e=a.evidence.resolve();v=read(root/'VERSION.json');tag=v['tag']
    report=read(e/'BROWSER_TAIL_REPORT.json');assert report['status']=='PASS_75_OF_75_REAL_MODEL_BELOW_1S'
    native=read(e/'scale-first-198/RESULT.json');miss=read(e/'actual-severity-miss/RESULT.json')
    final=read(e/'frozen-browser-windows/WINDOWS.json')['rows'][0]
    current=read(e/'frozen-browser-windows/candidate01-browser/RESULT.json')['rows']
    reference={r['id']:r for r in read(e/'scale-browser-windows/candidate01-browser/RESULT.json')['rows']}
    assert final['under_1000']==25 and len(current)==25
    for row in current:
        assert row['answer']==reference[row['id']]['answer']
        t=row['turn'];s=t['timing']['native_speculative_decoding']
        assert t['answer_source']=='MODEL' and t['actual_backend']=='CPU_REFERENCE' and t['delivery_receipt']['model_called'] is True
        assert t['delivery_receipt']['validation_status']=='pass' and s['target_eos_verified'] and not s['answer_cache_used']
    save(e/'FROZEN_REPEAT_REPORT.json',dict(status='PASS_25_OF_25_FROZEN_REAL_MODEL_BELOW_1S',window=final,
        exact_answers_match_checked_candidate=True,actual_model_calls=25,answer_cache_hits=0,BOARD='NOT_TESTED'))
    baseline=report['windows'][0];candidate=report['candidate'];wins=report['windows'][1:]
    summary=ROOT/'docs'/f'A12_REALTIME_TAIL_NOBOARD_SUMMARY_{tag}.md'
    tail=[]
    final_by_id={r['id']:r for r in current}
    for qid in ('DEV-005','V04'):
        rows=[r for r in report['tail_rows'] if r['id']==qid];times=[r['v2_ms'] for r in rows]
        tail.append(f"| {qid} | {rows[0]['v1_ms']:.1f}ms | {statistics.median(times):.1f}ms（{min(times):.1f}–{max(times):.1f}） | {rows[0]['v1_ms']-statistics.median(times):.1f}ms | {final_by_id[qid]['timing']['submit_to_paint_ms']:.1f}ms |")
    main=f'KV260_Qwen35_A12_RealtimeTail_DualPrefix_NoBoard_{tag}.zip'
    text=f'''# A12 实时模型长尾优化：无板总结（{tag}）

**固定25题已在三次独立热服务窗口达到75/75低于1秒，冻结部署副本另25/25通过。**每问真实运行Qwen3.5目标模型，确认模型EOS、完整答案通过原checker后才发布；性能测试不加载答案缓存。以下是开发机x86 CPU结果，新BOARD仍NOT_TESTED/null。

## 时间与版本

- 本轮方案记录启动：2026-10-27 13:50，北京时间UTC+08:00。
- 最终198组同输入串行/草稿验证完成：{native['at']}。
- 同机v1对照与三次候选网页窗口：{read(e/'scale-browser-windows/WINDOWS.json')['rows'][0]['start']} 至 {read(e/'scale-browser-windows/WINDOWS.json')['rows'][-1]['end']}。
- 版本冻结：{v['frozen_at']}；文件名中的{tag}表示冻结时刻，精确到分钟，BJT=北京时间UTC+08。
- 冻结副本复测：{final['start']} 至 {final['end']}。
- 实际上传完成时刻与远端commit另存本交付目录的PUBLISH_RECEIPT.json；不把计划上传时间写成完成证据。

## 相比之前，完整可用回答减少多少

真实Edge + HTTP/SSE；起点是用户提交，终点是完整核验答案更新DOM后两次animation frame。加载/预热未计入热服务逐问耗时。

| 指标 | 本轮v1实时模型对照25题 | v2三个独立窗口75题 | 冻结副本25题 |
| --- | ---: | ---: | ---: |
| 最快 | {baseline['min_ms']:.1f}ms | {candidate['min_ms']:.1f}ms | {final['min_ms']:.1f}ms |
| 中位 | {baseline['median_ms']:.1f}ms | **{candidate['median_ms']:.1f}ms** | {final['median_ms']:.1f}ms |
| 最慢 | {baseline['max_ms']:.1f}ms | **{candidate['max_ms']:.1f}ms** | {final['max_ms']:.1f}ms |
| 低于1秒 | 23/25 | **75/75** | **25/25** |
| 真实模型调用 | 25 | 75 | 25 |
| 答案缓存命中 | 0 | 0 | 0 |

两组中位数相差{baseline['median_ms']-candidate['median_ms']:.1f}ms，约减少{(baseline['median_ms']-candidate['median_ms'])/baseline['median_ms']*100:.1f}%。三轮各自中位为{' / '.join(f"{w['median_ms']:.1f}ms" for w in wins)}；不是挑一次最快值。两道原长尾分别为：

| 题目 | 本轮v1对照 | v2三轮中位及范围 | 配对中位减少 | 冻结副本 |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(tail)}

本轮主要改善尾延迟。冻结复测中位{final['median_ms']:.1f}ms高于v1对照{baseline['median_ms']:.1f}ms，存在窗口波动，不能据此宣称中位响应稳定提速；四个候选窗口均保留并逐项报告。

更早的原串行网页实测中位879.0ms、最慢1535.5ms；上一轮v1为618.3ms、23/25低于1秒。它们是历史不同窗口，不能当作本轮同步配对。42ms左右的已核验答案复用属于MODEL_CACHE路径，也不混入本表。

## 实现与完整性

连续候选使用4线程、34/43-token双中性前缀。severity改用原checker已有的完整表达“按10分计算，我的疼痛是N分”；固定量表说明在患者分值前，可复用其计算。43-token前缀含通用量表满分10，含患者评分值和病例ID的内容均不进入此前缀。其他事实保持原短表达；ordinary仍原3线程/34前缀/24输出。

每问从当前事实构造待验证草稿，目标模型真正计算所有候选位置，逐token贪心及EOS全部吻合才发布；不是交付模板。失败仍清空全部recurrent/conv/KV并恢复前缀、重放完整prompt。病例路由、原checker、原评分、模型/量化/native/HLS/公共ABI不变。网页来源MODEL，model_called=true、CPU_REFERENCE。两道severity答案措辞改变，数值、10分量表及全部必需事实由原checker独立复验，未截短回答换速度。

最终198组（三病例、11事实、最多双事实）实际串行生成与43-prefix草稿生成396次；相同输入的答案token、EOS、原checker全部通过，198/198严格目标草稿接受，worker正常exit0。198组是正确性覆盖，含部分超过1秒的双事实组合，**不声称所有198组或任意输入均低于1秒**。

真实删除severity目录项后的197条目录测试：仅1次模型未命中，确实复用43-token前缀；其后缓存命中11次，7项策略零模型/缓存查询，同场20分冻结、幂等、10场归档/8场内存保留及正常关闭通过。正常混合模式保留MODEL_CACHE来源标记；性能模式明确不加载该目录。48项网页/路由回归、15项浏览器协议回归和独立包离线导入/预算检查通过。

## 成本、失败尝试与限制

前缀实测保留{native['retained_prefix_bytes']}字节（约{native['retained_prefix_bytes']/1048576:.2f}MiB），比单前缀新增约{(native['retained_prefix_bytes']-21614659)/1048576:.2f}MiB。原每槽64MiB/双槽128MiB上限及192MiB admission预留不变；额外预热432次CPU运行，总792。逐问仍用最短34前缀的22320保守额度，覆盖验证及完整串行重放。候选服务启动就绪约{min(w['startup_ready_s'] for w in wins):.2f}–{max(w['startup_ready_s'] for w in wins):.2f}秒，v1对照{baseline['startup_ready_s']:.2f}秒，冷启动没有达到1秒承诺。

37-token/3线程首轮三窗口仅73/75低于1秒，最慢1022.3ms，未入选。38-token尾随空格没有匹配原输入，完成122对后停止，未标记完整通过；中断和原始日志保留。逻辑chunk=8的矩阵没有稳定改善，最终保持256、physical_ubatch=8。没有省略超时题或放宽checker。

PC native SHA256：64b6ebe583dc6d4f25cb21991548fed6f9816de02140b539ec924268f1efc925；A53 native SHA256：bb66432dafdcda9d990f08b0c2e766e0c9d3de82070177199183268b069047fc，均与v1字节一致。没有重建工具链或升级依赖。

这只证明固定25题、本开发机热服务的三窗口及冻结复测。实板可见时延、真实PL未命中、CMA、功耗和原Owner硬件恢复/独立释放仍NOT_TESTED/null；不能用此CPU毫秒结果减历史板端秒数推导板端加速。

## 文件、复现与上传

推荐总包：`{main}`。Deployment含独立UNBOUND部署候选；EngineeringIncrement含工程源码、回归、真实命令/退出码、原始证据及本总结，内外SHA与ZIP读取校验由ARCHIVES.json记录。模型权重、SDK、镜像、凭据和可重放执行授权不随包提供。

入口：[交付说明](../{rel(root)}/START_HERE.md)；证据：`{rel(e)}/`。重点查看BROWSER_TAIL_REPORT.json/CSV、scale-first-198/proof、actual-severity-miss、FROZEN_REPEAT_REPORT.json以及*-command日志。部署先做包内PC package检查；旧v1独立包保留用于回退。

本轮复杂实现、设计及证据验收未委派；沿用此前核实的Sol/High配置，单次实际推理参数无法核实仍记unknown。未做无关安全审查或板端操作。
'''
    summary.write_text(text,encoding='utf-8')
    entry=dict(status='PASS_PC_75_PLUS_25_REAL_MODEL_UNDER_1S',summary=rel(summary),entry=rel(root/'START_HERE.md'),
        evidence=rel(e),frozen_at=v['frozen_at'],prefix_tokens=[34,43],continuous_threads=4,ordinary_threads=3,
        three_windows=report['candidate'],under_1s='75/75',frozen_repeat=final,answer_cache_hits=0,native_cases=198,
        all_same_input_serial_tokens_EOS_checker_pass=True,question_reserve=22320,prefix_retained_bytes=native['retained_prefix_bytes'],
        web_tests=48,browser_regressions=15,BOARD='NOT_TESTED',board_actions=0,board_visible_ms=None,board_PL_miss=None)
    status=read(ROOT/'docs/PROJECT_STATUS.json');status={'a12_realtime_tail_no_board_'+tag:entry,**status};save(ROOT/'docs/PROJECT_STATUS.json',status)
    paragraph=f"三次独立真实Edge窗口75/75完整核验答案低于1秒，中位{candidate['median_ms']:.1f}ms、最慢{candidate['max_ms']:.1f}ms；冻结副本另25/25通过。每问真实CPU模型，答案缓存命中0。34/43通用前缀、连续4线程，原checker/评分/native不变；198组同输入串行/草稿396请求逐token/EOS通过，48项网页和15项浏览器回归、真实severity未命中/评分/归档通过。BOARD仍NOT_TESTED/null。详见[{summary.name}]({summary.name})。"
    for name in ('TEST_MATRIX.md','DECISIONS.md','DESIGN_GAP.md','AI_ASSISTANCE.md'):
        p=ROOT/'docs'/name;p.write_text(f'## {tag} A12 实时模型长尾无板收口\n\n{paragraph}\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
    print(json.dumps(dict(summary=rel(summary),status=entry['status']),indent=2))


def seal(a):
    root=a.root.resolve();e=a.evidence.resolve();v=read(root/'VERSION.json');tag=v['tag']
    candidate=root/v['candidate'];summary=a.summary.resolve();assert tag in summary.name
    from fast_response_prepare_support import verify_package
    verify_package(candidate)
    final=read(e/'frozen-browser-windows/WINDOWS.json')['rows'];assert len(final)==1 and final[0]['under_1000']==25
    prefix='KV260_Qwen35_A12_RealtimeTail_DualPrefix'
    main_name=f'{prefix}_NoBoard_{tag}.zip'
    deploy_name=f'{prefix}_Deployment_NoBoard_{tag}.zip'
    engineering_name=f'{prefix}_EngineeringIncrement_NoBoard_{tag}.zip'
    old=read(ROOT/'release/a12_realtime_model_draft_20261027_v1/ENGINEERING_MANIFEST.json')
    selected={r['path'] for r in old['files']}
    for folder in (ROOT/'platform/qwen35/web',ROOT/'bench/qwen35/web',e):
        selected.update(rel(p) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'
            and 'seal-command' not in p.parts)
    selected.update(rel(p) for p in [summary,ROOT/'docs/A12_REALTIME_TAIL_25_UNDER_1S_PLAN_20261027.md',
        ROOT/'docs/PROJECT_STATUS.json',ROOT/'docs/TEST_MATRIX.md',ROOT/'docs/DECISIONS.md',ROOT/'docs/DESIGN_GAP.md',ROOT/'docs/AI_ASSISTANCE.md'])
    files=[dict(path=p,bytes=(ROOT/p).stat().st_size,sha256=sha(ROOT/p)) for p in sorted(selected)]
    save(root/'ENGINEERING_MANIFEST.json',dict(schema='A12_REALTIME_TAIL_ENGINEERING_INCREMENT_V2',base_commit=a.base_commit,
        frozen_at=v['frozen_at'],sealed_at=stamp(),files=files))
    deploy=make_zip(root/deploy_name,[(p,candidate.name+'/'+p.relative_to(candidate).as_posix()) for p in sorted(candidate.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'])
    engineering=make_zip(root/engineering_name,[(ROOT/r['path'],r['path']) for r in files]+[(root/'ENGINEERING_MANIFEST.json','ENGINEERING_MANIFEST.json')])
    save(root/'PRODUCT_ARCHIVE.json',deploy)
    readme=f'''# KV260 Qwen3.5 A12 实时模型长尾优化，无板交付 v2

版本冻结：{v['frozen_at']}（北京时间UTC+08，文件名精确到分钟）。封包开始：{stamp()}。

推荐总包：{main_name}。内含两个子包：

- packages/{deploy_name}：独立部署候选。解压后从{candidate.name}/START_HERE.md开始，先做PC package检查。需要现有模型资产和依赖。
- packages/{engineering_name}：工程增量源码、测试、真实命令与证据、既有v1相关参考材料及本轮中文总结。仓库基线为{a.base_commit}。

总结：{summary.name}。三个独立热服务窗口75题均低于1秒，冻结副本另25题复测；均每问真实运行CPU模型，未加载答案缓存。这里只报告开发机x86数据。双前缀34/43-token与4线程用于连续候选，评分值仍实时输入；未改原checker、评分、模型或native二进制。

文件名规则：项目_阶段_功能_内容类型_NoBoard_YYYYMMDD_HHmm_BJT_v2.zip；日期时间表示本次版本冻结，测试起止另见总结，实际上传时间见仓库PUBLISH_RECEIPT.json。

BOARD为NOT_TESTED/null；实板操作按部署包中已有入口和专项授权执行。旧v1包可独立回退。模型权重、SDK、镜像、凭据及可重放执行授权不随包提供。
'''
    (root/'README.md').write_text(readme,encoding='utf-8')
    (root/'START_HERE.md').write_text(f'先阅读[中文总结](../../docs/{summary.name})及[交付说明](README.md)。\n\n独立部署入口：[START_HERE]({candidate.name}/START_HERE.md)。\n',encoding='utf-8')
    sums=f"{deploy['sha256']}  packages/{deploy_name}\n{engineering['sha256']}  packages/{engineering_name}\n"
    (root/'PACKAGE_SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    combined=make_zip(root/main_name,[(root/'README.md','README.md'),(summary,summary.name),
        (root/'VERSION.json','VERSION.json'),(root/'PACKAGE_SHA256SUMS.txt','PACKAGE_SHA256SUMS.txt'),
        (root/deploy_name,'packages/'+deploy_name),(root/engineering_name,'packages/'+engineering_name)])
    archives=[dict(role='CombinedDelivery',**combined),dict(role='Deployment',**deploy),dict(role='EngineeringIncrement',**engineering)]
    save(root/'ARCHIVES.json',dict(status='PASS_ALL_ARCHIVES_CRC_SHA_READBACK',sealed_at=stamp(),archives=archives))
    (root/'SHA256SUMS.txt').write_text(''.join(f"{r['sha256']}  {r['name']}\n" for r in archives),encoding='utf-8')
    save(root/'DELIVERY.json',dict(status='PASS_ALL_ARCHIVES_CRC_SHA_READBACK',recommended=combined,
        subpackages_inside_combined=[deploy,engineering],summary=rel(summary),version=v,final_repeat=final,
        repository='https://github.com/4hydrofuran/patient-FPGA',base_commit=a.base_commit,branch=a.branch,BOARD='NOT_TESTED'))
    print(json.dumps(dict(root=rel(root),recommended=combined,selected_engineering_files=len(files)),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('freeze','summarize','seal'))
    p.add_argument('--parent',type=Path);p.add_argument('--root',type=Path);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--summary',type=Path);p.add_argument('--branch');p.add_argument('--base-commit',default='e7a76cb0d60ae087f796c98fcb10def74733042b')
    a=p.parse_args();{'freeze':freeze,'summarize':summarize,'seal':seal}[a.action](a)
