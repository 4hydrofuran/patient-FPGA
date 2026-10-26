"""Connect the installed web gateway to an existing PS-owned NativePL.

This module creates no worker, Owner, device allocation, or hardware window.
The caller keeps servicing permits and owns shutdown after the web app returns.
"""
import importlib
import math


class OwnerBoundModel:
    """Keep the gateway's NativePL interface and use the owner's live budget."""

    def __init__(self, native_pl, *, is_ready, remaining_seconds, minimum_answer_seconds=180):
        if (getattr(native_pl, 'expected', None) != 'FPGA_REAL'
                or native_pl.ready.get('execution_kind') != 'FPGA_REAL'):
            raise ValueError('An existing BOARD NativePL is required')
        if not callable(is_ready) or not callable(remaining_seconds):
            raise TypeError('Existing owner readiness and remaining-budget callbacks are required')
        self.inner = native_pl
        self._is_ready = is_ready
        self._remaining_seconds = remaining_seconds
        self.minimum_answer_seconds = minimum_answer_seconds

    @property
    def expected(self):
        return self.inner.expected

    @property
    def ready(self):
        return self.inner.ready

    @property
    def count(self):
        return self.inner.count

    @property
    def broken(self):
        return self.inner.broken

    @broken.setter
    def broken(self, value):
        self.inner.broken = value

    @property
    def trace_context(self):
        return self.inner.trace_context

    @trace_context.setter
    def trace_context(self, value):
        self.inner.trace_context = value

    def _budget(self):
        value = self._remaining_seconds()
        if type(value) not in (int, float) or not math.isfinite(value):
            return 0.0
        return max(0.0, float(value))

    def available(self):
        return (not self.broken and self._is_ready() is True
                and self._budget() >= self.minimum_answer_seconds)

    def generate(self, messages, timeout_s=180):
        if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
                or timeout_s <= 0):
            raise ValueError('Positive finite answer timeout required')
        if self.broken or self._is_ready() is not True:
            raise RuntimeError('PS owner is not accepting web requests')
        if self._budget() < timeout_s:
            raise RuntimeError('Remaining owner budget is shorter than the answer budget')
        return self.inner.generate(messages, timeout_s=timeout_s)


def create_app(native_pl, *, is_ready, remaining_seconds, generation_timeout_s=180):
    """Call inside the PS owner scope, after its approved NativePL is ready.

    Use the gateway's existing frozen prompt, checker, delivery and score path.
    No CPU/model fallback or frontend reference rewrite is performed here.
    """
    if (type(generation_timeout_s) not in (int, float)
            or not math.isfinite(generation_timeout_s)
            or not 1 <= generation_timeout_s <= 600):
        raise ValueError('Answer timeout must be within 1..600 seconds')
    model = OwnerBoundModel(native_pl, is_ready=is_ready, remaining_seconds=remaining_seconds,
                            minimum_answer_seconds=generation_timeout_s)
    managed = importlib.import_module('patient_web.managed')
    return managed.create_managed_app(model, is_ready=model.available,
                                      generation_timeout_s=generation_timeout_s)


def serve(native_pl, *, is_ready, remaining_seconds, generation_timeout_s=180, port=8000):
    """Blocking web entry; return control to PS for its existing cleanup."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Port must be within 1..65535')
    app = create_app(native_pl, is_ready=is_ready, remaining_seconds=remaining_seconds,
                     generation_timeout_s=generation_timeout_s)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=port, workers=1)
