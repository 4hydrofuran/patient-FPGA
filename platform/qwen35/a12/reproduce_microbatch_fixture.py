"""Preserve the first test fixture's stale-limit overgrant and real refusal."""
from pathlib import Path
import tempfile
from microbatch_evidence import OUT,read,save
import test_microbatch_abi as fixture

fixture.BUILD=read(OUT/'BUILD-v5.json')
with tempfile.TemporaryDirectory(prefix='a12-fixture-repro-') as d:
    actor=fixture.Actor(Path(d),budget=4,count=3)
    try:
        actor.ready(4);first=actor.call(op='run',job=1);actor.page.end(1);actor.page.begin(1,1,'b'*64)
        second=actor.call(op='run',job=2)
        assert first['rc']==0 and second['rc']!=0 and second['report']['pc_started_calls']==1
        save(OUT/'FIXTURE_OVERGRANT_REPRODUCTION-v5.json',dict(status='REPRODUCED_REAL_BACKEND_REFUSAL',
            fixture_old_limit=4,real_new_limit=2,first=first,second=second,requests=actor.grants,
            reason='Fixture retained old range limit after request generation changed; native guard correctly refuses',
            BOARD='NOT_TESTED',PL_calls=0))
    finally:actor.close()
