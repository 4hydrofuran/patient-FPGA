"""Final send/return guards after a blocked journal operation."""
import json
import threading
import time
import types
import unittest
from unittest import mock

from health_fence import HealthFence,HealthBlocked
from native_health_fence import FencedSocket,HealthFencedNativeWorker


class BoundaryTests(unittest.TestCase):
    def worker(self):
        m=HealthFence(lambda:dict(ok=True));self.addCleanup(m.stop)
        # A real subclass instance without starting a process. This preserves
        # Python super() dispatch for the END/receipt hook under test.
        w=HealthFencedNativeWorker.__new__(HealthFencedNativeWorker)
        w.monitor=m;w.quarantined=False;w._request_failed=False
        w.delivery_cancelled=False;w.expires=time.monotonic()+5;w._health_local=threading.local()
        w._health_boundary=lambda t,closing=False:HealthFencedNativeWorker._health_boundary(w,t,closing=closing)
        w._health_local.ticket=m.fence();w._health_local.context=dict(sequence=3,phase='submit')
        return w

    def test_cancellation_expiry_or_quarantine_after_record_refuses_send(self):
        for key,value in (('delivery_cancelled',True),('quarantined',True),('_request_failed',True),('expires',0)):
            w=self.worker();setattr(w,key,value);sock=mock.Mock();proxy=FencedSocket(sock,w)
            with self.assertRaises(HealthBlocked):proxy.sendall(b'{"sequence":3,"allow":true}\n')
            sock.sendall.assert_not_called()

    def test_new_monitor_fault_after_record_refuses_send_and_ticket(self):
        w=self.worker();sock=mock.Mock();proxy=FencedSocket(sock,w);w.monitor._fault('late fault')
        with self.assertRaises(HealthBlocked):proxy.sendall(b'{"sequence":3,"allow":true}\n')
        sock.sendall.assert_not_called()

    def test_normal_send_once_and_sequence_binding(self):
        w=self.worker();sock=mock.Mock();proxy=FencedSocket(sock,w)
        proxy.sendall(b'{"sequence":3,"allow":true}\n');sock.sendall.assert_called_once()
        with self.assertRaises(HealthBlocked):proxy.sendall(b'{"sequence":3,"allow":true}\n')
        self.assertEqual(sock.sendall.call_count,1)

    def test_router_close_keeps_old_cancel_exception_but_not_fault_exception(self):
        w=self.worker();w.delivery_cancelled=True;w.expires=0
        w._health_local.context=dict(sequence=3,phase='router_close');sock=mock.Mock()
        FencedSocket(sock,w).sendall(b'{"sequence":3,"allow":true}\n');sock.sendall.assert_called_once()
        w=self.worker();w.quarantined=True;w._health_local.context=dict(sequence=3,phase='router_close')
        sock=mock.Mock()
        with self.assertRaises(HealthBlocked):FencedSocket(sock,w).sendall(b'{"sequence":3,"allow":true}\n')
        sock.sendall.assert_not_called()

    def test_completed_end_and_receipt_cannot_bypass_late_guard(self):
        for change in ('fault','cancel'):
            w=self.worker();w._chain='a'*64;w._completed_ids=['app_R0'];w.health_result_boundaries=[]
            w._isolate=lambda reason:setattr(w,'_request_failed',True);w.record=mock.Mock()
            def end(*args,**kw):
                if change=='fault':w.monitor._fault('after END')
                else:w.delivery_cancelled=True
            with mock.patch('native_health_fence.NativeJournalWorker._finish_verified',side_effect=end):
                with self.assertRaises(HealthBlocked):HealthFencedNativeWorker._finish_verified(w,None,None,None)
            self.assertEqual(w.health_result_boundaries,[]);self.assertTrue(w._request_failed)


if __name__=='__main__':unittest.main(verbosity=2)
