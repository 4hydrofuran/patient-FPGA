"""Freeze small teacher-forced and natural-text CPU-only requests."""
from jinja2.sandbox import ImmutableSandboxedEnvironment
from common import ROOT,save
from step06_prepare import OUT


if __name__=='__main__':
    template=(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text()
    env=ImmutableSandboxedEnvironment()
    messages=[dict(role='system',content='你是一名虚拟病人。已知事实：胸口疼，疼痛持续两小时。只依据这些事实，用一句中文回答。'),
              dict(role='user',content='哪里痛？')]
    prompt=env.from_string(template).render(messages=messages,add_generation_prompt=True,enable_thinking=False)
    assert prompt.endswith('<think>\n\n</think>\n\n')
    numeric=dict(op='generate',tokens=[1,2,3,4,5,6,7,8,9],teacher_tokens=[10,11],max_tokens=2,
                 logits_mode='all',diagnostic=True,cache_policy='R0')
    save(OUT/'requests.json',[dict(numeric,id='teacher_T8',prefill_chunk=8),dict(numeric,id='teacher_T1',prefill_chunk=1),
         dict(id='natural',op='generate',prompt=prompt,max_tokens=16,logits_mode='final',prefill_chunk=256,cache_policy='R0')])
    print('Three bounded CPU requests frozen; no held-out evaluation or medical-quality claim')
