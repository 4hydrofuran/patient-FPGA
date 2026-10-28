// B3 合成向量 testbench：独立行主序 golden、32-lane 部分和、真实尺寸与错误语义。

// 引入冻结 ABI 和被测实际 32-lane 数据通路声明。
#ifdef B01_BASELINE
#include "../baseline/b2/src/w4a8_linear_v1.hpp"
#else
#include "../src/w4a8_linear_v1.hpp"
#endif
#include "../host/linear_validation.hpp"
#include "../tests/support/quantization_checks.hpp"

// 期望值来自未打包矩阵的独立参考，绝不把 HLS 函数当作 expected。
#include "golden_w4a8.hpp"

// 测试端容器与文件操作不进入硬件综合。
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

#ifdef B02_CACHE_X
constexpr const char* kStageLabel = "B02";
#else
constexpr const char* kStageLabel = "B01";
#endif

// 联合仿真包装器会复制完整 depth，所有用例必须为每个端口预留该窗口。
constexpr std::size_t kWDepth = 2179072U;
constexpr std::size_t kSwDepth = 34048U;
constexpr std::size_t kXDepth = 38912U;
constexpr std::size_t kSxDepth = 8U;
constexpr std::size_t kYDepth = 38912U;

// 检查计数用于审计 PASS 实际覆盖了多少整数项与输出项。
std::uint64_t partial_checks = 0;
std::uint64_t output_checks = 0;
std::uint64_t transactions = 0;

// 所有断言失败均以非零进程退出，使 native/CSim/Cosim 都能判定失败。
void check(bool condition, const std::string& message) {

    // 报错保留明确用例和坐标，而不是只报告误差总数。
    if (!condition) {

        // testbench 可抛异常；该语句不属于可综合源码。
        throw std::runtime_error(message);
    }
}

// 使用明确算法而非实现相关的随机分布，保证同一个 seed 可跨工具复现。
std::uint32_t next_random(std::uint32_t& state) {

    // xorshift32 的移位和异或均为固定宽度无符号运算。
    state ^= state << 13U;
    state ^= state >> 17U;
    state ^= state << 5U;

    // 向量 manifest 记录初始 seed，运行时不使用时钟作为随机源。
    return state;
}

// 在核缓冲之外保留独立 dense 数学输入，避免 packed 寻址错误污染 golden。
struct Case {
    std::string name;
    std::uint32_t t, n, k, np, kp, groups, seed;
    std::vector<std::int8_t> dense_w;
    std::vector<float> dense_sw;
    std::vector<std::uint8_t> w;
    std::vector<float> sw;
    std::vector<std::int8_t> x;
    std::vector<float> sx;
    std::vector<float> y;
    bool public_case = false;
    w4a8_b2::KernelMeta meta{};

    // 每个端口额外留一个软件 guard；RTL 包装器只拷贝 depth，不应访问 guard。
    Case(const std::string& label, std::uint32_t tokens, std::uint32_t outputs,
         std::uint32_t inputs, std::uint32_t random_seed)
        : name(label), t(tokens), n(outputs), k(inputs), np((outputs + 31U) / 32U * 32U),
          kp((inputs + 127U) / 128U * 128U), groups(kp / 128U), seed(random_seed),
          dense_w(static_cast<std::size_t>(n) * k, 0), dense_sw(static_cast<std::size_t>(n) * groups, 1.0F),
          w(kWDepth + 1U, 0U), sw(kSwDepth + 1U, 1.0F), x(kXDepth + 1U, 0),
          sx(kSxDepth + 1U, 1.0F), y(kYDepth + 1U, -1234.5F) {

        // 确认所有测试尺寸位于本轮 cosim 窗口，不让包装器越界。
        check(static_cast<std::size_t>(np) * kp / 2U <= kWDepth &&
              static_cast<std::size_t>(np) * groups <= kSwDepth &&
              static_cast<std::size_t>(t) * kp <= kXDepth &&
              static_cast<std::size_t>(t) * np <= kYDepth, "cosim depth too small: " + name);
    }
};

