"""Real Linux FD/flock fixtures, one-use approval and fail-closed mutation tests."""
import fcntl
import os
from pathlib import Path
import tempfile
import time
from generation_binding import FixtureIssuer,Approval,board_issuer
from generation_evidence import OUT,save

def rejected(fn):
    try:fn()
    except (RuntimeError,OSError,ValueError):return
    raise AssertionError('expected specific generation operation to be refused')

def main():
    os.umask(0o077);results=[]
    def run(name,fn):
        with tempfile.TemporaryDirectory(prefix='a12-generation-') as root:
            issuer=FixtureIssuer(Path(root)/'fixture',time.monotonic_ns()+10_000_000_000)
            try:fn(issuer);results.append(dict(test=name,status='PASS_PC_ONLY'))
            finally:issuer._test_cleanup()
    def normal(i):
        rejected(lambda:i.issue('z'*64))
        a=i.issue('1'*64);i.consume(a,'1'*64);i.observe();assert i.used and i.pending is None
        rejected(lambda:i.consume(a,'1'*64));rejected(lambda:i.issue('1'*64))
    run('normal_one_use_and_replay_refused',normal)
    def counterfeit(i):
        a=i.issue('1'*64)
        for q in ({},Approval(i,a.nonce,a.context,a.observed_ns),object()):
            rejected(lambda:i.consume(q,'1'*64))
        rejected(lambda:i.consume(a,'2'*64));i.consume(a,'1'*64)
    run('JSON_copy_foreign_capability_and_wrong_context_refused',counterfeit)
    def stale(i):
        a=i.issue('1'*64);object.__setattr__(a,'observed_ns',time.monotonic_ns()-250_000_001)
        rejected(lambda:i.consume(a,'1'*64));assert not i.used
    run('stale_capability_refused',stale)
    def expiry(i):
        i.deadline=time.monotonic_ns()-1;rejected(i.observe);assert i.blocked
    run('expired_lease_refused',expiry)
    for field in ('boot_id','driver_generation','kernel_generation','device_generation','BO_generation','mutation_serial','epoch'):
        def changed(i,field=field):
            p=i.directory/'identity.json';raw=p.read_bytes();needle=('"'+field+'"').encode();assert needle in raw
            p.write_bytes(raw.replace(needle,b'"changed_'+field.encode()+b'"',1));rejected(i.observe)
            p.write_bytes(raw);rejected(i.observe);assert i.blocked and len(i.locks)==2
        run('changed_'+field+'_latches_revoke',changed)
    def lease_bytes(i):
        p=i.directory/'lease.json';st=p.stat();raw=p.read_bytes();p.write_bytes(raw.replace(b'"manager_pid"',b'"manager_pId"'))
        os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns));rejected(i.observe);assert i.blocked
    run('lease_bytes_changed_with_restored_mtime_refused',lease_bytes)
    def unlock(i):
        fcntl.flock(i.locks[1][1],fcntl.LOCK_UN);rejected(i.observe);assert i.blocked
    run('lost_second_actual_flock_refused',unlock)
    def replacement(i):
        p,_=i.locks[0];p.rename(p.with_name('old.lock'));p.write_bytes(b'');p.chmod(0o600);rejected(i.observe)
    run('canonical_lock_replaced_refused',replacement)
    def symlink(i):
        p,_=i.locks[0];old=p.with_name('old.lock');p.rename(old);p.symlink_to(old);rejected(i.observe)
    run('canonical_lock_symlink_refused',symlink)
    def permissions(i):
        i.locks[0][0].chmod(0o660);rejected(i.observe)
    run('canonical_lock_permissions_refused',permissions)
    def directory_permissions(i):
        i.directory.chmod(0o777);rejected(i.observe)
    run('fixture_directory_permissions_refused',directory_permissions)
    def process_identity(i):
        i.ticks+=1;rejected(i.observe);assert i.blocked
    run('manager_start_ticks_changed_refused',process_identity)
    def actual_boot(i):
        i.boot='different actual boot';rejected(i.observe);assert i.blocked
    run('actual_boot_binding_changed_refused',actual_boot)
    def mutation(i):
        called=[];rejected(lambda:i.before_platform_mutation(lambda:called.append('revoke_first')))
        assert called==['revoke_first'] and i.blocked and len(i.locks)==2;rejected(i.observe)
    run('before_mutation_revokes_without_executing_or_releasing',mutation)
    rejected(board_issuer);results.append(dict(test='Board_factory_hard_disabled',status='PASS_REFUSAL'))
    save(OUT/'ISSUER_TEST-v2.json',dict(status='PASS_PC_LIVE_FD_ISSUER_TESTS',tests=results,count=len(results),
        real_board_identity='NOT_TESTED',real_BO_inventory='NOT_TESTED',Board_issuer='DISABLED',model_settings='unknown',DeepSeek_used=False))
    print('PASS_PC_LIVE_FD_ISSUER_TESTS',len(results))
if __name__=='__main__':main()
