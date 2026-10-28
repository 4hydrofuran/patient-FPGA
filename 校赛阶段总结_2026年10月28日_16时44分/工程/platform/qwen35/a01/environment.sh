#!/usr/bin/env bash
set -euo pipefail
lscpu
free -h
g++ --version
cmake --version
python3 -c 'import sys,jinja2; print(sys.version); print("jinja2",jinja2.__version__)'
grep -E 'CMAKE_CXX_FLAGS_RELEASE|GGML_NATIVE:|GGML_CUDA:|GGML_VULKAN:|GGML_BLAS:' /home/member-a/qwen35-a01/build-cpu/CMakeCache.txt
sha256sum /home/member-a/qwen35-a01/native-build/qwen35-cpu /home/member-a/qwen35-a01/build-cpu/bin/llama-quantize /home/member-a/qwen35-a01/build-cpu/bin/libllama.so /home/member-a/qwen35-a01/build-cpu/bin/libggml-cpu.so /home/member-a/qwen35-a01/build-cpu/bin/libggml-base.so
ldd /home/member-a/qwen35-a01/native-build/qwen35-cpu
