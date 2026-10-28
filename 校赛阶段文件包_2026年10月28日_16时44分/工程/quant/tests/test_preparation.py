import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_audit as audit
import compare_logits as logits


class HeaderTests(unittest.TestCase):
    def check_file(self, header, payload=b'\0' * 12):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'fixture.safetensors'
            raw = json.dumps(header).encode()
            p.write_bytes(struct.pack('<Q', len(raw)) + raw + payload)
            return audit.tensor_header(p)

    def test_non_square_shape_retained(self):
        h, offset = self.check_file({'w': dict(dtype='BF16', shape=[2, 3], data_offsets=[0, 12])})
        self.assertEqual(h['w']['shape'], [2, 3])
        self.assertGreater(offset, 8)

    def test_overlapping_or_gapped_tensors_rejected(self):
        for offsets in ([2, 6], [8, 12]):
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                self.check_file({'a': dict(dtype='BF16', shape=[2], data_offsets=[0, 4]),
                                 'b': dict(dtype='BF16', shape=[2], data_offsets=offsets)})

    def test_wrong_byte_size_rejected(self):
        with self.assertRaises(ValueError):
            self.check_file({'w': dict(dtype='BF16', shape=[2, 3], data_offsets=[0, 10])})

    def test_duplicate_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            audit.unique_pairs([('w', 1), ('w', 2)])


class MappingTests(unittest.TestCase):
    def fixture(self):
        config = dict(architectures=['Qwen2ForCausalLM'], hidden_act='silu', hidden_size=2,
                      intermediate_size=3, num_hidden_layers=1, vocab_size=5, tie_word_embeddings=True)
        tensors = {f'model.layers.0.mlp.{p}_proj.weight': dict(shape=s, dtype='BF16', data_offsets=[0, 12])
                   for p, s in [('gate', [3, 2]), ('up', [3, 2]), ('down', [2, 3])]}
        tensors['model.embed_tokens.weight'] = dict(shape=[5, 2])
        for p in ('q', 'k', 'v'):
            tensors[f'model.layers.0.self_attn.{p}_proj.bias'] = dict(shape=[2])
        return config, tensors

    def test_ggml_dimension_order_not_payload_transpose(self):
        c, t = self.fixture()
        rows = audit.mapping(c, t)
        self.assertEqual(rows[0]['logical_shape_N_K'], [3, 2])
        self.assertEqual(rows[0]['ggml_ne_K_N'], [2, 3])
        self.assertFalse(rows[0]['transpose_payload'])
        self.assertEqual(rows[2]['graph_output'], 'ffn_out')

    def test_transposed_source_rejected(self):
        c, t = self.fixture()
        t['model.layers.0.mlp.gate_proj.weight']['shape'] = [2, 3]
        with self.assertRaises(ValueError):
            audit.mapping(c, t)

    def test_unexpected_mlp_bias_rejected(self):
        c, t = self.fixture()
        t['model.layers.0.mlp.gate_proj.bias'] = dict(shape=[3])
        with self.assertRaises(ValueError):
            audit.mapping(c, t)

    def test_unreviewed_explicit_lm_head_rejected(self):
        c, t = self.fixture()
        t['lm_head.weight'] = dict(shape=[5, 2])
        with self.assertRaises(ValueError):
            audit.mapping(c, t)


class LogitsTests(unittest.TestCase):
    def meta(self, stage='original', sidecar=None):
        return dict(schema='a2-float-observation-0.1', model_revision='fixture',
                    original_weight_sha256='fixture', token_ids_sha256='fixture', chat_template_sha256='fixture',
                    prompt_sha256='fixture', context_token_ids=[1, 2], positions=[1], vocab_size=3,
                    stage=stage, sidecar_sha256=sidecar,
                    comparison_basis=dict(engine_commit='fixture-engine', non_mlp_model_sha256='fixture-non-mlp', evaluation_protocol='fixture-protocol'))

    def test_identical_metrics_not_acceptance(self):
        a = np.array([[1., 3., 2.], [0., 0., 0.]], dtype=np.float32)
        r = logits.metrics(a, a)
        self.assertEqual(r['max_abs_error'], 0)
        self.assertEqual(r['top1_agreement'], 1)
        self.assertEqual(r['mean_kl_reference_to_candidate'], 0)
        self.assertIsNone(r['accepted'])

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            logits.metrics(np.array([[float('nan')]]), np.array([[0.]]))

    def test_changed_context_rejected(self):
        a, b = self.meta(), self.meta('sidecar_cpu', 'fixture-sidecar')
        b['context_token_ids'] = [2, 1]
        with self.assertRaisesRegex(ValueError, 'context_token_ids'):
            logits.compare_meta(a, b, 'quantization')

    def test_hardware_requires_same_sidecar(self):
        with self.assertRaisesRegex(ValueError, 'identical sidecar'):
            logits.compare_meta(self.meta('sidecar_cpu', 'a'), self.meta('sidecar_fpga', 'b'), 'hardware')

    def test_hardware_does_not_accept_original_baseline(self):
        with self.assertRaises(ValueError):
            logits.compare_meta(self.meta(), self.meta('sidecar_fpga', 'b'), 'hardware')

    def test_quantization_pair_valid(self):
        logits.compare_meta(self.meta(), self.meta('sidecar_cpu', 'fixture-sidecar'), 'quantization')

    def test_diagnostic_pair_does_not_allow_different_stage(self):
        with self.assertRaises(ValueError):
            logits.compare_meta(self.meta(), self.meta('sidecar_cpu', 'fixture-sidecar'), 'diagnostic')

    def test_large_logits_stable(self):
        a = np.array([[10000., 10001.]])
        r = logits.metrics(a, a + 5)
        self.assertEqual(r['max_abs_error'], 5)
        self.assertAlmostEqual(r['mean_kl_reference_to_candidate'], 0)

    def test_cross_engine_quality_comparison_rejected(self):
        a, b = self.meta(), self.meta('sidecar_cpu', 'fixture-sidecar')
        b['comparison_basis']['engine_commit'] = 'different-engine'
        with self.assertRaisesRegex(ValueError, 'comparison basis'):
            logits.compare_meta(a, b, 'quantization')

    def test_missing_pipeline_basis_rejected(self):
        a, b = self.meta(), self.meta('sidecar_cpu', 'fixture-sidecar')
        del a['comparison_basis']
        with self.assertRaisesRegex(ValueError, 'comparison basis'):
            logits.compare_meta(a, b, 'quantization')


if __name__ == '__main__':
    unittest.main()
