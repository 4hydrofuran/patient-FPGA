"""Add external process-start measurement; freeze the final task10 controller bytes."""
from common import ROOT,sha,save
from step10_common import OUT

if __name__=='__main__':
    p=ROOT/'platform/qwen35/a12/step10_manager.py';s=p.read_text(encoding='utf-8')
    pairs=[
      ("    process_start=time.monotonic_ns()\n    ready=receive(worker,owner,path);save(path/'ready.json',ready)",
       "    ready=receive(worker,owner,path);save(path/'ready.json',ready)\n    save(path/'startup-timing.json',dict(process_launch_monotonic_ns=worker.task10_launch_ns,ready_received_monotonic_ns=time.monotonic_ns(),process_to_ready_ms=(time.monotonic_ns()-worker.task10_launch_ns)/1e6,cache_state='NOT_PROVEN_COLD_FILE_CACHE'))"),
      ('        cpu=CPUWorker(args,', '        launch=time.monotonic_ns()\n        cpu=CPUWorker(args,'),
      ("        save(s1/'identity.json'", "        cpu.task10_launch_ns=launch\n        save(s1/'identity.json'"),
      ('        pl=owner.start_worker(BUNDLE);p.worker=pl', '        launch=time.monotonic_ns();pl=owner.start_worker(BUNDLE);pl.task10_launch_ns=launch;p.worker=pl')]
    for a,b in pairs:assert s.count(a)==1,a;s=s.replace(a,b)
    p.write_text(s,encoding='utf-8',newline='\n')
    save(OUT/'FROZEN_CONTROLLERS.json',dict(files={n:sha(ROOT/'platform/qwen35/a12'/n) for n in ('step10_manager.py','step10_window.py','step10_supervisor.py')},
         created_before_board_compute=True,normal_closeout='UNCHANGED_COMPLETE_SCAN_DEFAULT_RESTORE_AND_ARCHIVE'))
