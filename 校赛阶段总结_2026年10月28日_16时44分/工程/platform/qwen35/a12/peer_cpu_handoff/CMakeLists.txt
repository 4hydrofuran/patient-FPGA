cmake_minimum_required(VERSION 3.16)
project(a12_peer_cpu_components LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(PACKAGE_ROOT "" CACHE PATH "Verified handoff package root")
if(NOT EXISTS "${PACKAGE_ROOT}/source/llama/ggml/CMakeLists.txt")
  message(FATAL_ERROR "Set PACKAGE_ROOT to the extracted package")
endif()
# These are component tests. No model loader, XRT, device or network is used.
# The real request profiler interposes a backend symbol through RTLD_NEXT.
# Shared ggml libraries preserve that baseline linkage (static duplicates it).
set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP ON CACHE BOOL "" FORCE)
set(GGML_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GGML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
foreach(backend CUDA HIP VULKAN SYCL METAL OPENCL RPC CANN MUSA BLAS)
  set(GGML_${backend} OFF CACHE BOOL "" FORCE)
endforeach()
# Avoid attributing the enclosing project's git identity to the copied runtime.
set(GIT_EXE "" CACHE FILEPATH "" FORCE)
set(GGML_BUILD_COMMIT "81e39ad34368329b5db77620721510fd91107e80")
add_subdirectory("${PACKAGE_ROOT}/source/llama/ggml" ggml EXCLUDE_FROM_ALL)
add_library(peer_hook STATIC "${PACKAGE_ROOT}/source/runtime/sp-hook.cpp")
target_include_directories(peer_hook PUBLIC
  "${PACKAGE_ROOT}/source/runtime" "${PACKAGE_ROOT}/source/llama/include"
  "${PACKAGE_ROOT}/source/llama/ggml/include")
target_compile_options(peer_hook PRIVATE -fno-fast-math -ffp-contract=off)
add_executable(peer_projection_test "${PACKAGE_ROOT}/tests/projection.cpp")
target_compile_options(peer_projection_test PRIVATE -fno-fast-math -ffp-contract=off)
target_link_libraries(peer_projection_test PRIVATE peer_hook ggml-cpu ggml-base)
add_executable(peer_profile_test
  "${PACKAGE_ROOT}/tests/profile.cpp"
  "${PACKAGE_ROOT}/source/profile/request_profile.cpp")
target_include_directories(peer_profile_test PRIVATE
  "${PACKAGE_ROOT}/source/profile" "${PACKAGE_ROOT}/source/llama/vendor/nlohmann")
target_link_libraries(peer_profile_test PRIVATE ggml-cpu ggml-base ${CMAKE_DL_LIBS})
