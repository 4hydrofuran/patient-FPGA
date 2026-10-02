# B00 模块接口检查

公共契约为 contracts/sp_linear_v1.h 与 quant_v1.json，contract_sha256=83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6。
六个符号为 open/load/run/report/unload/close，接口文件原样复制。B00 只检查声明与模块边界；真实导出和 XRT 库实现安排在 B04，不以头文件编译代替实现。

| 检查项 | 现状 | 后续落实 |
|---|---|---|
| 新模型目标 | gate/up N3584 K1024；down N1024 K3584；T1..8 均在既有容量内 | B01 实际生成与执行新形状测试 |
| W4 分组与打包 | group128/tile32，偶 lane 低 nibble；与公共规范一致 | 固定字节 fixture 交叉核对 |
| 数值顺序 | INT32 每组；(float(sum)*Sw)*Sx，group 升序累加 | 不改 fast-math/FMA 顺序 |
| 内部 ABI | w4a8_linear_v1，17 参数，40 字节 KernelMeta，B3 build 0xB3000001 | 作为私有实现，不映射为公共文件格式 |
| 公共 ABI | 不透明 ctx、uint64 权重句柄、六个 C 函数 | B04 封装，A 无需内部头文件 |
| scale 与 A8 校验 | 旧核未完整拒绝非有限/非正 scale 与 A8 -128 | 公共主机适配层验证，B01 增负例 |
| padding | 旧核忽略有效区外 W4 保留码；公共输入要求 padding W/X=0、Sw=1 | 库边界实施公共输入规则，保留历史内部测试 |
| 输出容差 | 旧回归 1e-6 绝对误差；公共验收 atol1e-4+rtol1e-5 | 历史阈值保持，新模型独立按冻结公共门槛并报 NRMSE |
| 错误与计数 | 旧核失败不写 Y，meta 首次清零，成功计数由核回写 | 软件状态码不能直接冒充核状态码 |
| 生命周期 | 尚无权重所有权、POISONED、BUSY、超时恢复实现 | B04 验证；超时不释放可能仍被访问 BO |
| T8 Cosim 窗口 | X/Y 当前均 4864 元素，不覆盖新尺寸 T8 | 两种目标均需最大28672元素；若验全容量T8则38912，B01调整TB与depth |

公共调用关系：运行时量化输入 → sp_linear_run_v1 → B库校验/同步 → 私有核 → 校验meta/job → 成功才返回可消费Y。
权重 load 成功后由库持有；库与 xclbin 成套；未知板卡/platform/XRT资料为 null，不猜测。
