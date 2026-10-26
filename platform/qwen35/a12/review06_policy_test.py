"""Regression for original failed budget, cached case and allocated-stage accounting."""
import tempfile
from pathlib import Path
from common import sha,save
from review06_common import OUT
from capacity_policy import admission,review_archive_cache

if __name__=='__main__':
    total=140591104;rows=[]
    for label,mem,cma,charged,expected in [
      ('original_v1',2885608,216712,0,False),('original_v2',2953080,432612,0,True),
      ('step07_min_sample_only',2920336,373204,0,True),
      ('already_allocated_do_not_deduct_twice',2000000,110000,total,True),
      ('already_allocated_below_extra_reserve',2000000,98000,total,False),
      ('host_margin_fail',1100000,500000,0,False)]:
        r=admission(dict(MemAvailable=mem,CmaFree=cma),total,already_charged_bo_bytes=charged)
        assert r['allowed']==expected;rows.append(dict(case=label,**r))
    for charged in (-1,total+1):
        try:admission(dict(MemAvailable=2000000,CmaFree=200000),total,already_charged_bo_bytes=charged)
        except ValueError:pass
        else:raise AssertionError('bad charge accepted')
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'archive';p.write_bytes(b'fixed artifact bytes')
        pin=dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p));before=p.read_bytes()
        r=review_archive_cache([pin]);assert p.read_bytes()==before and r[0]['hash_verified_before_advice']
        try:review_archive_cache([dict(pin,sha256='0'*64)])
        except RuntimeError:pass
        else:raise AssertionError('foreign artifact accepted')
        link=Path(tmp)/'link';link.symlink_to(p)
        try:review_archive_cache([dict(pin,path=str(link))])
        except OSError:pass
        else:raise AssertionError('symlink accepted')
    save(OUT/'CAPACITY_POLICY_PC.json',dict(status='PASS_ORIGINAL_FAILURE_RETAINED_AND_STAGE_ACCOUNTING_CACHE_GUARDS',cases=rows,
       invalid_charge_checks=2,cache_wrong_hash_and_symlink_rejected=True,BOARD='NOT_TESTED'))
    print('PASS_CAPACITY_ADMISSION_AND_EXACT_ARTIFACT_CACHE_GUARDS')
