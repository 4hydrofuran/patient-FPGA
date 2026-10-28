"""Attach the web app to an existing A12 NativePL; device ownership stays with PS."""

import threading

from .api import create_app
from .engine import TextEngine


class CorrelatedPL:
    """NativePL validates its a12-N ID; only then map it to the browser request ID."""

    def __init__(self, native_pl):
        self.inner = native_pl
        self.trace_context = None

    @property
    def broken(self):
        return self.inner.broken

    @broken.setter
    def broken(self, value):
        self.inner.broken = value

    def generate(self, messages, timeout_s=180):
        if self.trace_context is None:
            raise RuntimeError("Web correlation context missing")
        self.inner.trace_context = dict(self.trace_context)
        try:
            result = self.inner.generate(messages, timeout_s=timeout_s)
            # NativePL's counter and returned identity must agree before relabelling.
            if (result.get("id") != f"a12-{self.inner.count}"
                    or result.get("type") != "result" or result.get("actual_backend") != "FPGA_REAL"
                    or result.get("state_cleared_before_response") is not True
                    or result.get("state_position_after_clear") != -1):
                self.broken = True
                raise RuntimeError("A12 result identity/state differs")
            return dict(result, native_request_id=result["id"],
                        id=self.trace_context["session_id"] + ":" + self.trace_context["request_id"])
        finally:
            self.inner.trace_context = None


class ManagedPLEngine(TextEngine):
    def __init__(self, native_pl, *, is_ready, generation_timeout_s=180):
        # Reuse the frozen application business pipeline, without starting a CPU model.
        super().__init__("demo", generation_timeout_s=generation_timeout_s)
        if native_pl.expected != "FPGA_REAL" or native_pl.ready.get("execution_kind") != "FPGA_REAL":
            raise ValueError("Only an existing BOARD NativePL can use managed-pl")
        if not callable(is_ready):
            raise ValueError("PS owner readiness callback required")
        self.backend = "managed-pl"
        self.execution_kind = "FPGA_REAL"
        self.model = CorrelatedPL(native_pl)
        self.owner_ready = is_ready
        self.detached = False
        self.can_cancel = False
        self.process_lock = threading.Lock()

    @property
    def healthy(self):
        return not self.detached and not self.model.broken and self.owner_ready() is True

    def cancel(self):
        # No signal, close, restart, or device operation is issued by the web layer.
        pass

    def close(self):
        # Coordinator has already waited for its active call. PS retains worker ownership.
        self.detached = True


def create_managed_app(native_pl, *, is_ready, generation_timeout_s=180):
    """Call from the PS-owned process after constructing its approved NativePL.

    The supplied worker transport must keep servicing PS permits/health while the
    application is running. The PS owner remains responsible for final close.
    """
    return create_app(backend="managed-pl", engine_factory=lambda: ManagedPLEngine(
        native_pl, is_ready=is_ready, generation_timeout_s=generation_timeout_s))


def serve_managed(native_pl, *, is_ready, generation_timeout_s=180, port=8000):
    """Blocking loopback web entry, to be called inside the existing PS owner scope."""
    import uvicorn

    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    uvicorn.run(create_managed_app(native_pl, is_ready=is_ready,
                                  generation_timeout_s=generation_timeout_s),
                host="127.0.0.1", port=port, workers=1)
