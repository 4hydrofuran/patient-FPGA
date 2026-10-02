/* 验证公共头文件可用于纯 C，不链接或伪称已有动态库。 */
#include "../../contracts/sp_linear_v1.h"

/* 固定 API 版本、规模和状态码，防止复制过程中改变契约。 */
_Static_assert(SP_LINEAR_API_VERSION == 1u, "API version");
_Static_assert(SP_LINEAR_MAX_T == 8u, "T limit");
_Static_assert(SP_LINEAR_MAX_NK == 4864u, "NK limit");
_Static_assert(SP_NUMERIC_ERROR == 9, "status enum");

/* 每个指针类型显式对应一个公共函数声明。 */
int32_t (*probe_open)(const char *, sp_linear_context **) = sp_linear_open_v1;
int32_t (*probe_load)(sp_linear_context *, uint32_t, uint32_t, const uint8_t *, uint64_t, const float *, uint64_t, uint64_t *) = sp_linear_load_v1;
int32_t (*probe_run)(sp_linear_context *, uint64_t, uint32_t, const int8_t *, uint64_t, const float *, uint64_t, float *, uint64_t, uint64_t, uint32_t) = sp_linear_run_v1;
int32_t (*probe_report)(sp_linear_context *, char *, uint64_t, uint64_t *) = sp_linear_report_v1;
int32_t (*probe_unload)(sp_linear_context *, uint64_t) = sp_linear_unload_v1;
int32_t (*probe_close)(sp_linear_context *) = sp_linear_close_v1;
