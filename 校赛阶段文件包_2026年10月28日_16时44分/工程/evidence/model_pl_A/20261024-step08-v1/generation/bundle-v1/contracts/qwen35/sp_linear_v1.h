#ifndef SP_LINEAR_V1_H
#define SP_LINEAR_V1_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* New software-module ABI for this plan, NOT the historical B2 kernel ABI. */
#define SP_LINEAR_API_VERSION 1u
#define SP_LINEAR_MAX_T 8u
#define SP_LINEAR_MAX_NK 4864u
typedef struct sp_linear_context sp_linear_context;
typedef enum sp_linear_status {
 SP_OK=0, SP_BAD_ARGUMENT=1, SP_CONTRACT_MISMATCH=2,
 SP_BUFFER_TOO_SMALL=3, SP_UNSUPPORTED=4, SP_TIMEOUT=5,
 SP_POISONED=6, SP_BUSY=7, SP_DEVICE_ERROR=8, SP_NUMERIC_ERROR=9
} sp_linear_status;
/* Only local trusted configuration. No exceptions may escape this C ABI. */
int32_t sp_linear_open_v1(const char *config_path, sp_linear_context **out_ctx);
/* Successful load owns/copies the required data; host arrays may be released. */
int32_t sp_linear_load_v1(sp_linear_context *ctx, uint32_t n, uint32_t k,
 const uint8_t *w_packed, uint64_t w_bytes,
 const float *scales, uint64_t scale_bytes, uint64_t *out_weight_handle);
/* One in-flight run. On failure, y MUST NOT be consumed. */
int32_t sp_linear_run_v1(sp_linear_context *ctx, uint64_t weight_handle,
 uint32_t t, const int8_t *xq, uint64_t x_bytes,
 const float *sx, uint64_t sx_bytes, float *y, uint64_t y_bytes,
 uint64_t job_id, uint32_t timeout_ms);
/* required_bytes includes NUL. dst==NULL with capacity==0 is size query. */
int32_t sp_linear_report_v1(sp_linear_context *ctx, char *dst,
 uint64_t capacity, uint64_t *required_bytes);
int32_t sp_linear_unload_v1(sp_linear_context *ctx, uint64_t weight_handle);
/* BUSY/POISONED keeps ownership until verified hardware quiescence. */
int32_t sp_linear_close_v1(sp_linear_context *ctx);
#ifdef __cplusplus
}
#endif
#endif
