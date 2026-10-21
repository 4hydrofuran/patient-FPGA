// 仅让未改动的 A 控制测试在 Windows 编译，不验证 Linux 的锁文件安全标志。
#pragma once
#if !defined(_WIN32) || !defined(SP_LINEAR_CONTROL_TEST)
#error "Windows file-lock adapter must never enter a production build"
#endif
#include <fcntl.h>
#define LOCK_EX 2
#define LOCK_NB 4
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef O_NOFOLLOW
#define O_NOFOLLOW 0
#endif
extern "C" int flock(int descriptor, int operation);
