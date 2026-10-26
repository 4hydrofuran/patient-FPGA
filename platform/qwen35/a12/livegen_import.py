"""Private namespace for frozen absolute imports; no original files are edited."""
import ast
import importlib
import importlib.abc
import importlib.util
import os
from pathlib import Path
import sys
import types
from livegen_evidence import BUNDLE,bundle_pin,sha
from plm_journal import need
PACKAGE='_a12_live_frozen_gates'

class Qualify(ast.NodeTransformer):
    def __init__(self,names):self.names=names;self.edits=[]
    def visit_ImportFrom(self,node):
        if not node.level and node.module in self.names:
            self.edits.append(('from',node.module));node.module=PACKAGE+'.'+node.module
        return node
    def visit_Import(self,node):
        for alias in node.names:
            if alias.name in self.names:
                self.edits.append(('import',alias.name));alias.asname=alias.asname or alias.name;alias.name=PACKAGE+'.'+alias.name
        return node

class FrozenLoader(importlib.abc.Loader):
    def __init__(self,path,names):self.path=path;self.names=names
    def create_module(self,spec):return None
    def exec_module(self,module):
        source=bundle_pin(self.path.relative_to(BUNDLE).as_posix()).read_text(encoding='utf-8')
        tree=ast.parse(source,str(self.path));q=Qualify(self.names);tree=q.visit(tree);ast.fix_missing_locations(tree)
        # Independently reverse every import qualification in the AST and compare
        # all executable original bodies, including asserts and thresholds.
        class Undo(ast.NodeTransformer):
            def visit_ImportFrom(self,node):
                if node.module and node.module.startswith(PACKAGE+'.'):node.module=node.module[len(PACKAGE)+1:]
                return node
            def visit_Import(self,node):
                for alias in node.names:
                    if alias.name.startswith(PACKAGE+'.'):
                        alias.name=alias.name[len(PACKAGE)+1:]
                return node
        # Import aliases need their original optional-asname to reverse exactly.
        old_imports=[n for n in ast.walk(ast.parse(source)) if isinstance(n,(ast.Import,ast.ImportFrom))]
        new_imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        need(len(old_imports)==len(new_imports),'original import tree shape differs')
        import copy
        inverse=copy.deepcopy(tree);inverse_imports=[n for n in ast.walk(inverse) if isinstance(n,(ast.Import,ast.ImportFrom))]
        for old,new in zip(old_imports,inverse_imports):
            if isinstance(old,ast.ImportFrom):new.module=old.module
            else:
                for a,b in zip(old.names,new.names):b.name=a.name;b.asname=a.asname
        need(ast.dump(inverse,include_attributes=False)==ast.dump(ast.parse(source),include_attributes=False),'original executable AST changed')
        module.__file__=str(self.path);module.__frozen_import_edits__=q.edits;module.__frozen_source_sha256__=sha(self.path)
        paths=list(sys.path);old=os.environ.get('SP_TT10_CONFIG')
        try:exec(compile(tree,str(self.path),'exec'),module.__dict__)
        finally:
            sys.path[:]=paths
            if old is None:os.environ.pop('SP_TT10_CONFIG',None)
            else:os.environ['SP_TT10_CONFIG']=old

class FrozenFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.paths={}
        for directory in (BUNDLE/'control/support',BUNDLE/'platform/qwen35/a12',BUNDLE/'platform/qwen35/a10'):
            for p in directory.glob('*.py'):
                bundle_pin(p.relative_to(BUNDLE).as_posix())
                if p.stem in self.paths:need(sha(p)==sha(self.paths[p.stem]),'ambiguous differing original modules: '+p.stem)
                else:self.paths[p.stem]=p
        self.paths['resource_probe_manager']=bundle_pin('control/resource_probe_manager.py')
    def find_spec(self,fullname,path=None,target=None):
        if not fullname.startswith(PACKAGE+'.'):return None
        name=fullname[len(PACKAGE)+1:]
        if name not in self.paths:return None
        return importlib.util.spec_from_loader(fullname,FrozenLoader(self.paths[name],set(self.paths)))

def load():
    need(__debug__,'original assertions require unoptimized Python')
    if PACKAGE not in sys.modules:
        package=types.ModuleType(PACKAGE);package.__path__=[];sys.modules[PACKAGE]=package
        sys.meta_path.insert(0,FrozenFinder())
    return importlib.import_module(PACKAGE+'.resource_probe_manager')
