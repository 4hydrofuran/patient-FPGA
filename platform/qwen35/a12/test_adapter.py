"""Application identity, no-fallback and state-delivery gate tests; no subprocess."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from system_qwen35.app.native_pl import NativePL


def ready():
    return dict(type='ready',execution_kind='PC_MATH_DOUBLE',physical_ubatch=8,
       cache_policy='R0_CLEAR_ALL_REPLAY',attention_schedule='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING',
       non_mlp_projection_schedule='STABLE_PER_TOKEN_SIMD_GEMV',
       bridge=dict(a12_route=dict(a12_route_scope='all',contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6')))


class Worker:
    def __init__(self,broken=False):self.requests=[];self.broken=broken;self.closed=False
    def send(self,r):self.requests.append(r)
    def get(self,t):
        return dict(type='result',id=self.requests[-1]['id'],status='OK',partial_output_usable=True,
           state_cleared_before_response=not self.broken,state_position_after_clear=-1,
           bridge=dict(a12_route=dict(a12_domain='PC_MATH_DOUBLE')))
    def close(self):self.closed=True;return False


class Tests(unittest.TestCase):
    def test_backend_and_scope_identity(self):
        r=ready();r['bridge']['a12_route']['a12_route_scope']='l0'
        with self.assertRaises(RuntimeError):NativePL(Worker(),r,max_output_tokens=2,domain='PC')
        with self.assertRaises(RuntimeError):NativePL(Worker(),ready(),max_output_tokens=2,domain='BOARD')
    def test_delivery_and_non_thinking_template(self):
        w=Worker();a=NativePL(w,ready(),max_output_tokens=2,domain='PC')
        r=a.generate([dict(role='user',content='哪里痛？')])
        self.assertEqual(r['actual_backend'],'PC_MATH_DOUBLE');self.assertEqual(w.requests[0]['max_tokens'],2)
        self.assertTrue(w.requests[0]['prompt'].endswith('<think>\n\n</think>\n\n'))
    def test_state_failure_blocks_delivery_and_following_request(self):
        w=Worker(True);a=NativePL(w,ready(),max_output_tokens=2,domain='PC')
        with self.assertRaises(RuntimeError):a.generate([dict(role='user',content='哪里痛？')])
        with self.assertRaises(RuntimeError):a.generate([dict(role='user',content='还有呢？')])
        self.assertEqual(len(w.requests),1)
    def test_close_does_not_claim_recovery(self):
        w=Worker();a=NativePL(w,ready(),max_output_tokens=2,domain='PC')
        self.assertFalse(a.close());self.assertTrue(w.closed)


if __name__=='__main__':unittest.main()
