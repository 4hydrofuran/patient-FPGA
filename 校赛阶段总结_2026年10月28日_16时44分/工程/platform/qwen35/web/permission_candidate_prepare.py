"""Prepare only local scheduling candidates from the frozen twenty-case frontend."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
PARENT=ROOT/'release/a12_case20_random_board_20261027_v1/case20-random-t4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def manifest(root,name):
    p=root/name;m=json.loads(p.read_text(encoding='utf-8'))
    m['files']=[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
        for f in sorted(root.rglob('*')) if f.is_file() and f!=p and '__pycache__' not in f.parts]
    save(p,m)


def prepare(out):
    from fast_response_prepare_support import verify_package
    verify_package(PARENT)
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(ROOT/'platform/qwen35/web/permission_compare.py',out/'permission_compare.py')
    roots=[]
    for name,adjustment,probe in (('baseline-miss-probe',0,True),('candidate-miss-probe',10,True),('candidate-service',10,False)):
        target=out/name;shutil.copytree(PARENT,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        window=target/'continuous';support=window/'bundle/platform/qwen35/a12'
        shutil.copyfile(ROOT/'platform/qwen35/a12/permission_hotpath.py',support/'permission_hotpath.py')
        shutil.copyfile(ROOT/'platform/qwen35/web/permission_probe.py',window/'permission_probe.py')
        shutil.copyfile(ROOT/'platform/qwen35/web/permission_compare.py',target/'permission_compare.py')
        save(window/'bundle/control/permission-runtime.json',dict(schema='A12_PERMISSION_SCHEDULING_V1',worker_nice_adjustment=adjustment))
        p=support/'cpu01b_supervisor_base.py';source=p.read_text(encoding='utf-8')
        needle='        self.process = subprocess.Popen(argv,';assert source.count(needle)==1
        source=source.replace(needle,"        from permission_hotpath import launch_from_bundle\n        argv,self.worker_launch_profile=launch_from_bundle(argv)\n"+needle)
        p.write_text(source,encoding='utf-8')
        p=window/'fast_response_preflight.py';source=p.read_text(encoding='utf-8')
        needle='    from resource_probe_binding import require_manager_api';assert source.count(needle)==1
        source=source.replace(needle,"    from permission_hotpath import policy\n    selection=policy(bundle/'control/permission-runtime.json')\n    if selection['worker_nice_adjustment'] and not Path('/usr/bin/nice').is_file():\n        raise RuntimeError('required child scheduler /usr/bin/nice absent before Owner')\n"+needle)
        p.write_text(source,encoding='utf-8')
        p=window/'interactive_case.py';source=p.read_text(encoding='utf-8')
        needle='    from continuous_sessions import question_reserve\n    budget_available='
        assert source.count(needle)==1
        source=source.replace(needle,"""    if config.get('permission_probe'):
        from permission_probe import run as run_permission_probe
        try:
            run_permission_probe(native,worker,path/'permission-probe',prompt_builder=builder(profile),repeats=2)
        except Exception as exc:
            api.save(path/'PERMISSION_PROBE_FAILED.json',dict(status='FAILED_PROBE',reason=type(exc).__name__+': '+str(exc)))
            if transport.inflight:raise
            # A rejected but terminal answer is a failed measurement, not an
            # unknown DMA. Normal shutdown may still return through original restore.
            assert worker.close(timeout=30) and worker.closed and worker.process.returncode==0
            return transport.last_result or transport.warm_result
        assert worker.close(timeout=30) and worker.closed and worker.process.returncode==0
        return transport.last_result
    from continuous_sessions import question_reserve
    budget_available=""")
        p.write_text(source,encoding='utf-8')
        config=json.loads((window/'web-config.json').read_text(encoding='utf-8'))
        config['permission_probe']=probe;config['profile_model_requests']=probe
        if probe:config.pop('answer_cache',None)
        save(window/'web-config.json',config)
        manifest(window/'bundle','manifest.json');manifest(target,'MANIFEST.json');verify_package(target)
        # The changed constructor must leave record/permission/close methods intact.
        for relative in ('cpu01b_supervisor.py','cpu02_support.py'):
            assert sha(support/relative)==sha(PARENT/'continuous/bundle/platform/qwen35/a12'/relative)
        before=ast.parse((PARENT/'continuous/bundle/platform/qwen35/a12/cpu01b_supervisor_base.py').read_text())
        after=ast.parse((support/'cpu01b_supervisor_base.py').read_text())
        methods=lambda tree:{n.name:ast.dump(n,include_attributes=False) for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name!='__init__'}
        assert methods(before)==methods(after)
        assert sha(window/'bundle/bin/qwen35-a12')==sha(PARENT/'continuous/bundle/bin/qwen35-a12')
        roots.append(dict(path=name,nice_adjustment=adjustment,probe_only=probe,
            parent_manifest_sha256=sha(PARENT/'MANIFEST.json'),native_binary_sha256=sha(window/'bundle/bin/qwen35-a12')))
    save(out/'PREPARED.json',dict(status='NO_BOARD_CANDIDATES_PREPARED',variants=roots,board_actions_this_preparation=0,
        BOARD='NOT_TESTED',board_latency_ms=None,model_math_abi_unchanged=True,
        synchronous_journal_and_permission_handler_unchanged=True,
        parent=str(PARENT.relative_to(ROOT))))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(prepare(args.output.resolve()))
