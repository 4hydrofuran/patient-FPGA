#pragma once
#include <cstdint>
#include <stdexcept>

namespace a10 {
// Soft gate between initialization calls. It cannot interrupt a stuck ioctl.
// Stop/error BEFORE a call must not invoke it; stop/error AFTER it must prevent
// the next call. This is also used by the production host, not just a fixture.
template<class Check, class Operation>
void checked_init(Check&& check, Operation&& operation) {
    check();
    operation();
    check();
}

enum class Phase { ready, submitted, completed, stopped, poisoned };
enum class RunState { running, completed, failed };
enum class Result { pass, stopped_before_submit, prepare_error, timeout, device_error,
                    readback_error, numeric_error, late_readback };
struct Control {
    Phase phase = Phase::ready;
    bool output_consumable = false;
    bool must_retain() const { return phase == Phase::submitted || phase == Phase::poisoned; }
    void poison() { phase = Phase::poisoned; output_consumable = false; }
};

// The adapter owns ALL XRT resources outside this function's stack. A timeout
// does NOT mean DMA is stopped. Production parks that owner instead of exiting.
template<class Adapter>
Result one(Control& c, Adapter& a, std::uint64_t timeout_ms = 1000) {
    if (c.phase != Phase::ready || !timeout_ms || timeout_ms > 1000)
        throw std::invalid_argument("Not ready / invalid bounded timeout");
    c.output_consumable = false;
    try {
        if (a.stop_requested()) { c.phase = Phase::stopped; return Result::stopped_before_submit; }
        a.prepare();
        if (a.stop_requested()) { c.phase = Phase::stopped; return Result::stopped_before_submit; }
    } catch (...) { c.phase = Phase::stopped; return Result::prepare_error; }
    const auto start = a.now_ms();
    // Before start(): a submit exception is NOT proof that submission failed.
    c.phase = Phase::submitted;
    try {
        a.start();
        for (;;) {
            if (a.stop_requested()) { c.poison(); return Result::device_error; }
            if (a.now_ms() - start >= timeout_ms) { c.poison(); return Result::timeout; }
            const auto state = a.state();
            if (state == RunState::completed) break;
            if (state != RunState::running) { c.poison(); return Result::device_error; }
            a.sleep_poll();
        }
    } catch (...) { c.poison(); return Result::device_error; }
    c.phase = Phase::completed; // Positive completion observed, not merely a terminal error.
    try {
        if (!a.readback_validate()) { c.phase = Phase::stopped; return Result::numeric_error; }
        if (a.now_ms() - start >= timeout_ms) { c.phase = Phase::stopped; return Result::late_readback; }
    } catch (...) { c.phase = Phase::stopped; return Result::readback_error; }
    c.output_consumable = true;
    c.phase = Phase::ready;
    return Result::pass;
}
} // namespace a10
