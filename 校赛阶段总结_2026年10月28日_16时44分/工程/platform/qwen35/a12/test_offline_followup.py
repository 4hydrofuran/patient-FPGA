"""Linux PC fixtures for prompt identity and bounded full-raw handoff rejection."""
import argparse
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import offline_diag_handoff as h
from short_prompt_offline import (SYSTEM, candidate_source, canonical_sha, common_prefix,
                                  identity_config, prefix_candidates)
from resource_probe_policy import ProbeBlocked


def write(path,data):
    with path.open('xb') as f:f.write(data)
    path.chmod(0o600)


def fixture(root):
    paths={}
    for case,positions in [('full',[0,1,2]),('warm',[0,1]),('hit',[2])]:
        folder=root/case;folder.mkdir(mode=0o700);paths[case]=folder
        projections=[]
        for stream in sorted(h.STREAM_IDS):
            x=b''.join(bytes([p+1])*4 for p in positions)
            y=b''.join(bytes([p+7])*4 for p in positions)
            a=stream+'.x.bin';b=stream+'.y.bin'
            write(folder/a,x);write(folder/b,y)
            projections.append(dict(id=stream,T=len(positions),K=1,N=1,input=a,output=b))
        logits=[]
        for p in positions:
            name='logits-'+str(p)+'.f32'
            write(folder/name,bytes([p])*h.LOGITS_BYTES)
            logits.append(dict(position=p,file=name))
        write(folder/'hybrid-state.bin',b'final-state' if case!='warm' else b'prefix-state')
        write(folder/'manifest.json',json.dumps(dict(projections=projections,logits=logits)).encode())
    return paths


