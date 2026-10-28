"""Derive manager source only. No board package, window, transport or deployment."""
import ast
import argparse
import difflib
import shutil
from tt10_01_common import ROOT,OUT,sha,save


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--revision',default='01');revision=ap.parse_args().revision
    if not revision.isdigit():raise ValueError('numeric fresh revision required')
    base=OUT/'cpu-close-20261025-v1';target=base/('manager-source' if revision=='01' else 'manager-source-'+revision);target.mkdir()
    parent=OUT/'candidate/bundle-v2/control/tt10_01_manager.py'
    old=parent.read_text(encoding='utf-8');text=old
    edits=[
        ('from cpu01b_supervisor import OwnedWorker as CPUWorker','from cpu01b_supervisor import OwnedWorker as ParentCPUWorker\nfrom tt10_01_cpu_close import CpuCloseOwnerMixin, CpuOnlyWorkerMixin, record_reserve_refusal\n\nclass CPUWorker(CpuOnlyWorkerMixin, ParentCPUWorker):\n    pass'),
        ("            if mem['MemAvailable'] < 1114112 or mem['CmaFree'] < 98304:\n                raise HealthBlocked('full-model live extra reserve gate')", "            if mem['MemAvailable'] < 1114112 or mem['CmaFree'] < 98304:\n                record_reserve_refusal(self, boot, mem, temps, full_resident)\n                raise HealthBlocked('full-model live extra reserve gate')"),
        ('class Owner(Window):','class Owner(CpuCloseOwnerMixin, Window):\n    cpu_default_name = DEFAULT'),
        ('        return self.platform.health_schedule.fresh(lambda: self._health_observation(closing=closing))','        return self.cpu_close_health(closing=closing, compute=lambda: self.platform.health_schedule.fresh(lambda: self._health_observation(closing=False)))'),
        ('cpu = CPUWorker(args, directory=', 'cpu = owner.start_cpu_worker(CPUWorker, args, directory='),
        ("        if owner:\n            owner.retain_until_finished(reason)","        if owner and owner.handle_cpu_failure(reason):\n            save(run / 'result.json', dict(status='FAIL_CPU_STAGE_NORMAL_FINALIZED', original_failure=reason, worker_exit_code=0, manager_exit_code=1, new_PL_calls=0, lease_archived=True, compute_pass=False, TTFT_app_s=None))\n            if p.kmsg_reader is not None:\n                p.kmsg_reader.close()\n            raise SystemExit(1)\n        if owner:\n            owner.retain_until_finished(reason)")]
    for before,after in edits:
        assert text.count(before)==1,before
        text=text.replace(before,after,1)
    # Exact inverse edits prove no other manager byte/threshold/PL path changed.
    inverse=text
    for before,after in reversed(edits):
        assert inverse.count(after)==1
        inverse=inverse.replace(after,before,1)
    assert inverse==old
    compile(text,str(target/'tt10_01_manager.py'),'exec')
    (target/'tt10_01_manager.py').write_text(text,encoding='utf-8',newline='\n')
    shutil.copyfile(ROOT/'platform/qwen35/a12/tt10_01_cpu_close.py',target/'tt10_01_cpu_close.py')
    (base/('manager-cpu-close.patch' if revision=='01' else 'manager-cpu-close-'+revision+'.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='frozen-v2/control/tt10_01_manager.py',tofile='source-only/tt10_01_manager.py')),encoding='utf-8')
    save(base/('DERIVATION.json' if revision=='01' else 'DERIVATION-'+revision+'.json'),dict(status='SOURCE_ONLY_NOT_A_DEPLOYABLE_BOARD_PACKAGE',parent_manager_sha256=sha(parent),
        sources={p.name:sha(p) for p in target.iterdir() if p.is_file()},edits=[a for a,b in edits],exact_inverse_matches_parent=True,
        PL_worker_supervisor_unchanged=True,public_contract_unchanged=True,original_reserve_thresholds_unchanged=True,
        new_window_prepared=False,board_recovery_authorized=False,BOARD='NOT_TESTED',actual_model_settings='unknown'))
    print('CPU_CLOSE_MANAGER_SOURCE_DERIVED_NO_BOARD_PACKAGE')


if __name__=='__main__':main()
