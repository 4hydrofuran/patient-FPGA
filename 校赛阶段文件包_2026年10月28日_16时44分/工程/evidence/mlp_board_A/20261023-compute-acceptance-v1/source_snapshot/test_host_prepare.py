"""PC tests of additive staging guards and upload planning; no board contact."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import upload_bundle as upload
import stage_bundle as stage

BOOT='81bb9dc6-7ccd-4edb-b9f5-07ee5ba166ea'  # synthetic PC fixture


class HostPreparation(unittest.TestCase):
    def test_upload_plan_pins_and_no_overwrite(self):
        with patch('subprocess.run',side_effect=AssertionError('PC may not connect')):
            commands,hashes=upload.plan(BOOT)
        self.assertEqual(len(hashes),81)
        self.assertEqual(len(commands),3)
        self.assertIn('StrictHostKeyChecking=yes',commands[0])
        self.assertIn('BindAddress=192.168.2.1',commands[0])
        self.assertNotIn('mkdir -p',commands[0][-1])
        self.assertIn('test ! -d /sys/module/zocl',commands[0][-1])
        self.assertTrue(all('reboot' not in ' '.join(c) for c in commands))
    def test_upload_rejects_bad_boot(self):
        with self.assertRaises(ValueError):upload.plan('not-a-uuid')
    def fixture(self):
        stack=contextlib.ExitStack();self.addCleanup(stack.close)
        root=Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='a11-host-pc-')))
        source=root/'source';source.mkdir();target=root/'var/lib/a11/bundle';target.parent.mkdir(parents=True)
        (source/'payload').write_bytes(b'PC_ONLY')
        man=dict(schema='A11_MLP_BUNDLE_V1',authorization_included=False,board_accepted=False,max_submissions=23,
                 files={'payload':dict(bytes=7,sha256=stage.sha(source/'payload'))})
        (source/'manifest.json').write_text(json.dumps(man))
        mapped={
            '/proc/sys/kernel/random/boot_id':BOOT,
            '/etc/machine-id':'PC_MACHINE',
            '/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status':'applied',
            '/sys/class/hwmon/hwmon0/temp1_input':'31000'}
        for name,data in mapped.items():
            p=root/name.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
        def paths(p):
            p=Path(p)
            return root/str(p).lstrip('/') if str(p).startswith(('/proc/','/etc/','/sys/','/var/')) else p
        stack.enter_context(patch.object(stage,'Path',paths))
        stack.enter_context(patch.object(stage,'SOURCE',source));stack.enter_context(patch.object(stage,'TARGET',target))
        stack.enter_context(patch.object(stage,'PIN',stage.sha(source/'manifest.json')))
        stack.enter_context(patch.object(stage,'MACHINE',hashlib.sha256(b'PC_MACHINE').hexdigest()))
        stack.enter_context(patch.object(stage.os,'geteuid',return_value=0))
        stack.enter_context(patch.object(stage.os,'uname',return_value=SimpleNamespace(release='6.8.12-a10irq2',machine='aarch64')))
        stack.enter_context(patch.object(stage.shutil,'disk_usage',return_value=SimpleNamespace(free=2**30)))
        old_stat=Path.lstat
        def stat(p,*a,**kw):
            v=list(old_stat(p,*a,**kw));v[4]=0 if p==target.parent else 1000
            if p==target.parent:v[0]&=~0o022
            return os.stat_result(v)
        stack.enter_context(patch.object(Path,'lstat',stat))
        return root,source,target
    def test_additive_stage_and_no_second_write(self):
        root,source,target=self.fixture()
        result=stage.stage(BOOT)
        self.assertEqual(result['compute_runs'],0)
        self.assertEqual((source/'payload').read_bytes(),(target/'payload').read_bytes())
        with self.assertRaisesRegex(RuntimeError,'target/pin'):stage.stage(BOOT)
    def test_wrong_boot_writes_nothing(self):
        root,source,target=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'identity'):stage.stage('91bb9dc6-7ccd-4edb-b9f5-07ee5ba166ea')
        self.assertFalse(target.exists())
    def test_corrupt_source_writes_nothing(self):
        root,source,target=self.fixture();(source/'payload').write_bytes(b'CORRUPT')
        with self.assertRaisesRegex(RuntimeError,'bad source'):stage.stage(BOOT)
        self.assertFalse(target.exists())
    def test_hot_board_writes_nothing(self):
        root,source,target=self.fixture();(root/'sys/class/hwmon/hwmon0/temp1_input').write_text('55000')
        with self.assertRaisesRegex(RuntimeError,'temperature'):stage.stage(BOOT)
        self.assertFalse(target.exists())


if __name__=='__main__':unittest.main(verbosity=2)
