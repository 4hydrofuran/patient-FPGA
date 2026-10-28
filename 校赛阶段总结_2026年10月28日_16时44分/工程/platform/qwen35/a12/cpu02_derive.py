"""Derive Python-only task02 from the sealed task01 integrated package."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
BASE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/integrated/bundle-v1'


def replace(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new,1)


def main():
    source=OUT/'source';source.mkdir()
    originals={p.name:p.read_text(encoding='utf-8') for p in (BASE/'platform/qwen35/a12').glob('cpu01b_*.py')}
    originals['cpu01_manager.py']=(BASE/'control/cpu01_manager.py').read_text(encoding='utf-8')
    for name,text in originals.items():
        after=text
        if name=='cpu01b_health.py':
            after='from cpu02_support import snapshot\n'+after
            after=replace(after,"self.raw += ''.join(pieces)","if pieces:\n                self.raw += ''.join(pieces)")
            after=replace(after,"len(self.raw.encode('utf-8'))","len(snapshot(self.raw).payload)")
        if name=='cpu01b_kernel_gate.py':
            after=replace(after,'from kernel_log_gate import KernelLogGate, diagnostics, digest','from kernel_log_gate import KernelLogGate, diagnostics\nfrom cpu02_support import digest')
            after=replace(after,'not raw.startswith(self.previous)','(raw is not self.previous and not raw.startswith(self.previous))')
        if name=='cpu01b_healthrecord.py':
            after='from cpu02_support import snapshot\n'+after
            after=replace(after,"payload = raw.encode('utf-8')","representation = snapshot(raw)\n                payload = representation.payload")
            after=replace(after,'pin = hashlib.sha256(payload).hexdigest()','pin = representation.sha256')
        if name=='cpu01b_window.py':
            after='from cpu02_support import owned_lock_fds\n'+after
            after=replace(after,'all((lock_owned(p, os.getpid()) for p in LOCKS))','owned_lock_fds(LOCKS, self.locks, os.getpid())')
        if name=='cpu01b_supervisor_base.py':
            tree=ast.parse(after)
            klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='OwnedWorker')
            record=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='record')
            new='''def record(self, **row):
    with ob.span('record.total'):
        with ob.lock_context(self._lock, 'record.lock_wait'):
            with ob.span('record.assembly'):
                row=dict(monotonic_ns=time.monotonic_ns(),**row)
            self.records.append(row)
            with ob.span('record.json_encode'):
                encoded=(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\\n').encode('utf-8')
            if not hasattr(self,'_journal'):
                self._journal=DurableJournal(self.directory/'events.jsonl')
            self._journal.append(encoded)
'''
            klass.body[klass.body.index(record)]=ast.parse(new).body[0]
            # Record the original final event before releasing its non-device FD.
            close=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='close')
            assert isinstance(close.body[-1],ast.Return)
            close.body.insert(len(close.body)-1,ast.parse("if hasattr(self,'_journal'):self._journal.close()").body[0])
            ast.fix_missing_locations(tree);after='from cpu02_support import DurableJournal\n'+ast.unparse(tree)+'\n'
        ast.parse(after)
        (source/name).write_text(after,encoding='utf-8',newline='\n')
        if after!=text:
            (OUT/(name+'.patch')).write_text(''.join(difflib.unified_diff(text.splitlines(True),after.splitlines(True),fromfile='cpu01/'+name,tofile='cpu02/'+name)),encoding='utf-8')
    shutil.copyfile(ROOT/'platform/qwen35/a12/cpu02_support.py',source/'cpu02_support.py')
    for name in ('cpu01_profile.py','cpu01_numeric.py','cpu01_usage.py'):
        shutil.copyfile(BASE/'platform/qwen35/a12'/name,source/name)
    data=dict(status='DERIVED_PYTHON_ONLY_02',parent_manifest_sha256=hashlib.sha256((BASE/'manifest.json').read_bytes()).hexdigest(),
        changed=[name for name,text in originals.items() if (source/name).read_text(encoding='utf-8')!=text],
        mathematical_or_native_binary_changed=False,task01A_or03_changed=False,fsync='EVERY_RECORD_BEFORE_REPLY_PLUS_FIRST_DIRECTORY_ENTRY_SYNC',
        dynamic_checks='fresh kmsg drain/sequence, boot, lock FD inode/FLOCK, lease hash, temperatures, memory, budget, journal path inode/length; no cached safety results',
        pure_cache='at most two exact immutable text objects and their UTF8/SHA256; kernel archive bytes still read and compared every observation')
    (OUT/'DERIVATION.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data))


if __name__=='__main__':main()
