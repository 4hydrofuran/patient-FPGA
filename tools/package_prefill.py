"""Freeze one verified B03 design and build a compact, reproducible handoff."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import zipfile

from archive_prefill_batches import ROOT, GROUPS, STRESS_COUNTS, sha


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def memory_peak(directory):
    """旧基线manifest未含execution时，从同组实际XSIM日志读取峰值。"""
    manifest = read(directory / "manifest.json")
    peak = manifest.get("execution", {}).get("xsim_peak_memory_KB")
    if peak is not None:
        return peak
    values = [int(match.replace(",", "")) for log in directory.glob("*.log")
              for match in re.findall(r"xsimkernel Simulation Memory Usage:.*?Peak:\s*([\d,]+)", log.read_text(errors="replace"))]
    return max(values) if values else None


def build(variant, output):
    output.mkdir(parents=True, exist_ok=True)
    ablation = read(ROOT / "reports/b03/ablation.json")
    stress = read(ROOT / "reports/b03/stress_acceptance.json")
    guard = read(ROOT / "reports/b03/artifact_guard.json")
    if ablation["status"] != "ALL_NOMINAL_RTL_PASS" or stress["status"] != "PASS" or stress["variant"] != variant or guard["status"] != "PASS":
        raise RuntimeError("All nominal/stall/artifact acceptance gates must pass before delivery")
    destination = ROOT / "artifact/b03_candidate"
    destination.mkdir(parents=True, exist_ok=True)
    xo = ROOT / f"build/b03_{variant}_hls/w4a8_linear_v1.xo"
    if sha(xo) != guard["variants"][variant]["xo_sha256"]:
        raise RuntimeError("Candidate XO changed after verification")
    manifest_path = destination / "candidate.json"
    if manifest_path.exists() and read(manifest_path)["variant"] != variant:
        raise RuntimeError("A different candidate was already frozen")
    if manifest_path.exists() and read(manifest_path)["artifact"]["xo_sha256"] != sha(xo):
        raise RuntimeError("Refusing to replace a frozen candidate with a different XO")
    frozen_at = read(manifest_path)["frozen_at"] if manifest_path.exists() else datetime.now().astimezone().isoformat()
    shutil.copy2(xo, destination / "w4a8_linear_v1.xo")
    shutil.copy2(ROOT / f"build/b03_{variant}_hls/hls/kernel.xml", destination / "kernel.xml")
    chosen = ablation["measurements"][variant]
    selection = read(ROOT / "reports/b03/selection.json")
    if selection["variant"] != variant or selection["status"] != "SELECTED_OFF_BOARD":
        raise RuntimeError("Candidate selection evidence mismatch")
    clean_path = ROOT / "reports/b03/clean_delivery.receipt.json"
    clean_result = "全新解压目录重新编译候选，full50与真实权重4例均通过；最终包源文件哈希与该次已测载荷一致" if clean_path.exists() and read(clean_path)["status"] == "PASS" else "PENDING：完成交付包后从全新目录复跑"
    manifest = {"stage": "B03", "status": "COMPLETE_OFF_BOARD", "variant": variant,
                "kernel_build_id_hex": {"baseline": "0xB3020002", "reuse": "0xB3030001", "double": "0xB3030002"}[variant],
                "private_meta_bytes": 40,
                "frozen_at": frozen_at,
                "contract_sha256": read(ROOT / "contracts/contract_lock.json")["contract_sha256"],
                "artifact": guard["variants"][variant], "nominal": chosen,
                "selection_reason": selection["reason"],
                "random_stall_transactions": stress["transactions"],
                "public_library": "NOT_IMPLEMENTED_B04", "implementation": "NOT_TESTED", "BOARD": "NOT_TESTED"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for name in ("qwen35_gate_up_t1", "qwen35_gate_up_t8", "qwen35_down_t1", "qwen35_down_t8"):
        values = [ablation["measurements"][v]["targets"][name]["cycles"] for v in ("baseline", "reuse", "double")]
        gains = [ablation["measurements"][v]["targets"][name]["improvement_percent"] for v in ("reuse", "double")]
        rows.append(f"| {name} | {values[0]:,} | {values[1]:,} | {values[2]:,} | {gains[0]:+.2f}% | {gains[1]:+.2f}% |")
    resources = []
    for v in ("baseline", "reuse", "double"):
        estimates = ablation["measurements"][v]["synthesis"]
        resources.append(f"| {v} | {estimates['bram18k_estimate']} | {estimates['dsp_estimate']} | {estimates['ff_estimate']:,} | {estimates['lut_estimate']:,} | {estimates['clock_slack_ns_estimate']:.2f} |")
    nominal_modes = {}
    for v in ("baseline", "reuse", "double"):
        nominal_modes[v] = [read(ROOT / f"evidence/b03/batches/{v}/{g}/manifest.json")["status"] for g in GROUPS]
    stress_modes = {g: read(ROOT / f"evidence/b03/batches/{variant}/stall_{g}/manifest.json")["status"] for g in STRESS_COUNTS}
    selection_text = ("选定double：两种T1均不退化，两种T8均比reuse更快。相对reuse，HLS估计增加5个BRAM18K、12个DSP、1,310个FF和2,104个LUT；选择依据是本次覆盖内的周期收益与上述代价。唯一候选并不表示所有工作负载或实现条件下都最优，布局布线后需重新确认。"
                      if variant == "double" else "选型依据见reports/b03/selection.json；唯一候选只适用于本次覆盖与估计条件，布局布线后需重新确认。")
    memory_rows = []
    for group in ("gate_t8", "down_t8"):
        peaks = [memory_peak(ROOT / f"evidence/b03/batches/{v}/{group}") for v in ("baseline", "reuse", "double")]
        values = [f"{peak / 1048576:.2f}" if peak is not None else "未报告" for peak in peaks]
        memory_rows.append(f"| {group} | {' | '.join(values)} |")
    report = f"""# B03 无板开发验收与交付

