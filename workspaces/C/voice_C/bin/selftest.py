"""Portable contract selftest; --real additionally requires local model assets."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voicec.client import Client
from voicec.checks import real_round, result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real',action='store_true')
    parser.add_argument('--output',type=Path,required=True,help='New output directory outside sealed package')
    args=parser.parse_args(); args.output=args.output.resolve()
    if args.output.is_relative_to(ROOT):
        parser.error('Write selftest results outside this package/runtime to preserve sealed files')
    args.output.mkdir(parents=True,exist_ok=False)
    os.chdir(ROOT)
    loader=unittest.TestLoader(); suite=unittest.TestSuite()
    for pattern in ('test_c00.py','test_microphone.py','test_c04.py'):
        suite.addTests(loader.discover(str(ROOT/'tests'),pattern=pattern))
    with (args.output/'unittest.log').open('w',encoding='utf-8') as stream:
        tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report=dict(contract_tests=tested.testsRun,failures=len(tested.failures),errors=len(tested.errors),
        skipped=len(tested.skipped),real_requested=args.real,real_status='NOT_TESTED',
        microphone_opened=False,board='NOT_TESTED',human_quality='NOT_TESTED')
    if tested.wasSuccessful() and args.real:
        c = None
        try:
            sample=ROOT/'data/c04_public_smoke.wav'
            with tempfile.TemporaryDirectory(prefix='candidate-selftest-') as temp,(args.output/'trace.jsonl').open('w',encoding='utf-8') as trace:
                def record(item): trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
                with Client(Path(temp),asr_config=ROOT/'configs/asr.selected.json',
                    tts_config=ROOT/'configs/tts.selected.json',stream_config=ROOT/'configs/stream.selected.json',
                    response_timeout=30,trace_callback=record,diagnostic_log=args.output/'audit') as c:
                    report['hello']=result(c.call('hello'))
                    report['real']=real_round(c,Path(temp),sample,'我没有发热，也没有咳嗽。')
                (args.output/'stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
                report.update(real_status='PASS',worker_exit_code=c.process.returncode)
        except Exception as exc:
            report.update(real_status='FAIL',real_error=dict(type=type(exc).__name__,message=str(exc)))
            if c is not None:
                (args.output/'stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
    report['status']='PASS' if tested.wasSuccessful() and (not args.real or report['real_status']=='PASS') else 'FAIL'
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','contract_tests','real_status','board')},ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
