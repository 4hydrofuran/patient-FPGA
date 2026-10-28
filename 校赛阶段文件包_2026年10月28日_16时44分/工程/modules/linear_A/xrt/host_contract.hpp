#pragma once
#include "sp_linear_v1.h"
#include <cstddef>
#include <cstdint>

// A-owned host logic only. No HLS, device emulation, or fabricated completion.
namespace a07 {
inline constexpr const char* contract_sha = "83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6";
inline constexpr uint32_t magic = 0x57344138;
inline constexpr uint64_t meta_bytes = 40;
struct Layout {
    uint32_t n=0,k=0,t=0,np=0,kp=0,g=0;
    uint64_t w=0,sw=0,x=0,sx=0,y=0;
};
int layout(uint32_t n,uint32_t k,uint32_t t,Layout& out) noexcept;
int weights(const Layout&,const uint8_t*,uint64_t,const float*,uint64_t) noexcept;
int inputs(const Layout&,const int8_t*,uint64_t,const float*,uint64_t,const float*,uint64_t) noexcept;
int output(const Layout&,const float*,uint64_t) noexcept;
int private_status(uint32_t) noexcept;
uint64_t read_le(const uint8_t*,size_t) noexcept;
void write_le(uint8_t*,uint64_t,size_t) noexcept;
int validate_meta(const uint8_t*,uint64_t,uint32_t build,uint64_t job,
                  uint64_t host_seed,uint64_t wbytes) noexcept;
// Accounting is a configured cap, never a statement of board RAM/BO reachability.
bool fits_budget(uint64_t budget,uint64_t used,uint64_t requested) noexcept;
bool in_window(uint64_t base,uint64_t span,uint64_t address,uint64_t bytes) noexcept;
enum class Phase { READY, RUNNING, POISONED };
class Lifecycle {
    Phase phase_=Phase::READY;
    uint64_t job_=0;
public:
    Phase phase() const noexcept {return phase_;}
    uint64_t job() const noexcept {return job_;}
    int idle() const noexcept;
    int begin(uint64_t job,uint32_t timeout_ms) noexcept;
    void poison() noexcept {phase_=Phase::POISONED;}
    int completed_and_validated() noexcept;
    // Intentionally no unpoison/reset API: recovery requires a verified platform procedure.
};
}
