"""An explicitly graphical, single-question PL window; keeps PS display alive."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from board_entry import prepared_main

ROOT=Path(__file__).resolve().parent
BUNDLE=ROOT/'bundle'
FRONT=Path('/home/ubuntu/patient-web-demo-20261026')


BO_BYTES=140591104
RESERVE_KIB=98304


def graphical_admission(original, memory, total_bo_bytes, *, already_charged_bo_bytes=0):
    result=original(memory,total_bo_bytes,already_charged_bo_bytes=already_charged_bo_bytes)
    total=memory['CmaTotal']
    if type(total) is not int or total<0:
        raise ValueError('invalid CMA pool reading')
    result['isolated_mode_allowed']=result['allowed']
    result['allowed']=(result['MemAvailable_after_pending_kib']>=result['required_MemAvailable_kib']
                       and total>=(total_bo_bytes+1023)//1024+RESERVE_KIB)
    result.update(mode='GRAPHICAL_ACTUAL_BO_ALLOCATION',CmaTotal_kib=total,
                  allocation_proven=False,
                  accounting='CmaFree is observed, not pinned availability. Kernel BO allocation and ready inventory must succeed before exposing MODEL.')
    return result


def graphical_platform(original, api=None):
    class GraphicalPlatform(original):
        def service(self,action):
            if action=='stop':
                result=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True,timeout=5)
                if result.stdout.strip()!='active':
                    raise RuntimeError('Manual HDMI session requires the active desktop')
                self.gdm_isolated=False
                self.emit('GDM_KEPT_FOR_USER_HDMI_SESSION',reason='User requested touch-screen text input')
            else:
                return super().service(action)

        def wait_prepl_quiet(self):
            # No GDM shutdown occurred. Reuse the existing PL-holder check once,
            # rather than waiting for shutdown-related process sets to settle.
            if self.pl_mutation_started or self.worker is not None:
                raise RuntimeError('Display coexistence admission must precede PL/native activity')
            self.no_users(module_loaded=False)

        def live_health(self, boot, full_resident):
            # Same cached temperature reader and schedule as the accepted manager.
            # Desktop pages can occupy CMA while remaining migratable by the allocator.
            with api.ob.span('health.live_total'):
                start=time.monotonic_ns()
                assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
                if self.stable_temperatures is None:
                    self.stable_temperatures=api.StableTemperatures()
                now=time.monotonic_ns()
                if now-self.topology_checked_ns>=1_000_000_000:
                    self.stable_temperatures.verify_topology()
                    self.topology_checked_ns=now
                temps=self.stable_temperatures.read()
                mem={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
                capacity=api.admission(mem,BO_BYTES,already_charged_bo_bytes=BO_BYTES if full_resident else 0)
                if not capacity['allowed']:
                    raise api.HealthBlocked('graphical full-model memory admission')
                result=dict(temperatures_mC=temps,memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree','CmaTotal')},
                            full_resident=full_resident,actual_reserve=capacity)
                self.health_parts['temperature_memory_ms']+=(time.monotonic_ns()-start)/1e6
                return result
    return GraphicalPlatform


def graphical_owner(original):
    class GraphicalOwner(original):
        def retain_until_finished(self,reason):
            if not self.platform.pl_mutation_started and self.platform.worker is None and not hasattr(self,'_owned_worker'):
                self.owner_check()
                self.platform.no_users(module_loaded=False)
                self._verify_default()
                target=Path('/var/lock/kv260-a1/history')/(self.review['window_id']+'-prepl-failure')
                (self.evidence/'prepl-failure.json').write_text(json.dumps(dict(reason=reason,PL_commands=0,worker_started=False)))
                Path('/var/lock/kv260-a1/active').rename(target)
                for fd in reversed(self.locks):os.close(fd)
                self.locks=[];self.finished=True
                return
            return super().retain_until_finished(reason)
    return GraphicalOwner


def graphical_main(source):
    # Keep the accepted entry; explicitly replace only its early free-CMA heuristic.
    prepared_main(source)
    tree=ast.parse(source)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    fn.body=fn.body[1:];fn.name='run_web_bound'
    matches=[n for n in ast.walk(fn) if isinstance(n,ast.Assert) and ast.unparse(n.test)=="initial['memory_kib']['CmaFree'] >= 32768"]
    if len(matches)!=1:raise RuntimeError('Accepted initial memory check differs')
    matches[0].test=ast.parse("initial['memory_kib']['CmaTotal'] >= 235600",mode='eval').body
    return compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<graphical-manager-new-web-window>','exec')


def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
    for path in (FRONT/'web_gateway/src',FRONT/'.venv/lib/python3.12/site-packages',ROOT):
        sys.path.insert(0,str(path))
    import patient_web.managed,interactive_case
    interactive_case.desktop_environment()
    assert not (BUNDLE/'run-v1').exists()
    raw=subprocess.check_output(['dmesg','--raw']).decode()
    (BUNDLE/'control/preflight.json').write_text(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel_raw=raw)))
    manifest=json.loads((BUNDLE/'manifest.json').read_text())
    manifest['files']=[dict(path=p.relative_to(BUNDLE).as_posix(),bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(BUNDLE.rglob('*'))
        if p.is_file() and p!=BUNDLE/'manifest.json']
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,indent=2))
    source=BUNDLE/'control/resource_probe_manager.py'
    spec=importlib.util.spec_from_file_location('manual_original_manager',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original_admission=module.admission
    module.admission=lambda memory,total_bo_bytes,**kw:graphical_admission(original_admission,memory,total_bo_bytes,**kw)
    module.Platform=graphical_platform(module.Platform,module)
    module.Owner=graphical_owner(module.Owner)
    from graphical_runtime import graphical_gate
    module.MinimalGate=graphical_gate(module.MinimalGate)
    module.run_case=lambda worker,owner,path,real:interactive_case.run_case(worker,owner,path,real=real,api=module,overlay=ROOT)
    exec(graphical_main(source.read_text()),module.__dict__)
    module.run_web_bound()
    interactive_case.keep_result_service(1800)


if __name__=='__main__':main()
