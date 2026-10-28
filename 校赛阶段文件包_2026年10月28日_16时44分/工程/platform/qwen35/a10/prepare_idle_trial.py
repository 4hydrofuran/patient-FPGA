"""PC-only empty-load package. No board connection, no execution permission."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ARTIFACTS = {
    'a1-vadd.bit.bin': '772b26d0756e43e71cc1cf05b0f0de9e51b6f25507d427eff5c2f82d3c790c23',
    'a1-vadd.dtbo': '14a014624b084f8c9f39fd13e15e156360f9eae367b7da7994328fee432e4646',
}
BOOT = 'd07af077-84c9-4910-8529-95757a09106d'


def make_plan(root):
    source = root / 'platform/build/a1-overlay-candidate-20260928'
    rows = []
    for name, wanted in ARTIFACTS.items():
        path = source / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != wanted:
            raise ValueError('Pinned artifact differs: ' + name)
        rows.append(dict(name=name, sha256=actual, bytes=path.stat().st_size))
    evidence = root / 'evidence/board_platform/A10_20261018_intake/ssh_dfx_recovery_inventory_01.json'
    inventory = json.loads(evidence.read_text(encoding='utf-8-sig'))
    if inventory['boot_id'] != BOOT or inventory['exit_code'] != 0:
        raise ValueError('Wrong source boot or failed inventory')
    default = '/lib/firmware/xilinx/k26-starter-kits/'
    restore = {name: inventory['files'][default + name]['sha256'] for name in [
        'k26_starter_kits.bit.bin', 'k26_starter_kits.dtbo']}
    return {
        'schema': 'A10_IDLE_PL_TRIAL_PLAN_V1', 'status': 'PC_PREPARED_NOT_DEPLOYMENT_PASS',
        'authorized': False, 'execution_performed': False, 'compute_authorized': False,
        'boot_id': BOOT, 'kernel': '6.8.0-1015-xilinx',
        'board_machine_id_sha256': 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec',
        'package_name': 'a10-vadd-20261019',
        'board_new_package_directory': '/lib/firmware/xilinx/a10-vadd-20261019',
        'artifacts': rows,
        'shell': {'shell_type': 'XRT_FLAT', 'num_pl_slots': 1, 'num_aie_slots': 0},
        'forbidden_payload_suffixes': ['.xclbin', '.ko', '.sh', '.py'],
        'existing_driver': {
            'path': '/home/ubuntu/a10-driver-check-20261018-v2/zocl.ko',
            'sha256': '545df42c8b66396dd847ccd6a280f19d9a0051d36e2e75c1ec84437caca328a9',
            'permanent_install': False},
        'restore_package': 'k26-starter-kits', 'restore_artifact_hashes': restore,
        'restore_evidence_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest(),
        'initial_slot_observation': {'slot': 0, 'handle': 0, 'must_revalidate': True},
        'gates': ['fresh health and same boot', 'exclusive central board lease and shared device lock',
                  'no processes holding accelerator device nodes', 'no existing same-name files overwritten',
                  'check package, driver and default restore hashes', 'read current slot handle; never assume zero',
                  'snapshot default overlay, device nodes, module bindings, kernel log and vart.conf'],
        'sequence': ['stage new package only after authorization', 'remove default by observed handle',
                     'independent confirmation default overlay removed', 'load hash-locked ZOCL module',
                     'load test package once', 'read back overlay, ZOCL binding and render node without opening it',
                     'remove test by freshly observed handle', 'independent confirmation test nodes removed and refcount zero',
                     'ordinary rmmod after unbound confirmation', 'load default once',
                     'verify default overlay, no zocl, stable health, unchanged vart.conf',
                     'release lease only after reconciliation'],
        'stop_policy': 'On any mismatch/unknown outcome retain evidence and lease; no retry, forced unload, reset, reboot or power action.',
        'timing': {'expected_operator_minutes': '1-2', 'no_compute_loop': True,
                   'monitor_each_step': True, 'stuck_driver_ioctl_hard_bound_guaranteed': False},
        'side_effects_to_review': ['libdfx allocates configuration DMA buffer (about 8 MiB, not a compute BO)',
                                   'libdfx copies a1-vadd.dtbo into /lib/firmware and removes that copy on destroy',
                                   'libdfx may use temporary state.txt in daemon working directory',
                                   'no xclbin inside firmware directory, so update_env has no xclbin to write to vart.conf'],
        'BOARD_compute': 'NOT_TESTED', 'real_comparisons': 0,
        'not_covered': ['XRT compute/BO allocation', 'DMA timeout recovery', '20 lengths/1000 comparisons'],
    }


def confirm_removed(observed):
    """Independent evidence gate, NOT a board operation or exit-code shortcut."""
    return (observed.get('query_exit') == 0
            and observed.get('test_overlays') == []
            and observed.get('zocl_bound_devices') == []
            and observed.get('accelerator_render_nodes') == []
            and observed.get('accelerator_open_holders') == []
            and type(observed.get('module_refcount')) is int
            and observed['module_refcount'] == 0)


def prepare(root, out):
    plan = make_plan(root)
    out.mkdir()  # An existing or partial target must fail, never overwrite.
    for row in plan['artifacts']:
        shutil.copyfile(root / 'platform/build/a1-overlay-candidate-20260928' / row['name'], out / row['name'])
    (out / 'shell.json').write_text(json.dumps(plan['shell'], indent=2) + '\n', encoding='utf-8')
    (out / 'plan.pending.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    return plan


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    p = prepare(a.root.resolve(), a.out.resolve())
    print(json.dumps({'status': p['status'], 'authorized': False,
                      'files': sorted(x.name for x in a.out.iterdir()), 'board_contact': False}))
