"""Real retained checker false positives plus polarity/value/extra-claim negatives."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from system_qwen35.app.test_a02 import planned
from system_qwen35.app.checking import check
class Regressions(unittest.TestCase):
    def test_unknown_radiation_relation(self):
        p=planned('疼痛会牵扯到别的地方吗？','SYN_CP_03')
        self.assertEqual(check(p,'疼痛牵涉部位我不清楚。')['status'],'pass')
        for text in ('疼痛牵涉到左臂。','疼痛没有牵涉部位。','疼痛牵涉部位我不清楚，我没有气短。'):
            with self.subTest(text=text):self.assertNotEqual(check(p,text)['status'],'pass')
    def test_known_not_unknown(self):
        self.assertNotEqual(check(planned('会牵扯到哪里？','SYN_CP_01'),'疼痛牵涉部位我不清楚。')['status'],'pass')
    def test_trigger_order(self):
        p=planned('什么情况下容易痛？','SYN_CP_01')
        self.assertEqual(check(p,'快走时出现疼痛。')['status'],'pass')
        for text in ('快走时没有出现疼痛。','不快走时出现疼痛。','慢走时出现疼痛。','快走时出现疼痛，持续20分钟。','快走后疼痛缓解。'):
            with self.subTest(text=text):self.assertNotEqual(check(p,text)['status'],'pass')
if __name__=='__main__':unittest.main()
