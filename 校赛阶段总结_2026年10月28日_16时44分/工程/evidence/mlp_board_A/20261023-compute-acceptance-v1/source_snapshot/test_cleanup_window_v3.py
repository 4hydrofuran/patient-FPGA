"""PC-only transport/staging safety tests, never connects to the board."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cleanup_window_v3_host as host
import cleanup_window_v3_remote as remote


class Transport(unittest.TestCase):
    def payload(self): return json.loads(host.candidate_payload())

    def test_pinned_payload(self):
        files=remote.validate_payload(self.payload())
        self.assertEqual(set(files),remote.NAMES)
        self.assertEqual(remote.sha(files['candidate.json']),remote.PIN)

    def test_changed_data(self):
        data=self.payload();data['cleanup_board_v3.py']='eA=='
        with self.assertRaises(AssertionError):remote.validate_payload(data)

    def test_path_injection(self):
        data=self.payload();data['../escape']='eA=='
        with self.assertRaises(AssertionError):remote.validate_payload(data)

    def test_fixed_actions(self):
        for action in ('stage','readback','launch','status'):
            argv,pin=host.plan(action)
            self.assertIn('StrictHostKeyChecking=yes',argv)
            self.assertEqual(len(pin),64)
            self.assertNotIn('password',argv[-1])
        with self.assertRaises(ValueError):host.plan('reboot')
        with self.assertRaises(AssertionError):host.plan('resume','injected;command',1)

    def test_stage_new_directory_only(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'new'
            stdin=io.TextIOWrapper(io.BytesIO(host.candidate_payload()))
            with patch.object(remote,'INSTALL',dest),patch.object(remote,'identity'),\
                 patch.object(remote,'trusted_directory'),patch.object(remote.os,'umask'),\
                 patch.object(remote.os,'O_DIRECTORY',0,create=True),\
                 patch.object(remote.os,'open',return_value=999),\
                 patch.object(remote.os,'close'),patch.object(remote.os,'fsync'),\
                 patch.object(remote.sys,'stdin',stdin),patch('sys.stdout',new_callable=io.StringIO):
                remote.stage()
                self.assertEqual(set(p.name for p in dest.iterdir()),remote.NAMES)
                with self.assertRaises(AssertionError):remote.stage()

    def test_remote_linux_paths_not_windows_escapes(self):
        import ast
        for action in ('launch','status','resume'):
            argv,_=host.plan(action,'user-cleanup-test-resume',1)
            command=argv[-1]
            program=command.split(' -c "',1)[1][:-1]
            strings=[n.value for n in ast.walk(ast.parse(program)) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
            remote_paths=[v for v in strings if 'cleanup-v3-20261023' in v]
            self.assertTrue(remote_paths)
            for value in remote_paths:
                self.assertTrue(value.startswith('/var/lib/kv260-a11/'),repr(value))
                self.assertNotIn('\\',value)
                self.assertNotIn('\x0b',value)

    def test_bad_payload_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'new';stdin=io.TextIOWrapper(io.BytesIO(b'{}\n'))
            with patch.object(remote,'INSTALL',dest),patch.object(remote,'identity'),\
                 patch.object(remote,'trusted_directory'),patch.object(remote.sys,'stdin',stdin),\
                 patch('sys.stdout',new_callable=io.StringIO):
                with self.assertRaises(AssertionError):remote.stage()
                self.assertFalse(dest.exists())

    def test_wrong_identity_no_write(self):
        with patch.object(remote,'identity',side_effect=AssertionError('wrong boot')),\
             patch.object(remote.Path,'mkdir') as mkdir:
            with self.assertRaises(AssertionError):remote.stage()
            mkdir.assert_not_called()

    def test_pc_seal_intact(self):
        seal=json.loads((host.EVIDENCE/'SEAL.json').read_bytes())
        for name,entry in seal['files'].items():
            path=host.ROOT/name
            self.assertEqual(path.stat().st_size,entry['bytes'],name)
            self.assertEqual(remote.sha(path.read_bytes()),entry['sha256'],name)

    def test_optional_vart_missing_is_null(self):
        with tempfile.TemporaryDirectory() as d:
            missing=Path(d)/'vart.conf'
            self.assertIsNone(remote.optional_digest(missing))
            with missing.open('xb') as f:f.write(b'fixture')
            self.assertEqual(remote.optional_digest(missing),remote.sha(b'fixture'))


if __name__=='__main__':unittest.main(verbosity=2)
