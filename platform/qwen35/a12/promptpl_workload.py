"""Pinned three-request facts-only cohort, original checker and numeric reference."""
import copy
from promptpl_evidence import ROOT,COHORT,read,sha
from request_journal_verified import FrozenProbe,digest
from resource_probe_policy import ordinary_comparison
from plm_journal import need

class PromptProbe(FrozenProbe):
    def __init__(self,build):
        super().__init__() # preserves original manifest, checker, cases and BO helper
        for field,key in [('requests_path','requests_sha256'),('prompt_prefix_template','prompt_prefix_sha256'),('accepted_prompt_workloads','accepted_prompt_workloads_sha256')]:
            need(sha(build[field])==build[key],'changed prompt input: '+field)
        for row in build['prompt_reference_artifacts']:need(sha(row['path'])==row['sha256'],'accepted CPU reference changed')
        all_inputs=read(build['accepted_prompt_workloads'])['real_inputs'];source=next(r for r in all_inputs if r['id']==build['prompt_cohort_id'])
        self.requests=read(build['requests_path']);prefix=build['prefix_tokens']
        need(type(prefix) is int and prefix==34 and len(self.requests)==3,'unverified prefix/request count')
        need([q['id'] for q in self.requests]==['app_R0','warm_prefix','app_hit'],'request lifecycle IDs changed')
        self.prefix=read(build['prompt_prefix_template'])
        for index,mode in ((0,'R0'),(2,'hit')):
            req=self.requests[index];expected=copy.deepcopy(source);expected.update(id=req['id'],cache_policy='R0' if index==0 else 'TT10_REQUIRE_HIT')
            if index==2:expected['cache_id']='short-neutral'
            need(req==expected and req['max_tokens']==24 and req['diagnostic_report'] is False and req['profile'] is False and req['logits_mode']=='final','fixed prompt request changed')
        warm=self.requests[1]
        need(warm['op']=='cache_create' and len(warm['tokens'])==prefix and warm['tokens'] in self.prefix['allowed_prefixes'] and
            warm['tokens']==source['tokens'][:prefix] and warm['cache_policy']=='R0' and warm['max_tokens']==1 and
            warm['confirmed_prefix'] is True and warm['cache_id']=='short-neutral','actual neutral prefix differs')
        need(self.prefix['identity']['input_workload_sha256']==digest(self.requests),'prefix workload identity differs')
        self.refs={name:read(build['prompt_reference_artifacts'][i]['path']) for i,name in enumerate(('app_R0','app_hit','warm_prefix'))}
    def check_answer(self,request,result):
        content=super().check_answer(request,result)
        comparison=ordinary_comparison(self.refs[request['id']],result)
        need(comparison['equal'] and self.refs[request['id']]['state_fingerprint']==result['state_fingerprint'],'accepted CPU reference/logits/state digest differs')
        return content
    def check_warm(self,result):
        a=self.refs['warm_prefix']['prefix_cache']['entries'][0];b=result['prefix_cache']['entries'][0]
        keys=('tokens','position','state_bytes','state_sha256','sequence_sha256','logits_bytes','logits_sha256')
        need({k:a[k] for k in keys}=={k:b[k] for k in keys},'new prefix snapshot digest differs from accepted CPU reference')
