"""仅归档已退出b04的失败预约；不解锁任何未知任务。"""
import json
from pathlib import Path
import sys

assert sys.platform == 'linux'
central = Path('/home/member-a/kv260-build/ra02-coordinator')
job = '01792899562136505946-A-a13-codecm-build-b04-46ce3535'
work = central / 'work' / job
assert work.resolve().parent == (central / 'work').resolve() and not work.is_symlink()
active = central / 'active.json'
value = json.loads(active.read_text())
assert value['job'] == job and value['owner'] == 'A' and not value['board_authorized']
result = json.loads((central / 'results' / (job + '.json')).read_text())
complete = json.loads(Path('/mnt/c/Patientqwen/local/a13c_b04/NATIVE_COMPLETION.json').read_text())
assert result['exit_code'] == complete['exit_code'] == 1 and result['status'] == 'FAILED'
assert complete['job'] == job
target = work / 'retained-failed-active.json'
assert not target.exists() and target.resolve().parent == work.resolve()
active.rename(target)
print(json.dumps({'archived_owned_failed_marker': str(target), 'original_failure_preserved': True,
                  'BOARD': 'NOT_TESTED'}))
