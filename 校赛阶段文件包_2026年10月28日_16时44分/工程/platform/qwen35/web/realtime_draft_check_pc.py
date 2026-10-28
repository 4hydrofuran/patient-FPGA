"""Actual target-model serial/draft pairs, original checker and rejection replay."""
import argparse
import copy
import hashlib
import json
import os
import signal
from pathlib import Path
import statistics
import sys
import time
import threading

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from answer_cache_paths import default_parent, vendor_source
sys.path.insert(0, str(vendor_source()))
sys.path.insert(0, str(ROOT / 'platform/qwen35/a12'))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values), samples=len(values))


def run(args):
    from supervisor import OwnedWorker
    from answer_cache_build import enumerate_plans
    from short_prompt_adapter import prompt_messages
    if args.no_spaces:
        from compact_fact_prompt import prompt_messages_no_spaces as prompt_messages,no_space_policy_sha256 as policy_sha256
    elif args.compact:
        from compact_fact_prompt import prompt_messages,policy_sha256
    from realtime_draft import fact_copy_draft
    from patient_web.reference.checking import check
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'proof').mkdir()
    parent = default_parent()
    deps = read(parent / 'PC_DEPENDENCIES.json')
    config = read(ROOT / 'evidence/model_pl_A/20261027-fast-response-v1/release-model/prefix-config-PC.json')
    config['identity']['executable_sha256'] = digest(args.binary)
    config['identity']['threads']=config['identity']['kernel_threads']=args.threads
    if args.compact:config['identity']['live_miss_prompt_policy_sha256']=policy_sha256()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SP_A12', 'SP_TT10', 'LD_', 'GGML_', 'OMP_'))}
    env.update(LD_LIBRARY_PATH=deps['library_dir'], OMP_NUM_THREADS=str(args.threads), OPENBLAS_NUM_THREADS='1')
    template = ImmutableSandboxedEnvironment().from_string((parent / 'continuous/bundle/control/chat_template.jinja').read_text(encoding='utf-8'))
    plans_all=list(enumerate_plans())
    cache_id='short34-t'+str(args.threads)
    if args.no_spaces:
        from fast_response_profile import digest as object_digest
        probe=OwnedWorker([str(args.binary),deps['model'],str(args.threads),'1024','all','TILED',str(args.threads),'8'],
            directory=out/'tokenizer-probe',env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+1800,real=False)
        try:
            probe_ready=probe.get(120);assert probe_ready['type']=='ready' and probe_ready['execution_kind']=='CPU_REFERENCE'
            save(out/'tokenizer-ready.json',probe_ready)
            def tokenize(rid,text):
                probe.send(dict(op='tokenize',id=rid,prompt=text));r=probe.get(30)
                assert r['type']=='tokens' and r['id']==rid,r
                return r['tokens']
            sample=template.render(messages=prompt_messages(plans_all[0][1],''),add_generation_prompt=True,enable_thinking=False)
            marker='事实句：\n';neutral=sample[:sample.index(marker)+len(marker)]
            prefix_tokens=tokenize('new-neutral-prefix',neutral)
            tokenized=[]
            for index,(case,p) in enumerate(plans_all,1):
                prompt=template.render(messages=prompt_messages(p,''),add_generation_prompt=True,enable_thinking=False)
                ids=tokenize('input-'+str(index),prompt)
                assert ids[:len(prefix_tokens)]==prefix_tokens and len(ids)+args.output_tokens<=1024
                tokenized.append(dict(id=index,case_id=case.case_id,required_fact_ids=p.required_fact_ids,prompt=prompt,tokens=ids))
            save(out/'TOKENIZED_INPUTS.json',tokenized)
            save(out/'NEUTRAL_PREFIX.json',dict(text=neutral,tokens=prefix_tokens,sha256=object_digest(prefix_tokens)))
            config['allowed_prefixes']=[prefix_tokens]
            config['identity'].update(prompt_policy_sha256=policy_sha256(),live_miss_prompt_policy_sha256=policy_sha256(),
                neutral_prefix_choices_sha256=object_digest([prefix_tokens]),input_workload_sha256=object_digest(tokenized))
            cache_id='nospace'+str(len(prefix_tokens))+'-t'+str(args.threads)
        finally:
            assert probe.close(15)
    save(out / 'prefix-config.json', config)
    env['SP_TT10_CONFIG']=str(out/'prefix-config.json')
    worker = None
    rows = []
    calls = 0
    start = time.monotonic()
    try:
        worker = OwnedWorker([str(args.binary), deps['model'], str(args.threads), '1024', 'all', 'TILED', str(args.threads), '8'], directory=out / 'worker',
                             env=env, health=lambda: None, max_runs=1, max_loads=1, expires=time.monotonic() + 7200, real=False)
        ready = worker.get(120)
        assert ready['type'] == 'ready' and ready['execution_kind'] == 'CPU_REFERENCE', ready
        save(out / 'ready.json', ready)
        binding = ready['prefix_cache']['binding_sha256']

        def raw(request,allow_cancel=False):
            nonlocal calls
            worker.send(request)
            begin = time.monotonic()
            while True:
                result = worker.get(180)
                assert result.get('id') == request['id'], result
                if result['type'] != 'token':
                    break
            save(out / 'proof' / (request['id'] + '.json'), dict(request=request, result=result, wall_ms=(time.monotonic() - begin) * 1000))
            assert result['type'] in ('result', 'cache_created'), result
            assert result['status'] in (('OK','CANCELLED') if allow_cancel else ('OK',)) and result['state_cleared_before_response'] and result['state_position_after_clear'] == -1, result
            if result['type'] == 'result':
                calls += 1
                assert result['teacher_forced'] is False and (result['eos'] is True or (allow_cancel and result['status']=='CANCELLED')), result
            return result

        warm = copy.deepcopy(read(parent / 'continuous/bundle/control/requests.json')[1])
        warm['cache_binding_sha256'] = binding
        warm['cache_id']=cache_id
        warm['tokens']=config['allowed_prefixes'][0]
        raw(warm)
        plans = plans_all[:args.limit]
        for i, (case, plan) in enumerate(plans, 1):
            messages = prompt_messages(plan, '')
            draft = fact_copy_draft(messages)
            prompt = template.render(messages=messages, add_generation_prompt=True, enable_thinking=False)
            common = dict(prompt=prompt, max_tokens=args.output_tokens, logits_mode='final', cache_policy='TT10_REQUIRE_HIT',
                          cache_id=warm['cache_id'], cache_binding_sha256=binding, prefill_chunk=256, profile=False, diagnostic_report=False)
            # Alternate order for native timing; the browser A/B uses frozen original separately.
            results = {}
            for mode in (('serial', 'draft') if i % 2 else ('draft', 'serial')):
                request = dict(common, id=f'pair-{i:03d}-{mode}')
                if mode == 'draft':
                    request.update(draft_strategy='FACT_COPY_GREEDY_VERIFY_V1', draft_text=draft)
                results[mode] = raw(request)
                assert check(plan, results[mode]['text'])['status'] == 'pass', results[mode]
            a, b = results['serial'], results['draft']
            assert a['text'] == b['text'] and a['output_tokens'] == b['output_tokens'], (i, a, b)
            spec = b['speculative_decoding']
            assert spec['answer_cache_used'] is False and spec['forced_output'] is False
            if spec['accepted']:
                assert spec['argmax_checks'] == len(b['output_tokens']) + 1 and spec['target_eos_verified']
                assert spec['target_greedy_tokens'][:-1] == b['output_tokens']
            else:
                assert spec['fallback_full_prompt_replayed'] or not spec['used']
            row = dict(id=i, case_id=case.case_id if hasattr(case, 'case_id') else plan.case_id,
                       serial_ms=a['request_profile']['native_request_wall_ms'], draft_ms=b['request_profile']['native_request_wall_ms'],
                       accepted=spec['accepted'], fallback=spec['fallback_full_prompt_replayed'],
                       output_tokens=len(a['output_tokens']), prompt_tokens=a['prompt_tokens'],
                       serial_decode_calls=a['decode_calls'], draft_decode_calls=b['decode_calls'])
            if i <= args.rejects:
                wrong = raw(dict(common, id=f'pair-{i:03d}-wrong', draft_strategy='FACT_COPY_GREEDY_VERIFY_V1', draft_text='这是错误的草稿。'))
                assert wrong['speculative_decoding']['fallback_full_prompt_replayed']
                assert not wrong['speculative_decoding']['accepted']
                assert wrong['text'] == a['text'] and wrong['output_tokens'] == a['output_tokens']
                assert check(plan, wrong['text'])['status'] == 'pass'
                row['wrong_draft_full_replay'] = True
            if i == 1:
                no_prefix = raw(dict(common, id='draft-R0-no-prefix', cache_policy='R0', draft_strategy='FACT_COPY_GREEDY_VERIFY_V1', draft_text=draft))
                assert no_prefix['text'] == a['text'] and no_prefix['output_tokens'] == a['output_tokens']
                assert check(plan, no_prefix['text'])['status'] == 'pass'
                if args.extended_checks:
                    for label,proposal,cache_policy in [('late-reject',draft+'错误。','TT10_REQUIRE_HIT'),
                                                         ('missing-eos',draft.removesuffix('。'),'TT10_REQUIRE_HIT'),
                                                         ('reject-R0','这是错误的草稿。','R0')]:
                        rejected=raw(dict(common,id=label,cache_policy=cache_policy,draft_strategy='FACT_COPY_GREEDY_VERIFY_V1',draft_text=proposal))
                        assert rejected['speculative_decoding']['fallback_full_prompt_replayed'] and not rejected['speculative_decoding']['accepted']
                        assert rejected['output_tokens']==a['output_tokens'] and rejected['text']==a['text']
                    timer=threading.Timer(.05,lambda:os.kill(worker.process.pid,signal.SIGUSR1))
                    timer.start()
                    cancelled_result=raw(dict(common,id='cancel-during-verification',draft_strategy='FACT_COPY_GREEDY_VERIFY_V1',draft_text=draft),allow_cancel=True)
                    timer.join()
                    assert cancelled_result['status']=='CANCELLED' and not cancelled_result['speculative_decoding']['accepted']
                    recovered=raw(dict(common,id='after-cancel',draft_strategy='FACT_COPY_GREEDY_VERIFY_V1',draft_text=draft))
                    assert recovered['output_tokens']==a['output_tokens'] and recovered['text']==a['text']
            rows.append(row)
            save(out / 'PROGRESS.json', dict(completed=i, target=len(plans), accepted=sum(r['accepted'] for r in rows), calls=calls, last=row))
        assert worker.close(15)
        result = dict(status='PASS_ACTUAL_TARGET_GREEDY_PAIRS', rows=rows, total=len(rows), real_model_requests=calls,
                      proposed_from='THIS_REQUEST_CANONICAL_INPUT_FACTS_NOT_ANSWER_CATALOG', answer_cache_reads=0,
                      accepted=sum(r['accepted'] for r in rows), fallback=sum(r['fallback'] for r in rows),
                      serial_ms=summary([r['serial_ms'] for r in rows]), draft_ms=summary([r['draft_ms'] for r in rows]),
                      reduction_ms=summary([r['serial_ms'] - r['draft_ms'] for r in rows]),
                      wrong_draft_replays=min(args.rejects, len(rows)), worker_exit=worker.process.returncode,
                      binary_sha256=digest(args.binary), elapsed_s=time.monotonic() - start, BOARD='NOT_TESTED')
        result['threads']=args.threads
        result['output_limit']=args.output_tokens
        result['live_miss_prompt_policy']='allowed-compact-no-space-01' if args.no_spaces else 'allowed-compact-01' if args.compact else 'original-forms-0'
        result['prefix_tokens']=len(config['allowed_prefixes'][0]);result['cache_id']=cache_id
        result['extended_reject_and_cancel_checks']=args.extended_checks
        save(out / 'RESULT.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, indent=2))
    finally:
        if worker and not worker.closed:
            worker.close(15)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--limit', type=int, default=198)
    p.add_argument('--rejects', type=int, default=6)
    p.add_argument('--threads',type=int,choices=(2,3),default=2)
    p.add_argument('--output-tokens',type=int,choices=(24,32),default=32)
    p.add_argument('--compact',action='store_true')
    p.add_argument('--extended-checks',action='store_true')
    p.add_argument('--no-spaces',action='store_true')
    run(p.parse_args())
