"""Exercise the actual new worker hook, durable observations and no-reuse boundary."""
from common import ROOT
from step10_common import OUT

if __name__=='__main__':
    text=(ROOT/'platform/qwen35/a12/step09_supervisor_test.py').read_text(encoding='utf-8')
    text=text.replace('from step09_common import OUT','from step10_common import OUT')
    text=text.replace('from step09_supervisor import OwnedWorker','from step10_supervisor import OwnedWorker')
    text=text.replace('health=lambda:None','health=lambda:dict(checked=True,checks_skipped=False)')
    text=text.replace("        assert permits[-1]['request']['phase']=='router_close' and permits[-1]['allow']", "        assert permits[-1]['request']['phase']=='router_close' and permits[-1]['allow']\n        assert all(r['health_observation']==dict(checked=True,checks_skipped=False) for r in permits)\n        assert w.permission_metrics['calls']==len(permits)")
    p=OUT/'derived-supervisor-test.py';p.write_text(text,encoding='utf-8')
    namespace={'__name__':'__main__'};exec(compile(text,str(p),'exec'),namespace)
