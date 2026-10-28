"""Two fixed fresh model questions, invoked by the existing trusted PS scope.

This creates no Owner, worker, browser, network connection or hardware window.
The original manager still owns startup, permits, normal shutdown and restore.
"""
import json
import time
from pathlib import Path

QUESTIONS=('每次疼痛持续多久？','疼痛有多严重？')


def run(native,worker,path,*,prompt_builder,repeats=2):
    if type(repeats) is not int or repeats not in (1,2):raise ValueError('probe repeat bound')
    from patient_web.reference.session import Session
    from permission_hotpath import checkpoint,summarize
    path=Path(path);path.mkdir(exist_ok=False)
    rows=[]
    for repeat in range(repeats):
        for index,question in enumerate(QUESTIONS):
            rid='permission-'+str(repeat)+'-'+str(index)
            session=Session('SYN_CP_03',software_test=True,prompt_builder=prompt_builder,answer_cache=None)
            request=dict(request_id=rid,text=question,source='typed',final=True)
            native.trace_context=dict(session_id=session.snapshot()['session_id'],request_id=rid,epoch=session.epoch)
            before=checkpoint(worker);began=time.monotonic_ns()
            try:response=session.submit(request,native,timeout_s=180)
            finally:native.trace_context=None
            after=checkpoint(worker)
            row=summarize(response,before,after,launch_profile=worker.worker_launch_profile)
            row.update(question=question,repeat=repeat,wall_ms=(time.monotonic_ns()-began)/1e6)
            (path/(rid+'.json')).write_text(json.dumps(dict(summary=row,response=response),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            rows.append(row)
            session.finish()
    report=dict(status='PASS_FRESH_MODEL_PERMISSION_PROBE',rows=rows,
        actual_backend=rows[0]['actual_backend'],answer_cache_used=False,
        observed_hardware_cycles=None,measurement='HOST_WALL_NOT_DEVICE_CYCLES')
    (path/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
