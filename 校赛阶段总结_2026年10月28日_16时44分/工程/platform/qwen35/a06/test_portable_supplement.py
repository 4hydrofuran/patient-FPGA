"""Guard that serialization portability cannot conceal changed vectors."""
import json
from pathlib import Path
import tempfile
import unittest
from portable_supplement import portable_bench, safe_relative, sha, verify_vectors, WITNESSES

R = Path(__file__).resolve().parents[3]
B = R / 'hw/linear_B_received/B03-supplement-e227297-20261003/payload'


class Portable(unittest.TestCase):
    def test_exact_source_transform(self):
        for name in WITNESSES:
            with self.subTest(name=name):
                original = (B / name).read_bytes()
                result = portable_bench(name, original)
                self.assertEqual(result.count(b'std::ofstream description('), 1)
                # Reversing exactly the two reviewed edits restores every byte.
                stream = (b'std::ofstream description(prefix + ".json"' if name.startswith('tb/')
                          else b'std::ofstream description(prefix+".json"')
                reverted = result.replace(stream + b', std::ios::binary);', stream + b');', 1)
                reverted = reverted.replace(b'}\\r\\n";', b'}\\n";', 1)
                self.assertEqual(reverted, original)
                with self.assertRaises(ValueError):
                    portable_bench(name, original + b' ')

    def test_strict_hashes_no_semantic_escape(self):
        with tempfile.TemporaryDirectory(prefix='a06-vector-guard-') as temp:
            root = Path(temp)
            a = root / 'vectors/pc_regenerated'; a.mkdir(parents=True)
            b = root / 'vectors/real_regenerated'; b.mkdir(parents=True)
            vectors = {'case.json': b'{"T":1}\r\n', 'case.bin': bytes(range(16))}
            manifest = {'files': {}}
            for folder, key in [(a, 'vectors/b03_double'), (b, 'vectors/b03_double_real')]:
                for name, data in vectors.items():
                    (folder / name).write_bytes(data)
                    manifest['files'][key + '/' + name] = {'bytes': len(data), 'sha256': sha(data)}
            self.assertEqual(sum(verify_vectors(root, manifest).values()), 4)
            for bad in [b'{"T":2}\r\n', b'{"T":1}\n', b'{"T":1}\r\r\n', b'{ "T":1}\r\n']:
                (a / 'case.json').write_bytes(bad)
                with self.assertRaises(ValueError):
                    verify_vectors(root, manifest)
            (a / 'case.json').write_bytes(vectors['case.json'])
            (a / 'case.bin').write_bytes(bytes([255]) + vectors['case.bin'][1:])
            with self.assertRaises(ValueError):
                verify_vectors(root, manifest)
            (a / 'case.bin').write_bytes(vectors['case.bin'])
            (a / 'extra.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):
                verify_vectors(root, manifest)

    def test_archive_names(self):
        for bad in ['../x', '/x', 'C:/x', 'a\\b', 'a/../b', 'a//b', '']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                safe_relative(bad)
        self.assertEqual(str(safe_relative('tb/test.cpp')), 'tb/test.cpp')


if __name__ == '__main__':
    unittest.main()