验收日期：{datetime.now().astimezone().date()}。工程：D:/KV260-project-HLS/b_qwen35。唯一冻结候选：**{variant}**。

## 完成内容

保留B02_X128作为冻结基线。reuse将T>1调度改为输出tile→group→token，同一W4/Sw块供全部token使用，并缓存本次输入；double进一步采用两个互相独占的权重/scale槽，计算当前块时装载下一块，两个任务完成后才交换。最后group禁止越界预取，写回在当前输出tile全部group完成后进行。T1保留原decode路径。

数学、FP32沿group递增的累加顺序、公共布局及顶层参数/控制偏移保持不变；私有meta仍40字节。最终版本将scale AXI端口固定为原32位，避免自动拓宽至512位后导致T1突发读取退化。最初reuse的gate/up T1曾慢5.41%，旧源码、实际结果和中断记录独立保留在evidence/b03/sw512_regression/与reports/b03/。最终消融只比较修正后、来源指纹匹配的完整结果。完整W4合法性预扫描在任何输出写入前执行。

## 分域验收

| 验证域 | 结果与覆盖 |
|---|---|
| PC数值 | 三版各50笔合成事务；两个目标形状各T1..8；原错误/量化/重复任务和新增奇偶group、N/K尾块 |
| 真实权重PC | 三版各4例；固定revision的layer0 gate/down权重、T1/T8，激活为合成数据 |
| Csim | 三版各完整50笔，退出0 |
| 综合/XO | 三版退出0；资源和slack为HLS估计 |
| 普通RTL | 三版各5组、34笔，总102笔；实际Y/meta经独立golden回放，分组集合与原34笔相同 |
| 随机背压RTL | 候选5组12/11/7/1/1笔，共32笔；五个内存master的地址/数据/响应通道0..7周期随机延迟，control 0..3；覆盖最大K/N、尾块、错误和重复任务，保留实际端口波形/BFM |
| 保护检查 | 公共契约、B02冻结源码、源到综合指纹、XO CRC/参数表、相同输入和独立expected向量均通过 |
| 回放反证 | 正确归档RTL输出通过；临时副本Y[0]改错后明确失败，原始证据SHA不变 |
| 清洁交付复跑 | {clean_result} |
| 实现/aarch64/BOARD/质量/整机时延/功耗 | NOT_TESTED，留待后续阶段 |

INT32部分和检查观察C++ MAC helper；RTL验收核对实际Y/meta，未宣称直接探测RTL内部部分和。历史小用例门槛1e-6和目标形状1e-4+1e-5×abs(reference)保持不变。真实权重范围不是全模型或问诊质量验证。

## 实测消融

以下均为相同隔离suite的XSIM周期；不把历史多事务报告混入比较。正百分比表示候选周期减少，负值表示回退，T1与T8分别列出。

| 目标 | baseline周期 | reuse周期 | double周期 | reuse周期减少 | double周期减少 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