// 生成合法 W4/A8、逐组不同的二进制精确 scale 和零 padding。
void fill_random(Case& c, bool zero = false, bool extremes = false, bool nonbinary = false) {

    // 随机状态只由该用例记录的固定 seed 决定。
    std::uint32_t state = c.seed;

    // 行主序 dense 权重是 golden 的数学输入，不依赖 tile 地址公式。
    for (std::size_t i = 0; i < c.dense_w.size(); ++i) {

        // W4 保留 -8 不出现在合法向量中，极值用例覆盖 -7 与 7。
        c.dense_w[i] = zero ? 0 : extremes ? (i & 1U ? -7 : 7) : static_cast<std::int8_t>(static_cast<int>(next_random(state) % 15U) - 7);
    }

    // 只填充真实 K，填充的 A8 始终为零。
    for (std::uint32_t token = 0; token < c.t; ++token) {

        // 多 token 测试用于兼容性，首轮吞吐优化目标仍只针对 T=1。
        c.sx[token] = nonbinary ? (0.3F + token * 0.013F) : std::ldexp(1.0F, -static_cast<int>(token % 4U + 1U));

        // A8 合法极值采用对称范围 -127..127。
        for (std::uint32_t col = 0; col < c.k; ++col) {

            // 该激活元素将被同一个 tile 的所有输出 lane 复用。
            c.x[static_cast<std::size_t>(token) * c.kp + col] = zero ? 0 : extremes ? (col & 1U ? -127 : 127) : static_cast<std::int8_t>(static_cast<int>(next_random(state) % 255U) - 127);
        }
    }

    // 不同输出、不同 group 都采用不同 scale，检测跨组恢复错误。
    for (std::size_t i = 0; i < c.dense_sw.size(); ++i) {

        // 非二进制小样例额外检查一般 FP32 舍入，其他样例便于严格数值对照。
        c.dense_sw[i] = nonbinary ? 0.07F + static_cast<float>(i % 7U) * 0.013F : std::ldexp(1.0F, -static_cast<int>(next_random(state) % 5U + 3U));
    }
}

// 由 dense 输入按 tile→group→输入位置→lane-pair 的物理遍历顺序打包。
void pack(Case& c) {

    // 顺序追加 packed 字节，避免与核共享一个随机地址辅助函数。
    std::size_t cursor = 0;

    // 每个输出 tile 始终占满 32 lane，尾部补数学零值。
    for (std::uint32_t block = 0; block < c.np / 32U; ++block) {

        // 各 K group 都对应 2048 个连续权重字节。
        for (std::uint32_t group = 0; group < c.groups; ++group) {

            // scale 的物理排列是 tile、group、输出 lane。
            for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                // padded 输出行的 scale 不影响最终清零，但仍占据完整位置。
                c.sw[(static_cast<std::size_t>(block) * c.groups + group) * 32U + lane] = block * 32U + lane < c.n ? c.dense_sw[static_cast<std::size_t>(block * 32U + lane) * c.groups + group] : 1.0F;
            }

            // 输入位置外层使同一位置的 32 权重连续排列。
            for (std::uint32_t r = 0; r < 128U; ++r) {

                // 每个字节将两条相邻 lane 分别放在低、高半字节。
                for (std::uint32_t pair = 0; pair < 16U; ++pair) {

                    // 当前物理位置对应两行相同列的数学权重。
                    const std::uint32_t row = block * 32U + pair * 2U;
                    const std::uint32_t col = group * 128U + r;

                    // 独立 row-major 输入访问，不调用核的 decode 或 offset 函数。
                    const std::uint8_t low = row < c.n && col < c.k ? static_cast<std::uint8_t>(c.dense_w[static_cast<std::size_t>(row) * c.k + col]) & 15U : 0U;
                    const std::uint8_t high = row + 1U < c.n && col < c.k ? static_cast<std::uint8_t>(c.dense_w[static_cast<std::size_t>(row + 1U) * c.k + col]) & 15U : 0U;

                    // cursor 严格递增，因此布局错误不会由共享地址函数互相抵消。
                    c.w[cursor++] = static_cast<std::uint8_t>(low | (high << 4U));
                }
            }
        }
    }

    // 完整填充矩阵必须恰好占用冻结公式规定的字节数。
    check(cursor == static_cast<std::size_t>(c.np) * c.kp / 2U, "packed length: " + c.name);
}

