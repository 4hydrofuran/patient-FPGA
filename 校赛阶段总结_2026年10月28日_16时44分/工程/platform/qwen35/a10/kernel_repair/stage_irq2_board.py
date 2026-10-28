"""Pinned irq2 additive staging only. No reboot, module load or PL operations.

Reuse the reviewed extractor in an isolated process with explicit irq2 pins.
An old verified backup is permitted ONLY after the base checker rehashes every
current original module. Its historical boot identity is never rewritten.
"""
import argparse
import json
from pathlib import Path
import stage_candidate_board as base

BOOT = 'bf3796f0-9785-4afd-a617-3ad578a24d10'
BACKUP_BOOT = 'eb429b2f-66aa-4959-8610-bfcfabcf0202'
PROOF_SHA = '6e1f70240905e4d56ed64f9f61877539e6f9f8232d9c2f44bfad456e5e9a8042'
RELEASE = '6.8.12-a10irq2'
PINNED = {
    'candidate.fit': (65555004, 'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'),
    'modules.tar.gz': (108755861, 'da96f92d8be1c0dfb498efec34dc8b7f041e4698e53ea90041760f1aca0d817d'),
}


def configure():
    base.BOOT, base.BACKUP_BOOT = BOOT, BACKUP_BOOT
    base.RELEASE = RELEASE
    base.SOURCE = Path('/home/ubuntu/a10-irq2-stage-20261021-v1')
    base.FIT_NAME = 'a10-candidate-irq2-20261021.fit'
    base.PINNED = dict(PINNED)
    base.ZOCL_SHA = '38992846680c0ddbdad7a05f6506b66488473a96c52975fa35a126b8401344f8'


def plan():
    configure()
    result = base.plan()
    result.update(current_boot=BOOT, backup_source_boot=BACKUP_BOOT,
                  backup_proof_sha256=PROOF_SHA, current_original_tree_rehash_required=True,
                  boot_authorized=False, board_compute='NOT_TESTED')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute-authorized-stage', action='store_true')
    a = p.parse_args()
    configure()
    if a.execute_authorized_stage:
        base.run(PROOF_SHA)
    else:
        print(json.dumps(plan(), indent=2))
