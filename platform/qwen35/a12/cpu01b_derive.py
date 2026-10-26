"""Mechanically instrument independent copies of the frozen Python managers."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'
PARENT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'


def timed(name, statements):
    return ast.fix_missing_locations(ast.With(items=[ast.withitem(context_expr=ast.Call(func=ast.Attribute(value=ast.Name(id='ob',ctx=ast.Load()),attr='span',ctx=ast.Load()),args=[ast.Constant(name)],keywords=[]))],body=statements))


class Instrument(ast.NodeTransformer):
    def __init__(self, mapping): self.mapping=mapping;self.function=''
    def visit_FunctionDef(self,node):
        previous=self.function;self.function=node.name
        node=self.generic_visit(node);self.function=previous
        if node.name in self.mapping:
            body=node.body
            # Keep docstring in its original semantic position.
            lead=body[:1] if body and isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str) else []
            node.body=lead+[timed(self.mapping[node.name],body[len(lead):])]
        return node
    def visit_With(self,node):
        node=self.generic_visit(node)
        if self.function in ('record','fresh','_health_observation'):
            for item in node.items:
                expr=ast.unparse(item.context_expr)
                if expr in ('self._lock','self.lock','self.platform.gate_lock'):
                    item.context_expr=ast.parse("ob.lock_context("+expr+", "+repr(self.function+'.lock_wait')+")",mode='eval').body
                elif '.open(' in expr:
                    item.context_expr=ast.parse("ob.file_context(lambda: "+expr+", 'record.file')",mode='eval').body
        return node
    def visit_Expr(self,node):
        text=ast.unparse(node)
        labels={'stream.write':'record.write','stream.flush':'record.flush','os.fsync':'record.fsync'}
        if self.function=='record':
            if text.startswith('stream.write('):
                value=node.value.args[0]
                assign=ast.Assign(targets=[ast.Name(id='_01b_encoded',ctx=ast.Store())],value=value)
                node.value.args[0]=ast.Name(id='_01b_encoded',ctx=ast.Load())
                return [timed('record.json_encode',[assign]),timed('record.write',[node])]
            for prefix,label in labels.items():
                if text.startswith(prefix):return timed(label,[node])
        if self.function=='_permissions' and text.startswith('self.manager_sock.sendall'):
            value=node.value.args[0]
            assign=ast.Assign(targets=[ast.Name(id='_01b_reply',ctx=ast.Store())],value=value)
            node.value.args[0]=ast.Name(id='_01b_reply',ctx=ast.Load())
            return [timed('reply.encode',[assign]),timed('reply.send',[node])]
        if self.function=='kernel_checkpoint' and text.startswith("self.emit('KERNEL_LOG_GATE'"):
            return timed('health.kernel_emit',[node])
        return node
    def visit_Assign(self,node):
        text=ast.unparse(node)
        rules={
            '_permissions': [('r = json.loads','request.parse'),('lane =','request.order'),('allowed =','decision'),('health_observation =','health.total')],
            'record':[('row =','record.assembly')],
            'kernel_checkpoint':[('raw =','health.kmsg_drain'),('result =','health.kernel_gate')],
            'live_health':[('temps =','health.temperatures'),('mem =','health.meminfo'),('result =','health.reserve')],
            'compact_kernel_record':[('payload =','health.archive_encode'),('pin =','health.archive_hash')],
        }
        for prefix,label in rules.get(self.function,[]):
            if text.startswith(prefix):return timed(label,[node])
        return node
    def visit_If(self,node):
        node=self.generic_visit(node);text=ast.unparse(node.test)
        if self.function=='_permissions' and text=='self.owner_check':return timed('owner.total',[node])
        if self.function=='_permissions' and text in ("phase == 'submit'", "phase == 'weight_load'", 'allowed', 'hook'):
            return timed('decision',[node])
        if self.function=='owner_check':
            label='owner.lease_locks' if 'lease.json' in text else 'owner.maps'
            return timed(label,[node])
        if self.function=='compact_kernel_record' and text=='p.exists()':return timed('health.archive_check_or_write',[node])
        if self.function=='live_health' and 'topology_checked_ns' in text:return timed('health.temperature_topology',[node])
        return node
    def visit_For(self,node):
        node=self.generic_visit(node)
        if self.function=='_permissions' and ast.unparse(node.target)=='line':
            # Original exception handler and fail-closed path remain outside this scope.
            body=node.body
            for index,statement in enumerate(body):
                if 'order.check(' in ast.unparse(statement):
                    body.insert(index+1,ast.parse('ob.bind(r)').body[0]);break
            node.body=[ast.With(items=[ast.withitem(context_expr=ast.parse("ob.scope('permission')",mode='eval').body)],body=body)]
        return node


def emit(source,target,mapping,replacements=()):
    text=(PARENT/source).read_text(encoding='utf-8')
    for old,new in replacements:
        if old not in text:raise ValueError('Missing mechanical anchor: '+old)
        text=text.replace(old,new)
    tree=Instrument(mapping).visit(ast.parse(text));ast.fix_missing_locations(tree)
    code='import cpu01b_observer as ob\n'+ast.unparse(tree)+'\n'
    if target=='cpu01b_manager.py':
        code=code.removeprefix('import cpu01b_observer as ob\n')
        anchor="sys.path.insert(0, str(BUNDLE / 'control/support'))"
        if anchor not in code:raise ValueError('Manager import-path anchor absent')
        code=code.replace(anchor,anchor+'\nimport cpu01b_observer as ob',1)
    ast.parse(code);(OUT/'source'/target).write_text(code,encoding='utf-8',newline='\n')


def main():
    (OUT/'source').mkdir(exist_ok=False)
    shutil.copyfile(ROOT/'platform/qwen35/a12/cpu01b_observer.py',OUT/'source/cpu01b_observer.py')
    emit('platform/qwen35/a12/supervisor.py','cpu01b_supervisor_base.py',{'record':'record.total'})
    emit('platform/qwen35/a12/step10_supervisor.py','cpu01b_supervisor.py',{},[('from supervisor import','from cpu01b_supervisor_base import')])
    emit('platform/qwen35/a12/health_opt_window.py','cpu01b_window.py',{},[('from step10_supervisor import','from cpu01b_supervisor import')])
    # Window.owner_check is the unchanged base method, instrumented in the copied file.
    path=OUT/'source/cpu01b_window.py';tree=Instrument({}).visit(ast.parse(path.read_text(encoding='utf-8')));ast.fix_missing_locations(tree)
    # emit already instruments targeted statements even without whole-function spans.
    emit('platform/qwen35/a12/health_opt.py','cpu01b_health.py',{'fresh':'health.schedule_total'})
    emit('platform/qwen35/a12/step08_health.py','cpu01b_healthrecord.py',{'compact_kernel_record':'health.archive_total'})
    emit('control/support/mlp_kernel_gate.py','cpu01b_kernel_gate.py',{'observe_action':'health.kernel_gate_total'})
    replacements=[('from health_opt_window import','from cpu01b_window import'),
        ('from step08_health import','from cpu01b_healthrecord import'),('from health_opt import','from cpu01b_health import'),
        ('from step10_supervisor import','from cpu01b_supervisor import'),('from mlp_kernel_gate import','from cpu01b_kernel_gate import'),
        ("before=dict(getattr(worker,'permission_metrics',{}));begin=", "ob.start_request(request)\n        before=dict(getattr(worker,'permission_metrics',{}));begin="),
        ("save(case/'client-timing.json',timing)","save(case/'client-timing.json',timing)\n        ob.finish_request(r,case/'management-profile.json')"),
        ("owner.platform.health_schedule.idle(owner._health_observation,owner.owner_check)","with ob.scope('idle'):\n            owner.platform.health_schedule.idle(owner._health_observation,owner.owner_check)")]
    emit('control/health_opt_manager.py','cpu01b_manager.py',{'kernel_checkpoint':'health.kernel_total','live_health':'health.live_total','_health_observation':'health.observation_total'},replacements)
    # Plain control runs preserve the exact original Python path apart from independent SPEC.
    shutil.copyfile(PARENT/'control/health_opt_manager.py',OUT/'source/cpu01b_control_manager.py')
    rows={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'source').glob('*.py'))}
    (OUT/'DERIVATION.json').write_text(json.dumps(dict(parent_manifest_sha256=hashlib.sha256((PARENT/'manifest.json').read_bytes()).hexdigest(),
        source=rows,public_ABI_changed=False,model_math_changed=False,ARM_binaries_changed=False,peer01A_03_changed=False,
        permission_record_bytes='Original expressions/order retained; monotonic timing values naturally differ',
        observation='Spans and bounded in-memory rows only; separate JSON after client end'),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PYTHON_01B_DERIVED',files=len(rows))))


if __name__=='__main__':main()