// 统一记录顶层事务，所有长度均为业务缓冲字节数而非 cosim 预留容量。
void invoke(Case& c, std::uint64_t job, std::uint32_t abi = 1U,
            bool short_weight = false, bool bad_dimension = false) {

    // 完整 tile 的权重长度严格按冻结布局计算。
    const std::uint64_t weight_bytes = static_cast<std::uint64_t>(c.np) * c.kp / 2ULL;

    // 被测顶层保持 B2 的参数顺序、类型、bundle 和状态语义。
    w4a8_linear_v1(c.w.data(), c.sw.data(), c.x.data(), c.sx.data(), c.y.data(), &c.meta,
                   bad_dimension ? 0U : c.t, c.n, c.k,
                   short_weight ? weight_bytes - 1ULL : weight_bytes,
                   static_cast<std::uint64_t>(c.np) * c.groups * 4ULL,
                   static_cast<std::uint64_t>(c.t) * c.kp, c.t * 4ULL,
                   static_cast<std::uint64_t>(c.t) * c.np * 4ULL, 40ULL, job, abi);

    // 该计数只叫测试事务数，不称为 FPGA 时钟周期。
    ++transactions;
}

// 在软件/Csim 中直接观察与顶层相同的 32-lane 子数据通路并逐组精确比对。
void check_partials(const Case& c, const GoldenResult& expected) {

    // 固定 32 个部分和与核当前组缓存大小一致。
    std::int32_t observed[32];

    // 对每个 token 检查全部有效输出和所有量化组。
    for (std::uint32_t token = 0; token < c.t; ++token) {

        // 每次辅助调用覆盖一个完整输出 tile。
        for (std::uint32_t block = 0; block < c.np / 32U; ++block) {

            // 部分和不跨组合并，因此能定位某个 group 的解包或乘加错误。
            for (std::uint32_t group = 0; group < c.groups; ++group) {

                // 观察值来自被测 helper，expected 始终来自 dense golden。
#ifdef B01_BASELINE
                // 旧B2独立helper逐lane对照，同样不用于生成expected。
                for (std::uint32_t lane=0; lane<32U; ++lane) {
                    observed[lane]=w4a8_group_sum(c.w.data(),c.x.data(),block,lane,group,c.groups,token,c.kp);
                }
#else
                w4a8_tile_group_sums(c.w.data() + (static_cast<std::size_t>(block) * c.groups + group) * 2048U,
                                     c.x.data() + static_cast<std::size_t>(token) * c.kp + group * 128U, observed);
#endif

                // N padding 没有数学输出，只检查实际有效的 lane。
                for (std::uint32_t lane = 0; lane < 32U && block * 32U + lane < c.n; ++lane) {

                    // token、row、group 的索引属于独立 golden 格式。
                    const std::size_t index = (static_cast<std::size_t>(token) * c.np + block * 32U + lane) * c.groups + group;

                    // 整数检查绝不使用误差阈值。
                    check(observed[lane] == expected.partials[index], c.name + " partial token=" + std::to_string(token) + " row=" + std::to_string(block * 32U + lane) + " group=" + std::to_string(group));

                    // 统计实际覆盖的整数元素，而非只计用例数量。
                    ++partial_checks;
                }
            }
        }
    }
}

// 保存可交给 A 回放的实际字节；向量目录由运行脚本预先创建。
template <typename T>
void dump_binary(const std::string& path, const std::vector<T>& values, std::size_t count) {

    // Windows 本机为小端，manifest 将明确记录二进制字节序。
    std::ofstream file(path, std::ios::binary);

    // 路径不可写时直接使测试失败，不能声称已保存输入。
    check(static_cast<bool>(file), "cannot write vector: " + path);

    // 仅导出实际业务长度，不把包装器预留的空窗口当成输入数据。
    file.write(reinterpret_cast<const char*>(values.data()), static_cast<std::streamsize>(count * sizeof(T)));

    // 写入失败也必须留下非零退出码。
    check(static_cast<bool>(file), "vector write failed: " + path);
}

