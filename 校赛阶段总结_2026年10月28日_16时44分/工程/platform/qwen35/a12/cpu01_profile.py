"""Read frozen V1 and candidate V2 explicitly; never add alternate node views."""
import math


def audit_profile(profile):
    assert profile['schema'] == 'N02_REQUEST_PROFILE_V1'
    assert profile['enabled'] and profile['accounting_valid']
    nodes = profile['node_profile']
    assert nodes['enabled']
    schema = nodes.get('schema', 'A12_LEGACY_NODE_BUCKETS_NO_SCHEMA')
    assert schema in ('A12_LEGACY_NODE_BUCKETS_NO_SCHEMA', 'A12_CPU_NODE_PROFILE_V2')
    if schema.endswith('V2'):
        assert nodes['accounting_valid']
    output = {}
    for phase in ('prefill', 'decode'):
        native = profile['phases'][phase]
        assert native['decode_failures'] == native['graph_failures'] == native['mlp_failures'] == 0
        node = nodes['phases'][phase]
        if schema.endswith('V2'):
            categories = node['categories']
            total = node['total']['wall_ms']
            assert categories['mlp_custom_linear']['timed_groups'] == native['mlp_calls']
            for key in ('timed_groups', 'logical_nodes', 'fused_extra_nodes', 'wall_us'):
                assert sum(row[key] for row in categories.values()) == node['total'][key]
                assert sum(row[key] for row in node['aggregates']) == node['total'][key]
            assert sum(node['logical_op_counts'].values()) == node['total']['logical_nodes']
            assert node['total']['logical_nodes'] == node['total']['timed_groups'] + node['total']['fused_extra_nodes']
            assert node['metadata_prepares'] == native['graph_calls']
            assert all(node[k] == 0 for k in ('metadata_prepare_failures', 'missing_metadata_callbacks', 'invalid_fusion_callbacks', 'duplicate_callbacks'))
        else:
            assert set(node) == {'mlp_custom','output_head','attention_named_projections_and_full_attention',
                'linear_attention_and_fused_state','linear_convolution','explicit_state_copy','other_norm_activation_residual'}
            categories = node
            total = sum(row['wall_ms'] for row in node.values())
            assert categories['mlp_custom']['calls'] == native['mlp_calls']
        assert 0 <= total <= native['cpu_graph_wall_ms'] + 0.01
        assert abs(native['cpu_graph_wall_ms'] + native['host_graph_prepare_schedule_ms'] - native['llama_decode_wall_ms']) < 1e-5
        assert abs(native['mlp_inclusive_wall_ms'] + native['non_mlp_cpu_graph_ms'] - native['cpu_graph_wall_ms']) < 1e-5
        pieces = sum(native[k] for k in ('linear_service_wall_ms','activation_gather_ms','activation_quant_ms',
            'activation_cache_copy_ms','output_copy_ms','bridge_other_ms'))
        assert abs(pieces - native['mlp_inclusive_wall_ms']) < 1e-5
        assert all(math.isfinite(v) and v >= 0 for k, v in native.items() if k.endswith('_ms'))
        pl = profile.get('pl_profile', {}).get('phases', {}).get(phase, {})
        if pl.get('calls', 0):
            back = pl['backend']
            assert pl['calls'] == native['mlp_calls']
            assert pl['backend_call_wall_ms'] + pl['completion_report_wall_ms'] <= native['linear_service_wall_ms'] + 0.01
            services = sum(back[k] for k in ('a11_input_copy_and_meta_seed_ms','a11_input_bo_sync_ms','a11_set_args_ms',
                'a11_submit_to_confirmed_completion_ms','a11_meta_sync_ms','a11_meta_validate_ms','a11_output_bo_sync_and_map_ms','a11_output_validate_ms'))
            assert abs(services - back['service_ms']) < 1e-5
            assert back['service_ms'] + back['a12_permission_wait_ms'] <= pl['backend_call_wall_ms'] + 0.01
        output[phase] = dict(categories=categories, node_group_wall_ms=total,
                             graph_planning_barrier_timer_remainder_ms=native['cpu_graph_wall_ms'] - total)
    return dict(schema=schema, phases=output)
