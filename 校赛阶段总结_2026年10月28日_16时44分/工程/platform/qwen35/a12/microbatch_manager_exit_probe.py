"""Disposable PC test manager exits while its child has cached grant credit."""
import os
from pathlib import Path
import sys
from microbatch_evidence import read
import test_microbatch_abi as fixture

fixture.BUILD=read(sys.argv[1]);root=Path(sys.argv[2]);root.mkdir()
actor=fixture.Actor(root,count=3);actor.ready(8)
assert actor.call(op='run',job=1)['rc']==0
actor.send(op='run',job=2,wait_parent_exit_pid=os.getpid(),parent_exit_report=str(root/'parent-exit-result.json'))
# Explicit abrupt PC-manager exit, no destructor/revoke or platform operations.
os._exit(0)
