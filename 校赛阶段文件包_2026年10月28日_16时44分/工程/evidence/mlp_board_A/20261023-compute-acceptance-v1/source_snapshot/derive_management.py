"""Generate narrowly changed A11 managers from hash-pinned A10 sources on PC."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PINS={
 'a10/isolated_single_trial.py':'b98bbef6dbbed9717cf1c41a34451e472bc2ade2f813f4368e06e215e8746c44',
 'a10/isolated_idle_trial.py':'d52a79a208a35285339cfddcb30ac8eb8da2fc78035411c0d43a95c209fa4695',
 'a10/minimal_gate.py':'671f2ca334c0ce905c61738b3adfce0766bacdd39373998678ded630fc4f58c0',
 'a11/mlp_boundary.py':'22e81fd4921d3df97a48eedb192a826be7d6c0d6b1eed5c4b0d9ede6604e72a3'}


def derive(out):
    out.mkdir(parents=True,exist_ok=False)
    def read(name):
        data=(ROOT/'platform/qwen35'/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==PINS[name],name+' source changed'
        return data.decode().replace('\r\n','\n')
    outputs={}
    base=read('a10/isolated_idle_trial.py').replace('from minimal_gate import MinimalGate','from mlp_kernel_gate import MinimalGate')
    base=base.replace("('a1-vadd.bit.bin', 'a1-vadd.dtbo')","('a11-mlp.bit.bin', 'a11-mlp.dtbo')")
    outputs['mlp_base.py']=base
    gate=read('a10/minimal_gate.py').replace('/__symbols__/krnl_vadd_1','/__symbols__/w4a8_linear_v1_1')
    outputs['mlp_kernel_gate.py']=gate
    b=read('a11/mlp_boundary.py').replace('from freeze_vectors import schedule','from mlp_policy import schedule')
    b=b.replace('        try:code=self.process.wait(timeout=timeout_s)', '''        try:
            deadline=time.monotonic()+timeout_s
            while True:
                self.pulse()
                remaining=deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired('A11_worker',timeout_s)
                try:
                    code=self.process.wait(timeout=min(.1,remaining))
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>=deadline:raise''')
    outputs['mlp_boundary_v2.py']=b
    s=read('a10/isolated_single_trial.py')
    # Every unchanged lifecycle/release method remains inherited from the A10
    # code. Neither originals nor their frozen evidence are edited.
    replacements=[
      ('from isolated_idle_trial import','from mlp_base import'),
      ('from minimal_gate import MinimalGate','from mlp_kernel_gate import MinimalGate'),
      ('from single_compute_boundary import SingleComputeBoundary','from mlp_boundary_v2 import MlpBoundary'),
      ('from single_compute_policy import (ASSETS, BO_BYTES, BO_COUNT, BOOT_FILES, CENTRAL, DEFAULT,',
       'from mlp_policy import (ASSETS, PLAN_SHA, BOOT_FILES, CENTRAL, DEFAULT,'),
      ('class IsolatedSingleTrial','class MlpTrial'),
      ('IsolatedSingleTrial(args.source','MlpTrial(args.source'),
      ('prior-idle-audit.json','prior-a10-audit.json'),
      ('prior_idle_audit_sha256','prior_a10_audit_sha256'),
      ('PASS_BOARD_IDLE_WITH_KNOWN_LIMITATIONS','PASS_BOARD_SINGLE_N32_POSTCOMPUTE_RELEASE_WITH_LIMITATIONS'),
      ('max_submissions=1','max_submissions=23'),
      ('300_000_000_000','600_000_000_000'),
      ("'a1-vadd.bit.bin', 'a1-vadd.dtbo'","'a11-mlp.bit.bin', 'a11-mlp.dtbo'"),
      ('SingleComputeBoundary(request','MlpBoundary(request'),
      ("'single_compute_entry.py'","'mlp_worker.py'"),
      ("'--execute-isolated-single', '--source'","'--source'"),
      ('self.worker.wait_normal(15)','self.worker.wait_normal(240)'),
      ('single-receipt.json','mlp-receipt.json'),
      ('compute_runs=1','compute_runs=23'),
      ('explicit_requested_peak_bytes=BO_COUNT*BO_BYTES','explicit_requested_peak_bytes=2162688'),
      ("A10='NOT_PASSED_UNTIL_INDEPENDENT_FINAL_READBACK_AND_REQUIREMENT_AUDIT'",
       "A11='NOT_PASSED_UNTIL_INDEPENDENT_FINAL_READBACK_AND_REQUIREMENT_AUDIT'"),
      ('PASS_SINGLE_N32_AND_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT',
       'PASS_MLP_23_AND_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT'),
      ('SINGLE_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED','MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED'),
      ('--execute-authorized-single-once','--execute-authorized-mlp-once'),
      ('args.execute_authorized_single_once','args.execute_authorized_mlp_once')]
    for a,bval in replacements:
        assert a in s,a
        s=s.replace(a,bval)
    s=s.replace('import time\n','import time\nfrom manager_support import pulse, latch_stop\n')
    s=s.replace('    def park(self, reason):\n        try:',
                '    def park(self, reason):\n        try:\n            latch_stop(self, reason)')
    s=s.replace("need(identity == self.identity, 'single worker identity differs')",'''
            need(all(identity.get(k)==v for k,v in self.identity.items()), 'MLP worker identity differs')
            if 'inherited_device_lock_fd' in identity:
                need(identity['inherited_device_lock_fd']==self.held_locks[1].fileno() and
                     identity['manager_start_ticks']==start_ticks(Path('/proc/self')), 'borrowed descriptor differs')'''.strip())
    s=s.replace("self.identity['worker_baseline_sha256'] = digest(self.source/'worker-baseline.json')",
                "self.identity['worker_baseline_sha256'] = digest(self.source/'worker-baseline.json')\n        self.identity['plan_sha256'] = PLAN_SHA")
    s=s.replace("'worker_baseline_sha256')}\n        self.worker", "'worker_baseline_sha256', 'plan_sha256')}\n        self.worker")
    s=s.replace("stdout_path=self.source/'worker.stdout.jsonl'", "device_lock_fd=self.held_locks[1].fileno(),\n                          stdout_path=self.source/'worker.stdout.jsonl'")
    s=s.replace('        result = self.worker.wait_normal(240)',
                '        self.worker.pulse = lambda: pulse(self)\n        result = self.worker.wait_normal(240)')
    outputs['mlp_manager.py']=s
    for name,text in outputs.items():
        compile(text,name,'exec')
        (out/name).write_text(text,encoding='utf-8')
    (out/'derivation.json').write_text(json.dumps(dict(PC_ONLY=True,source_pins=PINS,
        outputs={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in outputs}),indent=2))
    print(json.dumps(dict(status='GENERATED_NOT_YET_TESTED',files=list(outputs))))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    derive(ap.parse_args().out)