// 一个合法用例同时核对独立 partial、FP32 输出、元数据、padding 和连续第二次调用。
void run_case(Case& c, const std::string& dump_dir, bool repeat = false) {

    // 每个用例从其独立数学输入产生 golden，绝不读 HLS 结果生成期望。
    const GoldenResult expected = golden_dense(c.t, c.n, c.k, c.np, c.kp, c.dense_w, c.dense_sw, c.x, c.sx);

    // native 阶段可导出全部输入和 expected，Vitis 默认仅执行功能回归。
    if (!dump_dir.empty()) {

        // 所有文件共享用例名称，hash 清单可以绑定其真实字节。
        const std::string prefix = dump_dir + "/" + c.name;

        // 导出主机可以直接分配并同步到 BO 的六类业务数据。
        dump_binary(prefix + ".w_packed.bin", c.w, static_cast<std::size_t>(c.np) * c.kp / 2U);
        dump_binary(prefix + ".sw.bin", c.sw, static_cast<std::size_t>(c.np) * c.groups);
        dump_binary(prefix + ".xq.bin", c.x, static_cast<std::size_t>(c.t) * c.kp);
        dump_binary(prefix + ".sx.bin", c.sx, c.t);
        dump_binary(prefix + ".expected_y.bin", expected.y, expected.y.size());
        dump_binary(prefix + ".expected_partials.bin", expected.partials, expected.partials.size());

        // 行主序权重与 scale 允许另一实现重新计算 golden，而非只能信任 expected 文件。
        dump_binary(prefix + ".dense_w.bin", c.dense_w, c.dense_w.size());
        dump_binary(prefix + ".dense_sw.bin", c.dense_sw, c.dense_sw.size());

        // 每个样例明确标记合成来源，不能混称模型真实张量。
        std::ofstream description(prefix + ".json");

        // 保存维度、seed 和二进制格式，工具间可独立回放。
        description << "{\"case\":\"" << c.name << "\",\"source\":\"synthetic\",\"seed\":" << c.seed
                    << ",\"T\":" << c.t << ",\"N\":" << c.n << ",\"K\":" << c.k
                    << ",\"Np\":" << c.np << ",\"Kp\":" << c.kp << ",\"G\":" << c.groups
                    << ",\"endianness\":\"little\",\"absolute_fp32_tolerance\":" << (c.public_case ? 1e-4 : 1e-6) << ",\"relative_fp32_tolerance\":" << (c.public_case ? 1e-5 : 0.0) << ",\"partials_layout\":\"T,Np,G\"}\n";

        // JSON 写失败也影响最终验收状态。
        check(static_cast<bool>(description), "case metadata write: " + c.name);
    }

    // 检查实际 32-lane helper；这不是对 RTL 内部信号的直接观测。
    check_partials(c, expected);

    // 给完成计数明确的初值，使多次调用行为可重复。
    c.meta.hw_completed_count = 41ULL;

    // 软件计时不能替代核周期，testbench 只给输入与结果的功能证据。
    invoke(c, 1000ULL + transactions);

    // 元数据与冻结布局一致，构建标识使用本轮 B3 版本。
    check(c.meta.status == 0U && c.meta.done == 1U && c.meta.abi_magic == 0x57344138U &&
          c.meta.kernel_build_id == w4a8_b2::kKernelBuildId && c.meta.hw_completed_count == 42ULL &&
          c.meta.job_id == 999ULL + transactions &&
          c.meta.algorithm_weight_bytes == static_cast<std::uint64_t>(c.np) * c.kp / 2ULL, "meta: " + c.name);

    // 新形状按公共atol/rtol；历史用例保留原1e-6门槛，不混改旧证据。
    double squared_error=0.0, squared_reference=0.0;
    float maximum_error=0.0F;
    const float atol=c.public_case ? 1.0e-4F : 1.0e-6F;
    const float rtol=c.public_case ? 1.0e-5F : 0.0F;
    for (std::size_t i = 0; i < expected.y.size(); ++i) {

        // 一旦超过阈值，保存首个坐标和实际数值便于回放。
        check(std::isfinite(c.y[i]) && std::fabs(c.y[i] - expected.y[i]) <= atol + rtol * std::fabs(expected.y[i]),
              c.name + " y[" + std::to_string(i) + "] expected=" + std::to_string(expected.y[i]) + " observed=" + std::to_string(c.y[i]));

        // 统计实际误差与参考能量，NRMSE只作为数值诊断，不作性能指标。
        const double error=static_cast<double>(c.y[i])-expected.y[i];
        squared_error+=error*error;
        squared_reference+=static_cast<double>(expected.y[i])*expected.y[i];
        maximum_error=std::max(maximum_error,std::fabs(c.y[i]-expected.y[i]));
        ++output_checks;
    }

    // 检查逻辑输出结束到 cosim 窗口结束之间没有多余写入。
    for (std::size_t i = expected.y.size(); i < c.y.size(); ++i) {

        // 软件 guard 和业务窗口后的 sentinel 保持原值。
        check(c.y[i] == -1234.5F, "output guard: " + c.name);
    }

    // 重复调用复用相同 BO，以不同 job 检查状态和累计计数。
    if (repeat) {

        // 再次执行完整矩阵，而不是仅调用一个 tile。
        invoke(c, 7777ULL);

        // job_id 和完成计数必须来自第二次调用。
        check(c.meta.job_id == 7777ULL && c.meta.hw_completed_count == 43ULL && c.meta.status == 0U && c.meta.done == 1U, "repeat meta: " + c.name);

        // 复用缓冲后的全部输出仍与独立 golden 一致。
        for (std::size_t i = 0; i < expected.y.size(); ++i) {

            // 检查第二次调用没有保留前次内部累加状态。
            check(std::isfinite(c.y[i]) && std::fabs(c.y[i] - expected.y[i]) <= atol + rtol * std::fabs(expected.y[i]), "repeat output: " + c.name);
        }
    }

    const double nrmse=squared_reference==0.0 ? (squared_error==0.0 ? 0.0 : std::numeric_limits<double>::infinity()) : std::sqrt(squared_error/squared_reference);
    std::cout << "METRICS case=" << c.name << " max_abs=" << maximum_error << " nrmse=" << nrmse << " atol=" << atol << " rtol=" << rtol << '\n';
    // 日志逐条列出真实检查的形状，避免仅一个笼统 PASS。
    std::cout << "PASS case=" << c.name << " T=" << c.t << " N=" << c.n << " K=" << c.k << " source=synthetic seed=" << c.seed << '\n';
}

