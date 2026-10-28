import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

import original_module_backup as b
import stage_candidate_board as s


class OriginalBackupTests(unittest.TestCase):
    def fixture(self, root):
        tree = root / "old"
        (tree / "kernel").mkdir(parents=True)
        (tree / "kernel/x.ko").write_bytes(b"original-module")
        (tree / "modules.dep").write_bytes(b"kernel/x.ko:\n")
        archive = root / "original.tar"
        with archive.open("xb") as stream:
            b.export_tree(tree, stream, {"boot_id": b.BOOT, "machine_sha256": b.MACHINE})
        return tree, archive

    def test_roundtrip_and_proof_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tree, archive = self.fixture(root)
            proof = b.verify_archive(archive)
            proof_path = root / "proof.json"; proof_path.write_text(json.dumps(proof))
            self.assertEqual(len(proof["rows"]), 2)
            self.assertEqual(proof["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            s.check_backup_proof(proof_path, s.digest(proof_path), tree)

    def test_changed_original_file_blocks_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tree, archive = self.fixture(root)
            proof = b.verify_archive(archive)
            path = root / "proof"; path.write_text(json.dumps(proof))
            (tree / "kernel/x.ko").write_bytes(b"modified-module")
            with self.assertRaises(ValueError):
                s.check_backup_proof(path, s.digest(path), tree)

    def test_backup_hash_pin_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tree, archive = self.fixture(root)
            path = root / "proof"; path.write_text(json.dumps(b.verify_archive(archive)))
            for pin in (None, "arbitrary", "0" * 64):
                with self.assertRaises(ValueError):
                    s.check_backup_proof(path, pin, tree)

    def test_corrupted_archive_fails_content_check(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, archive = self.fixture(root)
            with tarfile.open(archive, "r:") as tar:
                offset = tar.getmember(b.PREFIX + "kernel/x.ko").offset_data
            raw = bytearray(archive.read_bytes())
            raw[offset] ^= 1  # corrupt payload only; keep tar headers valid
            archive.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "mismatch"):
                b.verify_archive(archive)

    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "empty.tar"
            with tarfile.open(archive, "w"):
                pass
            with self.assertRaisesRegex(ValueError, "manifest"):
                b.verify_archive(archive)

    def test_corrupted_header_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, archive = self.fixture(root)
            raw = bytearray(archive.read_bytes()); raw[0] ^= 1
            archive.write_bytes(raw)
            with self.assertRaises(tarfile.ReadError):
                b.verify_archive(archive)

    def test_traversal(self):
        for name in ("etc/shadow", b.PREFIX + "../key", b.PREFIX + "/absolute", b.PREFIX + "x\\y"):
            with self.assertRaises(ValueError):
                b.safe_relative(name)

    def test_duplicate_archive_member(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "duplicate.tar"
            with tarfile.open(archive, "w") as tar:
                for _ in range(2):
                    entry = tarfile.TarInfo(b.PREFIX + "modules.dep"); entry.size = 1
                    tar.addfile(entry, io.BytesIO(b"x"))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                b.verify_archive(archive)

    @unittest.skipUnless(os.name == "posix", "Linux symlink fixture")
    def test_build_link_recorded_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tree, _ = self.fixture(root)
            (tree / "build").symlink_to(b.BUILD_TARGET)
            archive = root / "with-link.tar"
            with archive.open("xb") as stream:
                b.export_tree(tree, stream, {"boot_id": b.BOOT, "machine_sha256": b.MACHINE})
            proof = b.verify_archive(archive)
            self.assertEqual(next(r["target"] for r in proof["rows"] if r["kind"] == "symlink"),
                             b.BUILD_TARGET)
            b.current_tree_matches(tree, proof)

    @unittest.skipUnless(os.name == "posix", "Linux symlink fixture")
    def test_other_link_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tree, _ = self.fixture(root)
            (tree / "escape").symlink_to("/etc")
            with self.assertRaisesRegex(ValueError, "symlink"):
                b.export_tree(tree, io.BytesIO(), {"boot_id": b.BOOT, "machine_sha256": b.MACHINE})

    def test_wrong_board_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tree, _ = self.fixture(root)
            archive = root / "wrong.tar"
            with archive.open("xb") as stream:
                b.export_tree(tree, stream, {"boot_id": "wrong", "machine_sha256": b.MACHINE})
            with self.assertRaisesRegex(ValueError, "board"):
                b.verify_archive(archive)


if __name__ == "__main__":
    unittest.main()
