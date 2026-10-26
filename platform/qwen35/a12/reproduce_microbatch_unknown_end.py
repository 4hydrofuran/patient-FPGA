"""Actual CPU API failure: preserve v4 local-END gap and v5 refusal."""
from pathlib import Path
import tempfile
from microbatch_evidence import OUT,read,save
import test_microbatch_abi as fixture

rows=[]
for revision in (4,5):
    fixture.BUILD=read(OUT/('BUILD-v'+str(revision)+'.json'))
    with tempfile.TemporaryDirectory(prefix='a12-unknown-end-') as d:
        actor=fixture.Actor(Path(d),budget=3,count=3)
        try:
            actor.ready(3);result=actor.call(op='run',job=1,bad_size=True)
            end_rc=actor.page.end_fn(actor.page.handle,1)
            assert result['rc']!=0 and result['report']['pc_started_calls']==1 and result['report']['cpu_run_count']==0
            assert (end_rc==0) is (revision==4)
            rows.append(dict(revision=revision,actual_cpu_failure=result,end_rc=end_rc,
                gate_after_end=actor.page.gate(),private_scope='LOCAL_GUARD_ONLY_NOT_OLD_MANAGER_ACCEPTANCE',
                BOARD='NOT_TESTED',PL_calls=0))
        finally:actor.close()
save(OUT/'UNKNOWN_END_V4_V5_REPRODUCTION.json',dict(status='REPRODUCED_V4_GAP_V5_REJECTS',cases=rows,
    limitation='No real DMA or kernel-failure injection; old manager already rejects failed CPU results'))
