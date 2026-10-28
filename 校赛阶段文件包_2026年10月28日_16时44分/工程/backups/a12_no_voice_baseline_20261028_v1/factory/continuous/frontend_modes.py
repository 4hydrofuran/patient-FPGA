"""Explicit B CPU/FPGA selection, retaining the original PS owner and its deadline."""
from pathlib import Path
import uuid


def install_cpu_mode(app, bundle, *, available, prompt_builder=None, generation_timeout_s=180):
    from patient_web.stdio_cpu import BoardCPUEngine
    class OwnerCPUEngine(BoardCPUEngine):
        @property
        def healthy(self):return available() is True and super().healthy
        def process(self,*args,**kwargs):
            if available() is not True:raise RuntimeError('PS window is no longer accepting model work')
            return super().process(*args,**kwargs)
    bundle=Path(bundle);coordinator=app.state.coordinator
    def cpu():
        if available() is not True:raise RuntimeError('PS window unavailable for CPU selection')
        engine=OwnerCPUEngine(bundle,bundle.parent/'cpu-runs'/uuid.uuid4().hex,generation_timeout_s=generation_timeout_s)
        engine.prompt_builder=prompt_builder
        return engine
    coordinator.backend_options={'managed-pl':dict(label='FPGA',factory=coordinator.factory),
                                 'native':dict(label='CPU',factory=cpu)}

