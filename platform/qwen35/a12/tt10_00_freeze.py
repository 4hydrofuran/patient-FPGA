"""Baseline identities and conservative future snapshot reserve, before BOARD."""
from tt10_00_prepare import ROOT,OUT,j,save,sha


def main():
    refs={}
    for mode,rel in [('health','evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'),
                     ('cpu02','evidence/model_pl_A/20261024-cpu-opt-02-v1/candidate/bundle-v1')]:
        p=ROOT/rel;m=j(p/'manifest.json')
        refs[mode]=dict(source=rel,manifest_sha256=sha(p/'manifest.json'),program_sha256=sha(p/'bin/qwen35-a12'),
            files=m['files'],asset_pins=j(p/'control/asset-pins.json'),
            configuration=dict(ggml_threads=2,kernel_threads=2,physical_T=8,context=1024,algorithm='TILED',
                               cache='R0_CLEAR_ALL_REPLAY',scope='24_layers_72_MLP_projections'),
            new_board_installed_paths='PENDING_FRESH_VERIFICATION',
            ordinary_observer='Detailed Python spans and native nodes disabled; all safety checks and fsync retained',
            profile_observer='CPU02 detailed plus native; original health native and aggregate manager only')
    save(OUT/'BASELINES.json',dict(status='FROZEN_BEFORE_BOARD',references=refs,
        historical_plain=dict(health=dict(ttft_s=52.623984512,complete_s=64.304047931),
                              cpu02_mean_n2=dict(ttft_s=50.7010481045,complete_s=61.762707798)),
        same_round_order=['health','cpu02'],acceptance='Baseline freeze; small fixed-order sample is not speedup acceptance',
        rollback='/var/lib/kv260-a12/cpu02-candidate-20261024-v1',new_model_math=False,new_cache=False))
    state=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/integrated/readback-v1/run-v1/s2/diag_exact/diag/hybrid-state.bin'
    save(OUT/'RESOURCE_ESTIMATE.json',dict(domain='PLANNING_WITH_PRIOR_BOARD_REFERENCE',current_stage_snapshots=0,
        prior_9_token_snapshot=dict(path=state.relative_to(ROOT).as_posix(),bytes=state.stat().st_size,sha256=sha(state),
                                   not_a_full_context_capacity_measurement=True),
        provisional_TT10_01_reserve=dict(slots=2,per_slot_MiB=64,restore_scratch_MiB=64,total_MiB=192,
            basis='Planning reserve above approximately 19.4MiB short-state reference; measure full state/restore peak before admission',
            actual_BOARD_available_for_snapshots=None,allocation_approved_this_stage=False),
        existing_explicit_BO=dict(count=148,bytes=140591104),XRT_implicit_bytes=None,complete_current_peak_BOARD=None,
        next_required='Exact neutral-boundary and full-context state size, snapshot/restore peak and fresh admission'))
    save(OUT/'PROTECTED_BEFORE.json',{p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in
         [ROOT/'runtime/qwen35_w4a8/sp-hook.cpp',ROOT/'config/qwen35/selection.json',ROOT/'contracts/qwen35/contracts.lock',
          ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/SEAL.json',ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/SEAL.json',
          ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1/SEAL.json',ROOT/'evidence/model_pl_A/20261024-ttft10-plan-v1/SEAL.json']} )
    print('TT10_00_BASELINES_AND_RESOURCES_FROZEN')

if __name__=='__main__':main()
