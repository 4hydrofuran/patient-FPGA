"""Extract the ORIGINAL pre-worker asset/budget gate without starting a worker."""
import ast
import copy
import importlib
from livegen_evidence import bundle_pin
from plm_journal import need

def original_asset_gate(original):
    p=bundle_pin('platform/qwen35/a12/cpu01b_window.py');tree=ast.parse(p.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='WindowBase')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='start_worker')
    stop=next(i for i,n in enumerate(method.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='profile' for t in n.targets))
    selected=copy.deepcopy(method);selected.name='verify_original_assets_only';selected.decorator_list=[]
    selected.body=copy.deepcopy(method.body[:stop])+[ast.Return(value=ast.Name(id='model',ctx=ast.Load()))]
    # Every original statement before profile generation remains byte-semantic;
    # no budget, trusted-file or full digest check is replaced by a JSON verdict.
    need(ast.dump(ast.Module(body=selected.body[:-1],type_ignores=[]),include_attributes=False)==
        ast.dump(ast.Module(body=method.body[:stop],type_ignores=[]),include_attributes=False),'original asset gate AST differs')
    module=importlib.import_module(original.Window.__module__);scope=dict(module.WindowBase.start_worker.__globals__)
    executable=ast.fix_missing_locations(ast.Module(body=[selected],type_ignores=[]));exec(compile(executable,str(p)+'#asset-gate-only','exec'),scope)
    return scope['verify_original_assets_only']
