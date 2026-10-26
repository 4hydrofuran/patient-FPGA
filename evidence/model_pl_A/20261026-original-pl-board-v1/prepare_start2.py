from pathlib import Path
p=Path(__file__).parent;s=(p/'start.py').read_text(encoding='utf-8')
s=s.replace('run_bound_original.py','run_bound_original2.py').replace('COMPUTE_BASELINE_REVIEW.json','COMPUTE_BASELINE_REVIEW-v2.json').replace('manager.stdout','manager2.stdout').replace('manager.stderr','manager2.stderr').replace('ATTEMPT_RESULT.json','ATTEMPT_RESULT-v2.json').replace('time.monotonic()+480','time.monotonic()+240')
(p/'start2.py').write_text(s,encoding='utf-8')
u=(p/'uart_http.ps1').read_text(encoding='utf-8').replace("'preflight','start'","'preflight','start2'").replace("$Stage='preflight'","$Stage='start2'").replace("$Stage -eq 'start'","$Stage -eq 'start2'")
(p/'uart_http2.ps1').write_text(u,encoding='utf-8')
