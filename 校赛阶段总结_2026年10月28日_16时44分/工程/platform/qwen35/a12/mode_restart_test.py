"""Actual abrupt coordinator exit, inherited flock and persistent dirty guard."""
import argparse
import json
from pathlib import Path
import select
import subprocess
import sys
import time
from mode_evidence import ROOT,OUT,read,save,sha,pin
from mode_reader import ProcessObservation
from mode_journal import ModeJournal,ModeBlocked,read_journal
from mode_coordinator import ModeCoordinator

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--capsule',type=Path,required=True);a=p.parse_args()
    directory=OUT/a.tag;directory.mkdir(exist_ok=False)
    stderr=(directory/'stderr.txt').open('x')
    process=subprocess.Popen([sys.executable,'-B',str(ROOT/'platform/qwen35/a12/mode_abrupt_parent.py'),
        '--tag',a.tag,'--capsule',str(a.capsule)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
    ready=None;manager=None;native=None
    try:
        poll=select.poll();poll.register(process.stdout,select.POLLIN);assert poll.poll(120000),'no active ownership telemetry'
        ready=json.loads(process.stdout.readline());assert ready['event']=='ABRUPT_COORDINATOR_READY'
        manager=ProcessObservation(ready['manager_pid'],ready['manager_ticks']);native=ProcessObservation(ready['native_pid'],ready['native_ticks'])
        assert not manager.terminal() and not native.terminal()
        process.stdin.write('ACK_LIVE_HANDLES\n');process.stdin.flush();process.stdin.close();process.wait(timeout=5)
        assert process.returncode==0
        live_handoff=not manager.terminal()
        try:unexpected=ModeJournal(Path(ready['state_directory']),'f'*32)
        except (BlockingIOError,ModeBlocked) as exc:first_refusal=type(exc).__name__+': '+str(exc)
        else:unexpected.dispose();raise AssertionError('new coordinator acquired an unclean active session')
        until=time.monotonic()+20
        while time.monotonic()<until and not (manager.terminal() and native.terminal()):time.sleep(.01)
        assert manager.terminal() and native.terminal(),'PC descendants did not cooperatively exit'
        try:unexpected=ModeCoordinator(Path(ready['state_directory']),a.capsule,trusted_worker=True)
        except ModeBlocked as exc:restart_refusal=str(exc)
        else:unexpected.journal.dispose();raise AssertionError('unclean session automatically restarted')
        rows=read_journal(Path(ready['state_directory'])/'coordinator.jsonl')
        assert rows[-1]['event']=='WINDOW_NATIVE_OBSERVED' and (Path(ready['state_directory'])/'DIRTY.json').exists()
        child=read(OUT/('run-'+ready['tag'])/'MODE_CHILD.json');assert child['cancelled'] and child['control_thread_stopped']
        failure=read(OUT/('run-'+ready['tag'])/'FAILURE.json');assert failure['validated_answers']==[]
        save(directory/'RESULT.json',dict(status='PASS_ACTUAL_ABRUPT_COORDINATOR_EXIT_NO_RESTART_OR_REPLAY',
            ownership=ready,live_handles_acquired=True,child_live_after_parent_exit=live_handoff,first_refusal=first_refusal,
            manager_pidfd_terminal=True,native_pidfd_terminal=True,restart_refusal=restart_refusal,
            dirty_marker_retained=True,history_rows=len(rows),new_windows_launched_after_restart=0,
            child_cancelled_on_parent_EOF=True,BOARD='NOT_TESTED',PL_calls=0,forced_signal=False,platform_released=False))
    finally:
        if manager:manager.close()
        if native:native.close()
        process.stdout.close();stderr.close()
