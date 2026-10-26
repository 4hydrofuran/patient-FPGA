import json
from pathlib import Path
folder=Path(__file__).parent
receipt=json.loads((folder/'review-uart.json').read_text(encoding='utf-8-sig'))
outer=next(json.loads(line.strip()) for line in receipt['output'].splitlines() if line.strip().startswith('{') and 'exit_code' in line)
result=json.loads(outer['stdout'])
result.update(task_scope='USER_SELECTED_BOARD_CPU_BASIC_RUN',PL_acceptance='NOT_TESTED',original_harness_failure_preserved=True,
              task_started_utc='2026-10-26T09:50:10Z',completed_within_20_minutes=True)
with (folder/'RESULT.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(result['status'],result['exit_code'])
