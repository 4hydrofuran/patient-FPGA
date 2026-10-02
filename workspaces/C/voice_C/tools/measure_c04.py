"""30 fresh-worker cycles and 200 module cycles with fixed development inputs."""
import hashlib
import json
import os
from pathlib import Path
import random
import socket
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voicec.checks import real_round, result
from voicec.client import Client


def stats(values):
    values = sorted(values)
    def q(p):
        if not values: return None
        pos=(len(values)-1)*p; low=int(pos); high=min(low+1,len(values)-1)
        return values[low]+(values[high]-values[low])*(pos-low)
    return dict(count=len(values), p50=q(.5), p95=q(.95), max=max(values,default=None))


def main():
    out = ROOT/'evidence/c04/measurements'; out.mkdir(exist_ok=False)
    freeze = json.loads((ROOT/'evidence/c04/freeze.json').read_text('utf-8'))
    for row in freeze['files']:
        assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest() == row['sha256']
    probe = {}
    try:
        with socket.create_connection(('1.1.1.1',443),timeout=2):
            probe = dict(status='CONNECTION_SUCCEEDED', physical_disconnection=False)
    except OSError as exc:
        probe = dict(status='CONNECTION_FAILED', type=type(exc).__name__, errno=exc.errno,
                     winerror=getattr(exc,'winerror',None), message=str(exc),
                     scope='ONE_OS_CONNECTION_PROBE_NOT_UNIVERSAL_NETWORK_PROOF')
    (out/'network_probe.json').write_text(json.dumps(probe,indent=2),encoding='utf-8')
    os.environ['PYTHONPATH'] = str(ROOT/'tools/c04_network_guard')
    os.environ['VOICE_C_NETWORK_GUARD_DIAGNOSTIC'] = '1'
    sources = [json.loads(s) for s in (ROOT/'data/c01_public/manifest.jsonl').read_text('utf-8').splitlines()]
    scripts = [json.loads(s) for s in (ROOT/'data/c02_scripts/manifest.jsonl').read_text('utf-8').splitlines()]
    print('tts_script_fields',list(scripts[0]),flush=True)
    order = [(i%len(sources),i%len(scripts)) for i in range(200)]
    random.Random(20261002).shuffle(order)
    plan = dict(seed=20261002, cold_workers=30, module_rounds=200, batch_workers=5,
        module_order=order, public_asr='C01_DEVELOPMENT', tts='C02_DEVELOPMENT',
        input_pacing='UNPACED_MODULE_ENGINEERING', final_dataset_used=False,
        physically_disconnected_pc='NOT_TESTED', operating_system_reboot='NOT_TESTED',
        restart_scope='FRESH_WORKER_MODEL_LOAD; OS_DISK_CACHE_NOT_FLUSHED',
        network_guard='PYTHON_AUDIT_HOOK_PLUS_EXECUTION_SANDBOX_POLICY')
    (out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    rows=[]; startups=[]
    with (out/'raw.jsonl').open('w',encoding='utf-8') as raw:
        for mode, groups in [('cold',[(i,[(i%len(sources),i%len(scripts))]) for i in range(30)]),
                              ('module',[(i,order[i*40:(i+1)*40]) for i in range(5)])]:
            for worker_no, batch in groups:
                run = out/f'{mode}-{worker_no:02}'; run.mkdir()
                with tempfile.TemporaryDirectory(prefix='c04-measure-') as temp, (run/'trace.jsonl').open('w',encoding='utf-8') as trace:
                    def record(item):
                        trace.write(json.dumps(item,ensure_ascii=False)+'\n'); trace.flush()
                    begin = time.perf_counter()
                    c = Client(Path(temp), asr_config=ROOT/'configs/asr.selected.json',
                        tts_config=ROOT/'configs/tts.selected.json', stream_config=ROOT/'configs/stream.selected.json',
                        response_timeout=30, trace_callback=record, diagnostic_log=run/'audit')
                    try:
                        hello = result(c.call('hello'))
                        startup = (time.perf_counter()-begin)*1000
                        startups.append(dict(mode=mode,worker=worker_no,hello_ready_ms=startup,hello=hello))
                        for index,(audio_no,text_no) in enumerate(batch):
                            source=sources[audio_no]; script=scripts[text_no]
                            row=dict(mode=mode,worker=worker_no,index=index,audio_id=source['recording_id'])
                            try:
                                row.update(real_round(c,Path(temp),ROOT/'data/c01_public'/source['audio_path'],script['text']))
                            except Exception as exc:
                                row.update(status='TIMEOUT' if isinstance(exc,TimeoutError) else 'FAIL',
                                    error_type=type(exc).__name__,message=str(exc))
                                try: c.call('reset',session_id='check')
                                except Exception: pass
                            rows.append(row); raw.write(json.dumps(row,ensure_ascii=False)+'\n'); raw.flush()
                        print(mode,worker_no+1,'batch_done',len(batch),flush=True)
                    finally:
                        c.close()
                        (run/'stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
                        assert any('C04_PYTHON_NETWORK_GUARD_ACTIVE' in x for x in c.stderr)
                        assert c.process.returncode == 0
    (out/'startups.json').write_text(json.dumps(startups,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={}
    for mode in ('cold','module'):
        group=[x for x in rows if x['mode']==mode]; ok=[x for x in group if x['status']=='PASS']
        summary[mode]=dict(runs=len(group),successes=len(ok),failures=sum(x['status']=='FAIL' for x in group),
            timeouts=sum(x['status']=='TIMEOUT' for x in group),
            hello_ready_ms=stats([x['hello_ready_ms'] for x in startups if x['mode']==mode]),
            whole_client_ms=stats([x['whole_client_ms'] for x in ok]),tts_ready_ms=stats([x['tts_ready_ms'] for x in ok]),
            asr_rtf=stats([x['whole']['compute_ms']/x['whole']['audio_duration_ms'] for x in ok]),
            tts_rtf=stats([x['tts']['compute_ms']/x['tts']['audio_duration_ms'] for x in ok]),
            peak_rss_bytes=max((x['tts']['memory']['peak_rss_bytes'] for x in ok),default=None))
    report=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',summaries=summary,
        network_probe=probe,physical_disconnection='NOT_TESTED',os_reboot='NOT_TESTED',
        main_app_e2e_rounds=0,human_final_quality='NOT_TESTED',board='NOT_TESTED')
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
