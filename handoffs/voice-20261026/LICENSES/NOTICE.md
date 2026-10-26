# 许可说明

各源文件保留原版权与SPDX；本交接不新增统一许可。

- Linux派生DMA/驱动对应源和GPL-2全文已附带。
- `project/board-kernel1036/Makefile`保留实际四模块构建原件；附加`Kbuild`列出五模块，
  可用精确1036头文件与A53交叉工具链在该目录构建。
- 对应Ubuntu内核为linux-xilinx 6.8.0-1036.37，原始源/头文件来自Ubuntu官方仓库：
  https://ports.ubuntu.com/ubuntu-ports/pool/universe/l/linux-xilinx/
  精确头文件与源文件指纹见`../evidence/kernel1036-provenance.json`。
- sherpa-onnx、ASR、Vocos及Matcha/Baker的声明与限制见资源锁。模型权重与私有ARM包不在本交接中。
- 厂家参考例程仅保留引用与审查结论，没有把未核清完整许可的厂家工程加入本包。
