"""Freeze and verify the user-selected short prompt with existing x86 CPU runtime.

No board operation, deployment, permissive checker or raw diagnostic export.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from resource_probe_policy import ProbeBlocked, ordinary_comparison, require
from resource_probe_entry import sha
from supervisor import OwnedWorker

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT/'evidence/model_pl_A/20261025-short-prompt-offline-v3'
FROZEN = ROOT/'evidence/model_pl_A/20261024-ttft10-00-v1'
PROBE = ROOT/'evidence/model_pl_A/20261025-resource-probe-v1'
SYSTEM = '你是模拟病人。用1—2句说完事实，保留是否和不清楚。'
MODEL = ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'
BINARY = Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1/pc04/qwen35-a12')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def common_prefix(arrays):
    require(bool(arrays) and all(type(a) is list and a for a in arrays), 'nonempty token arrays required')
    first = arrays[0]
    length = min(map(len, arrays))
    for a in arrays[1:]:
        length = next((i for i in range(length) if first[i] != a[i]), length)
    return first[:length]


def prefix_candidates(neutral, full_inputs):
    prefix = common_prefix([neutral, *full_inputs])
    require(len(prefix) >= 8, 'stable neutral prefix too short')
    lengths = list(dict.fromkeys([len(prefix), len(prefix)//8*8]))
    return [prefix[:n] for n in lengths]


def identity_config(parent, binary_sha, libraries, workloads, prefix_choices, template_sha):
    require(bool(prefix_choices) and all(prefix_choices), 'prefix choices absent')
    config = copy.deepcopy(parent)
    config['allowed_prefixes'] = prefix_choices
    config['identity'].update(executable_sha256=binary_sha, libraries=libraries,
        prompt_policy_sha256=canonical_sha(dict(system=SYSTEM, user_prefix='学生问题：')),
        input_workload_sha256=canonical_sha(workloads),
        neutral_prefix_choices_sha256=canonical_sha(prefix_choices), template_sha256=template_sha)
    return config


def candidate_source(before, style='copy_before_question'):
    """Only the isolated prompt builder changes; checker/router/default stay pinned."""
    tree = ast.parse(before)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prompt_messages')
    lines = before.splitlines(True)
    replacement = '''def prompt_messages(p, question):
    import json
    system = SYSTEM_LITERAL
    instruction = '仅逐字输出答句，不改写、不合并；保留数字、单位、否定、未知和句号。不要复述问题。\\n'
    payload = instruction + '学生问题：' + json.dumps(question, ensure_ascii=False) + '\\n答句：\\n'
    payload += '\\n'.join(forms(f)[0] + '。' for f in p.facts)
    return [{'role':'system','content':system},{'role':'user','content':payload}]
'''.replace('SYSTEM_LITERAL', repr(SYSTEM))
    if style == 'verbatim_before_question':
        replacement = replacement.replace(
            "仅逐字输出答句，不改写、不合并；保留数字、单位、否定、未知和句号。不要复述问题。",
            "把答句逐字复制作为回答。不得换词、合句、补充或解释。保留数字、单位、肯否和不清楚。直接输出原文，以句号结束。")
    after = ''.join(lines[:node.lineno-1]) + replacement + ''.join(lines[node.end_lineno:])
    def protected(text):
        return [ast.dump(n, include_attributes=False) for n in ast.parse(text).body
                if not (isinstance(n, ast.FunctionDef) and n.name == 'prompt_messages')]
    require(protected(before) == protected(after), 'candidate changed checker/router code')
    return after


def prepare(out, variant='requested'):
    out.mkdir(parents=True, exist_ok=False)
    app = out/'application'
    source_files = ['__init__.py', 'domain.py', 'planning.py', 'checking.py', 'session.py', 'scoring.py']
    package = app/'system_qwen35/app'
    package.mkdir(parents=True)
    shutil.copyfile(ROOT/'system_qwen35/__init__.py', app/'system_qwen35/__init__.py')
    for name in source_files:
        shutil.copyfile(ROOT/'system_qwen35/app'/name, package/name)
    if variant != 'requested':
        source = (package/'checking.py').read_text(encoding='utf-8')
        (package/'checking.py').write_text(candidate_source(source, variant), encoding='utf-8', newline='\n')
    case_dir = app/'system_qwen35/cases'
    case_dir.mkdir()
    for name in ('schema.json','SYN_CP_01.json','SYN_CP_02.json','SYN_CP_03.json'):
        path = ROOT/'system_qwen35/cases'/name
        if name != 'schema.json':
            obj = read(path)
            require(obj.get('case_id') == path.stem and obj.get('synthetic') is True,
                    'only known synthetic cases allowed')
        shutil.copyfile(path, case_dir/path.name)
    template = ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja'
    shutil.copyfile(template, out/'chat_template.jinja')
    sys.path.insert(0, str(app))
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from system_qwen35.app.domain import load_case, Transcript
    from system_qwen35.app.planning import plan
    from system_qwen35.app.checking import prompt_messages
    environment = ImmutableSandboxedEnvironment()
    original = read(FROZEN/'WORKLOADS.json')
    payloads = {r['id']:r for r in read(ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/prompt-short-20261025-v1/PAYLOADS.json')}
    workloads = []
    neutral = None
    for old in original['real_inputs']:
        item = old['application']
        case = load_case(item['case_id'])
        transcript = Transcript.parse(dict(request_id=old['id'], text=item['question'], source='typed', final=True))
        p = plan(case, transcript, ())
        require(p.route == 'answer' and list(p.required_fact_ids) == item['required_fact_ids'], 'frozen route/facts changed')
        # The frozen transport is JSON; dataclass tuples become JSON arrays.
        # Compare the exact canonical JSON value, without rewriting fact values.
        require(canonical_sha(p.to_dict()) == canonical_sha(item['plan']) and
                case.sha256 == item['case_sha256'], 'frozen facts/case changed')
        messages = prompt_messages(p, item['question'])
        require(messages[0]['content'] == SYSTEM and '学生问题：' in messages[1]['content'], 'requested system/question label changed')
        prompt = environment.from_string(template.read_text(encoding='utf-8')).render(
            messages=messages, add_generation_prompt=True, enable_thinking=False)
        expected = payloads[old['id']]
        if variant == 'requested':
            require(prompt == expected['prompt'] and messages == expected['messages'], 'mechanical payload snapshot changed')
        boundary = prompt.index(json.dumps(item['question'], ensure_ascii=False))
        prefix_text = prompt[:boundary]
        require(neutral is None or neutral == prefix_text, 'neutral text differs across cases')
        neutral = prefix_text
        row = copy.deepcopy(old)
        row.pop('tokens', None)
        row.pop('prefix_audit', None)
        row.update(prompt=prompt, max_tokens=24, state_fingerprint=True, diagnostic_report=False,
                   profile=False, logits_mode='final')
        row['application'].update(plan=p.to_dict(), messages=messages)
        workloads.append(row)
    require(len(workloads) == 25 and len(original['policy_inputs']) == 7, 'frozen cohort changed')
    save(out/'WORKLOADS.json', dict(schema='SHORT_PROMPT_PC_INPUTS_V1', real_inputs=workloads,
        policy_inputs=original['policy_inputs'], neutral_text=neutral, variant=variant,
        numerical_state_fingerprint='PC_ONLY_NO_RAW_STATE_FILE', output_limit=24,
        BOARD='NOT_TESTED', board_package=False))
    pins = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(app.rglob('*')) if p.is_file()]
    save(out/'PREPARED.json', dict(status='FROZEN_CURRENT_SHORT_PROMPT_FOR_PC_ONLY', files=pins,
        workload_sha256=sha(out/'WORKLOADS.json'), template_sha256=sha(out/'chat_template.jinja'),
        parent_workload_sha256=sha(FROZEN/'WORKLOADS.json'),
        protected_probe_zip_sha256=sha(PROBE/'bundle-v2.zip'),
        old_model_quality_rejections=['V07','V08'], variant=variant,
        default_checking_sha256=sha(ROOT/'system_qwen35/app/checking.py'),
        checker_and_fact_values_unchanged=True, model_quality='NOT_TESTED', BOARD='NOT_TESTED'))
    print(json.dumps(dict(status='SHORT_PROMPT_FROZEN', inputs=25, policy_inputs=7)))


def run(out):
    prepared = read(out/'PREPARED.json')
    require(sha(out/'WORKLOADS.json') == prepared['workload_sha256'] and
            sha(out/'chat_template.jinja') == prepared['template_sha256'], 'prepared text changed')
    for row in prepared['files']:
        require(sha(out/row['path']) == row['sha256'], 'prepared application changed')
    data = read(out/'WORKLOADS.json')
    evidence = out/'native-PC'
    evidence.mkdir(exist_ok=False)
    parent_native = read(PROBE/'native-PC-02/RESULT.json')
    require(sha(BINARY) == parent_native['native_sha256'], 'existing x86 binary changed')
    prior = read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    env = {k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=str(Path(prior['workspace'])/'pc'), OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
    workers = []
    def launch(name, environment):
        w = OwnedWorker([str(BINARY), str(MODEL), '2','1024','all','TILED','2','8'],
            directory=evidence/name, env=environment, health=lambda:None,
            max_runs=1, max_loads=1, expires=time.monotonic()+1800, real=False)
        workers.append(w)
        ready = w.get(120)
        require(ready['type'] == 'ready' and ready['execution_kind'] == 'CPU_REFERENCE', 'CPU identity differs')
        save(evidence/(name+'-ready.json'), ready)
        return w, ready
    def request(w, r, expected='result'):
        w.send(r)
        while True:
            result = w.get(180)
            require(result.get('id') == r['id'], 'foreign response')
            if result['type'] != 'token':break
        save(evidence/(r['id']+'.json'), result)
        require(result['type'] == expected, 'unexpected terminal response: '+r['id'])
        return result
    try:
        tokenizer, _ = launch('tokenizer', env)
        libraries = {}
        for line in (Path('/proc')/str(tokenizer.process.pid)/'maps').read_text().splitlines():
            fields = line.split()
            if not fields[-1].startswith('/'):continue
            p = Path(fields[-1]); name = p.name.split('.so.')[0]+'.so' if '.so.' in p.name else p.name
            if name.startswith(('libllama.','libggml','libsp_linear')):libraries[name] = sha(p)
        rows = data['real_inputs']
        for row in rows:
            result = request(tokenizer, dict(id='tokens-'+row['id'], op='tokenize', prompt=row['prompt']), 'tokens')
            row['tokens'] = result['tokens']
        neutral = request(tokenizer, dict(id='tokens-neutral', op='tokenize', prompt=data['neutral_text']), 'tokens')['tokens']
        choices = prefix_candidates(neutral, [r['tokens'] for r in rows])
        require(tokenizer.close(15), 'tokenizer close failed')
        save(out/'TOKENIZED_WORKLOADS.json', data)
        save(out/'PREFIX_CHOICES.json', dict(neutral_tokens=neutral, candidates=choices,
            candidate_lengths=[len(p) for p in choices], method='actual neutral/full token agreement then aligned fallback',
            old_70_token_identity_reused=False))
        config = identity_config(read(PROBE/'bundle-v2/control/prefix-config.json'), sha(BINARY), libraries,
                                 rows, choices, prepared['template_sha256'])
        save(out/'prefix-config-PC.json', config)
        env['SP_TT10_CONFIG'] = str(out/'prefix-config-PC.json')
        worker, ready = launch('model', env)
        binding = ready['prefix_cache']['binding_sha256']
        old_binding = read(PROBE/'native-PC-02/ready-PC.json')['prefix_cache']['binding_sha256']
        require(binding != old_binding, 'new prompt reused old snapshot identity')
        def warm(prefix, name):
            return request(worker, dict(id=name, op='cache_create', tokens=prefix, max_tokens=1,
                cache_id='short-neutral', cache_policy='R0', cache_binding_sha256=binding,
                confirmed_prefix=True, prefill_chunk=256, logits_mode='final', profile=False), 'cache_created')
        selected = None
        boundary_results = []
        for prefix in choices:
            n = len(prefix)
            warm(prefix, 'boundary-warm-'+str(n))
            r = dict(id='boundary-R0-'+str(n), op='generate', tokens=rows[0]['tokens'],
                max_tokens=1, teacher_tokens=[10], cache_policy='R0', prefill_chunk=256,
                logits_mode='final', profile=False, state_fingerprint=True)
            a = request(worker, r)
            b = request(worker, dict(r, id='boundary-hit-'+str(n), cache_policy='TT10_REQUIRE_HIT',
                cache_id='short-neutral', cache_binding_sha256=binding))
            equivalent = all(a.get(k) == b.get(k) for k in ('output_tokens','last_prompt_logits_sha256',
                'last_prompt_logits_fnv64','state_fingerprint','state_position_before_clear','state_position_after_clear'))
            boundary_results.append(dict(prefix_tokens=n, equivalent=equivalent))
            if equivalent:
                selected = prefix
                break
        save(out/'BOUNDARY_RESULTS.json', boundary_results)
        require(selected is not None, 'no bit-exact new neutral prefix boundary; preserve failures')
        sys.path.insert(0, str(out/'application'))
        helper = PROBE/'bundle-v2/platform/qwen35/a12/tt10_00_app.py'
        spec = importlib.util.spec_from_file_location('short_prompt_measured_app', helper)
        app = importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
        comparisons, quality = [], []
        for item in rows:
            pair = []
            for mode in ('R0','hit'):
                frozen = copy.deepcopy(item)
                frozen['id'] = item['id']+'-'+mode
                if mode == 'hit':frozen.update(cache_policy='TT10_REQUIRE_HIT', cache_id='short-neutral', cache_binding_sha256=binding)
                folder = evidence/frozen['id'];folder.mkdir()
                result, events, _, _, clock = app.measure(worker, lambda:worker.get(180),
                    (out/'chat_template.jinja').read_text(encoding='utf-8'), frozen)
                clock['cache'] = result['prefix_cache_request']
                save(folder/'request.json', frozen);save(folder/'result.json', result)
                save(folder/'application-timing.json', clock)
                require(result['status'] == 'OK' and result['state_cleared_before_response'] is True and
                        result['state_position_after_clear'] == -1, 'native failure/uncleared state')
                if mode == 'hit':require(result['prefix_cache_request']['hit'] is True and
                    result['prefix_cache_request']['reused_tokens'] == len(selected), 'new prefix not actually hit')
                pair.append((result,clock))
            comparison = ordinary_comparison(pair[0][0],pair[1][0])
            require(pair[0][0]['state_fingerprint'] == pair[1][0]['state_fingerprint'] and
                    type(pair[0][0]['state_fingerprint']) is dict, 'full hybrid state fingerprint differs')
            for field in ('answer_source','candidate_check','final_check','eos'):
                require(pair[0][1][field] == pair[1][1][field], 'R0/hit quality classification differs')
            comparisons.append(dict(id=item['id'], ordinary=comparison, full_hybrid_state_sha_equal=True))
            clock = pair[1][1]
            quality.append(dict(id=item['id'], answer_source=clock['answer_source'], eos=clock['eos'],
                candidate=clock['candidate_check'], final=clock['final_check'],
                raw_model_text=pair[1][0]['text'], raw_output_replaced=False,
                full_tokens=len(item['tokens']), reused_tokens=len(selected),
                new_tokens=len(item['tokens'])-len(selected),
                future_R0_prefill_PL_calls=72*((len(item['tokens'])+7)//8),
                future_hit_prefill_PL_calls=72*((len(item['tokens'])-len(selected)+7)//8),
                BOARD='NOT_TESTED'))
            print(json.dumps(dict(event='SHORT_PROMPT_CASE', id=item['id'], numeric='PASS',
                quality=clock['candidate_check']['status'], source=clock['answer_source'])), flush=True)
        from system_qwen35.app.session import Session
        original = {r['id']:r for r in read(ROOT/'eval/qwen35/a02/dev/questions-v2.json')}
        policies = []
        class NeverModel:
            def generate(self,*args,**kwargs):raise AssertionError('policy item unexpectedly called model')
        for row in data['policy_inputs']:
            item = original[row['id']]
            response = Session(item['case_id'],software_test=True).submit(dict(
                request_id=row['id'],text=row['question'],source='typed',final=True),NeverModel(),180)
            require(response['llm_calls'] == 0 and response['answer_plan']['route'] == row['route'], 'policy routing drift')
            policies.append(dict(id=row['id'],route=row['route'],llm_calls=0,final_check=response['final_check']))
        old70 = read(PROBE/'bundle-v2/control/requests.json')[1]['tokens']
        denied = request(worker, dict(id='old-prefix-create-denied', op='cache_create', tokens=old70,
            cache_id='old-neutral', max_tokens=1, confirmed_prefix=True, cache_binding_sha256=binding), 'error')
        require('prefix' in denied['message'], 'old prefix was not refused for prefix policy')
        warm(selected, 'identity-rewarm')
        denied = request(worker, dict(id='old-binding-denied',op='generate',tokens=rows[0]['tokens'],max_tokens=1,
            cache_policy='TT10_REQUIRE_HIT',cache_id='short-neutral',cache_binding_sha256=old_binding), 'error')
        require('VERSION_BINDING_MISMATCH' in denied['message'], 'old binding not explicitly refused')
        require(worker.close(15), 'model worker normal close failed')
        rejected = [r['id'] for r in quality if r['answer_source'] != 'MODEL' or not r['eos'] or r['candidate']['status'] != 'pass']
        save(out/'QUALITY.json',dict(status='PASS_FINITE_CHECKER' if not rejected else 'NOT_ACCEPTED_MODEL_QUALITY_REJECTIONS',
            rows=quality, rejected=rejected, model_items=25, policy_items=policies,
            unchanged_checker=True, medical_review='PENDING_NOT_CLAIMED'))
        summary = dict(status='PC_NUMERICAL_FLOW_COMPLETE', domain='PC_X86_CPU_REFERENCE',
            variant=data.get('variant','requested'),
            numerical_pairs=len(comparisons), policy_items=len(policies), prefix_tokens=len(selected),
            binding_sha256=binding, old_binding_rejected=True, old_70_prefix_rejected=True,
            model_quality='PASS_FINITE_CHECKER' if not rejected else 'NOT_ACCEPTED', quality_rejections=rejected,
            suffix_range=[min(r['new_tokens'] for r in quality),max(r['new_tokens'] for r in quality)],
            full_input_range=[min(r['full_tokens'] for r in quality),max(r['full_tokens'] for r in quality)],
            suffix_16_to_24_count=sum(16<=r['new_tokens']<=24 for r in quality),
            worker_exit_codes=[w.process.returncode for w in workers], native_sha256=sha(BINARY),
            full_hybrid_state_fingerprints_equal=True, raw_diagnostic_files=0,
            BOARD='NOT_TESTED', PL_calls=0, TTFT_board_s=None, board_candidate_eligible=False,
            note='New prompt remains separate from the frozen ordinary resource probe; no board package produced')
        save(out/'NUMERICAL_PAIRS.json',comparisons);save(out/'RESULT.json',summary)
        require(sha(PROBE/'bundle-v2.zip') == prepared['protected_probe_zip_sha256'], 'previous probe package changed')
        if 'default_checking_sha256' in prepared:
            require(sha(ROOT/'system_qwen35/app/checking.py') == prepared['default_checking_sha256'], 'default prompt changed')
        print(json.dumps(summary,ensure_ascii=True,indent=2))
    except BaseException as exc:
        save(out/'FAILURE.json',dict(reason=type(exc).__name__+': '+str(exc),BOARD='NOT_TESTED',retry=False))
        for w in workers:
            if not w.closed:w.close(20)
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--variant',choices=['requested','copy_before_question','verbatim_before_question'],default='requested')
    args=parser.parse_args()
    if args.action == 'prepare':prepare(args.out, args.variant)
    else:run(args.out)
