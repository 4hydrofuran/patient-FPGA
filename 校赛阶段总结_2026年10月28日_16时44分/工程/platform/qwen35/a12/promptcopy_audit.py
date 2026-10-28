"""Independent saved-native-output audit; original finite checker is unchanged."""
import ast
import copy
from pathlib import Path
import sys
from promptcopy_candidate import ROOT,OUT,CANDIDATE,USER_PREFIX,SYSTEM,read,save,sha,prior
from resource_probe_policy import require,ordinary_comparison

def rows(path):return [read_line(line) for line in path.read_text(encoding='utf-8').splitlines()]
def read_line(line):
    import json
    return json.loads(line)

def exact_result(plan,result,timing,stream,checker):
    require(result['domain']=='PC' and result['gpu_layers']==0 and result['teacher_forced'] is False and
        result['bridge']['a12_route']['execution_kind']=='CPU_REFERENCE','non-CPU or teacher-forced result')
    require(result['status']=='OK' and result['state_cleared_before_response'] is True and result['state_position_after_clear']==-1,'native state/result failure')
    messages=[r for r in stream if r.get('id')==result['id']]
    terminals=[r for r in messages if r['type']=='result'];tokens=[r for r in messages if r['type']=='token']
    require(terminals==[result] and [r['index'] for r in tokens]==list(range(len(tokens))) and
        [r['token'] for r in tokens]==result['output_tokens'],'saved native result/token stream differs')
    check=checker(plan,result['text']);response=timing['response']
    require(timing['candidate_check']==response['candidate_check']==check and timing['eos'] is result['eos'],'candidate check/EOS not reproduced')
    require(timing['answer_source']==response['answer_source'] and response['model_result']==result and
        response['llm_calls']==1,'actual application candidate/source differs')
    require(timing['final_check']==response['final_check']==checker(plan,response['text']),'final answer checker differs')
    accepted=result['eos'] is True and check['status']=='pass' and timing['answer_source']=='MODEL'
    if accepted:require(response['text']==result['text'] and timing['final_check']['status']=='pass','model output replaced before delivery')
    return accepted

def protected(text):return [ast.dump(n,include_attributes=False) for n in ast.parse(text).body
    if not(isinstance(n,ast.FunctionDef) and n.name=='prompt_messages')]