// ABI、长度、维度和位于最后有效 lane 的保留码都必须拒绝且不写 y。
void run_error_cases() {

    // 使用跨 tile、跨 group 形状，使最后位置判错能检查无部分输出保证。
    Case c("errors", 1U, 33U, 129U, 0x7654321U);

    // 先建立合法数据，错误仅改变一个因素。
    fill_random(c);
    pack(c);

    // 累计计数在错误调用后不得增长。
    c.meta.hw_completed_count = 19ULL;

    // ABI 版本错误在访问数学数据前返回。
    invoke(c, 9001ULL, 2U);
    check(c.meta.status == 1U && c.meta.done == 1U && c.meta.job_id == 9001ULL && c.meta.hw_completed_count == 19ULL, "bad ABI metadata");

    // 权重 BO 长度短一个字节也必须拒绝。
    invoke(c, 9002ULL, 1U, true);
    check(c.meta.status == 3U && c.meta.hw_completed_count == 19ULL && c.meta.done == 1U, "bad length metadata");

    // 零 token 是被冻结容量规则拒绝的维度。
    invoke(c, 9003ULL, 1U, false, true);
    check(c.meta.status == 2U && c.meta.hw_completed_count == 19ULL && c.meta.done == 1U, "bad dimension metadata");

    // N=33、K=129 的最后有效权重位于第二个 tile、第二个 group 的首个低半字节。
    c.w[3U * 2048U] = static_cast<std::uint8_t>((c.w[3U * 2048U] & 0xF0U) | 8U);

    // 非法码在完整扫描结束后返回，不允许前面 tile 已经写出。
    invoke(c, 9004ULL);
    check(c.meta.status == 5U && c.meta.done == 1U && c.meta.job_id == 9004ULL && c.meta.hw_completed_count == 19ULL, "late reserved-code metadata");

    // 核必须保留整个输出窗口原值，而不仅第一个输出。
    for (float value : c.y) {

        // 所有错误调用均遵守冻结的输出不变约定。
        check(value == -1234.5F, "error wrote partial output");
    }

    // 单独构造高半字节有效的非法权重，避免只检低半字节的漏洞。
    Case high("high_reserved", 1U, 2U, 1U, 1U);

    // lane1 是有效行，因此高半字节 0x8 必须拒绝。
    high.w[0] = 0x80U;
    invoke(high, 9005ULL);
    check(high.meta.status == 5U && high.y[0] == -1234.5F, "valid high nibble not rejected");

    // 错误事务也单独留痕，不混在合法数值用例数量中。
    std::cout << "PASS errors=bad_abi,bad_length,bad_dimension,late_reserved_code,high_nibble\n";
}


