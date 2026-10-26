"""Control-only tests; synthetic button actions are NOT human approval evidence."""
import threading,unittest
from .review import ReviewGate

class ReviewTests(unittest.TestCase):
    def test_exact_ticket_and_raw_text(self):
        seen=[];cancel=threading.Event();gate=None
        def notify(p):
            seen.append(p)
            self.assertFalse(gate.confirm('stale-ticket','yes'))
            self.assertTrue(gate.confirm(p['ticket'],'yes'))
            self.assertFalse(gate.confirm(p['ticket'],'no'))
        gate=ReviewGate(notify)
        self.assertTrue(gate.request('我不是没有气短。',cancel))
        self.assertEqual(seen[0]['text'],'我不是没有气短。')
        self.assertEqual(gate.last['raw_text'],'我不是没有气短。')
        self.assertIsNone(gate.pending)
        self.assertFalse(gate.confirm(seen[0]['ticket'],'yes'))

    def test_decline_never_rewrites(self):
        gate=None
        def notify(p):gate.confirm(p['ticket'],'no')
        gate=ReviewGate(notify)
        self.assertFalse(gate.request('过年情况',threading.Event()))
        self.assertEqual(gate.last['reason'],'declined');self.assertEqual(gate.last['raw_text'],'过年情况')

    def test_timeout_is_not_approval(self):
        gate=ReviewGate(lambda p:None,timeout_s=.02)
        self.assertFalse(gate.request('原始转录',threading.Event()))
        self.assertEqual(gate.last['reason'],'timeout');self.assertIsNone(gate.pending)

    def test_cancel_beats_approval(self):
        cancel=threading.Event();gate=None
        def notify(p):gate.confirm(p['ticket'],'yes');cancel.set()
        gate=ReviewGate(notify)
        self.assertFalse(gate.request('原始转录',cancel));self.assertEqual(gate.last['reason'],'cancelled')

    def test_bound_and_invalid_response(self):
        for t in (0,-1,61):
            with self.assertRaises(ValueError):ReviewGate(lambda p:None,t)
        gate=ReviewGate(lambda p:None)
        with self.assertRaises(ValueError):gate.confirm('ticket','YES')

    def test_no_parallel_review(self):
        gate=None
        def notify(p):
            with self.assertRaises(RuntimeError):gate.request('other',threading.Event())
            gate.confirm(p['ticket'],'no')
        gate=ReviewGate(notify)
        self.assertFalse(gate.request('first',threading.Event()));self.assertIsNone(gate.pending)

if __name__=='__main__':unittest.main()
