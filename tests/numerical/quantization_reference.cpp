// 独立量化自测可单独编译，链接中不包含HLS源码。
#include "../support/quantization_checks.hpp"
int main() {
    try { run_quantization_checks(); return 0; }
    catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