def audit():
    folder=OUT/CANDIDATE;prepared=read(folder/'PREPARED.json');data=read(folder/'TOKENIZED_WORKLOADS.json');summary=read(folder/'RESULT.json')
    for r in prepared['files']:require(sha(folder/r['path'])==r['sha256'],'prepared application bytes changed')
    require(sha(folder/'WORKLOADS.json')==prepared['workload_sha256'] and sha(folder/'chat_template.jinja')==prepared['template_sha256'],'prepared inputs changed')
    require(sha(ROOT/'system_qwen35/app/checking.py')==prepared['default_checking_sha256'],'default checker changed')
    require(protected((folder/'application/system_qwen35/app/checking.py').read_text())==
        protected((ROOT/'system_qwen35/app/checking.py').read_text()),'non-prompt checker AST changed')
    sys.path.insert(0,str(folder/'application'))
    from system_qwen35.app.domain import load_case,Transcript
    from system_qwen35.app.planning import plan
    from system_qwen35.app.checking import check,prompt_messages
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    render=ImmutableSandboxedEnvironment().from_string((folder/'chat_template.jinja').read_text())
    original=read(prior.FROZEN/'WORKLOADS.json');old={r['id']:r for r in original['real_inputs']}
    require([r['id'] for r in data['real_inputs']]==list(old) and data['policy_inputs']==original['policy_inputs'],'fixed cohort changed')
    native=folder/'native-PC';stream=rows(native/'model/stdout.jsonl');tokenizer=rows(native/'tokenizer/stdout.jsonl')
    require(stream[0]==read(native/'model-ready.json') and stream[0]['execution_kind']=='CPU_REFERENCE','model ready differs')
    require(tokenizer[0]==read(native/'tokenizer-ready.json') and tokenizer[0]['execution_kind']=='CPU_REFERENCE','tokenizer ready differs')
    require(summary['worker_exit_codes']==[0,0] and summary['PL_calls']==0 and summary['BOARD']=='NOT_TESTED','normal CPU exits or scope differ')
    boundary=read(folder/'BOUNDARY_RESULTS.json');require(any(r['equivalent'] and r['prefix_tokens']==summary['prefix_tokens'] for r in boundary),'actual prefix boundary not verified')
    quality=read(folder/'QUALITY.json');by_quality={r['id']:r for r in quality['rows']};out=[];plans={};pairs={}
    for row in data['real_inputs']:
        item=row['application'];old_item=old[row['id']]['application'];case=load_case(item['case_id'])
        p=plan(case,Transcript.parse(dict(request_id=row['id'],text=item['question'],source='typed',final=True)),())
        require(item['question']==old_item['question'] and case.sha256==old_item['case_sha256'] and
            prior.canonical_sha(p.to_dict())==prior.canonical_sha(old_item['plan'])==prior.canonical_sha(item['plan']),'question/fact routing identity changed')
        messages=prompt_messages(p,item['question']);require(messages==item['messages'] and messages[0]['content']==SYSTEM and
            messages[1]['content'].startswith(USER_PREFIX),'candidate prompt messages changed')
        require(render.render(messages=messages,add_generation_prompt=True,enable_thinking=False)==row['prompt'],'saved prompt does not match original application route')
        token_record=[r for r in tokenizer if r.get('id')=='tokens-'+row['id']]
        require(len(token_record)==1 and token_record[0]['tokens']==row['tokens'],'actual tokenization differs')
        pair=[];clocks=[];accepted=[]
        for mode in ('R0','hit'):
            where=native/(row['id']+'-'+mode);request=read(where/'request.json');result=read(where/'result.json');clock=read(where/'application-timing.json')
            require(request['prompt']==row['prompt'] and request['application']==item and request['tokens']==row['tokens'] and
                request['max_tokens']==24 and request['diagnostic_report'] is False and request['profile'] is False,'actual request changed or diagnostics enabled')
            require(result['id']==request['id']==row['id']+'-'+mode and result['prompt_tokens']==len(row['tokens']),'request/native identity differs')
            accepted.append(exact_result(p,result,clock,stream,check));pair.append(result);clocks.append(clock)
        comparison=ordinary_comparison(*pair);require(comparison['equal'] and pair[0]['state_fingerprint']==pair[1]['state_fingerprint'],'R0/hit native comparison differs')
        hit=pair[1]['prefix_cache_request'];require(hit['hit'] is True and hit['reused_tokens']==summary['prefix_tokens'] and
            hit['new_tokens']==len(row['tokens'])-summary['prefix_tokens'],'actual hit accounting differs')
        q=by_quality[row['id']];require(q['raw_model_text']==pair[1]['text'] and q['candidate']==check(p,pair[1]['text']) and
            q['answer_source']==clocks[1]['answer_source'] and q['eos'] is pair[1]['eos'],'stored quality not supported by raw output')
        plans[row['id']]=p;pairs[row['id']]=(pair,clocks)
        out.append(dict(id=row['id'],R0_accepted=accepted[0],hit_accepted=accepted[1],raw_model_text=pair[1]['text'],
            eos=pair[1]['eos'],tokens=len(row['tokens']),new_tokens=hit['new_tokens'],
            R0_complete_app_ms=clocks[0]['complete_app_ms'],hit_complete_app_ms=clocks[1]['complete_app_ms'],
            hit_internal_TTFT_app_ms=clocks[1]['TTFT_app_ms'],state_digest_equal=True,
            state_raw_bytes_independently_read=False,full_state_files=0,BOARD='NOT_TESTED'))
    rejected=[r['id'] for r in out if not(r['R0_accepted'] and r['hit_accepted'])]
    require(rejected==quality['rejected']==summary['quality_rejections'] and len(out)==25,'aggregate content status differs')
    require(len(quality['policy_items'])==7 and all(r['llm_calls']==0 and r['final_check']['status']=='pass' for r in quality['policy_items']),'policy routes differ')
    for name,reason in [('old-prefix-create-denied','prefix'),('old-binding-denied','VERSION_BINDING_MISMATCH')]:
        record=[r for r in stream if r.get('id')==name];require(len(record)==1 and record[0]['type']=='error' and reason in record[0]['message'],'old prefix/binding not actually rejected')
    require(sha(prior.PROBE/'bundle-v2.zip')==prepared['protected_probe_zip_sha256'],'ordinary probe changed')
    # Mutation tests prove this audit observes raw model/trace/checker fields;
    # these in-memory counterexamples are not added to real model results.
    tests=[]
    def refuses(call,name):
        try:call()
        except RuntimeError:tests.append(name);return
        raise AssertionError('audit accepted mutation: '+name)
    p=plans['DEV-002'];pair,clocks=pairs['DEV-002']
    changed=copy.deepcopy(pair[1]);changed['text']='胸痛是针扎感。'
    refuses(lambda:exact_result(p,changed,clocks[1],stream,check),'RESULT_DIFFERS_FROM_NATIVE_STDOUT')
    changed=copy.deepcopy(clocks[1]);changed['candidate_check']['status']='reject'
    refuses(lambda:exact_result(p,pair[1],changed,stream,check),'FALSE_CHECKER_CLASSIFICATION')
    changed=copy.deepcopy(clocks[1]);changed['eos']=False
    refuses(lambda:exact_result(p,pair[1],changed,stream,check),'FALSE_EOS_RECORD')
    changed=copy.deepcopy(clocks[1]);changed['answer_source']='TEMPLATE'
    refuses(lambda:exact_result(p,pair[1],changed,stream,check),'FALSE_MODEL_SOURCE_RECORD')
    for name,item,text in [('PARAPHRASE_REMAINS_UNCERTAIN','DEV-002','胸痛是针扎感。'),
        ('OMITTED_SCALE_REMAINS_UNCERTAIN','DEV-005','疼痛是4分。'),
        ('UNKNOWN_CHANGED_TO_KNOWN_REJECTED','DEV-011','最近服药了。'),
        ('ECHOED_WRONG_TIME_REJECTED','DEV-014','不是三天，是三周才开始的吗？')]:
        require(check(plans[item],text)['status']!='pass','original failure relaxed');tests.append(name)
    save(OUT/'INDEPENDENT_AUDIT.json',dict(status='PASS_ACTUAL_CPU_RAW_OUTPUT_AUDIT',model_inputs=25,numerical_pairs=25,
        model_generations=50,policy_inputs=7,all_finite_content_pass=not rejected,rejected=rejected,rows=out,
        negative_tests=tests,full_state_scope='RUNTIME_REPORTED_SHA_FINGERPRINT_ONLY_NO_EXPORTED_INTERMEDIATE_VALUES',
        finite_grammar_only=True,medical_review='NOT_PERFORMED',BOARD='NOT_TESTED',PL_calls=0,board_latency_saving_s=None))
    print('PASS_ACTUAL_CPU_RAW_OUTPUT_AUDIT',25-len(rejected),'of 25',len(tests),'negative tests')

if __name__=='__main__':audit()
