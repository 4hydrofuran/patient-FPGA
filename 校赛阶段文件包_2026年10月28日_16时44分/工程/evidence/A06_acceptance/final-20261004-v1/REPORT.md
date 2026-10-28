# A06最终验收：离线计算核接收通过

日期：2026-10-04（Asia/Shanghai）。结论：**PASS_A06_OFFLINE_KERNEL_ACCEPTANCE**。本次补齐的是当前e227297 double核的A本地Vitis Csim，不是旧源结果转移。`hw/linear_A/KERNEL_SOURCE.json`已accepted=true/frozen=true，仅允许A07离线链接；不代表实现收敛、B04候选、上板或生产部署验收。

## 本次实际结果

用户新提供的官方`Xilinx (2).lic`绑定当前Host ID `00155dbc29e7`。核对同一WSL boot实例后，独立安装到`/home/member-a/.Xilinx/kv260-a-rehost-20261004.lic`，权限0600。原件和旧许可不变，正文不入仓库、不输出。许可SHA256：`c334722c1bcf29b3a925427b4e19c40067a9d5a734556abade35b7bf7c27ee83`。实际checkout可用性以本次Csim成功为证，不保证WSL重启后MAC固定。

采用原配置、原A04独立C++参考及实际收到的double源码，Linux Vitis2026.1/HLS6493734执行：**61案例、2,800,022检查，exit0，CSim done with 0 errors**。两真实shape 3584/1024、1024/3584均T1..8；K129/N33尾块T1..8、共同手算、重复调用、全零/极值、FP32组序反例、18核错误与10主机拒绝均覆盖。所测Csim输出max_abs=0、FP32逐位一致；这是同数学数值验证，不是量化无损或板测误差为0。

实际完整命令/输出：`csim/csim.json`；配置`csim/acceptance.cfg`与原supplement配置逐字节相同。输入源/头/参考/runner/config指纹与Host ID/boot ID见`csim/host.json`；结果`csim/result.json`。

## 接收版本与冻结身份

| 项目 | 固定值 |
|---|---|
| provider / 维护 | 核来源B；A作接收审定、维护剩余工具；不代B/C签核 |
| source commit | `e227297ee1bb0bdf542fc81761642b23639e15c0` |
| variant / build ID | double / `0xB3030002` |
| 源SHA256 | `7e1eb3450c0839254148c5fecebf4be1b2d76ca7c18f39e8df8e63769d5874d2` |
| XO SHA256 | `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23` |
| XO内主XML SHA256 | `dadfa622dc114a373af9195778f64e34f4d715ea190426fa745dfd39f818d1de` |

1923个B payload文件再次核对原manifest；实际XO与主XML hash吻合。前一增量seal的2020文件核验，允许的治理更新单列（其他A任务更新状态不视作科学证据变化），测试/源产物不得静默改变。原A04参考及sidecar指纹复核，不重做已有效的导出或全模型测试。

## 原A06要求闭环

1. 源码、头、XO、kernel metadata、构建脚本、向量和报告独立保存，原件不修改。
2. 17参数顺序/类型/offset、实际端口、ap_ctrl_hs、40B meta、job/version/error映射已核验，A07说明更新。
3. A04独立PC与本次当前源Csim均通过；测试期望不调用被测核生成。
4. 必需两shape T1..8 Csim、两shape T1/T8 native Cosim原始同版记录均有证据。66笔归档RTL输出已由A04独立回放；本次不重跑未变化的RTL/优化搜索。
5. 器件K26、2026.1、起步6.667ns约150MHz、资源/局部II/访存复用有同XO报告；估计与实板分账。
6. 本地核按上述hash冻结，A07可据实际接口继续封装/链接；无板预算继续null。

逐条机器审计及原数值结果见`AUDIT.json`；冻结确认见`REPORT.json`。前一A序列化修复保持有效：382文件全部与原manifest逐字节SHA一致，原PC50/真实权重4例有效，不重复运行。

## 分域与限制

| 域 | 结果与限制 |
|---|---|
| PC | 原A04独立61例、严格382文件复现等证据复核，不重复计算 |
| A Csim | 本次当前源真实Vitis exit0，61例/2800022检查PASS |
| Cosim | 复用同版必需T1/T8成功证据；全包为65 native PASS＋1 stall_max_k原失败后postcheck恢复，不能写成66 native PASS |
| 综合 | 精确XO报告复用；BRAM18K110、DSP102、FF20848、LUT35817，HLS slack -0.40ns；不是实现收敛 |
| 实现/本轮ARM交叉构建/ARM执行/BOARD | NOT_TESTED；A07既有交叉构建与失败各自保留 |

INT32 helper部分和验证不等于观察RTL内部节点；66笔归档回放参考部分和641472项不是板计数。组2176B、down双整tile119KiB是推导，实际B双group槽4352B；P_N32/P_K1/P_T1。局部II1、逻辑读取字节不能替代全核II/实际AXI带宽。5WDB未附、内部AXI FIFO峰值未测仍列P2。板上功耗/误差/CMA/BO可达预算null。

## 命令、队列与失败保留

本次`check_contracts.py`、`qwen35_config.py`、许可安装、队列提交/运行、最终证据审计均exit0；每条实际argv/cwd/UTC时间/退出码在`commands/*.json`。最终验收日期按Asia/Shanghai记2026-10-04。

实际补测入口：

```text
python3 platform/ra02/build_queue.py submit --owner A --label a06-final-20261004 -- /bin/bash /mnt/c/Patientqwen/platform/qwen35/a06/retry_current_20261004.sh
python3 platform/ra02/build_queue.py run-next
```

队列实际任务`01791049978071771967-A-a06-final-20261004-2033a207`。wrapper只将既有runner的证据目录指向本增量，不改测试/源/配置。此前发现A07 control任务已失败退出1且无相关进程，仅归档其遗留active marker以释放队列，结果和失败未删除、未改判、未代跑A07修复。

历次许可失败、Windows part失败、工具换行/测试/封存失败全部保留；不通过删例、改容差或mock收口。本次源/模型/权重/公共契约无改动；当前脏工作树保留，HEAD仍`ed9df6c7152c908d512ecd1f871583182823e1eb`，无新commit/push。

## 改动与下一步

新增本次许可安装/队列回收/补测/审计脚本与当前证据；更新`hw/linear_A/KERNEL_SOURCE.json`、`A07_KERNEL_INTEGRATION.md`、PROJECT_STATUS、A状态、DESIGN_GAP、TEST_MATRIX和交接。修改前文件在`before/`。

A06到此停止。下一阶段是A07：控制层遗留失败处理、冻结XO的真实kv260_base链接/布局布线与配套核查。A07/B04整体仍未通过，不能凭本报告消费PL或刷写。请保持WSL终端开启；重启后需重新核对许可Host ID，而不是假定绑定永久稳定。
