"""Original finish function + actual CPU native worker, explicitly PC IO proxy.

Kernel/default-PL observations are fixture ports. The original statement order,
worker interface, stable process/FD scan, filesystem archive and lock close run.
This cannot instantiate a Board Owner or authorize physical resource release.
"""
import ast
import importlib
import os
from pathlib import Path
import tempfile
import time
import types
from plmode_evidence import ROOT,OUT,read,save,sha
from plmode_manager import Manager
from plmode_provider import CPUProvider
from livegen_platform import import_original_verified,inherited_lock_proof
from livegen_evidence import bundle_pin
from generation_binding import FixtureIssuer

def main():
    os.umask(0o077);bpath=OUT/'BUILD-v2.json';b=read(bpath);original=import_original_verified()
    window_module=importlib.import_module(original.Window.__module__);release=importlib.import_module(original.__package__+'.accelerator_release_gate_v2')
    p=bundle_pin('platform/qwen35/a12/cpu01b_window.py');tree=ast.parse(p.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Window');fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='finish')
    statements=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
    with tempfile.TemporaryDirectory(prefix='a12-owner-interface-') as root:
        root=Path(root);central=root/'central';central.mkdir();fixture=FixtureIssuer(central/'active',time.monotonic_ns()+180_000_000_000)
        evidence=root/'evidence';evidence.mkdir();events=[];default_ok=[False]
        proxy=root/'proc';(proxy/'sys/kernel/random').mkdir(parents=True);(proxy/'sys/kernel/random/boot_id').write_text(fixture.boot)
        myself=proxy/str(os.getpid());myself.mkdir()
        for name in ('stat','maps','fd'):(myself/name).symlink_to(Path('/proc')/str(os.getpid())/name,target_is_directory=name=='fd')
        owner=types.SimpleNamespace(boot=fixture.boot.strip(),review=dict(window_id='PC_OWNER_INTERFACE_ONLY'),evidence=evidence,
            locks=[fd for _,fd in fixture.locks],finished=False,owner_check=fixture.observe,
            health=lambda **kw:events.append('PC_KERNEL_PORT'),_kernel_ok=lambda:True)
        def verify_default():
            events.append('PC_DEFAULT_PL_PORT')
            if not default_ok[0]:raise RuntimeError('PC fixture default readback refused')
        owner._verify_default=verify_default
        owner._finalize_record=lambda event,**data:window_module.Window._finalize_record(owner,event,**data)
        scope=dict(window_module.Window.finish.__globals__,CENTRAL=central,collect=lambda **kw:release.collect(proxy))
        exec(compile(statements,str(p)+'#PC-finish-interface','exec'),scope);finish=scope['finish']
        provider=CPUProvider();provider.extra_fds=tuple(owner.locks)
        work=Path(b['workspace'])/'owner-interface-native';m=Manager(bpath,work,provider=provider,cap=72)
        inherited_lock_proof([path for path,fd in fixture.locks],owner.locks,m.p.pid,os.getpid())
        early=None
        try:finish(owner,m)
        except RuntimeError as e:early=str(e)
        assert early=='normal worker exit not proven' and events==[] and (central/'active').exists()
        m.ready()
        for i in range(3):m.run_request(i)
        result=m.normal_close();assert m.closed and m.process is m.p and m.p.returncode==0
        refused=None
        try:finish(owner,m)
        except RuntimeError as e:refused=str(e)
        assert refused=='PC fixture default readback refused' and not owner.finished and len(owner.locks)==2 and (central/'active').exists()
        default_ok[0]=True;finish(owner,m)
        assert owner.finished and owner.locks==[] and not (central/'active').exists() and (central/'history/PC_OWNER_INTERFACE_ONLY').exists()
        fixture.locks=[] # original finish already closed these private fixture FDs
        fixture._test_cleanup()
        save(OUT/'OWNER_INTERFACE_TEST.json',dict(status='PASS_ORIGINAL_FINISH_INTERFACE_PC_IO_PROXY_ONLY',early_refusal=early,
            original_default_failure_retains_lease=refused,original_archive_and_lock_close_verified=True,actual_worker_exit_code=m.p.returncode,
            original_finish_AST_unchanged=True,actual_CPU_model_claims=result['claims'],hardware_kernel_and_default_ports='SYNTHETIC_NOT_BOARD',
            actual_Board_owner_constructed=False,actual_Board_release=False,BOARD='NOT_TESTED'))
    print('PASS_ORIGINAL_FINISH_INTERFACE_PC_IO_PROXY_ONLY')
if __name__=='__main__':main()