每token周期及逐组来源见B03_消融结果.json。目标时钟6.667ns只是仿真/综合目标；这些周期不等于板端DDR或整机服务时延。

reuse的收益来自同一权重块服务8个token，减少重复装载，但加载和计算仍依次进行。double进一步让当前块计算与下一块加载重叠，两种T8相对reuse各再减少约10%的周期。总周期降幅小于权重请求字节降幅，因为每个token的乘加/FP32还原仍须执行，W4预扫描、首块装载、末块收尾和输出写回也保留。T1使用原decode路径，最终两个优化方案均与基线周期一致。

| HLS构建 | BRAM18K估计 | DSP估计 | FF估计 | LUT估计 | slack估计(ns) |
|---|---:|---:|---:|---:|---:|
{chr(10).join(resources)}

负slack意味着尚不能证明实现后满足目标频率；B04需完成离线链接与布局布线时序/资源检查。

{selection_text}

两种目标矩阵每份W4为1,835,008字节。T8包括预扫描的逻辑W4请求由baseline的16,515,072降到reuse/double的3,670,016字节，减少77.78%；Sw从917,504降到114,688字节。**物理AXI/DDR总线字节没有实测，保持null。**

## 串行恢复与证据

| T8用例 | baseline仿真器峰值(GiB) | reuse峰值(GiB) | double峰值(GiB) |
|---|---:|---:|---:|
{chr(10).join(memory_rows)}

以上来自同类XSIM日志的Simulation Memory Usage Peak，属于电脑仿真器内存，不是FPGA BRAM或板端DDR容量。Windows私有内存采样另见reports/b03/memory_samples.jsonl。分组避免多核仿真进程同时驻留，复用减少重复AXI事务；不把某一时刻的低占用当作最终峰值。

五组普通RTL逐组启动、退出、归档后再进入下一组，trace_level=none；应力组使用random_stall=1和trace_level=port。原combined入口仍保留，不在32GB主机推荐使用。

默认random_stall的生成BFM只随机化control，五个内存master事务延迟仍固定64。首组通过保存在control_only_random_stall，未计入最终背压验收。最终五组另使用tests/support/prefill_axi_stall.json，经实际生成BFM逐通道检查后验收；没有修改综合RTL。工具支持JSON背压文件，参见[AMD cosim_stall文档](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Project-Commands)。该有限背压配置通过不证明所有AXI调度。

普通组验收模式：{json.dumps(nominal_modes, ensure_ascii=False)}。

候选背压组验收模式：{json.dumps(stress_modes, ensure_ascii=False)}。其中max_k原生RTL完整结束但原生回放启动失败，显式POST_CHECK回放实际Y/meta通过；本次原生失败码及RTL前后SHA证明随组保留。

PASS_NATIVE表示原生流程完成；PASS_RECOVERED表示原生工具链失败收据仍保留，当前完整object重新链接后实际XSIM和明确POST_CHECK分别退出0。PASS_POSTCHECK_RECOVERED表示本次原生RTL已有完整结束证据，仅重建明确POST_CHECK并回放实际输出，文件前后SHA不变；未观测的RTL子进程退出码保持null。未把原生退出1改写成0，也未用旧报告替代本次结果。详情见docs/b03/RTL_RECOVERY.md与FAILURE_HISTORY.md。

少数原生通过组还处理过本机停滞的uname系统检测子进程，处理记录随组归档；随后的完整RTL与回放通过才接受。此工具恢复与数值/性能修正分开记录。

完整原始输入/RTL输出/波形保存在本机evidence/b03/batches/<variant>/<group>/，每组manifest列出SHA。交付zip保留这些manifest、实际周期、BFM和日志等紧凑证据，排除巨大tv/wdb文件；固定seed可重生成合成输入。两份真实FP32权重及来源/许可随包提供，排除完整模型。

## 复现与B04交接

本机工具：Vitis/Vivado 2026.1；健康MinGW位于D:/mingw64/bin；本机BusyBox辅助程序位于D:/codex-vitis-shims。runner仅调整进程环境，未安装软件或改全局配置。移机时需提供对应工具路径及辅助程序；六函数公共动态库尚未实现。

移机或解压至另一目录后，先将五个hls_prefill_double_stall_*.cfg的cosim.user_stall更新为包内tests/support/prefill_axi_stall.json的绝对路径；Vitis的该选项不按cfg所在目录解析相对路径。普通验收时的稳定runner另保存在evidence/b03/sw32_nominal_runner/；当前runner增加了JSON输入指纹记录，核与golden保持相同。

