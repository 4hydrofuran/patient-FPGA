import hashlib, importlib.util, io, json, stat, tempfile, unittest, zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('intake',Path(__file__).with_name('inspect_delivery.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def archive(self,members):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'test.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name,data in members:
                if isinstance(name,str):
                    # Windows ZipInfo normalizes backslashes at construction;
                    # preserve attack bytes so the test exercises our reader.
                    info=zipfile.ZipInfo(name);info.filename=name;name=info
                z.writestr(name,data)
        return path
    def test_missing_xo_not_accepted(self):
        p=self.archive([('README.md','only a path: artifact/kernel.xo')]);r=m.inspect(p)
        self.assertTrue(r['missing_actual_xo']);self.assertFalse(r['accepted']);self.assertFalse(r['frozen'])
    def test_hash(self):
        p=self.archive([('manifest.json','{}')])
        m.inspect(p,hashlib.sha256(p.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):m.inspect(p,'0'*64)
    def test_path_attacks(self):
        for name in ('../escape','/absolute','C:/x','foo\\bar','a/../b','a/./b','a//b','CON.txt','NUL/file','trailing.','stream:name'):
            with self.subTest(name=name),self.assertRaises(ValueError):m.inspect(self.archive([(name,'x')]))
    def test_case_duplicate(self):
        with self.assertRaises(ValueError):m.inspect(self.archive([('A/x','1'),('a/X','2')]))
    def test_symlink(self):
        info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError):m.inspect(self.archive([(info,'../outside')]))
    def test_embedded_xml_structure_only(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('x/kernel.xml','<root><kernel name="STRUCTURE_FIXTURE_NOT_B_KERNEL"><args><arg id="0"/></args></kernel></root>')
        r=m.inspect(self.archive([('test_only.xo',buf.getvalue())]))
        self.assertEqual(len(r['xo']),1);self.assertFalse(r['accepted'])
        self.assertEqual(r['xo'][0]['kernels'][0]['attributes']['name'],'STRUCTURE_FIXTURE_NOT_B_KERNEL')
    def test_dtd(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('kernel.xml','<!DOCTYPE x [<!ENTITY x "hello">]><x/>')
        with self.assertRaises(ValueError):m.inspect(self.archive([('test.xo',buf.getvalue())]))
    def test_size_bound(self):
        old=m.MAX_TOTAL;m.MAX_TOTAL=1
        try:
            with self.assertRaises(ValueError):m.inspect(self.archive([('x','12')]))
        finally:m.MAX_TOTAL=old

    def test_identical_packager_xml_copy(self):
        buf=io.BytesIO();data='<root><kernel name="STRUCTURE_ONLY"/></root>'
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('k/kernel.xml',data)
            z.writestr('ip_repo/sub/.kernelxml/kernel.xml',data)
        result=m.inspect(self.archive([('test.xo',buf.getvalue())]))
        self.assertEqual(result['xo'][0]['embedded_metadata_path'],'k/kernel.xml')
        self.assertEqual(len(result['xo'][0]['identical_metadata_copies']),2)
        self.assertFalse(result['accepted'])

    def test_conflicting_packager_xml_copy(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('k/kernel.xml','<root/>')
            z.writestr('ip_repo/sub/.kernelxml/kernel.xml','<different/>')
        with self.assertRaisesRegex(ValueError,'conflicting'):
            m.inspect(self.archive([('test.xo',buf.getvalue())]))

    def test_ambiguous_primary_xml(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('a/kernel.xml','<root/>');z.writestr('b/kernel.xml','<root/>')
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            m.inspect(self.archive([('test.xo',buf.getvalue())]))

if __name__=='__main__':unittest.main(verbosity=2)
