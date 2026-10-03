// B04：将实际归档 RTL 的 40 字节 meta 送入 B 独立验收器，输出结构化结果。
#include "../../host/b04_private_probe.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

// 输入为本地字节文件；命令行路径由 Python 使用 ASCII 相对目录传递。
int main(int argc, char** argv) {
    try {
        if (argc != 5) return 2;
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) return 3;
        std::vector<std::uint8_t> data((std::istreambuf_iterator<char>(input)), {});
        const auto result = b04::inspect_completion(data.data(), data.size(),
            std::stoull(argv[2]), std::stoull(argv[3]), std::stoull(argv[4]));
        std::cout << "{\"public_status\":" << result.public_status
                  << ",\"issue\":\"" << b04::issue_name(result.issue)
                  << "\",\"consume_y\":" << (result.consume_y ? "true" : "false")
                  << ",\"private_status\":" << result.meta.status
                  << ",\"done\":" << result.meta.done
                  << ",\"completed_count\":" << result.meta.completed_count << "}\n";
        return 0;
    } catch (...) {
        std::cerr << "B04 meta probe argument or I/O error\n";
        return 4;
    }
}