// 公共主机校验与旧核错误域分开。拒绝时不启动核、不修改meta、不消费上次Y。
void run_public_errors() {
    Case c("public_errors",1U,33U,129U,0x20261002U);
    fill_random(c); pack(c);
    c.meta.hw_completed_count=19;
    unsigned checks=0;
    auto request=[&]() { return host_b::Request{c.t,c.n,c.k,c.w.data(),c.sw.data(),c.x.data(),c.sx.data(),c.y.data(),
        static_cast<std::uint64_t>(c.np)*c.kp/2U,static_cast<std::uint64_t>(c.np)*c.groups*4U,
        static_cast<std::uint64_t>(c.t)*c.kp,c.t*4U,static_cast<std::uint64_t>(c.t)*c.np*4U,55}; };
    auto reject=[&](host_b::Request r, int expected, const char* label) {
        const auto saved_meta=c.meta;
        const auto saved_y=c.y;
        const auto saved_transactions=transactions;
        const int code=host_b::validate(r);
        if(code==SP_OK) invoke(c,r.job);
        check(code==expected && std::memcmp(&c.meta,&saved_meta,sizeof(saved_meta))==0 && c.y==saved_y && transactions==saved_transactions,label);
        ++checks;
        std::cout << "PASS host_rejection=" << label << " public_status=" << code << " kernel_started=false output_consumed=false\n";
    };
    check(host_b::validate(request())==SP_OK,"valid public request");
    auto r=request();r.job=0;reject(r,SP_BAD_ARGUMENT,"zero_job");
    r=request();r.t=0;reject(r,SP_BAD_ARGUMENT,"zero_t");
    r=request();r.t=9;reject(r,SP_BAD_ARGUMENT,"t_overflow");
    r=request();r.n=4865;reject(r,SP_BAD_ARGUMENT,"n_overflow");
    r=request();r.k=0;reject(r,SP_BAD_ARGUMENT,"zero_k");
    r=request();r.w=nullptr;reject(r,SP_BAD_ARGUMENT,"null_weight");
    r=request();r.sw=nullptr;reject(r,SP_BAD_ARGUMENT,"null_sw");
    r=request();r.x=nullptr;reject(r,SP_BAD_ARGUMENT,"null_x");
    r=request();r.sx=nullptr;reject(r,SP_BAD_ARGUMENT,"null_sx");
    r=request();r.y=nullptr;reject(r,SP_BAD_ARGUMENT,"null_y");
    r=request();--r.wb;reject(r,SP_BUFFER_TOO_SMALL,"short_weight");
    r=request();--r.swb;reject(r,SP_BUFFER_TOO_SMALL,"short_sw");
    r=request();--r.xb;reject(r,SP_BUFFER_TOO_SMALL,"short_x");
    r=request();--r.sxb;reject(r,SP_BUFFER_TOO_SMALL,"short_sx");
    r=request();--r.yb;reject(r,SP_BUFFER_TOO_SMALL,"short_y");
    const auto original_x=c.x;
    c.x[0]=-128;reject(request(),SP_NUMERIC_ERROR,"reserved_a8");c.x=original_x;
    c.x[c.k]=1;reject(request(),SP_NUMERIC_ERROR,"activation_padding");c.x=original_x;
    const auto original_w=c.w;
    c.w[0]=(c.w[0]&0xf0U)|8U;reject(request(),SP_NUMERIC_ERROR,"reserved_w4_low");c.w=original_w;
    c.w[0]=(c.w[0]&0x0fU)|0x80U;reject(request(),SP_NUMERIC_ERROR,"reserved_w4_high");c.w=original_w;
    c.w[3U*2048U+16U]=1;reject(request(),SP_NUMERIC_ERROR,"weight_k_padding");c.w=original_w;
    c.w[3U*2048U]|=0x10U;reject(request(),SP_NUMERIC_ERROR,"weight_n_padding");c.w=original_w;
    const auto original_sw=c.sw;
    c.sw[3U*32U+1U]=2.0F;reject(request(),SP_NUMERIC_ERROR,"scale_padding");c.sw=original_sw;
    const float invalid[]={0.0F,-1.0F,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity()};
    const char* labels[]={"zero","negative","nan","positive_inf","negative_inf"};
    for(unsigned i=0;i<5;++i) {
        c.sw[0]=invalid[i];reject(request(),SP_NUMERIC_ERROR,(std::string("sw_")+labels[i]).c_str());c.sw=original_sw;
        c.sx[0]=invalid[i];reject(request(),SP_NUMERIC_ERROR,(std::string("sx_")+labels[i]).c_str());c.sx[0]=1.0F;
    }
    std::cout << "PASS host_validation rejection_cases=" << checks << " domain=HOST_ADAPTER\n";
}

