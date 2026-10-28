"""Owner/deadline wiring fixtures only; no worker, model or PL starts here."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from frontend_modes import install_cpu_mode


class Tests(unittest.TestCase):
    def test_install_does_not_start_cpu_and_retains_original_pl_factory(self):
        factory=lambda:None
        c=types.SimpleNamespace(factory=factory)
        app=types.SimpleNamespace(state=types.SimpleNamespace(coordinator=c))
        module=types.ModuleType('patient_web.stdio_cpu');module.BoardCPUEngine=object
        with patch.dict(sys.modules,{'patient_web.stdio_cpu':module}):
            install_cpu_mode(app,Path('/unused'),available=lambda:False)
        self.assertIs(c.backend_options['managed-pl']['factory'],factory)
        with self.assertRaisesRegex(RuntimeError,'PS window unavailable'):c.backend_options['native']['factory']()

    def test_cpu_health_and_dispatch_stop_with_original_owner(self):
        live=[True];started=[]
        class FixtureCPU:
            def __init__(self,*args,**kwargs):started.append(args)
            @property
            def healthy(self):return True
            def process(self,*args,**kwargs):return 'synthetic-processed'
        module=types.ModuleType('patient_web.stdio_cpu');module.BoardCPUEngine=FixtureCPU
        c=types.SimpleNamespace(factory=lambda:None);app=types.SimpleNamespace(state=types.SimpleNamespace(coordinator=c))
        builder=object()
        with patch.dict(sys.modules,{'patient_web.stdio_cpu':module}):
            install_cpu_mode(app,Path('/unused'),available=lambda:live[0],prompt_builder=builder)
        self.assertEqual(started,[])
        engine=c.backend_options['native']['factory']()
        self.assertIs(engine.prompt_builder,builder);self.assertTrue(engine.healthy)
        self.assertEqual(engine.process(),'synthetic-processed')
        live[0]=False;self.assertFalse(engine.healthy)
        with self.assertRaisesRegex(RuntimeError,'PS window'):engine.process()


if __name__=='__main__':unittest.main()
