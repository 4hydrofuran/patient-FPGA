import struct
import base64
from pathlib import Path
import re
import unittest
import zlib
from elf_sections_readonly import inspect


def fixture():
    b=bytearray(320);b[:7]=b'\x7fELF\x02\x01\x01'
    struct.pack_into('<H',b,18,183);struct.pack_into('<Q',b,40,64)
    struct.pack_into('<HHH',b,58,64,3,1)
    names=b'\0.shstrtab\0.text\0';b[256:256+len(names)]=names;b[280:284]=b'abcd'
    struct.pack_into('<IIQQQQIIQQ',b,128,1,3,0,0,256,len(names),0,0,1,0)
    struct.pack_into('<IIQQQQIIQQ',b,192,11,1,6,4096,280,4,0,0,4,0)
    return b


class ElfTests(unittest.TestCase):
    def test_embedded_program_matches_reviewed_file(self):
        root=Path(__file__).parent
        script=(root/'driver_board_step.ps1').read_text(encoding='utf-8-sig')
        blob=re.search(r"\$sectionProbeBlob='([^']+)'",script)[1]
        self.assertEqual(zlib.decompress(base64.b64decode(blob)),(root/'elf_sections_readonly.py').read_bytes())
    def test_hand_text_digest(self):
        r=inspect(fixture())['sections'][1]
        self.assertEqual(r['name'],'.text')
        self.assertEqual(r['sha256'],'88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589')
    def test_short_header(self):
        with self.assertRaises(ValueError):inspect(b'ELF')
    def test_wrong_machine(self):
        b=fixture();struct.pack_into('<H',b,18,62)
        with self.assertRaises(ValueError):inspect(b)
    def test_section_table_bounds(self):
        b=fixture();struct.pack_into('<Q',b,40,310)
        with self.assertRaises(ValueError):inspect(b)
    def test_section_payload_bounds(self):
        b=fixture();struct.pack_into('<Q',b,224,1000)
        with self.assertRaises(ValueError):inspect(b)
    def test_section_name_bounds(self):
        b=fixture();struct.pack_into('<I',b,192,40)
        with self.assertRaises(ValueError):inspect(b)
    def test_nobits_does_not_read(self):
        b=fixture();struct.pack_into('<I',b,196,8);struct.pack_into('<Q',b,224,1000)
        self.assertEqual(len(inspect(b)['sections']),1)
    def test_missing_terminator(self):
        b=fixture();b[272]=1
        with self.assertRaises(ValueError):inspect(b)


if __name__=='__main__':unittest.main(verbosity=2)