class PromptTests(unittest.TestCase):
    def test_neutral_prefix_excludes_common_question_accident(self):
        neutral=list(range(11));full=[list(range(11))+[91,92],list(range(11))+[91,93]]
        self.assertEqual(len(prefix_candidates(neutral,full)[0]),11)
        self.assertEqual(len(prefix_candidates(neutral,full)[1]),8)

    def test_common_prefix_and_invalid_inputs(self):
        self.assertEqual(common_prefix([[1,2,3],[1,2,4]]),[1,2])
        for arrays in ([],[[]]):
            with self.assertRaises(ProbeBlocked):common_prefix(arrays)

    def test_canonical_json_preserves_wire_values(self):
        self.assertEqual(canonical_sha({'facts':(1,'x')}),canonical_sha({'facts':[1,'x']}))
        self.assertNotEqual(canonical_sha({'n':True}),canonical_sha({'n':1}))
        self.assertNotEqual(canonical_sha({'n':4}),canonical_sha({'n':'4'}))

    def test_prompt_identity_changes_without_mutating_parent(self):
        parent=dict(identity={'model_sha256':'a'},allowed_prefixes=[[70]])
        before=copy.deepcopy(parent)
        a=identity_config(parent,'b',{'cpu':'c'},[{'prompt':'one'}],[[1,2]],'d')
        b=identity_config(parent,'b',{'cpu':'c'},[{'prompt':'two'}],[[1,2]],'d')
        self.assertNotEqual(canonical_sha(a),canonical_sha(b));self.assertEqual(parent,before)
        self.assertNotIn([70],a['allowed_prefixes'])

    def test_experiment_changes_only_prompt_builder(self):
        root=Path(__file__).resolve().parents[3]
        before=(root/'system_qwen35/app/checking.py').read_text(encoding='utf-8')
        funcs=lambda text:{n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body
                           if isinstance(n,ast.FunctionDef) and n.name!='prompt_messages'}
        for style in ('copy_before_question','verbatim_before_question'):
            after=candidate_source(before,style)
            self.assertEqual(funcs(before),funcs(after))
            self.assertIn(SYSTEM,after)


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='a12-handoff-fixture-')
        cls.root=Path(cls.temp.name);cls.paths=fixture(cls.root)
        cls.archive=cls.root/'complete.zip';cls.export=h.export_pc(cls.paths,cls.archive)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory(prefix='a12-handoff-negative-')
        self.work=Path(self.scratch.name)
    def tearDown(self):self.scratch.cleanup()
    def copy_archive(self,name,edit):
        dest=self.work/name
        with zipfile.ZipFile(self.archive) as source,zipfile.ZipFile(dest,'x') as target:
            for info in source.infolist():
                result=edit(info.filename,source.read(info))
                if result is not None:target.writestr(h.zip_info(info.filename),result)
        dest.chmod(0o600)
        return dest,hashlib.sha256(dest.read_bytes()).hexdigest()

    def test_full_roundtrip_hashes_all_raw_bytes_once(self):
        before=set(self.root.iterdir())
        r=h.verify_archive(self.archive,self.export['archive_sha256'])
        self.assertEqual(r['raw_files'],444)
        self.assertEqual(r['comparison']['projection_streams'],144)
        self.assertEqual(r['comparison']['full_logit_vectors'],3)
        self.assertEqual(r['decompressed_read_passes_per_raw_file'],1)
        self.assertEqual(self.export['archive_sha256'],hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(before,set(self.root.iterdir()))

    def test_wrong_archive_digest_rejected(self):
        with self.assertRaises(h.HandoffBlocked):h.verify_archive(self.archive,'0'*64)

    def test_changed_raw_byte_rejected_even_with_new_outer_digest(self):
        name='hit/l00_gate.y.bin'
        p,d=self.copy_archive('changed.zip',lambda n,b:(bytes([b[0]^1])+b[1:]) if n==name else b)
        with self.assertRaises(h.HandoffBlocked):h.verify_archive(p,d)

    def test_missing_raw_member_rejected(self):
        p,d=self.copy_archive('missing.zip',lambda n,b:None if n=='hit/l00_gate.x.bin' else b)
        with self.assertRaises(h.HandoffBlocked):h.verify_archive(p,d)

    def test_traversal_symlink_and_duplicate_members_rejected(self):
        for kind in ('traversal','symlink','duplicate'):
            with self.subTest(kind=kind):
                p,d=self.copy_archive(kind+'.zip',lambda n,b:b)
                with zipfile.ZipFile(p,'a') as z:
                    if kind=='traversal':z.writestr(h.zip_info('../escape'),b'bad')
                    if kind=='symlink':
                        info=h.zip_info('hit/link');info.external_attr=(stat.S_IFLNK|0o777)<<16
                        z.writestr(info,b'/etc/passwd')
                    if kind=='duplicate':z.writestr(h.zip_info('HANDOFF.json'),b'{}')
                d=hashlib.sha256(p.read_bytes()).hexdigest()
                with self.assertRaises(h.HandoffBlocked):h.verify_archive(p,d)
                self.assertFalse((self.work.parent/'escape').exists())

    def test_no_board_exporter_activation(self):
        with mock.patch.object(h.platform,'machine',return_value='aarch64'):
            with self.assertRaises(h.HandoffBlocked):h.export_pc(self.paths,self.work/'denied.zip')
        self.assertFalse((self.work/'denied.zip').exists())

    def test_incomplete_layer_coverage_and_bad_shapes_rejected(self):
        raw=(self.paths['full']/'manifest.json').read_bytes();m=json.loads(raw)
        for change in ('coverage','zero','bool','oversize','duplicate'):
            with self.subTest(change=change):
                bad=copy.deepcopy(m)
                if change=='coverage':bad['projections'].pop()
                if change=='zero':bad['projections'][0]['T']=0
                if change=='bool':bad['projections'][0]['K']=True
                if change=='oversize':bad['projections'][0]['N']=4865
                if change=='duplicate':bad['logits'][1]['position']=bad['logits'][0]['position']
                with self.assertRaises(h.HandoffBlocked):h.manifest_plan(json.dumps(bad).encode())

    def test_symlink_source_and_unlisted_file_refused(self):
        p=self.work/'link';p.symlink_to(self.paths['full'],target_is_directory=True)
        with self.assertRaises(OSError):h.DirectoryCase(p)
        folder=self.work/'source';folder.mkdir(mode=0o700)
        for file in self.paths['hit'].iterdir():write(folder/file.name,file.read_bytes())
        write(folder/'unexpected.bin',b'bad')
        with self.assertRaises(h.HandoffBlocked):h.DirectoryCase(folder)

    def test_repeated_read_latches_reader(self):
        source=h.DirectoryCase(self.paths['hit'])
        try:
            with self.assertRaises(h.HandoffBlocked):source.read('manifest.json',capture=True)
            self.assertTrue(source.failed)
            with self.assertRaises(h.HandoffBlocked):source.read('hybrid-state.bin')
        finally:source.close()

    def test_cache_advice_failure_does_not_report_success(self):
        with mock.patch.object(h.os,'posix_fadvise',side_effect=OSError('PC injected advice failure')):
            with self.assertRaises(OSError):h.DirectoryCase(self.paths['hit'])

    def test_source_change_during_advice_rejected(self):
        folder=self.work/'source';folder.mkdir(mode=0o700)
        for file in self.paths['hit'].iterdir():write(folder/file.name,file.read_bytes())
        target=folder/'manifest.json'
        actual=h.os.posix_fadvise
        def change(fd,*args):
            actual(fd,*args)
            with target.open('ab') as f:f.write(b' ')
        with mock.patch.object(h.os,'posix_fadvise',side_effect=change):
            with self.assertRaises(h.HandoffBlocked):h.DirectoryCase(folder)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=False)
    output=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    (args.evidence/'unittest.txt').write_text(output.getvalue(),encoding='utf-8')
    row=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
             failures=len(result.failures),errors=len(result.errors),domain='PC_LINUX_FIXTURES',
             BOARD='NOT_TESTED',model_runs=0,PL_calls=0)
    (args.evidence/'RESULT.json').write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
    print(output.getvalue());print(json.dumps(row))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