```powershell
.\\run_prefill.ps1 -Variant {variant} -Target native
.\\run_prefill.ps1 -Variant {variant} -Target csim
.\\run_prefill.ps1 -Variant {variant} -Target synth
# 普通组依次选择smoke/gate_t1/gate_t8/down_t1/down_t8，归档后才能运行下一组
.\\run_prefill.ps1 -Variant {variant} -Target cosim -Group gate_t8
# 背压组依次选择basic/lifecycle/tail/max_k/max_n
.\\run_prefill.ps1 -Variant {variant} -Target stall -StressGroup max_k
```

后续B04实现sp_linear_v1六个导出函数、BO驻留和同步、超时poisoned生命周期与安全close；取得匹配kv260_base平台后离线链接为xclbin、检查实现时序/资源并交叉编译aarch64。候选XO通过本阶段无板验收，尚不是可直接部署的板端系统。

候选XO SHA256：{sha(xo)}。公共契约SHA256：{manifest['contract_sha256']}。源文件、配置、逐笔周期和退出码均在包内对应manifest/receipt中。

客户端模型/推理/速度选项未经本机文件核实，PROJECT_STATUS.json继续记录unverified；本次没有更改客户端设置。
"""
    (ROOT / "docs/b03/B03_REPORT.md").write_text(report, encoding="utf-8")
    (output / "B03_验收报告.md").write_text(report, encoding="utf-8")
    shutil.copy2(ROOT / "reports/b03/ablation.json", output / "B03_消融结果.json")
    members = set()
    for directory in ("src", "tb", "host", "reference", "tests/support", "tests/numerical", "baseline/b02",
                      "contracts", "docs/b03", "reports/b03", "logs/b03", "artifact/b03_candidate",
                      "evidence/b03/verification", "evidence/b03/sw512_regression/source",
                      "evidence/b03/sw32_nominal_runner", "evidence/b03/tool_failures", "evidence/b03/clean_delivery"):
        members.update(path for path in (ROOT / directory).rglob("*") if path.is_file())
    members.update(ROOT.glob("hls_prefill*.cfg"))
    members.update(ROOT.glob("run_prefill*.ps1"))
    members.update(ROOT / name for name in ("PROJECT_STATUS.json", "AGENTS.md", "README.md", ".gitignore", ".gitattributes"))
    members.update(ROOT / "tools" / name for name in ("archive_prefill_batches.py", "verify_prefill_artifact.py", "verify_prefill_stress.py", "audit_prefill_replay.py", "package_prefill.py", "complete_prefill_postcheck.ps1", "download_model_tensors.py", "check_prefill_os_probe.ps1", "check_prefill_delivery.py"))
    for name in ("gate_proj.fp32.bin", "down_proj.fp32.bin", "source_manifest.json", "LICENSE", "config.json"):
        members.add(ROOT / "vectors/model_source" / name)
    for v in ("baseline", "reuse", "double"):
        for group in (*GROUPS, *("stall_" + g for g in STRESS_COUNTS)):
            folder = ROOT / f"evidence/b03/batches/{v}/{group}"
            if folder.exists():
                members.update(path for path in folder.rglob("*") if path.is_file() and "tv" not in path.relative_to(folder).parts and path.suffix != ".wdb")
    members = {p for p in members if "__pycache__" not in p.parts and p.suffix != ".wdb"}
    payload = {str(p.relative_to(ROOT)).replace("\\", "/"): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(members)}
    if sum(name.endswith(".xo") for name in payload) != 1:
        raise RuntimeError("Delivery must contain exactly one candidate XO")
    archive_path = output / "B03_交付包.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in payload:
            archive.write(ROOT / name, name)
        archive.writestr("B03_package_manifest.json", json.dumps({"candidate": variant, "files": payload,
                         "raw_tv_wdb": "retained on original host; see archived batch manifests"}, indent=2))
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Delivery ZIP CRC failed")
    (output / "B03_交付包.sha256.txt").write_text(f"{sha(archive_path)}  {archive_path.name}\n", encoding="utf-8")
    print(json.dumps({"candidate": variant, "zip": str(archive_path), "bytes": archive_path.stat().st_size,
                      "members": len(payload) + 1, "sha256": sha(archive_path)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=("baseline", "reuse", "double"))
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    build(arguments.variant, arguments.output.resolve())
