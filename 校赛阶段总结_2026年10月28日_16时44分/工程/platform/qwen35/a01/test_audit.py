import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('audit',HERE/'audit_model.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class AuditRegression(unittest.TestCase):
    def test_text_v_projection_not_vision(self):
        self.assertFalse(audit.excluded_tensor('blk.3.attn_v.weight'))
        self.assertFalse(audit.excluded_tensor('blk.0.attn_qkv.weight'))
    def test_excluded_namespaces(self):
        for name in ['v.blk.0.weight','mm.0.weight','blk.24.ffn_up.weight','blk.24.nextn.eh_proj.weight']:
            with self.subTest(name=name):self.assertTrue(audit.excluded_tensor(name))
    def test_visual_bias_is_not_text_bias(self):
        self.assertFalse(audit.trunk_mlp_bias('model.visual.blocks.0.mlp.linear_fc1.bias'))
        self.assertTrue(audit.trunk_mlp_bias('model.language_model.layers.0.mlp.up_proj.bias'))
    def test_actual_mlp_map(self):
        m=json.loads((audit.ROOT/'quant/qwen35_tensor_map.json').read_text(encoding='utf-8'))
        self.assertEqual(len(m['mlp']),72)
        self.assertEqual(len({x['source'] for x in m['mlp']}),72)
        self.assertTrue(all(x['f16_elementwise_source_match'] and not x['transpose_data'] for x in m['mlp']))
        self.assertFalse(m['boundaries']['unknown'])
    def test_current_lock_not_old_model(self):
        m=json.loads((audit.ROOT/'models/model.lock.json').read_text())
        self.assertEqual(m['model'],'Qwen/Qwen3.5-0.8B')
        self.assertFalse(m['vision_exported']);self.assertFalse(m['mtp_exported'])
        self.assertEqual(len(m['converted_files']),2)


if __name__=='__main__':unittest.main()
