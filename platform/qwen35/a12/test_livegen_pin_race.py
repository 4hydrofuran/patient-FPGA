"""Revocation must precede observer cleanup locks; FD reuse stays isolated."""
import os
from pathlib import Path
import tempfile
import threading
import time
from livegen_evidence import ROOT,OUT,read,save
from livegen_source import NodePins,MutationInterlock
from livegen_fixtures import FixturePorts
from livegen_binding import Binding
from plm_page import Page,REVOKED

def main():
    os.umask(0o077);b=read(OUT/'BUILD-v2.json');failures=[]
    with tempfile.TemporaryDirectory(prefix='a12-pin-race-') as root:
        root=Path(root);node=root/'node';node.write_text('PC_ONLY\n');guard=root/'guard';guard.write_text('OWN_GUARD\n')
        pins=NodePins([node]);barrier=threading.Barrier(8)
        def close_and_reuse():
            try:
                barrier.wait()
                for _ in range(200):
                    pins.close();fd=os.open(guard,os.O_RDONLY|os.O_CLOEXEC)
                    try:assert os.fstat(fd).st_ino==guard.stat().st_ino
                    finally:os.close(fd)
            except BaseException as e:failures.append(type(e).__name__+': '+str(e))
        threads=[threading.Thread(target=close_and_reuse) for _ in range(8)]
        for t in threads:t.start()
        for t in threads:t.join(10)
        assert not failures and all(not t.is_alive() for t in threads) and pins.closed
        ports=FixturePorts(root/'fixture',time.monotonic_ns()+10_000_000_000);page=Page(b['writer_library'],b['writer_sha256'])
        binding=Binding(page,b,ports,MutationInterlock());started=threading.Event()
        def revoke():
            started.set()
            try:binding.source.revoke('PC held observer lock fixture')
            except BaseException as e:failures.append(str(e))
        with ports.nodes.lock:
            thread=threading.Thread(target=revoke);thread.start();assert started.wait(1)
            until=time.monotonic()+2
            while not page.state()&REVOKED and time.monotonic()<until:time.sleep(.001)
            assert page.state()&REVOKED and thread.is_alive() # blocked only AFTER native revocation
        thread.join(5);assert not thread.is_alive() and not failures and ports.nodes.closed
        assert binding.source.blocked and len(ports.base.locks)==2
        binding.slot.close();binding.observer.close();ports.test_cleanup();page.close()
    save(OUT/'PIN_CONCURRENCY_TEST.json',dict(status='PASS_REVOCATION_BEFORE_CLEANUP_LOCK_AND_NO_FD_REUSE_DAMAGE',
        concurrent_closers=8,close_reuse_attempts=1600,unrelated_guard_FD_failures=failures,
        native_atomic_revoke_visible_while_observer_lock_held=True,original_lease_dual_locks_retained=True,BOARD='NOT_TESTED'))
    print('PASS_REVOCATION_BEFORE_CLEANUP_LOCK_AND_NO_FD_REUSE_DAMAGE')
if __name__=='__main__':main()
