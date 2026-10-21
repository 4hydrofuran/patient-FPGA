// Windows 控制测试使用真实操作系统文件锁；不改写 A 生产后端或 XRT 替身。
#if !defined(_WIN32) || !defined(SP_LINEAR_CONTROL_TEST)
#error "Native lock adapter is test-only"
#endif
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <io.h>
#include <cerrno>
#include <sys/file.h>

// 每个句柄独立取得一字节排他锁，句柄关闭后由系统释放。
extern "C" int flock(int descriptor, int operation) {
    if (operation != (LOCK_EX | LOCK_NB)) {
        errno = EINVAL;
        return -1;
    }
    const auto raw = _get_osfhandle(descriptor);
    if (raw == -1) {
        errno = EBADF;
        return -1;
    }
    OVERLAPPED offset{};
    if (LockFileEx(reinterpret_cast<HANDLE>(raw),
                   LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY,
                   0, 1, 0, &offset)) {
        return 0;
    }
    errno = EWOULDBLOCK;
    return -1;
}