// 重复job不当作去重键；每次成功都递增真实核写回的完成计数。
void run_repeat_jobs(const std::string& dump_dir) {
    Case c("repeat_jobs",2U,33U,129U,0x20261002U+32U);
    fill_random(c);pack(c);run_case(c,dump_dir,true);
    const auto saved=c.y;
    invoke(c,7777ULL);
    check(c.meta.job_id==7777ULL && c.meta.hw_completed_count==44ULL && c.y==saved,"same job repeated");
    invoke(c,8888ULL);
    check(c.meta.job_id==8888ULL && c.meta.hw_completed_count==45ULL && c.y==saved,"different job repeated");
    const auto byte=c.w[0];c.w[0]=(byte&0xf0U)|8U;
    invoke(c,8888ULL);
    check(c.meta.status==5 && c.meta.hw_completed_count==45ULL && c.y==saved,"failed run must not consume old output");
    c.w[0]=byte;invoke(c,9999ULL);
    check(c.meta.status==0 && c.meta.job_id==9999ULL && c.meta.hw_completed_count==46ULL && c.y==saved,"valid recovery after input error");
    std::cout << "PASS repeat_jobs same_and_different=verified successes=5 rejected=1 kernel_count=46 output_consumed_on_error=false\n";
}

}  // namespace

