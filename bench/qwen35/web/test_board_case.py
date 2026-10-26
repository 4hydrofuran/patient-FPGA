"""Offline transport/entry checks; no board access or hardware simulation."""
import ast
import importlib.util
from pathlib import Path
import types
import unittest

ROOT=Path(__file__).resolve().parents[3]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'platform/qwen35/web'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class Tests(unittest.TestCase):
    def test_transport_tracks_token_and_terminal_without_closing_owner(self):
        module=load('board_case');sent=[]
        events=iter([{'type':'token'},{'type':'result','id':'a12-1'}])
        worker=types.SimpleNamespace(send=sent.append)
        api=types.SimpleNamespace(receive=lambda *a,**kw:next(events))
        t=module.WorkerTransport(worker,object(),Path('/unused'),api)
        t.send({'id':'a12-1'})
        self.assertTrue(t.inflight)
        t.get(1);self.assertTrue(t.inflight)
        t.get(1);self.assertFalse(t.inflight)
        self.assertEqual(t.last_result['id'],'a12-1')
        self.assertEqual(sent,[{'id':'a12-1'}])

    def test_manager_main_only_removes_unbound_stop(self):
        module=load('board_entry')
        path=ROOT/'evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2/control/resource_probe_manager.py'
        source=path.read_text();tree=ast.parse(source)
        original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        expected=ast.dump(ast.Module(body=original.body[1:],type_ignores=[]),include_attributes=False)
        code=module.prepared_main(source)
        # Compile succeeds without executing imports, hardware or Owner creation.
        scope={};exec(code,scope)
        self.assertIn('run_web_bound',scope)
        tree2=ast.parse(source)
        self.assertEqual(expected,ast.dump(ast.Module(body=next(n for n in tree2.body if isinstance(n,ast.FunctionDef) and n.name=='main').body[1:],type_ignores=[]),include_attributes=False))

    def test_unknown_manager_entry_is_not_executed(self):
        module=load('board_entry')
        with self.assertRaises(RuntimeError):
            module.prepared_main('def main():\n    return None\n')

if __name__=='__main__':unittest.main()
