"""Remove observer-only AST additions and compare against frozen Python sources."""
import ast
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'
PARENT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'
ALIASES={'cpu01b_supervisor_base':'supervisor','cpu01b_supervisor':'step10_supervisor',
         'cpu01b_window':'health_opt_window','cpu01b_healthrecord':'step08_health',
         'cpu01b_health':'health_opt','cpu01b_kernel_gate':'mlp_kernel_gate'}


class Strip(ast.NodeTransformer):
    def __init__(self):self.temporary={}
    def visit_Import(self,node):
        if any(a.name=='cpu01b_observer' for a in node.names):return None
        return node
    def visit_ImportFrom(self,node):
        node.module=ALIASES.get(node.module,node.module);return node
    def visit_With(self,node):
        expr=node.items[0].context_expr
        if isinstance(expr,ast.Call) and isinstance(expr.func,ast.Attribute) and isinstance(expr.func.value,ast.Name) and expr.func.value.id=='ob':
            if expr.func.attr in ('span','scope'):
                result=[]
                for item in node.body:
                    item=self.visit(item)
                    if isinstance(item,list):result.extend(item)
                    elif item is not None:result.append(item)
                return result
            if expr.func.attr=='lock_context':node.items[0].context_expr=expr.args[0]
            elif expr.func.attr=='file_context':node.items[0].context_expr=expr.args[0].body
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id.startswith('_01b_'):
            self.temporary[node.targets[0].id]=node.value;return None
        return self.generic_visit(node)
    def visit_Name(self,node):
        if isinstance(node.ctx,ast.Load) and node.id in self.temporary:
            return copy.deepcopy(self.temporary[node.id])
        return node
    def visit_Expr(self,node):
        call=node.value
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='ob':
            if call.func.attr in ('bind','start_request','finish_request'):return None
        return self.generic_visit(node)


if __name__=='__main__':
    pairs={
        'cpu01b_supervisor_base.py':'platform/qwen35/a12/supervisor.py',
        'cpu01b_supervisor.py':'platform/qwen35/a12/step10_supervisor.py',
        'cpu01b_window.py':'platform/qwen35/a12/health_opt_window.py',
        'cpu01b_health.py':'platform/qwen35/a12/health_opt.py',
        'cpu01b_healthrecord.py':'platform/qwen35/a12/step08_health.py',
        'cpu01b_kernel_gate.py':'control/support/mlp_kernel_gate.py',
        'cpu01b_manager.py':'control/health_opt_manager.py',
        'cpu01b_control_manager.py':'control/health_opt_manager.py'}
    for derived,original in pairs.items():
        tree=ast.parse((OUT/'source'/derived).read_text(encoding='utf-8'))
        stripped=Strip().visit(tree)
        frozen=ast.parse((PARENT/original).read_text(encoding='utf-8'))
        if ast.dump(stripped,include_attributes=False)!=ast.dump(frozen,include_attributes=False):
            (OUT/(derived+'.stripped.txt')).write_text(ast.dump(stripped,indent=2),encoding='utf-8')
            (OUT/(derived+'.original.txt')).write_text(ast.dump(frozen,indent=2),encoding='utf-8')
            raise RuntimeError('Non-observer AST change: '+derived)
    print(json.dumps(dict(status='PASS_MECHANICAL_OBSERVER_REMOVAL_AST_EQUIVALENCE',files=len(pairs),
        scope='Original checks, decisions, persistence expressions and call order; timing additions and local serialization temporaries removed')))