// full 覆盖四种真实尺寸；cosim 覆盖代表性 up/down；smoke 仅跑较短边界回归。
int main(int argc, char** argv) {

    // 默认直接运行完整合成测试；脚本通过显式参数选择联合仿真子集。
    std::string suite = "full";
    std::string dump_dir;

    // 参数只影响测试规模和落盘位置，不改变核的数学或 ABI。
    for (int i = 1; i < argc; ++i) {

        // 仅接受有文档的 suite 和 dump 参数，防止静默运行错误子集。
        if (std::string(argv[i]) == "--suite" && i + 1 < argc) {
            suite = argv[++i];
        } else if (std::string(argv[i]) == "--dump" && i + 1 < argc) {
            dump_dir = argv[++i];
        } else {
            std::cerr << "Unknown/incomplete argument: " << argv[i] << '\n';
            return 2;
        }
    }

    // 所有 testbench 异常转换为明确 FAIL 和非零退出，方便 Vitis 归档输入。
    try {

        // 不允许拼写错误导致误以为已跑完整真实尺寸回归。
        check(suite == "full" || suite == "cosim" || suite == "smoke", "unknown suite: " + suite);

        // 固定手算样例同时钉住 nibble 顺序和原 B1 的结果。
        Case hand("hand_sample", 1U, 2U, 2U, 1U);
        hand.dense_w = {7, -1, -7, 2};
        hand.x[0] = 127;
        hand.x[1] = -1;
        pack(hand);
        check(hand.w[0] == 0x97U && hand.w[16] == 0x2FU, "hand packed bytes");
        run_case(hand, dump_dir, true);
        check(hand.y[0] == 890.0F && hand.y[1] == -891.0F, "B1 hand expected");

        // 覆盖满 tile、跨 N/K 尾块、全零、正负极值与既有多 token 功能。
        const std::uint32_t shapes[][3] = {{1,32,128},{1,33,129},{1,65,257},{1,1,1},{1,33,129},{1,32,128},{4,33,129},{8,1,1},{1,32,128}};
        const char* names[] = {"tile_random","nk_tail","three_groups","single","zeros","extremes","t4_compat","t8_compat","nonbinary_scale"};

        // 每个样例拥有独立 seed；合成输入在原始文件中固定保存。
        for (std::size_t i = 0; i < 9U; ++i) {
            Case c(names[i], shapes[i][0], shapes[i][1], shapes[i][2], 0x20261001U + static_cast<std::uint32_t>(i));
            fill_random(c, i == 4U, i == 5U, i == 8U);
            pack(c);
            run_case(c, dump_dir);
        }

        // N/K padding 中的保留码依然允许，只有有效矩阵区域才参与拒绝。
        Case padding("padding_reserved", 1U, 1U, 1U, 17U);
        padding.dense_w[0] = 3;
        padding.x[0] = 2;
        pack(padding);
        padding.w[0] |= 0x80U;
        padding.w[16] = 8U;
        run_case(padding, dump_dir);
        check(padding.y[0] == 6.0F, "padding ignored");

        // 所有参考/适配层检查是主机端测试，不能声明观测RTL内部分支。
        run_quantization_checks();
        run_public_errors();
        run_repeat_jobs(dump_dir);
        // 任一私有核错误事务必须保留全部 y，且不得增加完成计数。
        run_error_cases();

        if (suite != "smoke") {
            if(suite=="full") {
                const std::uint32_t old_shapes[][2]={{4864,896},{896,4864},{896,896},{128,896}};
                const char* old_names[]={"mlp_up_synthetic","mlp_down_synthetic","projection_synthetic","small_projection_synthetic"};
                for(unsigned i=0;i<4;++i) {
                    Case c(old_names[i],1U,old_shapes[i][0],old_shapes[i][1],0x48640896U+i);
                    fill_random(c);pack(c);run_case(c,dump_dir);
                }
            }
            const std::uint32_t shapes[][2]={{3584,1024},{1024,3584}};
            const char* names[]={"qwen35_gate_up_t","qwen35_down_t"};
            for(unsigned shape=0;shape<2;++shape) {
                const unsigned last=suite=="cosim" ? 1U : 8U;
                for(unsigned t=1;t<=last;++t) {
                    Case c(std::string(names[shape])+std::to_string(t),t,shapes[shape][0],shapes[shape][1],0x20261002U+shape*256U+t);
                    c.public_case=true;
                    fill_random(c,false,false,true);pack(c);
                    const host_b::Request r{c.t,c.n,c.k,c.w.data(),c.sw.data(),c.x.data(),c.sx.data(),c.y.data(),
                        static_cast<std::uint64_t>(c.np)*c.kp/2U,static_cast<std::uint64_t>(c.np)*c.groups*4U,
                        static_cast<std::uint64_t>(c.t)*c.kp,c.t*4U,static_cast<std::uint64_t>(c.t)*c.np*4U,100};
                    check(host_b::validate(r)==SP_OK,"new-shape public inputs");
                    run_case(c,dump_dir);
                }
            }
        }
        // PASS 包括输入来源、suite、事务数与逐项比较计数，避免将合成数据说成训练集。
        std::cout << kStageLabel << " PASS suite=" << suite << " source=synthetic transactions=" << transactions
                  << " int32_partial_checks=" << partial_checks << " fp32_output_checks=" << output_checks << '\n';

        // 只有全部检查通过才返回成功。
        return 0;
    } catch (const std::exception& error) {

        // 首个失败携带用例坐标，可用已落盘或固定 seed 输入复现。
        std::cerr << kStageLabel << " FAIL: " << error.what() << '\n';

        // Vitis 与自动化都可通过非零返回值判失败。
        return 1;
    }
}
