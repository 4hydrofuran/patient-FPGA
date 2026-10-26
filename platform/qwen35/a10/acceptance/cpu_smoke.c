/* Single 4 MiB write/read and small integer dot product, NOT a RAM stress test.
 * No threads, devices, mmap, MMIO, XRT or kernel invocation. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

int main(void) {
    const size_t words = (4u * 1024u * 1024u) / sizeof(uint32_t);
    alarm(3); /* Only ordinary process memory: terminating this process is safe. */
    struct timespec start, end;
    if (clock_gettime(CLOCK_MONOTONIC, &start)) return 3;
    volatile uint32_t *p = malloc(words * sizeof(uint32_t));
    if (!p) return 4;
    for (size_t i = 0; i < words; ++i) p[i] = (uint32_t)i ^ UINT32_C(0xa5963cc3);
    for (size_t i = 0; i < words; ++i) {
        if (p[i] != ((uint32_t)i ^ UINT32_C(0xa5963cc3))) {
            fprintf(stderr, "MEMORY_MISMATCH word=%zu\n", i);
            free((void *)p); return 5;
        }
    }
    free((void *)p);
    /* Explicit integer inputs, exact independent expected value: 2*3-3*4+4*(-2)+(-5)*(-6)=16. */
    volatile int32_t a[4] = {2,-3,4,-5}, b[4] = {3,4,-2,-6};
    int32_t sum = 0;
    for (unsigned i = 0; i < 4; ++i) sum += a[i] * b[i];
    if (sum != 16) return 6;
    if (clock_gettime(CLOCK_MONOTONIC, &end)) return 3;
    printf("{\"status\":\"PASS_BASIC_CPU_ONLY\",\"threads\":1,\"bytes\":4194304,\"passes\":1,\"dot\":%d,\"seconds\":%.6f}\n",
           sum, (double)(end.tv_sec-start.tv_sec) + (double)(end.tv_nsec-start.tv_nsec)/1e9);
    return 0;
}
